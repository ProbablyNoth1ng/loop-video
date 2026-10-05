# Ambient Loop Global Run Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clicking ComfyUI's main Run / Queue button on the Ambient Loop workflow offers an explicit stage choice without producing the reported execution error or queueing multiple stages.

**Architecture:** Intercept the frontend Run entry point before full workflow conversion. Show an extension-owned stage chooser, then submit an explicitly selected stage through the existing `queue(stage, target, status)` function. Preserve the low-level unsafe-prompt guard and the current stage graph and review checks.

**Tech Stack:** JavaScript ES modules, ComfyUI frontend extension, Node test runner, existing Python browser fixture.

**Spec:** User screenshot and confirmed trigger on 2026-10-04; requirements below; existing stage contracts in `README.md` and `docs/superpowers/plans/2026-10-04-ambient-loop-staged-points.md`.

## Evidence and diagnosis

- The user confirmed that ComfyUI's main Run / Queue button caused the screenshot.
- `comfy_nodes/ambient_loop/web/ambient_loop.js` currently wraps `api.queuePrompt()` and throws the exact screenshot message when `prompt.output` contains both `AmbientSaveCandidate` and `AmbientUpscale`.
- The supplied workflow contains both stage outputs. The normal Run path submits the full graph to the guard; the node stage buttons instead call `stageGraph()` before submission.
- This rejection is deliberate stage isolation. The user-facing fault is that an expected stage-selection requirement escapes as an execution exception.
- Upstream [ComfyUI frontend app.ts](https://github.com/Comfy-Org/ComfyUI_frontend/blob/main/src/scripts/app.ts) defines `app.queuePrompt(number, batchCount, optionsOrQueueNodeIds): Promise<boolean>`. It converts the graph and calls `api.queuePrompt(number, prompt, options)`. Returning `false` before that processing provides a cancellation boundary. Verify this interface against the installed frontend before implementing; upstream main is not proof of the deployed version.
- Investigation here was source inspection and user confirmation. No deployed browser reproduction, GPU run, or tests were performed for this planning request.

## Global constraints and proposed behavior

- Run on a workflow containing a top-level `AmbientMotionEditor`, `AmbientSaveCandidate`, or `AmbientUpscale` opens one chooser titled **Choose an Ambient Loop stage**. It does not queue anything immediately.
- Copy: **Prepare points, review them, then Render. Upscale uses a saved candidate. Each choice queues one stage.** Actions: **Prepare points**, **Render**, **Upscale**, **Cancel**.
- Run does not infer a stage from review state, automatically accept review, or combine rendering and finishing.
- Prepare retains only its editor and LoadImage ancestors. Render retains its saver and generation ancestors, excludes Upscale, and requires current accepted review. Upscale uses the saved-candidate branch only.
- Chooser actions submit exactly one job through the existing stage path. The main Run batch count does not apply; the chooser explicitly explains its single-stage behavior.
- Cancel, Escape, or dismissal resolves the intercepted Run as `false`, with no `/prompt` request or success message.
- Repeated Run calls reuse the open chooser. Disable action buttons while a stage submission is pending. Re-enable after failure so the user can correct or retry it.
- If a stage has no unique target, disable that action and explain the missing/ambiguous target. If multiple editors exist, disable chooser Render and direct the user to resolve the ambiguity; do not silently choose the first editor.
- If the active root graph changes or a target is removed while the chooser is open, cancel the old choice and ask the user to reopen Run for the current workflow.
- Calls with explicit partial-execution targets remain on ComfyUI's original queue path and retain the existing API guard. Auto-queue on Ambient workflows must not start stages automatically or repeatedly open dialogs; return `false` and show one explanatory notice per active graph.
- Ordinary workflows delegate all queue arguments, receiver, return values, and errors unchanged. API wrappers must also forward the optional third argument and any later arguments.
- Genuine conversion, validation, and backend errors remain errors. Never fabricate a `prompt_id`, return `undefined` as a queue result, or suppress unrelated exceptions.
- Keep existing working-tree changes intact. Backend nodes, model pipeline, generated workflow topology, and the earlier point-editor fixes are outside this issue's scope.

## Review focus

- Repeated clicks and auto-queue: one chooser or notice, no duplicate submission.
- Missing/unaccepted/stale review: Render sends no request and displays the existing actionable validation message.
- Workflow switching and removed targets: no submission against a stale graph.
- Non-Ambient workflows and partial execution: original queue contract and API options preserved.
- Conversion/backend rejection: visible failure and usable retry controls, without false success.

---

### Task 1: Add a cancellable Run interception boundary

**Files:** Create `comfy_nodes/ambient_loop/web/queue_control.mjs` and `tests/test_queue_control.mjs`; modify `comfy_nodes/ambient_loop/web/ambient_loop.js` setup.

**Interfaces:** Export `installStageQueueControl(app, showStageChooser, showAutoQueueNotice): void`. `showStageChooser(graph): void` opens or reuses the chooser; `showAutoQueueNotice(graph): void` displays one notice per graph. The installed `app.queuePrompt(...args): Promise<boolean>` delegates to the original method or returns `false` after offering stage controls. Resolve the active graph as `app.rootGraph ?? app.graph`; match node classes by `comfyClass ?? type`.

- [ ] Confirm the deployed main Run and keyboard shortcut call `app.queuePrompt`. Record the installed frontend version and third-argument form. If this entry point is absent or bypassed, identify its supported cancellation boundary before proceeding; do not implement an API wrapper that pretends submission succeeded.
- [ ] Write regression tests using injected app/callback doubles: Ambient full Run resolves `false`, calls the chooser with the active graph, and never calls original queue/conversion/API; a normal workflow forwards the exact arguments and receiver and preserves the original result/error. Cover both object `queueNodeIds` and legacy array partial targets, auto-queue intent, and all three Ambient output classes.
- [ ] Run `node --test tests/test_queue_control.mjs`; confirm the new tests fail because interception is absent.
- [ ] Implement the helper and install it once from extension setup. Leave explicit partial execution on the original path. For Ambient auto-queue, return `false` and call the explanatory notice callback instead of the chooser.
- [ ] Keep `api.queuePrompt`'s two existing unsafe-prompt checks. Change its wrapper to forward trailing arguments to the captured original API function. Add a regression assertion that options such as `partialExecutionTargets` reach that function; mixed Render/Upscale and Prepare/generation prompts must still reject before network submission.
- [ ] Run `node --test tests/test_queue_control.mjs tests/test_stages.mjs`; expect every test to pass.

### Task 2: Connect the chooser to the existing stage controls and qualify the result

**Files:** Modify `comfy_nodes/ambient_loop/web/ambient_loop.js`, `tests/editor_harness.py`, `tests/test_queue_control.mjs`, `README.md`, `docs/qualification.md`, and the instruction text in `tools/build_motion_workflow.mjs`; regenerate `workflows/ambient-motion.json` for that instruction change only.

**Interfaces:** Implement `showStageChooser(graph): void` and `showAutoQueueNotice(graph): void` in the extension. Change `queue(stage, target, status): Promise<boolean>` to return `true` only for a confirmed successful submission, and `false` after displaying a caught error. Existing node buttons may ignore its return value. The chooser passes its own visible status element and an exact live target to this same function.

- [ ] Extend the fixture with main Run, repeated Run, auto-queue, and workflow-switch controls. Supply a realistic `app.queuePrompt` stub, count simulated API submissions, and allow a simulated queue rejection. Serve `queue_control.mjs` alongside the existing extension assets.
- [ ] Add regression checks around the real extension setup and stage callbacks. Load the extension in a Node fixture with its ComfyUI app/API imports replaced by controlled module stubs; stub only the DOM operations used by the chooser. Assert: Cancel/Escape send zero requests; a Prepare choice sends only editor/LoadImage; reviewed Render sends only its generation branch; unreviewed or changed settings send zero requests; Upscale sends only selector/upscale. Also cover one chooser on repeated Run, one submission on repeated action clicks, disabled missing/ambiguous targets, graph switching, target removal, and a rejected submission followed by a successful retry.
- [ ] Run `node --test tests/test_queue_control.mjs`; confirm chooser tests fail before its implementation.
- [ ] Build the chooser using the existing DOM helpers and an accessible dialog, with the exact copy and actions above. Focus its first enabled action; Escape/Cancel close it and restore focus. Capture the graph on opening, verify it and the target again on action, and close on successful submission. Keep errors in its visible status element and restore retry controls. Deduplicate auto-queue notices by active graph.
- [ ] Update README and the builder's workflow note to explain that main Run opens the chooser and that node stage buttons remain available. Regenerate workflow JSON and inspect the diff: only the instruction text should change.
- [ ] Run `node --test tests/test_queue_control.mjs tests/test_stages.mjs tests/test_motion_workflow.mjs tests/test_editor_geometry.mjs`; expect every test to pass. Run `python -m unittest tests.test_stages -v` to confirm the backend stage contract is preserved.
- [ ] Start `python tests/editor_harness.py` and verify the chooser visually: keyboard focus, Escape, disabled actions, pending state, error/retry state, node stage controls, and repeated Run. Record actual results in qualification notes.
- [ ] On the deployed ComfyUI frontend after loading the new extension, reproduce main Run and keyboard queue. Verify no **Prompt execution failed** popup for this stage-choice case and no `/prompt` request until a choice is made. Use manual Prepare to verify the actual selected payload; cancel Render/Upscale if a costly GPU run is not part of the authorized verification. Inspect the installed API signature and verify a normal workflow still queues normally.

## Acceptance and handoff

The reported main Run action opens the chooser without an execution-error popup. Cancel submits nothing; each valid stage choice submits exactly one isolated stage; point review remains enforced; ordinary workflows and existing stage buttons retain their queue behavior. Record fixture checks separately from deployed frontend checks. Planning is complete when this document is saved; the issue is fixed only after implementation and the checks above.

Recommended execution: implement inline with `superpowers:executing-plans`. The two tasks share one frontend queue boundary and do not require parallel agents.
