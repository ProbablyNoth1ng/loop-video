#!/usr/bin/env bash
set -euo pipefail
COMFY_ROOT="${COMFY_ROOT:-/workspace/runpod-slim/ComfyUI}"
PROJECT_ROOT="${PROJECT_ROOT:-/workspace/ambient-loop}"
test -f "$COMFY_ROOT/main.py"
test -f "$PROJECT_ROOT/pyproject.toml"
python -m pip install -e "$PROJECT_ROOT"
mkdir -p "$PROJECT_ROOT/outputs" "$PROJECT_ROOT/checkpoints" "$PROJECT_ROOT/assets" "$PROJECT_ROOT/workflows"
if [ ! -e "$COMFY_ROOT/custom_nodes/ambient_loop" ]; then
  ln -s "$PROJECT_ROOT/comfy_nodes/ambient_loop" "$COMFY_ROOT/custom_nodes/ambient_loop"
fi
printf '%s\n' 'Start ComfyUI once, then qualify with ambient-loop environment record and the actual image digest.'
