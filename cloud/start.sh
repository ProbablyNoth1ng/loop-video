#!/usr/bin/env bash
set -euo pipefail
COMFY_ROOT="${COMFY_ROOT:-/workspace/runpod-slim/ComfyUI}"
test -f "$COMFY_ROOT/main.py"
command -v ffmpeg >/dev/null
command -v ffprobe >/dev/null
cd "$COMFY_ROOT"
exec python main.py --listen 0.0.0.0 --port 8188 --cache-none
