"""Validation helpers shared by Niko Video Studio V2 runtime checks."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "niko-video-project/v1"
MIN_DURATION = 0.5
MAX_DURATION = 60.0
MAX_SEED = 2_147_483_647
VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v"}


def _is_mapping(value: Any) -> bool:
    return isinstance(value, dict)


def validate_project(project: Any) -> list[str]:
    errors: list[str] = []
    if not _is_mapping(project):
        return ["Le projet doit être un objet JSON."]

    if project.get("schema") != SCHEMA:
        errors.append(f"Schéma attendu : {SCHEMA}.")
    sections = project.get("sections")
    continuity = project.get("continuity")
    shots = project.get("shots")
    if not _is_mapping(sections):
        errors.append("Sections de production absentes ou invalides.")
    if not _is_mapping(continuity):
        errors.append("Bloc de continuité absent ou invalide.")
    if not isinstance(shots, list) or not shots:
        errors.append("Le projet ne contient aucun plan exploitable.")
        return errors

    seen_ids: set[int] = set()
    for index, shot in enumerate(shots, 1):
        if not _is_mapping(shot):
            errors.append(f"Plan {index} invalide.")
            continue
        raw_id = shot.get("id")
        if isinstance(raw_id, bool):
            shot_id = None
        else:
            try:
                numeric_id = float(raw_id)
                shot_id = int(numeric_id) if numeric_id.is_integer() else None
            except (TypeError, ValueError, OverflowError):
                shot_id = None
        if shot_id is None or shot_id < 1:
            errors.append(f"Plan {index} : identifiant invalide.")
        elif shot_id in seen_ids:
            errors.append(f"Plan {index} : identifiant dupliqué ({shot_id}).")
        else:
            seen_ids.add(shot_id)

        prompt = str(shot.get("prompt") or "").strip()
        if not prompt:
            errors.append(f"Plan {index} : prompt vide.")

        try:
            duration = float(shot.get("duration"))
        except (TypeError, ValueError, OverflowError):
            duration = float("nan")
        if not math.isfinite(duration) or not MIN_DURATION <= duration <= MAX_DURATION:
            errors.append(
                f"Plan {index} : durée invalide ({MIN_DURATION:g} à {MAX_DURATION:g} s)."
            )
    return errors


def validate_timeline_rows(rows: Iterable[Any]) -> list[str]:
    project = {
        "schema": SCHEMA,
        "sections": {},
        "continuity": {},
        "shots": [],
    }
    for index, row in enumerate(rows, 1):
        if not isinstance(row, (list, tuple)) or len(row) < 3:
            project["shots"].append({"id": index, "prompt": "", "duration": None})
            continue
        project["shots"].append({"id": row[0], "prompt": row[1], "duration": row[2]})
    return validate_project(project)


def normalize_seed(value: Any) -> int:
    if value is None or isinstance(value, bool):
        raise ValueError("Seed invalide. Utilise -1 pour automatique ou un entier positif.")
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Seed invalide. Utilise -1 pour automatique ou un entier positif.") from exc
    if not math.isfinite(numeric) or not numeric.is_integer():
        raise ValueError("La seed doit être un entier.")
    seed = int(numeric)
    if seed == -1:
        return seed
    if not 0 <= seed <= MAX_SEED:
        raise ValueError(f"La seed doit être -1 ou comprise entre 0 et {MAX_SEED}.")
    return seed


def existing_video_paths(paths: Iterable[Any]) -> list[str]:
    videos: list[str] = []
    for value in paths:
        if value is None:
            continue
        path = Path(str(value)).expanduser()
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        if path.is_file():
            videos.append(str(path))
    return videos
