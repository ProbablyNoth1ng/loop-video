# Faster Finishing Implementation Plan

> For agentic workers: use superpowers:executing-plans for this owner-directed inline implementation. Track steps with checkboxes.

Goal: Finish one saved candidate repeatedly with Fast, Balanced AI or Original AI and compare results.
Architecture: Add a new selector node and dispatch in the existing candidate finishing path. Keep old node contracts; extend stage isolation and generated editable workflow.
Tech stack: Python >=3.11, Pillow 11.3.0, FFmpeg, Spandrel, ComfyUI, Node test runner.
Spec: [faster finishing design](../specs/2026-10-08-faster-finishing-design.md).

## Constraints and review focus

Keep official LTX graph unchanged, old Upscale inputs/defaults compatible, and saved candidate bytes intact. Test unsupported FP16, OOM tile fallback, corrupt frames, near-16:9 legacy crop and graphs containing both finishing node classes.

## Task 1: Finishing methods

Files: `ambient_loop/candidates.py`, `tests/test_candidates.py`.

- [x] Write behavioral tests for Fast exact frames/timing/candidate immutability, method records, FP16 rejection and adaptive tile fallback.
- [ ] Run focused Python tests and observe missing-method/incorrect-dispatch failures. Blocked: no Python runtime; PyManager could not download one.
- [x] Implement method dispatch and precision/tile policy; preserve the default Original AI path.
- [ ] Rerun focused tests and record outcomes. Requires a configured Python environment.

## Task 2: Nodes and stage isolation

Files: `ambient_loop/staged_comfy.py`, `comfy_nodes/ambient_loop/web/{stages,queue_control,ambient_loop}.mjs`, `tests/test_stages.py`, `tests/{test_stages,test_queue_control,test_previews}.mjs`.

- [x] Write tests for the new node defaults, old node compatibility, chooser target and isolated queueing.
- [x] Run focused Node tests; observed four expected failures for missing new-node handling. Python red check blocked as above.
- [x] Register the new node and update chooser/pruning/guard/preview behavior.
- [x] Rerun focused Node tests; stage tests passed 16/16, then direct-selection case passed 7/7, and preview tests passed 7/7. Python check remains pending.

## Task 3: Editable workflow and handoff

Files: `tools/build_motion_workflow.mjs`, `workflows/ambient-motion.json`, `tests/test_motion_workflow.mjs`, specs, `codemap.md`.

- [x] Write workflow test for Fast/1080p default and saved-selector edge; observed expected missing-node failure.
- [x] Update builder and regenerate workflow; workflow tests passed 5/5.
- [ ] Run full Python and Node suites plus `git diff --check`; inspect diff and reconcile docs/codemap. Node 37/37 and diff check passed; Python unavailable.
- [x] Record GPU timing and visual acceptance as pending because no saved LTX candidate or local GPU is available.

## Verification and handoff

Node red: `node --test tests/test_stages.mjs tests/test_queue_control.mjs` failed 4 expected new-node cases; `node --test tests/test_motion_workflow.mjs` failed on missing `AmbientFinish`; `node --test tests/test_previews.mjs` failed on missing method display. Node green: the same focused suites passed after implementation; `node --test <all tests/*.mjs>` passed 37/37. `git diff --check` and `git diff --exit-code -- workflows/ltx-2.5-motion-track.official.json` passed. FFmpeg 9.0 probe cropped two 1290x720 source frames to numbered 1920x1080 PNGs; an independent encoder probe produced a silent MP4 with one video stream, two frames and 8 FPS. `python -m unittest discover -s tests -v` could not start: no installed Python, and `uv python install 3.11` failed because network access is blocked. Thus Python red/green, application MP4 integration, GPU timings and visual acceptance are pending.
