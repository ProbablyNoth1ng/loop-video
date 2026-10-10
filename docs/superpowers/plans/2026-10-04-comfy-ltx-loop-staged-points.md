# Comfy LTX Loop Staged Execution and Point Review Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Prepare reliably deliver a reviewable landmark plan, make Render queue the generation chain without the node 5014 error, and show both Qwen and manual landmarks clearly on the source image and in a list.

**Architecture:** Keep `ComfyLTXLoopMotionEditor` as the Prepare output and `ComfyLTXLoopSaveCandidate` as the Render output. Trace ComfyUI workflow conversion before changing the graph: `app.graphToPrompt()` currently runs before `stageGraph()`, and the adapted `Input Parameters` subgraph connects its image input directly to its `resized` output. Repair the confirmed conversion/routing fault at its source, then make stage boundaries and the plan-to-UI contract explicit. Keep the official model, sampler, guide, and decode subgraphs intact.

**Tech Stack:** ComfyUI workflow JSON and custom nodes, JavaScript ES modules, Python, Node test runner, unittest, local browser harness.

**Spec:** User issue summary (2026-10-04), `README.md`, and `docs/qualification.md`.

## Global Constraints

- Prepare's prompt must contain `LoadImage` and `ComfyLTXLoopMotionEditor` only; its terminal output is the editor.
- Render's prompt must contain `ComfyLTXLoopSaveCandidate` and its required generation ancestors, including node 5014 when needed; its terminal output is the saver. Upscale remains separate.
- Preserve reviewed plan fingerprints and invalidation when the image, motion settings, or points change.
- Preserve the official `Load Models`, `Sampler - Distilled (8 steps)`, `Preprocess`, and `Decode` subgraphs.
- Show each proposed or manually added landmark as a high contrast dot on the original image and as a labeled list item with coordinates. Selecting a dot or row selects the same landmark. Disabled landmarks remain distinguishable.
- An image preview alone is insufficient: Prepare succeeds only when the frontend receives a valid `motion_plan` and displays its landmarks; an empty manual plan must be clearly identified as awaiting points.

## Review Focus

- `graphToPrompt()` fails before `stageGraph()` sees a graph: capture the exception and its origin, then test conversion of the adapted subgraph on the deployed frontend.
- A stale browser extension or backend class definition is loaded: record frontend/backend revisions and verify the active `ComfyLTXLoopMotionEditor`/`ComfyLTXLoopSaveCandidate` definitions.
- Qwen fails or returns partial/invalid points: show the actual feedback and leave a usable, visibly empty manual editor.
- Source image aspect ratio or letterboxing changes click coordinates: test portrait, landscape, and edge clicks against normalized point positions.
- Save/reopen or repeated Prepare loses or misroutes a plan: test the UI event, widget/metadata persistence, review state, and later Render input.

---

### Task 1: Locate the failing boundary on the running ComfyUI installation

**Files:** Inspect `comfy_nodes/comfy_ltx_loop/web/comfy_ltx_loop.js`, `comfy_nodes/comfy_ltx_loop/web/stages.mjs`, `workflows/comfy-ltx-loop-motion.json`, `tools/build_comfy_ltx_loop_workflow.mjs`, `comfy_ltx_loop/staged_comfy.py`; record findings in the implementation notes or test fixture.

**Interfaces:** `app.graphToPrompt() -> {workflow, output}`; `stageGraph(output, targetId, stage) -> selected`; `api.queuePrompt(0, {output:selected, workflow})`.

- [ ] Instrument a local run at the three boundaries: before/after `graphToPrompt()`, after `stageGraph()`, and at `/prompt`. Record stage, target ID, selected node IDs/classes, and the full error stack; do not log image bytes or model prompts.
- [ ] Reproduce Prepare and Render with the deployed workflow. If `graphToPrompt()` throws, isolate node 5014's `resized` subgraph output. If it succeeds, inspect selected graph and server response for the first broken reference.
- [ ] Compare active browser extension and backend node definitions with the checkout; hard refresh/reload only after recording versions. Confirm editor and saver have `OUTPUT_NODE = True` in the running backend.
- [ ] Capture a minimal failing workflow-conversion fixture or a precise live reproduction before changing production code. The result must distinguish workflow conversion, stage filtering, queue validation, and backend execution failures.

### Task 2: Repair the confirmed workflow conversion/routing fault

**Files:** Modify `tools/build_comfy_ltx_loop_workflow.mjs` and regenerated `workflows/comfy-ltx-loop-motion.json`; test in `tests/test_motion_workflow.mjs`. Modify `comfy_nodes/comfy_ltx_loop/web/comfy_ltx_loop.js` or `stages.mjs` only if Task 1 places the failure there.

**Interfaces:** The generated workflow retains editor output `canvas` at slot 0, `motion_plan` at slot 2, and saver input `motion_plan`; `stageGraph()` receives a valid flattened API prompt.

- [ ] Add a failing regression test for the precise broken mapping/reference found in Task 1. Include the internal `Input Parameters` output and its top-level consumer when that is the failing boundary; a static link-consistency check alone is insufficient.
- [ ] Change the builder at the responsible layer. If ComfyUI cannot flatten the direct subgraph input-to-output link, route the already prepared canvas to its consumer through a supported mapping, without resizing it again. Regenerate the JSON from the builder.
- [ ] Run `node --test tests/test_motion_workflow.mjs tests/test_stages.mjs`; expect all tests to pass, and confirm `graphToPrompt()` succeeds on the deployed frontend.
- [ ] Inspect the flattened graph: Prepare has editor and LoadImage only; Render reaches `ComfyLTXLoopSaveCandidate`, includes the required LTX ancestors, and has no dangling `[nodeId, slot]` references. Node 5014 may be present in Render as an upstream conditioning node.

### Task 3: Make stage output and UI message contracts observable

**Files:** Modify `comfy_nodes/comfy_ltx_loop/web/stages.mjs`, `comfy_nodes/comfy_ltx_loop/web/comfy_ltx_loop.js`, and targeted tests in `tests/test_stages.mjs`/`tests/test_stages.py` as evidence requires.

**Interfaces:** `stageGraph(output, targetId, stage)` validates the expected target class and upstream references. `ComfyLTXLoopMotionEditor.execute()` returns `ui.motion_plan` and `ui.bg_image` plus the seven existing result slots.

- [ ] Add failing tests for wrong target class, missing upstream reference, and stage-specific node membership. Keep Prepare limited to LoadImage/editor and Render free of Upscale.
- [ ] Add a backend contract test that Prepare returns `ui.motion_plan[0]`, `ui.bg_image[0]`, and result slot 2 containing the same plan. Cover manual and failed-Qwen preparation.
- [ ] Make frontend errors identify the failing boundary and node instead of reporting only an opaque queue error. Verify the browser receives the editor execution event and that `message.motion_plan[0]` is a valid plan before enabling review.
- [ ] Run `node --test tests/test_stages.mjs` and `python -m unittest tests.test_stages -v`; expect passes. Verify a real Prepare event updates the hidden plan widget and persisted workflow metadata.

### Task 4: Make Qwen and manual points visible and editable

**Files:** Modify `comfy_nodes/comfy_ltx_loop/web/comfy_ltx_loop.js`; extend `tests/editor_harness.py` and add focused browser/UI checks. Touch `comfy_ltx_loop/motion.py` or `comfy_ltx_loop/vision.py` only for a proven data contract or grounding defect.

**Interfaces:** The editor reads `plan.landmarks[]` with normalized `x`/`y`, label, enabled state, strength, and path. All edits update `plan_json`, reset review to pending, persist the plan, and redraw both image and list.

- [ ] Reproduce manual Add point and Qwen-proposed points in the harness; capture whether the failure is absent plan data, missing execution event, background timing, or drawing/hit testing.
- [ ] Add a landmark list beside/below the image: numbered label, normalized coordinates, enabled state, and clear selection. Use a bright green dot and readable label on the image; use a distinct selected style and muted disabled style.
- [ ] Make Add point work from a valid empty manual plan. After a click, show the dot and row immediately, select the new landmark, and update coordinates during drag. Row selection must highlight the matching dot and expose its path controls.
- [ ] Show Qwen failure or missing requested landmarks as actionable feedback. Keep manual editing available. Do not silently accept an empty plan as reviewed; keep backend `review_plan()` as the final guard.
- [ ] Exercise portrait/landscape images, letterboxed edges, multiple points, disable/delete, path edit, Qwen fallback, save/reopen, and Accept point review in the browser harness. Confirm the rendered green dot corresponds to the stored normalized coordinate.

### Task 5: End-to-end qualification and handoff

**Files:** Update `README.md` and `docs/qualification.md` with any changed behavior and actual test results; retain captured API graphs or logs as task evidence where appropriate.

- [ ] Run `python -m unittest discover -s tests -v` and `node --test tests/test_stages.mjs tests/test_motion_workflow.mjs`; record passes and failures.
- [ ] On the running ComfyUI installation, use the user's 2752×1536 image at 3 seconds, 24 FPS, strength 0.01, short side 720. Prepare manually, add and review a visible point, Render, and inspect preview. Repeat Prepare with local Qwen and verify proposed points or explicit failure feedback.
- [ ] Inspect both `/prompt` payloads and the execution UI event. Prepare must exclude 5014; Render must end at `ComfyLTXLoopSaveCandidate`; `message.motion_plan[0].landmarks` must match the visible list and dots. Verify the 73-frame plan and no `No output node found for id [5014] slot [1] resized` error.
- [ ] Save/reopen the workflow and repeat point review and Render. Record any remaining Qwen accuracy limitations separately from routing/UI failures; do not claim GPU/browser qualification from local tests alone.
