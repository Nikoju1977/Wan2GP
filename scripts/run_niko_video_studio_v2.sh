#!/bin/bash
set -e
cd "$(dirname "$0")/.." || exit 1

if [ ! -f "envs.json" ]; then
    echo "[!] envs.json not found. Run scripts/install.sh first."
    exit 1
fi

ENV_OUTPUT=$(python3 setup.py get_env_info 2>/dev/null | grep "^ENV_INFO|" || true)
if [ -z "$ENV_OUTPUT" ]; then
    echo "[!] No active WanGP environment found."
    exit 1
fi

ENV_TYPE=$(echo "$ENV_OUTPUT" | cut -d'|' -f2)
ENV_PATH=$(echo "$ENV_OUTPUT" | cut -d'|' -f3)

if [ "$ENV_TYPE" = "venv" ] || [ "$ENV_TYPE" = "uv" ]; then
    source "$ENV_PATH/bin/activate"
elif [ "$ENV_TYPE" = "conda" ]; then
    if command -v conda >/dev/null 2>&1; then
        eval "$(conda shell.bash hook)"
    else
        for base in "$HOME/miniconda3" "$HOME/anaconda3" "/opt/miniconda3" "/opt/anaconda3"; do
            if [ -f "$base/etc/profile.d/conda.sh" ]; then
                source "$base/etc/profile.d/conda.sh"
                break
            fi
        done
    fi
    conda activate "$ENV_PATH"
elif [ "$ENV_TYPE" != "none" ]; then
    echo "[!] Unknown environment type: $ENV_TYPE"
    exit 1
fi

HOST="${NIKO_VIDEO_HOST:-127.0.0.1}"
PORT="${NIKO_VIDEO_PORT:-7871}"
PY_CMD="python"
[ "$ENV_TYPE" = "none" ] && PY_CMD="python3"

echo "[*] Starting validated Niko Video Studio V2 on http://$HOST:$PORT"
exec "$PY_CMD" niko_video_studio_v2_runtime.py --host "$HOST" --port "$PORT" "$@"
