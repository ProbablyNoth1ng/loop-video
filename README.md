# Ambient Loop · ComfyUI anime loops

Load image → enter motion prompt → **Prepare points** → review/edit → **Render**
→ preview → optionally **Upscale** → save. Creative work stays inside ComfyUI.
The existing CLI remains compatible: see [legacy CLI](docs/legacy-cli.md).
The new animation path does not require producing or accepting Workflow A.

Import [ambient-motion.json](workflows/ambient-motion.json) after
[cloud installation](docs/cloud-setup.md).

RunPod can install all nodes, dependencies and model weights at first boot:
see [automatic installation](docs/runpod-autoinstall.md).

1. Load one anime image. Set the motion prompt and requested parts (`auto` by
   default, or a comma-separated list) in **Prepare and review**. Choose
   **local Qwen3.5**, **local Qwen** (Qwen3-VL), or **manual** preparation.
2. Click **Prepare points**. Local Qwen proposes normalized landmarks and
   unloads before generation. Failed analysis leaves the editor available with
   feedback; add points manually or retry.
   Analysis aims for 16–24 useful visible points, adapting to the image; hidden
   anatomy is omitted. Valid partial suggestions survive with omission feedback.
3. Review the numbered landmark list and labeled dots on the source image.
   Green points move; blue points anchor stationary parts; disabled points are gray.
   A row and its dot select the same point; disabled points appear muted. A
   manual or failed-Qwen Prepare shows an empty list with an Add point prompt.
   Move, add, delete or disable landmarks. Select a point and drag path handles;
   edit its label, body part, role, reason and strength. Scrub or play trajectories.
   New proposals use semantic roles: only motion requested by the prompt moves.
   Changing a role resets the path to stationary or gently returning motion.
   Legacy points retain their existing paths. Click **Accept
   point review** before rendering.
4. Click **Render** for the official LTX-2.5 single-stage Motion Track pipeline.
   Continuous and forward seam previews play automatically in **Render preview**. Change
   seed for another candidate. Image, prompt, timing, motion strength, canvas or
   point or analysis-setting changes invalidate review. After setting changes, Prepare again.
5. The last completed render is automatically selected in **Select saved candidate**.
   Choose another original render in its dropdown to preview it automatically.
   Optionally click **Upscale** for 1080p/1440p/4K (1440p remains the default).
   Resolutions use short sides of 1080/1440/2160, preserving orientation and
   aspect ratio with even dimensions. Finishing reads saved PNGs and
   keeps the same frame count, FPS and timing. Review for flicker and click
   **Save silent MP4**. Lossless frames remain beside the output.

Use **Run** to choose exactly one Ambient Loop stage: **Prepare points**,
**Render**, or **Upscale**. The chooser submits one stage and does not apply
Run's batch count. The node stage buttons remain available. Preparing points
cannot queue generation; Upscale has only the saved-candidate branch upstream.
Save the workflow after editing: plans live in its serialized editor widget and
metadata. Render records live in `ComfyUI/output/ambient-loop/`. Saved candidates
load automatically after reopening; **Refresh candidates** reloads the list.

Defaults: six seconds, 24 FPS, seed 42, generation short side near 720 pixels,
original aspect ratio, stationary camera intent. Canvases use recorded edge
padding to multiples of 64, keeping the half-resolution Motion Track IC-LoRA
guide aligned to multiples of 32; exports remove that padding. Generation produces
145 frames, measures endpoint closure and exports 144 playback frames.
Returning tracks do not guarantee a seamless loop. Inspect face identity,
hair motion, background drift and seams; retry poor candidates. No automatic
ping-pong playback is used.

After updating from a version that used 32-pixel canvas alignment, run
**Prepare points**, check the landmarks and trajectories, then click **Accept
point review** before **Render**. Previously reviewed plans with changed canvas
dimensions are rejected. Saved rendered candidates remain available through
**Select saved candidate**.

The [unchanged official workflow](workflows/ltx-2.5-motion-track.official.json)
is retained for qualification. The adapted graph replaces input preparation
and output persistence while retaining model loading, the single-stage sampler,
IC-LoRA conditioning and tiled decoding. Prompt enhancement is off. The official
pipeline still uses audio latents; Ambient Loop exports silent videos.

**Qualification is pending:** local tests cover motion transforms, review
invalidation, stage isolation, candidate reopening and frame-preserving
finishing. The local editor fixture exercises manual and Qwen sample landmarks.
Deployed ComfyUI conversion, cloud GPU rendering and the real anime pilot still
need verification. No supported GPU minimum or measured inference runtime is
claimed. See [qualification](docs/qualification.md).

```bash
python -m unittest discover -s tests -v
node --test tests/*.mjs
```

Sources: [LTX Motion Control](https://docs.ltx.io/open-source-model/feature-guides/structural-control/motion-control),
[Motion Track IC-LoRA model card](https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-Motion-Track-Control),
[Qwen3-VL](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct),
[Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B),
[Real-ESRGAN anime model](https://github.com/xinntao/Real-ESRGAN/blob/master/docs/anime_video_model.md).
