#!/usr/bin/env bash
set -euo pipefail
COMFY_ROOT="${COMFY_ROOT:-/workspace/runpod-slim/ComfyUI}"
PROJECT_ROOT="${PROJECT_ROOT:-/workspace/comfy-ltx-loop}"
test -f "$COMFY_ROOT/main.py"
test -f "$PROJECT_ROOT/pyproject.toml"
python -m pip install -e "$PROJECT_ROOT[vision]"
LTX_ROOT="$COMFY_ROOT/custom_nodes/ComfyUI-LTXVideo"
if [ ! -d "$LTX_ROOT" ]; then
  git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git "$LTX_ROOT"
fi
python -m pip install -r "$LTX_ROOT/requirements.txt"
if [ ! -e "$COMFY_ROOT/custom_nodes/comfy_ltx_loop" ]; then
  ln -s "$PROJECT_ROOT/comfy_nodes/comfy_ltx_loop" "$COMFY_ROOT/custom_nodes/comfy_ltx_loop"
fi
mkdir -p "$COMFY_ROOT/output/comfy-ltx-loop" "$COMFY_ROOT/models/upscale_models"
printf '%s\n' 'Install documented models, qualify the official workflow, then import workflows/comfy-ltx-loop-motion.json.'
