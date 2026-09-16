# Niko Video Studio

Niko Video Studio is a focused local video-creation interface built on top of the WanGP Python API.

> WanGP remains the generation engine. This application clearly discloses that dependency and remains subject to the repository's `LICENSE.txt` and third-party model licenses.

## Features

- Automatic discovery of WanGP video models.
- Text-to-video generation.
- Image-to-video generation when the selected model declares image input support.
- Cinematic, music-video, documentary, commercial, experimental, or neutral direction presets.
- Prompt and negative prompt.
- Resolution, duration, FPS, inference steps, and seed controls.
- Live WanGP progress reporting.
- Generation cancellation.
- Integrated video preview and generated-file access.
- Responsive browser interface suitable for desktop and mobile browsers.

## Start on Windows

After WanGP has been installed and an environment has been configured:

```bat
scripts\run_niko_video_studio.bat
```

Then open:

```text
http://127.0.0.1:7870
```

## Start on Linux

```bash
bash scripts/run_niko_video_studio.sh
```

Then open:

```text
http://127.0.0.1:7870
```

## Access from a phone on the same trusted LAN

Bind the application to all local interfaces. Do this only on a trusted network and keep your firewall enabled.

### Windows

```bat
set NIKO_VIDEO_HOST=0.0.0.0
scripts\run_niko_video_studio.bat
```

### Linux

```bash
NIKO_VIDEO_HOST=0.0.0.0 bash scripts/run_niko_video_studio.sh
```

Open `http://<PC-LAN-IP>:7870` from the phone.

## Direct launch

```bash
python niko_video_studio.py --host 127.0.0.1 --port 7870
```

Optional Gradio public sharing can be enabled with `--share`. A public share link exposes the UI to the internet, so use it only when you understand the access implications.

## How generation works

The application initializes `shared.api.init(...)`, discovers models through `list_model_metadata(main_output="video")`, starts from each model's `get_default_settings(...)`, and submits the resulting settings with `submit_task(...)`.

For image-to-video, the uploaded image is passed as `image_start`. WanGP's API normalization infers the compatible image prompt mode when the model supports a start image.

Durations are passed using the supported seconds notation (`video_length="4s"`, for example), allowing WanGP to normalize the request to the frame constraints of the selected model.

## License note

The WanGP Community License allows personal, studio, research, internal business and client-production use, subject to its terms. It restricts paid SaaS, white-label, OEM and other monetized access to WanGP itself without a separate commercial/reseller license. Third-party models and components keep their own licenses.
