# Niko Video Studio V2 — Validation gates

Date: 2026-09-16

This document records the validation evidence for the IA Studio Ciné → Niko Video Studio V2 → WanGP pipeline. A stage is only marked validated when a concrete check has passed. GitHub Actions infrastructure status is reported separately from code-test status.

## Gate 1 — IA Studio Ciné export contract

Status: VALIDATED locally.

Contract: `niko-video-project/v1`.

Checks executed with Node.js:
- valid project accepted
- project with no shots rejected
- duration outside the accepted range rejected
- empty prompt rejected
- duplicated shot id rejected

`wangp_bridge.html` disables copy/download until its project validator succeeds.

## Gate 2 — Python import contract

Status: VALIDATED locally.

`niko_video_project_contract.py` is the independent Python-side validator. Six unit tests passed:
- valid project
- exact schema required
- empty prompt / invalid duration / duplicated id rejected
- timeline validation
- seed validation
- existing video path filtering

This means a JSON file edited after export is validated again before generation.

## Gate 3 — Runtime safety / GPU serialization

Status: VALIDATED locally.

Runtime tests validate:
- valid/invalid project import
- timeline validation
- one GPU generation at a time
- Gradio callback signature preservation
- continuity frame is mandatory in frame-continuity mode
- invalid/missing video files are rejected before montage

The official Windows and Linux V2 launchers start `niko_video_studio_v2_runtime.py`.

## Gate 4 — Shot continuity

Status: VALIDATED by deterministic simulation.

Two sequence tests passed:
- with an image-to-video model, shot 1 receives the initial reference and shot 2 receives the extracted frame from shot 1
- all shots keep the same continuity seed
- with a text-only model, no `image_start` is injected

The runtime additionally stops the sequence if the continuity frame cannot be extracted or is empty.

## Gate 5 — Final montage

Status: VALIDATED with real media.

A real FFmpeg test generated two H.264 clips at 320×180 / 24 fps, assembled them through the validated runtime, and produced a readable non-empty MP4. `ffprobe` reported a final duration of 1.25 seconds.

The official validated runtime uses direct FFmpeg assembly and refuses missing/non-video input files.

## Gate 6 — UI and launchers

Status:
- Python syntax: VALIDATED locally
- Linux launcher Bash syntax: VALIDATED locally with `bash -n`
- Gradio UI construction: VALIDATED locally with a dummy WanGP engine (`Blocks` created successfully)
- Windows launcher: STATICALLY REVIEWED, not executed in this Linux environment

A Windows execution test still requires a Windows machine with the WanGP environment installed. This limitation is intentionally not reported as a successful runtime validation.

## Automated CI

Workflow: `.github/workflows/static-smoke.yml`

The workflow contains Python syntax checks, Bash syntax checks, Niko Video Studio unit tests, contract marker checks, launcher checks, and WanGP attribution checks.

Current GitHub Actions infrastructure state on 2026-09-16: the workflow run is created, but GitHub reports the job as failed with no runner steps (`steps: null`) and no job logs. Therefore the CI badge must not be presented as green validation yet. The local tests above did execute and pass; the GitHub-hosted runner did not start.

## Merge rule

Do not merge solely because local validation is green if a green GitHub Actions badge is required by the release policy. Either restore GitHub Actions runner availability and obtain a green run, or explicitly accept local validation plus the documented Windows-runtime limitation.
