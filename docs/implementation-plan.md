# ComfyUI anime loop implementation

The supplied ComfyUI-only design is the implementation brief. Preserve the CLI,
but make Load image → Prepare → review/edit → Render → preview → optional Upscale
the primary journey. No accepted Workflow A is needed.

1. Vendor the official LTX-2.5 single-stage motion-track workflow unchanged.
   Cloud qualification remains pending until an actual provider GPU is available.
   Record revisions, package freeze, model SHA256, canvas, peak VRAM and wall time.
2. Add `motion.py`: normalized MOTION_PLAN validation, image identity, review
   fingerprint, returning paths, and recorded aspect-preserving canvas transforms.
   Test portrait/landscape round trips, invalid suggestions and stale reviews first.
3. Add local Qwen analysis with strict JSON validation and unconditional model
   cleanup. Add an embedded ComfyUI editor; persist its plan in a serialized widget
   and workflow metadata. Manual preparation must work without model dependencies.
4. Add staged node interfaces and frontend queue pruning. Prepare targets only the
   editor, Render targets candidate persistence through official LTX generation,
   and Upscale targets only a selected disk record. Test dependency isolation.
5. Persist 145 lossless frames, measure closure, export 144 playback frames plus a
   forward seam preview. Save RENDER_HANDLE without tensors; reload after restart.
6. Finish saved frames in bounded chunks with realesr-animevideov3; retain frame
   count/FPS/timing, encode silent MP4 and preview before download.
7. Ship the adapted editable workflow and provider installation/storage guidance.
   Run unit/integration checks and explicitly separate local proof from pending
   GPU inference and real-anime visual qualification.

Defaults: 6 seconds, 24 FPS, seed 42, shorter side near 720 pixels, stationary
camera, original aspect ratio, optional 1440p/4K. Returning tracks are guidance,
not a seamless-loop guarantee. Never automatically ping-pong frames.
