# Automatic RunPod installation

Use `runpod/comfyui:1.3.3-comfyuiv0.30.0-cuda13.0` with an NVIDIA Blackwell GPU.
The launcher fixture was extracted from image digest
`sha256:e8505fe1ba1b39cc6a140c2f01fe8d8d47f680cc7af45662ec0d77858fba8355`.
This installs the current BF16 workflow; its minimum GPU memory is not qualified.
The installer does not silently substitute quantized models.

## Storage

Use the Pod's temporary container disk. No Network Volume is needed.

1. Set Container disk to 250 GB as a starting allocation for the image, copied
   ComfyUI environment, BF16 model files and outputs. Actual required space is
   checked before model downloads; large numbers of renders can need more.
2. Set Volume disk to 0 GB and do not attach a Network Volume. Leave the template
   mount-path field at `/workspace`; without a volume, this is simply a directory
   on the container disk, not a separately provisioned storage resource.
3. Expose HTTP 8188 for ComfyUI and 8888 for JupyterLab. TCP 22 is optional for SSH.

Every fresh Pod downloads the project, nodes, dependencies and models from their
existing GitHub/Hugging Face sources automatically. Container-disk files are lost
when the Pod stops or is deleted. Download finished videos, frames and saved
workflows before stopping it. The container disk itself is billed by RunPod;
this configuration avoids a separate persistent volume.

## Start command

Publish `cloud/install.py` and `cloud/runpod_entrypoint.py` in your repository
before using this command. Both files must be available on the selected revision.
Then generate the short command locally:

```powershell
python tools/build_runpod_command.py
```

The generated `outputs/runpod-start-command.json` is the **complete value** for
the template's Start command field. It explicitly overrides the image's Docker
entrypoint using RunPod's supported JSON `entrypoint`/`cmd` format. A plain CMD
does not replace the official image's `/start.sh` entrypoint.

The JSON contains only a small loader, below RunPod's 4000-character `dockerArgs`
limit. It clones the project and runs `cloud/runpod_entrypoint.py` from:

```text
https://github.com/ProbablyNoth1ng/loop-video.git
```

The installer preserves the official launcher: SSH, Jupyter, ComfyUI
initialization and its virtual environment still run. It inserts installation
immediately before the launch of ComfyUI, with `--cache-none` for the staged
workflow. If the image launcher changes incompatibly, startup fails explicitly
instead of launching a partially installed environment. The adapter recognizes
both the image's `COMFY_ARGS` array launch and the older `FIXED_ARGS` launch.
The extracted image launcher is covered by local regression tests.

## Environment variables

| Variable | Value |
| --- | --- |
| `AMBIENT_REPO` | Optional repository URL; defaults to the URL above |
| `AMBIENT_REVISION` | Optional Git branch/tag/commit, used on first clone |
| `LTX_REVISION` | Optional LTX Git branch/tag/commit, used on first clone |
| `HF_TOKEN` | Hugging Face token with read access to the required models |
| `JUPYTER_PASSWORD` | Your JupyterLab token/password |
| `FILEBROWSER_PASSWORD` | Your FileBrowser password if exposing port 8080 |

Use RunPod Secrets for tokens. First accept any access conditions required by
the LTX-2.5 and Gemma repositories using your Hugging Face account. The installer
cannot accept account agreements for you. It does not print `HF_TOKEN` or put it
in the generated command. Your current public GitHub repository needs no token.

## What happens on boot

- Clone Ambient Loop and ComfyUI-LTXVideo into `/workspace` on the container disk.
- Install project, vision, ComfyUI and LTX requirements using ComfyUI's active
  virtual environment, while constraining Torch/torchvision/torchaudio to the
  image's installed versions. Install ffmpeg if missing.
- Connect the Ambient Loop custom nodes.
- Download the six exact model files declared by the official Motion Track
  workflow, a Qwen3-VL-8B-Instruct snapshot including configs/tokenizer/weights,
  and Real-ESRGAN's `realesr-animevideov3.pth`.
- Resolve Hugging Face models to immutable commits before downloads, check free
  disk space, file sizes and available source SHA256 hashes, and validate the
  Real-ESRGAN checkpoint with Spandrel.
- Add both workflows to ComfyUI's saved workflows, preserving existing copies.
- Start ComfyUI on 8188 only after installation succeeds.

The first boot includes large downloads and checksum reads. Its duration depends
on the network and disk throughput. During setup, use the Pod logs or Jupyter;
the ComfyUI port is not ready yet. Look for `AMBIENT LOOP INSTALLED`, followed by
ComfyUI's normal server startup. Open `ambient-motion` from saved workflows.
Successful installation is not proof of GPU rendering or visual loop quality.

When files still exist, another invocation uses the existing project/LTX revisions,
installed dependencies and model files; it does not automatically pull upstream code.
An existing `/workspace/ambient-loop` checkout does not automatically pull a
published adapter fix on restart. Use a fresh Pod or update that checkout explicitly.
A new or cleared container disk always gets a complete installation. Fast model checks
compare recorded sizes, plus the small upscale model's checksum. They do not
rehash all large weights on every boot. Interrupted HF downloads reuse their
local download metadata on retry while those files remain on disk.
Missing/truncated models trigger recovery.
Checksums, model revisions and `pip freeze` are retained under
`ComfyUI/.ambient-loop-install/`. Run one Pod at a time against this installation.

If setup fails, fix the issue shown in the logs and retry. Stopping the Pod clears
the temporary files; a new boot downloads them again. Account
access errors require fixing the token or accepting the model's terms. A failed
installation never writes a completed models marker.

## Manual installation

For an already initialized ComfyUI environment with the project available:

```bash
python3.12 /workspace/ambient-loop/cloud/install.py
```

This command selects the official ComfyUI virtual environment if invoked from
system Python. Stop/restart ComfyUI after manual installation so it loads the
new nodes. Use the generated Start command for automatic setup on future boots.

Sources: [RunPod template command format](https://docs.runpod.io/pods/templates/manage-templates),
[official image launcher](https://github.com/runpod-workers/comfyui-base/blob/main/start.sh),
[RunPod storage](https://docs.runpod.io/pods/storage/types).
