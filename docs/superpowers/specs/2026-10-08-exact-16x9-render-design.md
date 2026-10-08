# Exact 16:9 render design

Date: 2026-10-08. Status: implemented locally; GPU and visual qualification pending.
Product requirements: [P-01 and P-11](../../product-spec.md).

## Intent and scope

Correct dimensions caused by slightly-wide sources after generation-canvas padding is removed. If a source long-to-short ratio is within 2% of 16:9, output has exact 16:9 landscape or 9:16 portrait dimensions. The crop is centered and applies only to exported candidate frames and newly written finish frames. Raw generated images and the reviewed canvas/plan are not changed. All other source ratios keep the current even-dimension aspect-ratio behavior.

## Behavior and acceptance criteria

- A 1290x720 near-16:9 export saves 1280x720 frames and metadata; its 1080p, 1440p and 4K finishes save 1920x1080, 2560x1440 and 3840x2160.
- Portrait uses the corresponding 9:16 dimensions. A true 16:9 source stays exact; a ratio outside the inclusive 2% tolerance remains uncropped.
- Existing 1290x720 candidate records are readable and produce corrected new finish records without rerendering or modifying original records, raw frames or frames.
- Frame count, FPS, silence, preview encoding and stage isolation are unchanged.

## Architecture and contracts

`ambient_loop.candidates` owns `output_size` and exported frame persistence. `save_candidate` crops its post-padding content image before writing `frames/` and records that exact size. `finish_candidate` normalizes a loaded candidate frame to the same exact-aspect target before calling the enhancer, so legacy saved candidates are corrected only in the new finish output. The crop keeps its centered axis and uses only integral, even output sizes.

## Library research

Lookup date: 2026-10-08. Project pin: Pillow 11.3.0 (`pyproject.toml`). Context7 selected high-reputation `/python-pillow/pillow`; its crop documentation defines `(left, upper, right, lower)` pixel boxes, and resize supports `Image.Resampling.LANCZOS`. Source: [Pillow tutorial](https://github.com/python-pillow/pillow/blob/main/docs/handbook/tutorial.rst). Compatibility decision: retain the existing `Image.crop(...).resize(..., Image.Resampling.LANCZOS)` approach; no dependency or node-interface change.

## Test strategy

`tests/test_candidates.py` asserts post-padding pixel crops, output metadata and legacy saved-candidate finishes. Cases cover landscape/portrait, exact 16:9, outside-tolerance preservation and every finish preset; tests also assert original record/raw/frame bytes stay unchanged. FFmpeg-enabled checks probe generated MP4 dimensions. Local tests cannot qualify ComfyUI conversion, GPU inference or visual anime quality.

## Delivery and evidence

Plan: [exact 16:9 render plan](../plans/2026-10-08-exact-16x9-render.md). The focused red run showed 1290x720 export, 1936x1080 legacy finish and 720x1290 portrait failures. After implementation, the focused candidate suite passed 8 tests; the Python suite passed 83 tests and Node suite passed 35 tests. FFmpeg/ffprobe confirmed a 1280x720 render and a 1920x1080 finish, each 8 FPS/8 frames. GPU and visual checks remain pending in [qualification](../../qualification.md).
