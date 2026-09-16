#!/usr/bin/env python3
"""Niko Video Studio — a focused video-generation UI powered by WanGP.

This local/studio application is intentionally a thin UI layer over WanGP's
public Python API. WanGP remains the generation engine and must be installed in
this repository. See LICENSE.txt and docs/API.md for the applicable terms.
"""

from __future__ import annotations

import argparse
import threading
from pathlib import Path
from typing import Any

import gradio as gr

from shared.api import init

APP_NAME = "Niko Video Studio"
ROOT = Path(__file__).resolve().parent

_SESSION = None
_SESSION_LOCK = threading.Lock()
_ACTIVE_JOB: dict[str, Any] = {"job": None}
_ACTIVE_JOB_LOCK = threading.Lock()

STYLE_PRESETS = {
    "Cinéma": "cinematic lighting, expressive camera movement, controlled depth of field, natural motion, filmic composition",
    "Clip musical": "bold music-video direction, rhythmic camera movement, striking lighting, graphic composition, high visual energy",
    "Documentaire": "observational documentary realism, natural light, credible textures, restrained camera movement, authentic detail",
    "Publicité": "premium commercial cinematography, polished lighting, precise product framing, elegant camera motion, crisp detail",
    "Expérimental": "experimental moving-image art, unexpected transitions, expressive motion, abstract visual language, contemporary digital cinema",
    "Aucun": "",
}

CSS = r"""
:root {
  --niko-bg: #090b10;
  --niko-panel: rgba(18, 21, 29, 0.86);
  --niko-border: rgba(255, 255, 255, 0.09);
  --niko-text: #f4f6fb;
  --niko-muted: #9ba3b3;
}
.gradio-container { max-width: 1480px !important; background: var(--niko-bg) !important; }
#niko-hero {
  padding: 22px 24px;
  margin: 8px 0 18px 0;
  border: 1px solid var(--niko-border);
  border-radius: 22px;
  background: linear-gradient(135deg, rgba(255,255,255,.06), rgba(255,255,255,.015));
}
#niko-hero h1 { margin: 0 0 4px 0; font-size: clamp(30px, 5vw, 56px); letter-spacing: -0.04em; }
#niko-hero p { margin: 0; color: var(--niko-muted); font-size: 15px; }
.niko-card { border: 1px solid var(--niko-border) !important; border-radius: 18px !important; background: var(--niko-panel) !important; }
.niko-note { color: var(--niko-muted); font-size: 13px; }
#generate-btn { min-height: 52px; font-weight: 700; }
#cancel-btn { min-height: 52px; }
footer { display: none !important; }
"""


def get_session():
    global _SESSION
    if _SESSION is None:
        with _SESSION_LOCK:
            if _SESSION is None:
                _SESSION = init(root=ROOT, console_output=True)
    return _SESSION


def discover_video_models():
    session = get_session()
    models = session.list_model_metadata(main_output="video")
    choices = []
    for item in models:
        model_type = str(item.get("model_type") or "").strip()
        if not model_type:
            continue
        name = str(item.get("name") or model_type).strip()
        family = str(item.get("family_label") or item.get("family") or "").strip()
        label = f"{name} · {family}" if family and family.lower() not in name.lower() else name
        choices.append((label, model_type))
    choices.sort(key=lambda x: x[0].lower())
    return choices


def model_defaults(model_type: str):
    if not model_type:
        return gr.update(), gr.update(), gr.update(), "Sélectionne un modèle vidéo."

    session = get_session()
    defaults = session.get_default_settings(model_type) or {}
    schema = session.get_model_schema(model_type) or {}

    resolution = defaults.get("resolution") or "1280x720"
    steps = defaults.get("num_inference_steps") or 8
    fps = defaults.get("force_fps") or schema.get("fps") or 24

    caps = schema.get("capabilities") or {}
    inputs = schema.get("inputs") or []
    i2v = bool(caps.get("image_to_video") or "image" in inputs)
    audio = bool(caps.get("audio_output"))
    name = schema.get("name") or model_type
    desc = str(schema.get("description") or "").strip()
    info = f"**{name}**  \nImage→vidéo: {'oui' if i2v else 'non'} · Audio: {'oui' if audio else 'non'}"
    if desc:
        info += f"  \n{desc[:320]}"

    return (
        gr.update(value=str(resolution)),
        gr.update(value=int(steps)),
        gr.update(value=float(fps)),
        info,
    )


def _compose_prompt(prompt: str, preset: str) -> str:
    prompt = (prompt or "").strip()
    suffix = STYLE_PRESETS.get(preset or "Aucun", "")
    if prompt and suffix:
        return f"{prompt}. {suffix}."
    return prompt or suffix


def generate_video(
    model_type: str,
    mode: str,
    prompt: str,
    negative_prompt: str,
    source_image: str | None,
    preset: str,
    resolution: str,
    duration: float,
    fps: float,
    steps: int,
    seed: int,
    progress=gr.Progress(track_tqdm=False),
):
    if not model_type:
        raise gr.Error("Sélectionne un modèle vidéo.")
    if not (prompt or "").strip():
        raise gr.Error("Ajoute un prompt avant de lancer la génération.")

    session = get_session()
    schema = session.get_model_schema(model_type) or {}
    defaults = session.get_default_settings(model_type) or {}

    if mode == "Image → Vidéo":
        capabilities = schema.get("capabilities") or {}
        inputs = schema.get("inputs") or []
        supports_i2v = bool(capabilities.get("image_to_video") or "image" in inputs)
        if not supports_i2v:
            raise gr.Error("Ce modèle ne déclare pas de capacité image→vidéo. Choisis un autre modèle.")
        if not source_image:
            raise gr.Error("Ajoute une image de départ pour le mode Image → Vidéo.")

    settings = dict(defaults)
    settings["model_type"] = model_type
    settings["prompt"] = _compose_prompt(prompt, preset)
    if (negative_prompt or "").strip():
        settings["negative_prompt"] = negative_prompt.strip()
    if (resolution or "").strip():
        settings["resolution"] = resolution.strip()
    settings["video_length"] = f"{float(duration):g}s"
    settings["force_fps"] = float(fps)
    settings["num_inference_steps"] = int(steps)
    if int(seed) >= 0:
        settings["seed"] = int(seed)
    if mode == "Image → Vidéo":
        settings["image_start"] = str(source_image)

    class StudioCallbacks:
        ratio = 0.0

        def on_status(self, status):
            text = str(status or "").strip()
            if text:
                progress(self.ratio, desc=text)

        def on_progress(self, update):
            raw = float(getattr(update, "progress", 0) or 0)
            self.ratio = max(0.0, min(1.0, raw / 100.0))
            label = str(getattr(update, "status", "") or getattr(update, "phase", "") or "Génération…")
            progress(self.ratio, desc=label)

    job = session.submit_task(settings, callbacks=StudioCallbacks())
    with _ACTIVE_JOB_LOCK:
        _ACTIVE_JOB["job"] = job

    try:
        result = job.result()
    finally:
        with _ACTIVE_JOB_LOCK:
            if _ACTIVE_JOB.get("job") is job:
                _ACTIVE_JOB["job"] = None

    if result.cancelled:
        return None, "Génération annulée.", None
    if not result.success:
        messages = [str(error) for error in result.errors] or ["Échec de la génération."]
        raise gr.Error("\n".join(messages))

    generated = [str(path) for path in result.generated_files]
    video_path = generated[0] if generated else None
    details = "✅ Génération terminée."
    if generated:
        details += "  \n" + "  \n".join(f"`{p}`" for p in generated[:6])
    return video_path, details, generated or None


def cancel_generation():
    with _ACTIVE_JOB_LOCK:
        job = _ACTIVE_JOB.get("job")
    if job is None or getattr(job, "done", False):
        return "Aucune génération active."
    job.cancel()
    return "Demande d’annulation envoyée."


def refresh_models():
    choices = discover_video_models()
    value = choices[0][1] if choices else None
    return gr.update(choices=choices, value=value), f"{len(choices)} modèles vidéo détectés."


def build_ui():
    with gr.Blocks(title=APP_NAME, css=CSS, theme=gr.themes.Base()) as demo:
        gr.HTML(
            """
            <section id="niko-hero">
              <h1>Niko Video Studio</h1>
              <p>Création vidéo IA locale — interface dédiée, moteur WanGP.</p>
            </section>
            """
        )

        with gr.Row(equal_height=False):
            with gr.Column(scale=5, elem_classes=["niko-card"]):
                with gr.Row():
                    model = gr.Dropdown(label="Modèle vidéo", choices=[], scale=4)
                    refresh = gr.Button("↻ Modèles", scale=1)
                model_info = gr.Markdown("Initialisation du moteur WanGP…", elem_classes=["niko-note"])

                with gr.Row():
                    mode = gr.Radio(["Texte → Vidéo", "Image → Vidéo"], value="Texte → Vidéo", label="Mode")
                    preset = gr.Dropdown(list(STYLE_PRESETS.keys()), value="Cinéma", label="Direction visuelle")

                source_image = gr.Image(label="Image de départ", type="filepath", height=240)
                prompt = gr.Textbox(
                    label="Prompt",
                    placeholder="Décris le plan, le sujet, la lumière, le mouvement caméra, l’atmosphère…",
                    lines=5,
                )
                negative = gr.Textbox(label="Prompt négatif", lines=2, placeholder="Éléments à éviter…")

                with gr.Accordion("Réglages de génération", open=True):
                    with gr.Row():
                        resolution = gr.Textbox(label="Résolution", value="1280x720")
                        duration = gr.Slider(1, 20, value=4, step=0.5, label="Durée (s)")
                    with gr.Row():
                        fps = gr.Slider(8, 60, value=24, step=1, label="FPS")
                        steps = gr.Slider(1, 60, value=8, step=1, label="Steps")
                        seed = gr.Number(value=-1, precision=0, label="Seed (-1 = auto)")

                with gr.Row():
                    generate = gr.Button("Générer la vidéo", variant="primary", elem_id="generate-btn")
                    cancel = gr.Button("Annuler", variant="stop", elem_id="cancel-btn")

                status = gr.Markdown("Prêt.")

            with gr.Column(scale=4, elem_classes=["niko-card"]):
                output_video = gr.Video(label="Résultat", height=520)
                output_files = gr.File(label="Fichiers générés", file_count="multiple")
                gr.Markdown(
                    "**WanGP est le moteur de génération utilisé par cette application.** "
                    "L’usage de l’API reste soumis à la licence WanGP du dépôt.",
                    elem_classes=["niko-note"],
                )

        demo.load(refresh_models, outputs=[model, status])
        model.change(model_defaults, inputs=model, outputs=[resolution, steps, fps, model_info])
        refresh.click(refresh_models, outputs=[model, status])
        generate.click(
            generate_video,
            inputs=[model, mode, prompt, negative, source_image, preset, resolution, duration, fps, steps, seed],
            outputs=[output_video, status, output_files],
            concurrency_limit=1,
        )
        cancel.click(cancel_generation, outputs=status, concurrency_limit=None)

    return demo


def parse_args():
    parser = argparse.ArgumentParser(description="Niko Video Studio — WanGP-powered local video UI")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address. Use 0.0.0.0 for LAN access.")
    parser.add_argument("--port", type=int, default=7870, help="Web UI port")
    parser.add_argument("--share", action="store_true", help="Enable Gradio public share link")
    return parser.parse_args()


def main():
    args = parse_args()
    demo = build_ui()
    demo.queue(default_concurrency_limit=2)
    demo.launch(server_name=args.host, server_port=args.port, share=args.share, inbrowser=False)


if __name__ == "__main__":
    main()
