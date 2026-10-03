#!/usr/bin/env bash
set -euo pipefail
COMFY_ROOT="${COMFY_ROOT:-/workspace/runpod-slim/ComfyUI}"
PROJECT_ROOT="${PROJECT_ROOT:-/workspace/ambient-loop}"
ambient-loop environment check --comfy "$COMFY_ROOT" --lock "$PROJECT_ROOT/environment.lock.json"
exec python "$COMFY_ROOT/main.py" --listen 0.0.0.0 --port 8188 --cache-none
