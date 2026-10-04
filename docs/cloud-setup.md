# Installation and storage

Perform installation before creative work. Neither provider has a tested
GPU minimum yet. Use an authenticated provider gateway for ComfyUI.

## RunPod

For automatic node/dependency/model installation on Pod creation, see
[RunPod automatic installation](runpod-autoinstall.md). The steps below are
the older manual path; `cloud/bootstrap.sh` alone does not download models.

Use a ComfyUI template with enough container disk space for the install, models
and outputs. A Network Volume is optional. Without one, set Volume disk to 0 GB;
`/workspace` is an ordinary directory on the temporary container disk. A common
template path is `/workspace/runpod-slim/ComfyUI`; use your actual template path.
Download outputs before stopping/deleting the Pod; a cleared disk requires
installing and downloading the models again. The automatic launcher does this
on each fresh Pod.

```bash
export COMFY_ROOT=/workspace/runpod-slim/ComfyUI
export PROJECT_ROOT=/workspace/ambient-loop
bash "$PROJECT_ROOT/cloud/bootstrap.sh"
bash "$PROJECT_ROOT/cloud/start.sh"
```

Place this project at PROJECT_ROOT first. Install ffmpeg/ffprobe using your
image's package manager if absent. Expose 8188 through the provider gateway.
The legacy `runpod/start.sh` checks the older CLI environment lock; use the
cloud launcher for this workflow.

## Vast.ai

Use a ComfyUI image or install ComfyUI in its CUDA Python environment. Put both
ComfyUI and this project on the provider's actual persistent mount:

```bash
export COMFY_ROOT=/workspace/ComfyUI
export PROJECT_ROOT=/workspace/ambient-loop
bash "$PROJECT_ROOT/cloud/bootstrap.sh"
bash "$PROJECT_ROOT/cloud/start.sh"
```

`/workspace` is an example; mounts vary by offering/image. Expose 8188 through
the authenticated connection. Verify which storage survives stop, replacement
and destroy operations. Copy models, workflows and outputs to retained storage
before destroying an instance; instance disks are not assumed to survive.

## Models and dependencies

Bootstrap installs Ambient Loop's vision extra and ComfyUI-LTXVideo. It does
not download gated weights or replace the template Torch/CUDA installation.
Dependency ranges are installation candidates, not a tested lock. Record the
installed revisions/package freeze during qualification.

Install the models in the official workflow's Model Links note into its named
ComfyUI directories. Accept Hugging Face access terms first using your account.
Keep the same BF16 distilled transformer, Gemma 4 encoder/enhancer, video/audio
VAEs and Motion Track IC-LoRA files for baseline and adapted validation.

Download a Qwen3-VL-8B-Instruct snapshot into
`$COMFY_ROOT/models/Qwen3-VL-8B-Instruct`, including configs/tokenizer and weights.
Record its immutable revision and SHA256 files. Set the editor's `vision_model`
to that absolute path or use the default relative path. The launcher starts in
the ComfyUI directory. Prepare uses `local_files_only=True`; it never calls a
hosted service or downloads weights during creative work. Missing weights give
editor feedback and leave manual placement available. Anime landmarks require
visual validation against the original source image.

Install [realesr-animevideov3.pth](https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth)
in `$COMFY_ROOT/models/upscale_models/`. Finishing uses ComfyUI's Spandrel support
and tiled Torch inference; the older BasicSR package is not needed. Finishing
records include the actual upscale weight hash.

## Retained data

If persistence is desired, keep `models/`, `input/`, `output/`, user workflows
and the project on retained storage. For container-disk-only RunPod sessions,
download the needed artifacts before stopping the Pod. Each unique candidate
directory retains `raw/` (145 generated frames),
`frames/` (144 playback frames), `record.json`, `loop.mp4` and `seam.mp4`.
Each finish retains its own enhanced PNGs, record and previews. Frame hashes are
verified before finishing; do not rename/remove frame files.

After restart, reopen the saved workflow, refresh candidates and select an
original candidate. Finishing has no dependency on source image/editor/video
models. Initial generation still materializes the official decoded batch;
RENDER_HANDLE and finishing never retain that full tensor batch.
