#!/usr/bin/env bash
set -euo pipefail
COMFY_ROOT="${COMFY_ROOT:-/workspace/runpod-slim/ComfyUI}"
PROJECT_ROOT="${PROJECT_ROOT:-/workspace/comfy-ltx-loop}"
test -f "$COMFY_ROOT/main.py"
test -f "$PROJECT_ROOT/pyproject.toml"
python -m pip install -e "$PROJECT_ROOT"
mkdir -p "$PROJECT_ROOT/outputs" "$PROJECT_ROOT/checkpoints" "$PROJECT_ROOT/assets" "$PROJECT_ROOT/workflows"
if [ ! -e "$COMFY_ROOT/custom_nodes/comfy_ltx_loop" ]; then
  ln -s "$PROJECT_ROOT/comfy_nodes/comfy_ltx_loop" "$COMFY_ROOT/custom_nodes/comfy_ltx_loop"
fi
printf '%s\n' 'Start ComfyUI once, then qualify with comfy-ltx-loop environment record and the actual image digest.'
