#!/usr/bin/env python3
"""Niko Video Studio V2 — director workflow powered by WanGP.

V2 adds an IA Studio Ciné project bridge, editable shot timeline, batch
generation, visual continuity chaining, and automatic final assembly.
WanGP remains the generation engine and its license/third-party model terms apply.
"""

from __future__ import annotations

import argparse
import json
import random
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

import gradio as gr

import niko_video_studio as v1

APP_NAME = "Niko Video Studio V2"
ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "outputs" / "niko_video_studio_v2"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_BATCH_CANCEL = threading.Event()

CSS = r"""
:root {
  --nv-bg:#07090d; --nv-panel:rgba(17,20,28,.92); --nv-border:rgba(255,255,255,.09);
  --nv-text:#f5f7fb; --nv-muted:#99a3b5; --nv-accent:#e74c3c;
}
.gradio-container { max-width: 1540px !important; background: var(--nv-bg) !important; }
#v2-hero { padding:24px; margin:8px 0 18px; border:1px solid var(--nv-border); border-radius:22px;
  background:linear-gradient(135deg,rgba(231,76,60,.18),rgba(255,255,255,.02)); }
#v2-hero h1 { margin:0 0 5px; font-size:clamp(30px,5vw,58px); letter-spacing:-.04em; }
#v2-hero p { margin:0; color:var(--nv-muted); }
.nv-card { border:1px solid var(--nv-border) !important; border-radius:18px !important; background:var(--nv-panel) !important; }
.nv-note { color:var(--nv-muted); font-size:13px; }
#sequence-btn, #single-generate { min-height:52px; font-weight:750; }
footer { display:none !important; }
"""

def _table_rows(table: Any) -> list[list[Any]]:
    if table is None:
        return []
    if hasattr(table, "values"):
        return table.values.tolist()
    if isinstance(table, list):
        return table
    return []

def _extract_prompts(text: str) -> list[str]:
    import re
    return [m.strip() for m in re.findall(r"\[PROMPT:\s*([\s\S]*?)\]", text or "", flags=re.I) if m.strip()]

def _load_json_source(project_file: str | None, project_json: str | None) -> dict[str, Any]:
    if project_file:
        raw = Path(str(project_file)).read_text(encoding="utf-8")
    elif (project_json or "").strip():
        raw = str(project_json)
    else:
        raise gr.Error("Importe un fichier projet JSON ou colle son contenu.")
    try:
        project = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise gr.Error(f"JSON invalide : {exc}") from exc
    if not isinstance(project, dict):
        raise gr.Error("Le projet doit être un objet JSON.")
    return project

def import_ia_studio_project(project_file: str | None, project_json: str | None):
    project = _load_json_source(project_file, project_json)
    schema = str(project.get("schema") or "")
    if schema and schema != "niko-video-project/v1":
        raise gr.Error(f"Format projet non reconnu : {schema}")

    shots = project.get("shots") if isinstance(project.get("shots"), list) else []
    if not shots:
        sections = project.get("sections") if isinstance(project.get("sections"), dict) else {}
        prompts = _extract_prompts(str(sections.get("image") or ""))
        shots = [{"id": i + 1, "prompt": prompt, "duration": 4} for i, prompt in enumerate(prompts)]

    rows = []
    for i, shot in enumerate(shots, 1):
        if not isinstance(shot, dict):
            continue
        prompt = str(shot.get("prompt") or "").strip()
        if not prompt:
            continue
        duration = float(shot.get("duration") or 4)
        rows.append([int(shot.get("id") or i), prompt, duration])

    continuity = project.get("continuity") if isinstance(project.get("continuity"), dict) else {}
    bible = str(continuity.get("bible") or "")
    visual = str(continuity.get("visual_direction") or "")
    light = str(continuity.get("lighting_direction") or "")
    continuity_text = "\n\n".join(x for x in [
        "CONTINUITÉ PERSONNAGES / DÉCORS :\n" + bible[:3500] if bible else "",
        "DIRECTION VISUELLE :\n" + visual[:2200] if visual else "",
        "LUMIÈRE :\n" + light[:1200] if light else "",
    ] if x)

    title = str(project.get("title") or "Projet IA Studio Ciné")
    summary = (
        f"### Projet chargé : {title}\n"
        f"**{len(rows)} plan(s)** détecté(s) · source `{project.get('source','inconnue')}`.  \n"
        "La timeline ci-dessous est éditable avant génération."
    )
    return project, rows, continuity_text, summary

def _supports_i2v(session: Any, model_type: str) -> bool:
    schema = session.get_model_schema(model_type) or {}
    caps = schema.get("capabilities") or {}
    inputs = schema.get("inputs") or []
    return bool(caps.get("image_to_video") or "image" in inputs)

def _extract_last_frame(video_path: str, shot_index: int) -> str | None:
    try:
        import av
        source = av.open(video_path)
        last = None
        for frame in source.decode(video=0):
            last = frame
        source.close()
        if last is None:
            return None
        target = OUTPUT_DIR / f"continuity_{shot_index:03d}.png"
        last.to_image().save(target)
        return str(target)
    except Exception:
        return None

def _assemble_videos(paths: list[str], fps: float) -> str:
    if not paths:
        raise RuntimeError("Aucun plan à assembler.")
    if len(paths) == 1:
        return paths[0]

    from moviepy.editor import VideoFileClip, concatenate_videoclips

    clips = []
    final = None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output = OUTPUT_DIR / f"film-{stamp}.mp4"
    try:
        clips = [VideoFileClip(path) for path in paths]
        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(
            str(output),
            codec="libx264",
            audio_codec="aac",
            fps=float(fps),
            threads=4,
            logger=None,
        )
    finally:
        if final is not None:
            final.close()
        for clip in clips:
            clip.close()
    return str(output)

def cancel_sequence():
    _BATCH_CANCEL.set()
    with v1._ACTIVE_JOB_LOCK:
        job = v1._ACTIVE_JOB.get("job")
    if job is not None and not getattr(job, "done", False):
        job.cancel()
    return "Annulation demandée. Le plan actif est interrompu puis la séquence s’arrête."

def generate_sequence(
    project: dict[str, Any] | None,
    shots_table: Any,
    continuity_text: str,
    model_type: str,
    preset: str,
    reference_image: str | None,
    continuity_mode: str,
    resolution: str,
    fps: float,
    steps: int,
    seed: int,
    progress=gr.Progress(track_tqdm=False),
):
    rows = _table_rows(shots_table)
    rows = [row for row in rows if len(row) >= 3 and str(row[1] or "").strip()]
    if not rows:
        raise gr.Error("La timeline ne contient aucun plan.")
    if not model_type:
        raise gr.Error("Sélectionne un modèle vidéo.")

    session = v1.get_session()
    defaults = session.get_default_settings(model_type) or {}
    supports_i2v = _supports_i2v(session, model_type)
    if continuity_mode.startswith("Frame") and not supports_i2v:
        continuity_mode = "Prompt seulement"

    _BATCH_CANCEL.clear()
    generated: list[str] = []
    previous_frame: str | None = None
    base_seed = int(seed) if int(seed) >= 0 else random.randint(1, 2_147_483_000)
    total = len(rows)

    class BatchCallbacks:
        def __init__(self, shot_no: int):
            self.shot_no = shot_no
        def on_status(self, status):
            label = str(status or "Préparation…")
            progress((self.shot_no - 1) / total, desc=f"Plan {self.shot_no}/{total} · {label}")
        def on_progress(self, update):
            raw = float(getattr(update, "progress", 0) or 0) / 100.0
            overall = ((self.shot_no - 1) + max(0.0, min(1.0, raw))) / total
            label = str(getattr(update, "status", "") or getattr(update, "phase", "") or "Génération…")
            progress(overall, desc=f"Plan {self.shot_no}/{total} · {label}")

    for index, row in enumerate(rows, 1):
        if _BATCH_CANCEL.is_set():
            break

        shot_id = int(float(row[0])) if str(row[0]).strip() else index
        shot_prompt = str(row[1]).strip()
        duration = max(0.5, float(row[2] or 4))

        prompt_parts = [shot_prompt]
        if (continuity_text or "").strip():
            prompt_parts.append(
                "Maintain strict visual continuity of recurring characters, wardrobe, props, locations, palette and production design across all shots. "
                + continuity_text.strip()
            )
        prompt = v1._compose_prompt(". ".join(prompt_parts), preset)

        settings = dict(defaults)
        settings["model_type"] = model_type
        settings["prompt"] = prompt
        settings["video_length"] = f"{duration:g}s"
        settings["force_fps"] = float(fps)
        settings["num_inference_steps"] = int(steps)
        if (resolution or "").strip():
            settings["resolution"] = resolution.strip()

        settings["seed"] = base_seed

        start_image = None
        if supports_i2v:
            if continuity_mode.startswith("Frame") and previous_frame:
                start_image = previous_frame
            elif reference_image:
                start_image = str(reference_image)
        if start_image:
            settings["image_start"] = start_image

        job = session.submit_task(settings, callbacks=BatchCallbacks(index))
        with v1._ACTIVE_JOB_LOCK:
            v1._ACTIVE_JOB["job"] = job
        try:
            result = job.result()
        finally:
            with v1._ACTIVE_JOB_LOCK:
                if v1._ACTIVE_JOB.get("job") is job:
                    v1._ACTIVE_JOB["job"] = None

        if result.cancelled or _BATCH_CANCEL.is_set():
            break
        if not result.success:
            errors = "; ".join(str(e) for e in result.errors) or "erreur inconnue"
            raise gr.Error(f"Plan {shot_id} : {errors}")

        paths = [str(p) for p in result.generated_files]
        if not paths:
            raise gr.Error(f"Plan {shot_id} terminé sans fichier vidéo.")
        video_path = paths[0]
        generated.append(video_path)

        if continuity_mode.startswith("Frame") and supports_i2v:
            previous_frame = _extract_last_frame(video_path, index) or previous_frame

    if not generated:
        return None, "Séquence annulée avant la création d’un plan.", None

    progress(0.98, desc="Montage des plans…")
    final_path = _assemble_videos(generated, float(fps))
    progress(1.0, desc="Film terminé")

    state = "annulée partiellement" if _BATCH_CANCEL.is_set() else "terminée"
    details = (
        f"### Séquence {state}\n"
        f"**{len(generated)}/{total} plan(s)** généré(s).  \n"
        f"Seed de continuité : `{base_seed}`  \n"
        f"Film final : `{final_path}`"
    )
    return final_path, details, generated

def refresh_models_v2():
    choices = v1.discover_video_models()
    value = choices[0][1] if choices else None
    return gr.update(choices=choices, value=value), f"{len(choices)} modèles vidéo détectés."

def build_ui():
    with gr.Blocks(title=APP_NAME, css=CSS, theme=gr.themes.Base()) as demo:
        gr.HTML("""
        <section id="v2-hero">
          <h1>Niko Video Studio V2</h1>
          <p>De la préproduction IA Studio Ciné au film généré avec WanGP.</p>
        </section>
        """)

        with gr.Tabs():
            with gr.Tab("🎬 Séquence / Storyboard"):
                project_state = gr.State({})
                with gr.Row(equal_height=False):
                    with gr.Column(scale=5, elem_classes=["nv-card"]):
                        gr.Markdown("### 1. Import IA Studio Ciné")
                        with gr.Row():
                            project_file = gr.File(label="Projet .json", file_types=[".json"], type="filepath")
                            import_btn = gr.Button("Importer le projet", variant="primary")
                        project_json = gr.Textbox(
                            label="Ou coller le JSON",
                            lines=3,
                            placeholder='{"schema":"niko-video-project/v1", ...}',
                        )
                        import_status = gr.Markdown("Exporte ton projet depuis `wangp_bridge.html` dans IA Studio Ciné.")
                        continuity = gr.Textbox(
                            label="Bible de continuité",
                            lines=6,
                            placeholder="Personnages, costumes, décors, palette, lumière…",
                        )
                        shots = gr.Dataframe(
                            headers=["Plan", "Prompt vidéo", "Durée (s)"],
                            datatype=["number", "str", "number"],
                            row_count=(4, "dynamic"),
                            col_count=(3, "fixed"),
                            interactive=True,
                            label="Timeline des plans",
                        )

                    with gr.Column(scale=4, elem_classes=["nv-card"]):
                        gr.Markdown("### 2. Moteur de tournage")
                        with gr.Row():
                            model = gr.Dropdown(label="Modèle WanGP", choices=[], scale=4)
                            refresh = gr.Button("↻", scale=1)
                        model_info = gr.Markdown("Initialisation…", elem_classes=["nv-note"])
                        reference = gr.Image(label="Référence personnage / décor (optionnel)", type="filepath", height=220)
                        continuity_mode = gr.Radio(
                            ["Frame précédente → plan suivant", "Prompt seulement"],
                            value="Frame précédente → plan suivant",
                            label="Continuité",
                        )
                        preset = gr.Dropdown(list(v1.STYLE_PRESETS.keys()), value="Cinéma", label="Direction visuelle")
                        with gr.Row():
                            resolution = gr.Textbox(value="1280x720", label="Résolution")
                            fps = gr.Slider(8, 60, value=24, step=1, label="FPS")
                        with gr.Row():
                            steps = gr.Slider(1, 60, value=8, step=1, label="Steps")
                            seed = gr.Number(value=-1, precision=0, label="Seed (-1 = auto)")
                        with gr.Row():
                            sequence_btn = gr.Button("Générer toute la séquence", variant="primary", elem_id="sequence-btn")
                            stop_btn = gr.Button("Arrêter", variant="stop")

                with gr.Row():
                    final_video = gr.Video(label="Film assemblé", height=520)
                    with gr.Column():
                        sequence_status = gr.Markdown("Prêt.")
                        generated_files = gr.File(label="Plans générés", file_count="multiple")

            with gr.Tab("⚡ Plan unique"):
                with gr.Row(equal_height=False):
                    with gr.Column(scale=5, elem_classes=["nv-card"]):
                        with gr.Row():
                            s_model = gr.Dropdown(label="Modèle vidéo", choices=[], scale=4)
                            s_refresh = gr.Button("↻", scale=1)
                        s_info = gr.Markdown("Initialisation…", elem_classes=["nv-note"])
                        with gr.Row():
                            s_mode = gr.Radio(["Texte → Vidéo", "Image → Vidéo"], value="Texte → Vidéo", label="Mode")
                            s_preset = gr.Dropdown(list(v1.STYLE_PRESETS.keys()), value="Cinéma", label="Direction visuelle")
                        s_image = gr.Image(label="Image de départ", type="filepath", height=220)
                        s_prompt = gr.Textbox(label="Prompt", lines=5)
                        s_negative = gr.Textbox(label="Prompt négatif", lines=2)
                        with gr.Row():
                            s_res = gr.Textbox(value="1280x720", label="Résolution")
                            s_duration = gr.Slider(1, 20, value=4, step=.5, label="Durée")
                        with gr.Row():
                            s_fps = gr.Slider(8, 60, value=24, step=1, label="FPS")
                            s_steps = gr.Slider(1, 60, value=8, step=1, label="Steps")
                            s_seed = gr.Number(value=-1, precision=0, label="Seed")
                        with gr.Row():
                            s_generate = gr.Button("Générer le plan", variant="primary", elem_id="single-generate")
                            s_cancel = gr.Button("Annuler", variant="stop")
                    with gr.Column(scale=4, elem_classes=["nv-card"]):
                        s_video = gr.Video(label="Résultat", height=520)
                        s_status = gr.Markdown("Prêt.")
                        s_files = gr.File(label="Fichiers", file_count="multiple")

        gr.Markdown(
            "**Moteur : WanGP.** Cette interface conserve l’attribution WanGP et reste soumise à `LICENSE.txt` "
            "ainsi qu’aux licences des modèles utilisés.",
            elem_classes=["nv-note"],
        )

        demo.load(refresh_models_v2, outputs=[model, sequence_status])
        demo.load(refresh_models_v2, outputs=[s_model, s_status])

        import_btn.click(
            import_ia_studio_project,
            inputs=[project_file, project_json],
            outputs=[project_state, shots, continuity, import_status],
        )

        model.change(v1.model_defaults, inputs=model, outputs=[resolution, steps, fps, model_info])
        refresh.click(refresh_models_v2, outputs=[model, sequence_status])

        sequence_btn.click(
            generate_sequence,
            inputs=[
                project_state, shots, continuity, model, preset, reference,
                continuity_mode, resolution, fps, steps, seed,
            ],
            outputs=[final_video, sequence_status, generated_files],
            concurrency_limit=1,
        )
        stop_btn.click(cancel_sequence, outputs=sequence_status, concurrency_limit=None)

        s_model.change(v1.model_defaults, inputs=s_model, outputs=[s_res, s_steps, s_fps, s_info])
        s_refresh.click(refresh_models_v2, outputs=[s_model, s_status])
        s_generate.click(
            v1.generate_video,
            inputs=[s_model, s_mode, s_prompt, s_negative, s_image, s_preset, s_res, s_duration, s_fps, s_steps, s_seed],
            outputs=[s_video, s_status, s_files],
            concurrency_limit=1,
        )
        s_cancel.click(v1.cancel_generation, outputs=s_status, concurrency_limit=None)

    return demo

def parse_args():
    parser = argparse.ArgumentParser(description="Niko Video Studio V2")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7871)
    parser.add_argument("--share", action="store_true")
    return parser.parse_args()

def main():
    args = parse_args()
    demo = build_ui()
    demo.queue(default_concurrency_limit=2)
    demo.launch(server_name=args.host, server_port=args.port, share=args.share, inbrowser=False)

if __name__ == "__main__":
    main()
