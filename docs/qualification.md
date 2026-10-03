# GPU and visual qualification

Status: **pending**. No provider instance was available. Local CPU tests do not
prove LTX inference, Qwen anime landmark accuracy, Spandrel weight compatibility
or ComfyUI browser behavior on a provider.

## Official generation baseline

Import `workflows/ltx-2.5-motion-track.official.json` unchanged. Install its exact
models and run its defaults on the selected GPU. Do not alter sampler, precision,
LoRA, resizing or decoding for this first run. Save its exported API graph,
ComfyUI logs and output. Export the API graph using ComfyUI's developer option
after selecting the source image. The observer queues that graph without edits:

```bash
python /workspace/ambient-loop/tools/qualify_ltx.py \
  --comfy "$COMFY_ROOT" --api-graph baseline.api.json \
  --image-digest 'REGISTRY/IMAGE@sha256:ACTUAL_DIGEST' \
  --record /workspace/ambient-loop/evidence/cloud-baseline.json
```

It records queue/history result, wall time including queue wait, sampled total
GPU memory (not isolated process allocation), package freeze, ComfyUI/LTX
revisions and installed model/workflow hashes. Preserve output history and
actual dimensions/frame count. The unchanged baseline defaults differ from
the adapted six-second recipe; run and record the adapted recipe separately.
Reconcile lost queue responses/timeouts against queue/history; never blindly
resubmit an expensive job.

Qualify a supported minimum only after repeated successful actual runs of
Prepare → vision unload → Render → decode/save → Upscale. Record peak memory,
stage runtimes, storage, image digest, CUDA/driver and exact dependency/model
revisions. Check Qwen tensors are not resident during generation. Save a tested
lock from those results; weight file size alone cannot qualify a GPU.

## Browser checks

Test portrait/landscape sources, corner points/padding edges, point/path editing,
workflow save/reopen, and trajectory alignment in tracks_preview. Test missing
vision weights, malformed JSON, missing landmarks and out-of-bounds paths:
feedback must leave manual correction available. Review must stale on image,
prompt, timing, canvas and point changes. Test switching candidates and a full
ComfyUI restart. Inspect `/prompt` requests: Prepare contains no generation;
Render contains no Upscale; Upscale contains no generation.

Verify the current frontend's flattened subgraph API export. The adapted Input
Parameters passes the already transformed canvas directly to its image output.

## Real anime pilot

Use licensed portrait/landscape anime with closeups, fine hair, occlusion,
cel shading and detailed backgrounds. Record provenance and held-out examples.
Inspect face identity, hair tips, fixed roots/head/shoulders, camera/background
drift and seams over three continuous cycles. Endpoint mean error is evidence,
not perceptual acceptance. Retry visibly poor seams; never substitute ping-pong.

Review 1440p and 4K finishes for line preservation and temporal flicker. Verify
144 playback frames, 24 FPS, six-second silent MP4 and distinct candidate/finish
names. Retain all 145 raw generated frames and sidecar records.
