"""Validated runtime entrypoint for Niko Video Studio V2.

This layer keeps the V2 UI focused while enforcing the production invariants:
project contract validation, one GPU generation at a time, timeline/seed checks,
and real video-file checks before and after assembly.
"""
from __future__ import annotations

import functools
import inspect
import math
import re
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable

import gradio as gr

import niko_video_studio as v1
import niko_video_studio_v2 as v2
from niko_video_project_contract import (
    existing_video_paths,
    normalize_seed,
    validate_project,
    validate_timeline_rows,
)

_GPU_LOCK = threading.Lock()
_INSTALLED = False
_ORIGINAL_IMPORT = v2.import_ia_studio_project
_ORIGINAL_SEQUENCE = v2.generate_sequence
_ORIGINAL_SINGLE = v1.generate_video
_ORIGINAL_ASSEMBLE = v2._assemble_videos
_ORIGINAL_EXTRACT = getattr(v2, "_extract_last_frame", None)


def _validation_error(errors: list[str]) -> None:
    if errors:
        raise gr.Error("Validation refusée :\n- " + "\n- ".join(errors))


def _arg(args: tuple[Any, ...], kwargs: dict[str, Any], index: int, name: str, default: Any = None) -> Any:
    if name in kwargs:
        return kwargs[name]
    return args[index] if len(args) > index else default


def _validate_numeric(value: Any, name: str, minimum: float, maximum: float, integer: bool = False) -> None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise gr.Error(f"{name} invalide.") from exc
    if not math.isfinite(number) or number < minimum or number > maximum:
        raise gr.Error(f"{name} doit être compris entre {minimum:g} et {maximum:g}.")
    if integer and not number.is_integer():
        raise gr.Error(f"{name} doit être un entier.")


def _validate_resolution(value: Any) -> None:
    text = str(value or "").strip().lower()
    match = re.fullmatch(r"(\d{2,5})x(\d{2,5})", text)
    if not match:
        raise gr.Error("Résolution invalide. Format attendu : 1280x720.")
    width, height = map(int, match.groups())
    if not (64 <= width <= 16384 and 64 <= height <= 16384):
        raise gr.Error("Résolution hors limites (64 à 16384 pixels par côté).")


def validated_import(project_file: str | None, project_json: str | None):
    project = v2._load_json_source(project_file, project_json)
    _validation_error(validate_project(project))
    return _ORIGINAL_IMPORT(project_file, project_json)


def _validated_sequence(*args: Any, **kwargs: Any):
    shots_table = _arg(args, kwargs, 1, "shots_table")
    rows = v2._table_rows(shots_table)
    _validation_error(validate_timeline_rows(rows))
    try:
        normalize_seed(_arg(args, kwargs, 10, "seed"))
    except ValueError as exc:
        raise gr.Error(str(exc)) from exc
    _validate_resolution(_arg(args, kwargs, 7, "resolution"))
    _validate_numeric(_arg(args, kwargs, 8, "fps"), "FPS", 1, 240)
    _validate_numeric(_arg(args, kwargs, 9, "steps"), "Steps", 1, 500, integer=True)
    return _ORIGINAL_SEQUENCE(*args, **kwargs)


def _validated_single(*args: Any, **kwargs: Any):
    try:
        normalize_seed(_arg(args, kwargs, 10, "seed"))
    except ValueError as exc:
        raise gr.Error(str(exc)) from exc
    _validate_resolution(_arg(args, kwargs, 6, "resolution"))
    _validate_numeric(_arg(args, kwargs, 7, "duration"), "Durée", 0.5, 60)
    _validate_numeric(_arg(args, kwargs, 8, "fps"), "FPS", 1, 240)
    _validate_numeric(_arg(args, kwargs, 9, "steps"), "Steps", 1, 500, integer=True)
    return _ORIGINAL_SINGLE(*args, **kwargs)


def _gpu_guard(fn: Callable[..., Any], label: str) -> Callable[..., Any]:
    @functools.wraps(fn)
    def wrapped(*args: Any, **kwargs: Any):
        if not _GPU_LOCK.acquire(blocking=False):
            raise gr.Error(
                f"Une génération GPU est déjà en cours. Termine ou annule la tâche active avant de lancer {label}."
            )
        try:
            return fn(*args, **kwargs)
        finally:
            _GPU_LOCK.release()

    wrapped.__signature__ = inspect.signature(fn)
    return wrapped


def validated_extract_last_frame(video_path: str, shot_index: int) -> str:
    if _ORIGINAL_EXTRACT is None:
        raise gr.Error("Jalon continuité indisponible : extracteur de frame absent.")
    extracted = _ORIGINAL_EXTRACT(video_path, shot_index)
    if not extracted:
        raise gr.Error(
            f"Jalon continuité refusé après le plan {shot_index} : impossible d’extraire la dernière frame."
        )
    frame = Path(str(extracted)).expanduser()
    if not frame.is_file() or frame.stat().st_size <= 0:
        raise gr.Error(
            f"Jalon continuité refusé après le plan {shot_index} : frame extraite absente ou vide."
        )
    return str(frame)


def _has_audio_stream(path: str) -> bool:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return False
    probe = subprocess.run(
        [
            ffprobe,
            "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=index",
            "-of", "csv=p=0",
            path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return probe.returncode == 0 and bool(probe.stdout.strip())


def _ffconcat_line(path: str) -> str:
    normalized = Path(path).resolve().as_posix()
    return "file '" + normalized.replace("'", "'\\''") + "'"


def validated_assemble(paths: list[str], fps: float) -> str:
    videos = existing_video_paths(paths)
    if len(videos) != len(paths):
        valid = set(videos)
        invalid = [str(path) for path in paths if str(path) not in valid]
        raise RuntimeError(
            "Montage refusé : certains résultats ne sont pas des fichiers vidéo lisibles : "
            + ", ".join(invalid[:5])
        )
    if not videos:
        raise RuntimeError("Montage refusé : aucun fichier vidéo valide.")
    if len(videos) == 1:
        return videos[0]

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg est introuvable. Installe FFmpeg ou vérifie le PATH de l’environnement WanGP.")

    output_dir = Path(getattr(v2, "OUTPUT_DIR", Path.cwd() / "outputs" / "niko_video_studio_v2"))
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"film-validated-{__import__('datetime').datetime.now().strftime('%Y%m%d-%H%M%S-%f')}.mp4"

    manifest_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".ffconcat",
            prefix="niko-video-",
            dir=output_dir,
            encoding="utf-8",
            delete=False,
        ) as manifest:
            manifest.write("ffconcat version 1.0\n")
            for video in videos:
                manifest.write(_ffconcat_line(video) + "\n")
            manifest_path = Path(manifest.name)

        all_have_audio = all(_has_audio_stream(video) for video in videos)
        command = [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-f", "concat",
            "-safe", "0",
            "-i", str(manifest_path),
            "-map", "0:v:0",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-r", f"{float(fps):g}",
        ]
        if all_have_audio:
            command += ["-map", "0:a:0?", "-c:a", "aac", "-b:a", "192k"]
        else:
            command += ["-an"]
        command += ["-movflags", "+faststart", str(output)]

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            message = (completed.stderr or completed.stdout or "Erreur FFmpeg inconnue").strip()
            raise RuntimeError(f"Échec du montage FFmpeg : {message[-1800:]}")
    finally:
        if manifest_path is not None:
            manifest_path.unlink(missing_ok=True)

    if not output.is_file() or output.stat().st_size <= 0:
        raise RuntimeError("Le montage FFmpeg s’est terminé sans produire de fichier vidéo final valide.")
    return str(output)


def install_runtime_guards() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    v2.import_ia_studio_project = validated_import
    v2._assemble_videos = validated_assemble
    v2._extract_last_frame = validated_extract_last_frame
    v2.generate_sequence = _gpu_guard(_validated_sequence, "une nouvelle séquence")
    v1.generate_video = _gpu_guard(_validated_single, "un nouveau plan")
    _INSTALLED = True


def main() -> None:
    install_runtime_guards()
    v2.main()


if __name__ == "__main__":
    main()
