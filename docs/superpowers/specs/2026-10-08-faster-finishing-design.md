# Faster finishing design

Date: 2026-10-08. Status: implemented in source; Python, installed ComfyUI, GPU performance and visual acceptance pending.
Product requirements: [P-01, P-06, P-09 and P-12](../../product-spec.md).
Plan: [faster finishing](../plans/2026-10-08-faster-finishing.md).

## Intent and scope

Finish the same saved Render candidate repeatedly at 1080p to compare elapsed time and visual quality. New editable workflows select Fast by default. Preserve old `ComfyLTXLoopUpscale` node behavior and saved workflow socket order. Do not change the official LTX generation graph, install a new model, or integrate paid Topaz nodes.

## Behavior and acceptance criteria

- Fast reads candidate PNGs and writes lossless target PNGs using FFmpeg Lanczos scaling, then the existing silent MP4/preview encoder. A standard 1280x720 candidate finishes at exactly 1920x1080.
- Balanced AI uses the installed `realesr-animevideov3` weights in FP16 only if Spandrel reports support; otherwise fail clearly. It starts at 512-pixel tiles, falls back to 256 then 128 on recognized GPU OOM, and retains the original x4 inference then target resize.
- Original AI retains today's FP32, 256-pixel tile path and 128-pixel OOM fallback. Old nodes keep 1440p as default.
- Every finish validates the disk handle and source hashes, writes a separate finish directory and method field, and preserves source bytes, frame count, FPS, target size, aspect/crop rule, silent MP4 and lossless frames. Failed runs never mark a record complete.
- The stage chooser allows either finishing node only when fed by `ComfyLTXLoopSavedCandidate`; Render and Prepare exclude both. Ambiguous graphs with two finishing nodes ask the user to choose one by removing or disabling a node.

## Architecture and contracts

`comfy_ltx_loop/candidates.py` dispatches `finish_candidate(..., method='original_ai')`. Fast scales the validated image sequence with an FFmpeg subprocess into the allocated finish frame directory. Balanced and Original share the frame loop; `anime_enhancer(precision='fp16'|'fp32')` selects model precision and tile policy. `comfy_ltx_loop/staged_comfy.py` registers `ComfyLTXLoopFinish` with candidate, resolution, method and chunk size inputs; `ComfyLTXLoopUpscale` remains registered with the same inputs and calls the default Original AI path. Frontend stage pruning and queue guards recognize both classes. The workflow builder emits `ComfyLTXLoopFinish` connected only to the saved selector.

## Library research

Lookup date: 2026-10-08. Repository pins: Python >=3.11, NumPy 2.2.6, Pillow 11.3.0; Spandrel and FFmpeg are installed by the cloud installer without a repository version pin. Context7 IDs: `/websites/ffmpeg_documentation` (current documentation) and `/chainner-org/spandrel` (current library documentation). [FFmpeg image sequence and scaler docs](https://ffmpeg.org/ffmpeg-all.html) document numbered-image input, `-framerate`, and Lanczos scaling. [Spandrel documentation](https://github.com/chaiNNer-org/spandrel) documents `supports_half` and `model.half()`; the model must report support before conversion. Compatibility decision: reuse the installed binaries and weights, with no dependency upgrade. Installed GPU/weight compatibility remains unverified.

## Test strategy

Python candidate tests cover Fast frame pixels/dimensions, timing, count, source hashes, method records, old-node compatibility, and FP16 unsupported/OOM fallback behavior. Node tests cover new workflow wiring and isolated stage selection including both node types. Real FFmpeg/ffprobe test checks Fast MP4 dimensions, count, FPS and silence. Local tests cannot prove GPU runtime, FP16 model compatibility or anime quality.

## Delivery and evidence

The generated editable workflow defaults to Fast/1080p. The existing `ComfyLTXLoopUpscale` inputs/defaults remain in source. Node's 37 tests pass, including stage isolation, workflow wiring and preview method display. A local FFmpeg 9.0 probe cropped two 1290x720 frames to 16:9 and wrote numbered 1920x1080 PNGs; its silent MP4 probe reported one video stream, two frames at 8 FPS and 1920x1080. The official LTX graph has no diff. The [plan](../plans/2026-10-08-faster-finishing.md) records the red/green and blocked checks; [qualification](../../qualification.md) tracks external acceptance. This Windows environment has no Python runtime, and its network cannot download one, so the Python integration path remains unverified here. No saved LTX candidate or local GPU is available for timing and visual comparison.
