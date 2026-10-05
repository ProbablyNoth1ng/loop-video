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
Parameters no longer connects its image input directly to its `resized` output.
The already transformed editor canvas feeds the top-level Preprocess image input
without another resize. Capture `graphToPrompt()` output on the deployed frontend
before claiming this conversion is qualified.

## 2026-10-04 local staged-point implementation evidence

- `node --test tests/test_stages.mjs tests/test_motion_workflow.mjs tests/test_editor_geometry.mjs`: 14 passed, including portrait/landscape image and CSS letterbox coordinate mapping.
- `python -m unittest tests.test_stages -v`: 4 passed.
- `python -m unittest discover -s tests -v`: 41 passed.
- Local browser fixture at `127.0.0.1:8766`: manual Prepare displayed an empty
  plan and Add point created a numbered row with normalized coordinates. A Qwen
  sample event displayed four labeled rows; selecting the first row populated
  its label and path controls. Disabling that point changed its row, and the
  state survived simulated reopen. A Qwen failure event showed explicit
  feedback, an empty list, and disabled review. An invalid Prepare event after
  a reviewed plan cleared the old plan and blocked Render. This fixture
  simulates queueing and does not run
  ComfyUI's `graphToPrompt()`.
- The pod was terminated, so deployed checks were deferred at the user's
  request. The workflow conversion, `/prompt` payloads, 2752 × 1536 image run,
  73-frame render, Qwen model inference, save/reopen in ComfyUI, and GPU preview
  remain unverified. The frontend now logs stage, target ID, selected node
  IDs/classes and error stack without logging image bytes or prompt text, for
  that run.

## 2026-10-05 global Run interception evidence

- `node --test tests/test_queue_control.mjs tests/test_stages.mjs
  tests/test_motion_workflow.mjs tests/test_editor_geometry.mjs`: 23 passed.
  The checks cover cancellation before conversion, unchanged ordinary and
  partial queues, one auto-queue notice per graph, isolated-stage guards, and
  trailing API queue arguments.
- The local fixture served the updated main Run controls and
  `queue_control.mjs` over HTTP. It remains a simulated queue fixture and has
  not qualified dialog focus, keyboard Escape, or the installed ComfyUI
  frontend's `app.queuePrompt` signature.
- No installed ComfyUI frontend was present in this checkout or user profile.
  Deployed verification still needs to confirm main Run and the keyboard queue
  entry point, the current third-argument form, no `/prompt` request before a
  stage is chosen, and normal-workflow queueing.

## Real anime pilot

Use licensed portrait/landscape anime with closeups, fine hair, occlusion,
cel shading and detailed backgrounds. Record provenance and held-out examples.
Inspect face identity, hair tips, fixed roots/head/shoulders, camera/background
drift and seams over three continuous cycles. Endpoint mean error is evidence,
not perceptual acceptance. Retry visibly poor seams; never substitute ping-pong.

Review 1440p and 4K finishes for line preservation and temporal flicker. Verify
144 playback frames, 24 FPS, six-second silent MP4 and distinct candidate/finish
names. Retain all 145 raw generated frames and sidecar records.
