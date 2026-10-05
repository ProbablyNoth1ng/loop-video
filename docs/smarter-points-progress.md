# Smarter character points and 1080p — implementation ledger

Source of intent: user-provided plan, 2026-10-05.

- [x] Semantic proposals, partial parsing, model dispatch and cleanup
- [x] Editable roles, dense point selection, saved workflow compatibility
- [x] Configurable model installation and 1080p finishing
- [x] Local verification and final review
- [ ] Affected-candidate investigation and deployed GPU qualification

Pre-flight: analyzer fields feed plan creation, validation and editor serialization;
analysis settings must be checked on both client and backend. Installer selection
must survive process re-execution and change the model cache identity. Resolution
options must retain 1440p as the existing default.

Ruling: implement in the supplied checkout — user requested implementation here,
and repository metadata is read-only in this sandbox. No branch/commit changes.

Ruling: preserve the list-returning parser/analyzer interface; accumulate partial
response feedback through an optional list parameter. Legacy landmark dictionaries
without semantic fields retain their trajectories and label-based initialization.

Initial evidence: 29 JavaScript tests passed. Python launcher cannot find its
runtime inside the sandbox; escalated suite launched. No affected LTX candidate
record exists locally; requested the current GPU endpoint and record path.

Implementation evidence:

- Semantic roles override label heuristics for new proposals; legacy plans retain
  their initialization and serialized schema. Partial responses keep valid points
  with skipped-point/missing-part/omission feedback.
- Both model families dispatch from local config. Transformers range is 5.2–5.x;
  Qwen3.5 thinking is disabled. Exception cause/context frames are cleared before
  model/input/output collection and CUDA cache cleanup.
- Editor supports editable roles/body parts/reasons, color-coded points, nearest
  point selection and compact numeric labels with the selected full label.
  Analysis/semantic edits stale review. Existing widget order and sockets persist.
- Installer selections survive re-execution and participate in cache identity.
  Legacy manifests migrate with pinned records; per-model manifests retain both
  snapshots and checksums. New workflows match the selected analyzer; saved ones
  are preserved.
- All six resolution/orientation combinations preserve candidate hashes, frame
  count, FPS and render settings; 1440p remains the default.

Ruling: short-side finishing preserves the saved candidate's aspect ratio. The
first 16:9 fixture used a 256-pixel short side and rounded to 456×256, so its
1924×1080 finish correctly followed that ratio. Use 512×288 for exact 16:9 checks;
do not force finishing to a different ratio than the saved frames.

Final verification, 2026-10-05:

- `python -m unittest discover -s tests`: 67 passed, no failures or skips.
- `node --test` on all six `tests/*.mjs` files: 32 passed.
- `git diff --check`: passed.
- Real local browser fixture: 20 synthetic points displayed moving/anchor colors;
  a selected anchor disabled path motion controls. Role/disabled state survived
  reopen. Browser QA found text edits did not commit under fill/blur; oninput
  persistence fixed it and the role reason then survived reopen. Numeric labels
  reduce crowding while the list and selected point show full labels.
- Fresh-context reviewer: no remaining Critical or Important findings after fixes
  for selected-model workflow defaults, legacy snapshot migration and chained
  exception cleanup. These fixes have regression tests.

Outstanding external verification: user confirmed the A40 pod was terminated.
No affected LTX raw/exported frames or guide exist locally. GPU workflow, real
landmark accuracy, actual VRAM recovery, first affected frame and artifact
improvement remain unverified. Detailed controlled-comparison steps are recorded
in `docs/qualification.md`; no acceptance claim for model/animation quality.
