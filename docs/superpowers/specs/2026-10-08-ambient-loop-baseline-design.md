# Ambient Loop technical baseline

Date: 2026-10-08. Status: implemented repository baseline; deployment qualification pending.
Product contract: [P-01–P-10](../../product-spec.md).

This document captures current architecture for future work. It was derived from
local source and existing records, without a fresh library compatibility audit or
GPU run. Historical test evidence is in [qualification](../../qualification.md).

## Architecture and ownership

```text
Load image + settings
  → AmbientMotionEditor (Prepare: manual or local Qwen)
  → serialized MOTION_PLAN + shared frontend editor
  → explicit point review
  → AmbientMotionEditor (Render: validate review, map canvas/tracks)
  → adapted official LTX-2.5 single-stage graph
  → AmbientSaveCandidate → disk record + continuous/seam previews
  → AmbientSavedCandidate → optional AmbientUpscale → silent MP4
```

| Product IDs | Owner | Existing test coverage |
| --- | --- | --- |
| P-01, P-05 | `ambient_loop/motion.py`, `staged_comfy.py`, frontend `geometry.mjs` and `ambient_loop.js` | `test_motion.py`, `test_stages.py`, `test_editor_geometry.mjs` |
| P-02, P-03 | `ambient_loop/vision.py`, `motion.py`, `staged_comfy.py`, frontend editor | `test_vision.py`, `test_semantic_points.py`, `test_stages.py`, `test_editor_semantics.mjs` |
| P-04, P-05 | Frontend editor, `ambient_loop/comfy_routes.py`, motion validation | `test_editor_semantics.mjs`, `test_motion.py`, local `editor_harness.py` |
| P-06 | Frontend `queue_control.mjs`, `stages.mjs`, `ambient_loop.js` | `test_queue_control.mjs`, `test_stages.mjs`, `test_stages.py` |
| P-07 | `workflows/ambient-motion.json`, `tools/build_motion_workflow.mjs`, `AmbientSaveCandidate` | `test_motion_workflow.mjs`, `test_candidates.py`, `test_previews.mjs` |
| P-08, P-09 | `ambient_loop/candidates.py`, staged candidate/finishing nodes and frontend | `test_candidates.py`, `test_resolution_integration.py`, `test_previews.mjs` |
| P-10 | `cloud/`, `runpod/`, `tools/build_runpod_command.py`, CLI modules | `test_cloud_install.py`, `test_vision_install.py`, `test_operations.py`, `test_workflow.py` |

File names in the test column are under `tests/`. This maps coverage ownership,
not a claim that every acceptance criterion has deployed evidence.

## Motion and review contracts

- `MOTION_PLAN` is JSON with schema `ambient-motion-plan/1`, source identity/size,
  prompt/requested parts, timing, strength, canvas transform, landmarks and review.
- Landmark positions and paths use normalized source-image coordinates. Semantic
  fields identify `motion_role` (`move` or `anchor`), body part/object and reason.
  `group` identifies character/background; legacy ungrouped points mean character.
- Anchors remain stationary; returning paths start/end at the landmark. Validate
  finite coordinates, increasing path times, enabled state and strengths.
- `review_plan()` rejects an empty enabled-point set and stale preparation. Enabled
  background motion requires a valid prompt/preparation and a moving enabled point.
- `require_review()` checks source, instructions, model/preparation and fingerprint
  before Render. Frontend timing/canvas edits also invalidate acceptance; backend
  transform regeneration supports normalized paths. Inspect both layers on changes.
- Source change clears groups. Independent preparation preserves the other group;
  manual/model-failure paths preserve editable existing points with feedback.
- `background_prompt.strip()` is the animation switch. The optional legacy
  `animate_background` socket remains for workflow compatibility.

## Image, timing and generation contracts

- Exactly one source image. Content resizing preserves aspect ratio; edge padding
  aligns the generation canvas to multiples of 64 and the half-resolution guide to 32.
  Export crops padding using the recorded transform.
- `duration * fps` must be an integer multiple of 8, at least 8. Generated frame count
  is playback count plus one endpoint. Defaults: 6 seconds, 24 FPS, 145 generated,
  144 playback frames, seed 42, strength 0.01, generation short side 720.
- Retain `workflows/ltx-2.5-motion-track.official.json` unchanged as the qualification
  baseline. The adapted graph changes preparation/persistence around official model
  loading, IC-LoRA conditioning, the single-stage sampler and tiled decode.
- Prompt enhancement is off; official audio latents remain in the pipeline and
  exported videos are silent. Returning tracks do not guarantee perceptual closure.

## Stage and persistence contracts

- Frontend stage pruning prevents preparing points from reaching generation,
  rendering from reaching finishing, and finishing from reaching generation.
- Global Run is intercepted for Ambient workflows and opens explicit stage choices.
  Ordinary workflows and explicit partial execution preserve their queue contracts.
- Plans persist in serialized editor widgets/workflow metadata. Saved candidates
  persist under `ComfyUI/output/ambient-loop/`, with schema `ambient-render-handle/1`.
- Candidates retain raw PNGs, playback PNGs, previews, settings and hashes. Handles
  contain disk records rather than live tensors. Candidate paths remain within the
  output root. Reopening discovers completed original candidates.
- Finishing uses `realesr-animevideov3` in bounded chunks; short sides 1080/1440/2160,
  default 1440. Preserve candidate files, aspect ratio, even dimensions, count and FPS.
- New schema, socket ordering or model-cache changes need explicit compatibility
  tests against existing saved workflows and manifests.

## Vision and environment baseline

Vision loads local snapshots only. `config.json` selects Qwen3-VL or Qwen3.5 model
classes. Qwen3.5 thinking is disabled. Parsing retains valid partial points and
omission feedback. All success/failure paths release model/input/output references
and request CUDA cleanup before generation; real VRAM recovery is still unverified.

| Component | Repository constraint or revision | Evidence scope |
| --- | --- | --- |
| Python | `>=3.11` | `pyproject.toml` |
| NumPy / Pillow / SciPy | `2.2.6` / `11.3.0` / `1.15.3` | Project pins, not latest-release claims |
| Transformers / Accelerate | `>=5.2,<6` / `>=1.10,<2` | Optional vision dependency constraints |
| Vision snapshots | `Qwen/Qwen3.5-9B`; `Qwen/Qwen3-VL-8B-Instruct` | Local config dispatch and installer manifests |
| ComfyUI installer compatibility | v0.38.0; commit `6b747c0428c343e1417219641db93a4fb7cb69ae` | Installer pin; compatible existing versions may be retained |
| LTX integration | Official saved graph and installer-resolved model/repository records | GPU/model compatibility still needs qualification |

Before changing any dependency/API, use Context7 and official release records for
the relevant version, record dated results in the feature design and preserve
existing pins until a justified, tested compatibility change is authorized.

## Failure cases and proof boundary

Cover malformed/partial vision output, unavailable snapshots, model load/generate
failure, stale review, source/prompt/model changes, empty/background-only groups,
workflow reopen, canvas padding/orientation, queue cancellation/ambiguity, corrupt
candidate records, and frame-preserving finishing.

CPU and synthetic editor tests cannot prove actual ComfyUI graph conversion,
GPU inference, anime landmark placement, animation quality or temporal finishing
quality. Preserve these unresolved checks in [qualification](../../qualification.md).
Future changes start from this baseline and add their own observed test-first evidence.
