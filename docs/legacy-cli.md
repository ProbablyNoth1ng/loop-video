# Comfy LTX Loop - Workflow A

Runnable deterministic Workflow A, with optional gated regional Motion Track
experiments. The renderer runs on CPU using NumPy float32 and SciPy sampling;
ComfyUI invokes the same implementation without retaining video tensor batches.
No GPU performance claim is made for this implementation.

## Local use

Requires Python 3.11+, ffmpeg and ffprobe on PATH.

```powershell
python -m pip install -e .
python -m comfy_ltx_loop examples examples
python -m comfy_ltx_loop validate examples/rainy-window/project.json
python -m comfy_ltx_loop preview examples/rainy-window/project.json outputs/preview
```

The supplied examples are synthetic test images, not the licensed 12-image
artwork pilot and not approved assets. Inspect their source, masks, roots,
support overlay, movement and seams. For an actual prepared project:

```powershell
python -m comfy_ltx_loop approve assets/project.json masks --reviewer YOUR_NAME --reviewed
python -m comfy_ltx_loop approve assets/project.json motion --reviewer YOUR_NAME --reviewed
python -m comfy_ltx_loop render assets/project.json outputs/job
python -m comfy_ltx_loop accept outputs/job --reviewer YOUR_NAME --visually-reviewed
```

The two approval commands are human attestations, not automatic approvals.
Rendering never accepts an output. Inspect `review.html` before accepting.
The PNG sequence in `frames/` is the lossless master. MP4 is silent H.264,
CRF 18, yuv420p, constant 24 FPS. The review includes loop, quarter-speed,
seam-centered playback and support overlay. Preview outputs cannot be accepted.

## Project contract

Projects are JSON, `schema: comfy-ltx-loop/1`. Paths resolve relative to the
project file. `source` is opaque RGB/RGBA; `guard` is a grayscale immutable mask.
Every region specifies a unique `id`, integer `depth`, `kind`, grayscale `mask`
and binary `support`, all at original source dimensions. Support excludes guards.
White alpha is active. White root weight is free; black is fixed. Foliage also
requires a `roots` mask with zero weight on all white roots.

```json
{
  "schema": "comfy-ltx-loop/1",
  "source": "source.png",
  "guard": "guard.png",
  "working_mode": "1080p",
  "output_resolution": "1440p",
  "duration": 6,
  "fps": 24,
  "seed": 42,
  "preset": "calm-wind",
  "regions": [{
    "id": "grass", "kind": "foliage", "depth": 0,
    "mask": "grass-mask.png", "support": "grass-support.png",
    "roots": "grass-roots.png", "root_weight": "grass-weight.png",
    "amplitude": 2
  }]
}
```

`working_mode`: 720p or 1080p. `output_resolution`: 1080p, 1440p or 4K.
The short side is 720/1080/1440/2160, preserving landscape or portrait ratio.
Ratios that cannot map exactly to even yuv420p dimensions are explicitly rejected;
the renderer does not stretch, pad or crop. Duration is 4-30 seconds with a whole
number of 24 FPS frames. Seed is a nonnegative 63-bit integer.

Foliage amplitude is in 1080p-short-side pixels and scales with working size.
The safe interior taper keeps source sampling inside approved support and fixes
roots. Folded fields are rejected on every frame. Silhouette disocclusion is
deliberately refused (`expose_background: true`): clean-plate silhouette moving
is not implemented/qualified. Prepare approved interior regions instead.

Rain supports `particles` (1-2000) and `strength` (0-.2). Shimmer supports
`strength` (0-.2). Presets label the intended scene; explicit region assets and
settings determine motion. Source/asset/settings/renderer changes stale approvals.

Compositing uses linear RGB with premultiplied masked changes. Lanczos is used
for enlargement only; the 1080p -> 1080p enlargement path is skipped. The original
source is resized once in linear light as the chosen-resolution reference. All
unchanged and locked pixels are retained from that reference; fixed roots are
restored as well. Lossy H.264 pixels are not expected to remain bit-identical.

## Automation

Reissue `render` with the same project and output directory to resume. Each
frame is saved atomically, hashed and checkpointed with global indices. Changed
or truncated frames are regenerated. A changed job needs a new output directory.
The renderer holds one frame at a time. `--chunk-size` bounds scheduling/checkpoint
groups; OOM halves it and stops after three repeated failures. A one-frame OOM
requires reducing resource pressure; chunk reduction cannot fix that minimum.

An exclusive `.render.lock` blocks concurrent writers. After a disconnected/crashed
process, verify it has stopped and remove that job's stale lock before resuming.
Checkpoint hashes remain authoritative. States are `rendered`, `failed`,
`failed_qc`, `awaiting_review`, `accepted`.

`batch jobs.json` consumes a JSON list of `{ "project": "...", "output": "..." }`.
It validates all approvals before rendering and records individual failures.

```powershell
python -m comfy_ltx_loop graphs assets/project.json workflows --output /workspace/comfy-ltx-loop/outputs/job
python -m comfy_ltx_loop submit workflows/workflow-a.api.json queue-receipt.json --server http://127.0.0.1:8188
python -m comfy_ltx_loop status queue-receipt.json
python -m comfy_ltx_loop benchmark assets/project.json benchmarks --transfer-to REVIEW_DOWNLOAD_DIRECTORY
```

When exporting locally for RunPod, add `--project-path /workspace/comfy-ltx-loop/assets/project.json`.
The supplied sample graphs point to `/workspace/comfy-ltx-loop/examples/rainy-window/project.json`.

Queue submission persists an intent before the request. A lost response is marked
uncertain and never automatically resubmitted. Check the server queue/history.
Benchmark renders are unaccepted comparisons: 720p and 1080p working modes at
the selected output, plus a direct-1440p reference. Report includes renderer,
enlargement, restoration, encoding, QC, storage and actual transfer timing.
Unix RSS is a cumulative process high-water mark, not isolated per-run memory.
Use fresh processes for deployment memory comparisons. 720p is never promoted
automatically. Transfer is a file copy, network transfer only for a network target.

## RunPod

Use the existing official RunPod ComfyUI template, attach persistent storage at
`/workspace`, and put this project at `/workspace/comfy-ltx-loop`. Default ComfyUI
path is `/workspace/runpod-slim/ComfyUI`; override `COMFY_ROOT` if your template
uses another persistent path. No compute is rented by these scripts.

1. Run `bash runpod/bootstrap.sh` once in the template's Python environment.
2. Start ComfyUI, verify the Comfy LTX Loop node is registered.
3. Record the actual image digest supplied by your container/RunPod deployment:

```bash
comfy-ltx-loop environment record --comfy "$COMFY_ROOT" \
  --lock /workspace/comfy-ltx-loop/environment.lock.json \
  --image-digest 'REGISTRY/IMAGE@sha256:ACTUAL_64_CHARACTER_DIGEST'
```

4. Use `bash runpod/start.sh` on subsequent starts. It validates the recorded
   revisions, pins, GPU allocation, storage, node code, tiny rendering and encoding
   before launching with `--cache-none`. It never installs packages.

There is no fabricated tested digest checked into this repository. Qualification
must happen on the real pod. The GPU check validates GPU access; A itself is CPU.
Keep assets, workflows, checkpoints, model weights and outputs on the attached
volume. Copy review materials off the pod before releasing compute.

Template reference: https://github.com/runpod/runpod-plugins-official/blob/main/plugins/runpod/skills/runpod-templates/reference/comfyui.md

## Optional regional LTX

Run after A is accepted. Cache the official BF16 models under `/workspace` with
`cache-weight HTTPS_URL DESTINATION --sha256 EXPECTED_HASH` and
smoke-test the official single-stage Motion Track recipe unchanged. Export its
API graph from the tested ComfyUI server. No FLF, refinement, motion extraction
or learned seam repair is added. This repository does not distribute weights.

`regional` project settings require: `crop: [x,y,width,height]`, binary `support`,
binary `protected` (anatomy, text and sensitive linework), source-coordinate
`tracks` (145 positions per track), `official_api`, `smoke_record`, and `bindings`.
Configure these before A approval so fallback and region plans bind the same hash.
Support is limited to 10% of the original source and must lie within the crop.

`smoke_record` JSON contains `passed: true`,
`recipe: "BF16-single-stage-motion-track"`, `workflow_sha256`, and
`weights: [{"path": "models/...", "sha256": "..."}]`. It records actual tests,
not guessed compatibility. Every weight and graph hash is checked.

`bindings` maps each control to `[node_id, input_name]` in the exported API graph:
width, height, frames, fps, cfg, adapter_strength, prompt_enhancement, seed,
tracks, image. Bind the actual smoke-tested nodes; local API node IDs vary.
The image loader must accept the prepared crop path, or copy it into ComfyUI input
and bind a compatible loader. The experiment fixes 512x512, 145 frames, 24 FPS,
CFG 1, adapter strength 1 and prompt enhancement off. Seeds are 42,43,44.

```bash
comfy-ltx-loop regional prepare assets/project.json outputs/accepted-a experiments/region
# Human inspects crop, track-guide.png and track-guide.mp4 before the next command.
comfy-ltx-loop regional candidate assets/project.json outputs/accepted-a experiments/region --reviewer NAME
comfy-ltx-loop submit experiments/region/candidate-42.api.json experiments/region/receipt-42.json
comfy-ltx-loop status experiments/region/receipt-42.json
comfy-ltx-loop regional finish assets/project.json outputs/accepted-a experiments/region \
  --seed 42 --raw-frames RAW_145_FRAME_PNG_DIRECTORY
```

Import requires exactly 145 512x512 raw PNGs. Check raw unchanged-region drift,
endpoint closure and velocity before support-limited, feathered linear compositing
over accepted A. Export 144 unique frames, recheck locked pixels and encoding,
then repeat human review. Initial numeric thresholds are conservative design
values, not validated perceptual metrics. Retain accepted A on every failure.
The actual BF16 graph adaptation and inference still require GPU qualification.

## Verification and pilot

```powershell
python -m unittest discover -s tests -v
```

Unit coverage includes all dimension combinations, portrait sizing, periods,
whole frame counts, periodic displacement/velocity/rain, fixed roots, missing
assets, guard overlap, stale approvals, frame corruption/resumption and graph
control parity. Local preview smoke verifies encoding through ffprobe.

The report's pilot requires 12 licensed real images: four per preset, at least
one held out per preset. Include face closeups, full figure, fine hair, cel
shading, painterly background, dense grass, reflections, portrait, landscape and
difficult occlusion. Run each working/output combination, then two reviewers judge
preservation, plausible motion, stability and seams over three cycles. Record
disagreements, acceptance rates and measured all-in costs. Synthetic examples
do not substitute for this pilot or final visual acceptance.
