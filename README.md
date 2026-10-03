# Ambient Loop · ComfyUI anime loops

Load image → enter motion prompt → **Prepare points** → review/edit → **Render**
→ preview → optionally **Upscale** → save. Creative work stays inside ComfyUI.
The existing CLI remains compatible: see [legacy CLI](docs/legacy-cli.md).
The new animation path does not require producing or accepting Workflow A.

Import [ambient-motion.json](workflows/ambient-motion.json) after
[cloud installation](docs/cloud-setup.md).

1. Load one anime image. Set the motion prompt and requested landmark labels in
   **Prepare and review**. Choose **local Qwen** or **manual** preparation.
2. Click **Prepare points**. Local Qwen3-VL proposes normalized landmarks and
   unloads before generation. Failed analysis leaves the editor available with
   feedback; add points manually or retry.
3. Move, add, delete or disable landmarks. Select a point and drag path handles;
   edit its label/strength. Scrub or play trajectories. Roots, head and shoulders
   start stationary; other points get gentle returning paths. Click **Accept
   point review** before rendering.
4. Click **Render** for the official LTX-2.5 single-stage Motion Track pipeline.
   Review continuous and forward seam playback in **Render preview**. Change
   seed for another candidate. Image, prompt, timing, motion strength, canvas or
   point changes invalidate review. After motion-setting changes, Prepare again.
5. Refresh **Select saved candidate**, choose an original candidate and preview
   it. Optionally click **Upscale** for 1440p/4K. Finishing reads saved PNGs and
   keeps the same frame count, FPS and timing. Review for flicker and click
   **Save silent MP4**. Lossless frames remain beside the output.

Use the separate stage buttons. Global **Run** is rejected if it would mix
rendering with finishing. Preparing points cannot queue generation; Upscale has
only the saved-candidate branch upstream. Save the workflow after editing:
plans live in its serialized editor widget and metadata. Render records live in
`ComfyUI/output/ambient-loop/`. Refresh candidates after restarting ComfyUI.

Defaults: six seconds, 24 FPS, seed 42, generation short side near 720 pixels,
original aspect ratio, stationary camera intent. Canvases use recorded edge
padding to multiples of 32; exports remove that padding. Generation produces
145 frames, measures endpoint closure and exports 144 playback frames.
Returning tracks do not guarantee a seamless loop. Inspect face identity,
hair motion, background drift and seams; retry poor candidates. No automatic
ping-pong playback is used.

The [unchanged official workflow](workflows/ltx-2.5-motion-track.official.json)
is retained for qualification. The adapted graph replaces input preparation
and output persistence while retaining model loading, the single-stage sampler,
IC-LoRA conditioning and tiled decoding. Prompt enhancement is off. The official
pipeline still uses audio latents; Ambient Loop exports silent videos.

**Qualification is pending:** local tests cover motion transforms, review
invalidation, stage isolation, candidate reopening and frame-preserving
finishing. No cloud GPU baseline, deployed ComfyUI browser acceptance or real
anime visual pilot has been performed. No supported GPU minimum or measured
inference runtime is claimed. See [qualification](docs/qualification.md).

```bash
python -m unittest discover -s tests -v
node --test tests/test_stages.mjs tests/test_motion_workflow.mjs
```

Sources: [LTX Motion Control](https://docs.ltx.io/open-source-model/feature-guides/structural-control/motion-control),
[Qwen3-VL](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct),
[Real-ESRGAN anime model](https://github.com/xinntao/Real-ESRGAN/blob/master/docs/anime_video_model.md).
