# One anime still → a seamless ambient loop

Technical research and implementation blueprint · **26 September 2026** · USD prices

**Decision:** use deterministic, masked deformation and procedural compositing as the production foundation. Use LTX-2.5 **Motion Track as an optional regional motion-proposal tool**, not the main renderer. Whole-image Motion Track generation is a poor fit when preserving the finished drawing takes priority over generating new motion. The strongest preservation control is retaining the original pixels outside deliberately animated regions.

Workflows A/B/C below are implementation specifications, not runnable graphs. No source image, GPU run, or installed ComfyUI was available. Compatibility was checked against official documentation, model cards, workflow graphs, and node source; anime quality, acceptance rates, VRAM peaks, and clip runtimes were **not personally benchmarked**. Budget ranges explicitly use assumptions where comparable measurements are missing.

The request refers to 24 topics without supplying a numbered list. Sections 1–24 map its stated requirements into 24 topics; the three workflows and the cheapest-method answer follow them.

## 1. Objective, acceptance, and limits

Produce a subtle 4–10 second, locked-camera loop of a finished anime image. Optimize lexicographically: artwork preservation → natural continuity → repeatability → GPU cost. A cheaper candidate that changes the face loses to a more expensive candidate that preserves it. A perfect seam with unnatural reversing rain also fails.

Default deliverable: silent, constant-frame-rate video plus a lossless frame master and a manifest. Preserve the source composition and aspect ratio. Offer 1440p and 4K export; these are output raster sizes, not claims that the input contains native 4K detail. Six seconds at 24 FPS is the default; 48 FPS is optional.

“Any character” means the process can accept any finished drawing. It does **not** mean every drawing can support convincing hair, cloth, water, or facial motion from one view. Occluded surfaces are unknown. When safe deformation is impossible, animate an appropriate light or weather layer, or retain a nearly still result. Never invent conspicuous motion simply to demonstrate animation.

## 2. Evidence standard and dated compatibility audit

Use four labels throughout implementation:

| Label | Meaning |
|---|---|
| **Documented** | Official workflow/card specifies the pairing or behavior. This establishes support, not anime quality. |
| **Code-confirmed** | The inspected implementation implements the stated interface or operation. No inference quality guarantee follows. |
| **Design** | A proposed setting, equation, threshold, or module for this task; requires validation. |
| **Experimental** | An unverified combination or behavior; excluded from the default production route. |

GitHub revisions retrieved during this audit:

| Repository | Revision |
|---|---|
| [ComfyUI](https://github.com/Comfy-Org/ComfyUI/tree/79be670e2d9be63e238785af307369d2b9039ed1) | `79be670e2d9be63e238785af307369d2b9039ed1` |
| [ComfyUI-LTXVideo](https://github.com/Lightricks/ComfyUI-LTXVideo/tree/61ee82b23b18b6d7665c665bef47dbc270215f7d) | `61ee82b23b18b6d7665c665bef47dbc270215f7d` |
| [workflow_templates](https://github.com/Comfy-Org/workflow_templates/tree/25ff90a51cc8f6ee56bd78ec3b11f294925fb36d) | `25ff90a51cc8f6ee56bd78ec3b11f294925fb36d` |
| [ComfyUI-Majoor-ImageOps](https://github.com/MajoorWaldi/ComfyUI-Majoor-ImageOps/tree/bf499d46247d6191c902b8240cadee40c5b7171c) | `bf499d46247d6191c902b8240cadee40c5b7171c` |
| [ComfyUI-Frame-Interpolation](https://github.com/Fannovel16/ComfyUI-Frame-Interpolation/tree/26545cc2dd95bc3d27f056016300673bdeee78f5) | `26545cc2dd95bc3d27f056016300673bdeee78f5` |
| [ComfyUI-VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite/tree/4d907bee61e92c2e65af3bd6383a4e4d356126d1) | `4d907bee61e92c2e65af3bd6383a4e4d356126d1` |

These are research reference pins, **not an installed-and-tested dependency lock**. Source reads and revision queries were separate requests, so installation must fetch these pins and compare the relevant schemas again. Record model repository revision, file size, and SHA-256 after authorized downloads; filenames alone do not prove identical weights. No weights were downloaded here. Official LTX guidance requires recording workflow revisions and matching assets before modifications. [Compatibility guide](https://docs.ltx.io/open-source-model/reference/workflow-asset-compatibility).

## 3. Three architectures compared for this task

The following ranking is an engineering inference from how the architectures operate, not a measured anime leaderboard.

| Architecture | Preservation | Motion control | Loop continuity | Repeatability | Cost and recommendation |
|---|---|---|---|---|---|
| Controlled image warp + compositing | Exact source outside changed support; interpolation resamples moving pixels | Explicit displacement, roots, masks, opacity, depth order | Analytically periodic position and velocity | Strong with fixed assets and equations | Lowest GPU demand; default A |
| LTX-2.5 guided whole-frame generation | Latent reconstruction and generated details can alter linework | Learned response to image, prompt, endpoints, tracks | Endpoint guidance helps position; no certified cyclic dynamics | Seeds reproduce only within a pinned environment | More retries; evaluate, do not default |
| Hybrid | Source retained outside approved animated support | Deterministic motion plus a small generated patch | Deterministic layers close exactly; generated patch must independently pass seam QC | Strong base; variable regional acceptance | Preferred B/C when deformation alone is inadequate |

LTX’s documented tracks guide sparse object motion; its inpainting workflow supplies a separate video-and-mask editing route. Neither description establishes near-pixel-level preservation of a complete anime drawing. [Motion guide](https://docs.ltx.io/open-source-model/feature-guides/structural-control/motion-control), [inpainting guide](https://docs.ltx.io/open-source-model/feature-guides/editing-effects/in-outpainting).

## 4. LTX-2.5 compatibility matrix

**Status checked 26 September 2026.** Use the named starting graph, not an improvised mixture of similarly named controls.

| Capability or combination | Official starting point / evidence | Status and production policy |
|---|---|---|
| Ordinary first-image I2V | `video_ltx2_5_i2v`; `LTX-2.5_T2V_I2V_Two_Stage_Distilled.json` | Documented; two stages |
| Single-stage I2V preview | `LTX-2.5_T2V_I2V_Single_Stage_Distilled.json` | Documented; no spatial refinement |
| First + last image | `video_ltx2_5_flf2v.json` | Documented; single stage; B’s regional candidate route |
| Sparse Motion Track | `LTX-2.5_ICLoRA_Motion_Track_Distilled.json` | Documented; single stage; optional side branch |
| Motion adapter named 2.3 with base 2.5 | `ltx-2.3-22b-ic-lora-motion-track-control-ref0.5.safetensors` in the 2.5 graph | Explicitly documented reuse; a specific exception to version isolation |
| In/outpaint adapter named 2.3 with base 2.5 | `ltx-2.3-22b-ic-lora-in-outpainting-0.9.safetensors` in the 2.5 inpaint graph | Explicitly documented reuse; C’s regional editing route |
| Ordinary two-stage latent upscale | 2.5 I2V two-stage graph + 2.5 latent spatial upscaler | Documented; 8 + 3 steps |
| Inpaint two-stage refinement | 2.5 inpaint graph | Documented; different pixel decode/blend/re-encode path, 8 + 2 steps |
| INT8 ConvRot transformer + INT8 ConvRot encoder + Conv VAE | Lower-VRAM configuration in compatibility guide | Documented ComfyUI configuration |
| INT8 ConvRot + DiffVAE in FLF | Current native FLF template | Documented; retain its loaders; B final candidate |
| Quantized transformer + Motion Track / inpaint adapter | Not established by the inspected BF16 task graphs | Experimental here; B uses no IC-LoRA; C and track test use BF16 |
| Motion Track + identical first/last conditioning | No inspected official combined graph | Experimental; not used in A/B/C |
| Motion Track + ordinary latent upscale/refine | Official track graph is single-stage | Experimental; do not append the ordinary second stage and claim support |
| Motion Track + Cinemagraph / slow-motion / union adapters | No verified stacked recipe | Experimental; evaluate separately |
| Native DFR / temporal upscalers / pixel-upscale adapters grafted into track graph | Separate pipelines and assets | Experimental for this blueprint; not needed for 4K export |

The index establishes graph families; the compatibility guide distinguishes native first/last from two-stage I2V. The task guides explicitly establish the two 2.3 adapter exceptions. [Workflow index](https://github.com/Lightricks/ComfyUI-LTXVideo/blob/61ee82b23b18b6d7665c665bef47dbc270215f7d/example_workflows/2.5/README.md), [compatibility](https://docs.ltx.io/open-source-model/reference/workflow-asset-compatibility), [Motion Track](https://docs.ltx.io/open-source-model/feature-guides/structural-control/motion-control), [in/outpainting](https://docs.ltx.io/open-source-model/feature-guides/editing-effects/in-outpainting).

## 5. Exact LTX assets, quantization, decoding, and memory

Obtain base components from [Lightricks/LTX-2.5](https://huggingface.co/Lightricks/LTX-2.5). Folder names below are under `ComfyUI/models/`.

| File | Folder | Use |
|---|---|---|
| `ltx-2.5-22b-distilled-transformer-bf16.safetensors` | `diffusion_models` | C and BF16 track evaluation |
| `ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors` | `diffusion_models` | B |
| `gemma4-12b-with-proj-ltx-2.5-bf16.safetensors` | `text_encoders` | C / track |
| `gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors` | `text_encoders` | B |
| `ltx-2.5-video-vae-conv-bf16.safetensors` | `vae` | B preview; faster/lighter decode choice |
| `ltx-2.5-video-vae-bf16.safetensors` | `vae` | B final / C; diffusion decoder |
| `ltx-2.5-audio-vae-bf16.safetensors` | `vae` | Keep in official AV graphs even for silent exports |
| `ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors` | `latent_upscale_models` | Ordinary I2V two-stage comparison; retain C graph’s declared asset pending wiring audit |

The card identifies the distilled fixed eight-step recipe and Comfy-only ConvRot weights. It also lists `ltx-2.5-22b-distilled-transformer-nvfp4.safetensors`, with a Blackwell/kernel-specific native route. NVFP4 is an evaluation option, not the default: its quality and adapter support are not validated here. Do not substitute arbitrary FP8/GGUF assets or an LTX-2.3 text encoder. [Base model card](https://huggingface.co/Lightricks/LTX-2.5).

Disable local prompt enhancement and use the supplied prompt directly. Thus `gemma4_e2b_it_bf16.safetensors` / `gemma4_e2b_it_int8_convrot.safetensors` are not required by the proposed branches when enhancement is fully bypassed. Keep local text encoding; hosted encoding would add a separate API cost and dependency. [Comfy LTX tutorial](https://docs.comfy.org/tutorials/video/ltx/ltx-2-5).

**VRAM planning, not measurements:** A: roughly 1–4 GB for small frame chunks. B: budget 32–48 GB for regional INT8 generation; provision 48 GB first. C: budget 80–120 GB for tiled BF16 regional work; provision 141 GB for initial validation. Offload text encoding before sampling; allocate 64–128 GB system RAM for B, 128 GB+ for C, with fast SSD. A 22B BF16 transformer alone is approximately `22×10^9×2 ≈ 44 GB` of parameters before overhead; quantizing weights does not eliminate activation, guide, audio, or decoder memory.

Official LTX requirements list 32 GB+ minimum and A100/H100 recommended. Those are broad platform recommendations, not measured peaks for these graphs. A separate vLLM implementation reports about 114 GB for canonical 1920×1088 two-stage generation; this is **not** a ComfyUI VRAM figure. It illustrates why runtime/topology-specific measurements are necessary. [LTX system requirements](https://docs.ltx.io/open-source-model/getting-started/system-requirements), [vLLM recipe](https://github.com/vllm-project/vllm-omni/blob/main/recipes/LTX/LTX-2.5.md).

## 6. First/last conditioning: useful, but not a loop guarantee

The current FLF template uses `LTXVAddGuide` at frame indices `0` and `-1`, each with shipped strength `0.7`, followed by guide cropping and decode. It has an eight-step schedule and no ordinary two-stage upscaler. B supplies the **same regional reference** at both endpoints. [Official FLF graph](https://github.com/Comfy-Org/workflow_templates/blob/25ff90a51cc8f6ee56bd78ec3b11f294925fb36d/templates/video_ltx2_5_flf2v.json).

Design settings: start with `0.7` unchanged; evaluate `1.0` endpoint strength only as a separate parameter variant. Stronger latent conditioning does not establish exact decoded endpoint pixels. The code represents guides and image conditioning in latent space. A face should still be restored from the source during final compositing. [Core LTX nodes](https://github.com/Comfy-Org/ComfyUI/blob/79be670e2d9be63e238785af307369d2b9039ed1/comfy_extras/nodes_lt.py).

Endpoints constrain position/appearance. They do not specify endpoint derivatives, acceleration, or the internal motion path. A clip can return to the same image while arriving too fast and leaving too slowly. Removing a duplicate last frame is valid **after** boundary QC, not a repair for a mismatching last frame.

## 7. Sparse Track implementation: what is actually encoded

Code-confirmed interface and behavior:

| Detail | Result |
|---|---|
| Track payload | A JSON string containing lists of `{x,y}` points; order within each list is time |
| Coordinates | Pixel positions in the renderer’s width/height canvas; no normalized-coordinate conversion in the renderer |
| Editor | `points_store`, `coordinates`, `points_to_sample`; stored control points take precedence |
| Interpolation | One point repeats; two points interpolate linearly; longer splines use Catmull–Rom with duplicated endpoint controls and rounded coordinates |
| Renderer | `LTXVDrawTracks(tracks,width,height)` emits IMAGE frames; length is the longest track |
| Guide appearance | Circles with age-dependent size/color, backward trail up to 50 frame intervals; high-resolution rasterization, bilinear reduction, RGB-to-BGR swap |
| Missing samples | Shorter tracks cease being current; earlier visible samples can remain in the trail |

This is a colored trajectory-video representation. It contains no semantic part names, mesh, depth, rigid-body constraints, physical force, or face-lock flag. The current renderer does not overlay the artwork itself into its black-background output. The opening still is conditioned separately. [Inspected sparse_tracks.py](https://github.com/Lightricks/ComfyUI-LTXVideo/blob/61ee82b23b18b6d7665c665bef47dbc270215f7d/sparse_tracks.py).

## 8. Programmatic injection and coordinate handling

Implementation design:

1. Record one affine transform from original pixels to model canvas: scale, pad offsets, and regional crop origin. Use it for the reference, all masks, and all tracks.
2. Store authoring points normalized to the **original** image for portability; convert to canvas pixels before submission. Do not send normalized coordinates directly to `LTXVDrawTracks`.
3. Produce equal-length arrays, one point per generated frame, including the endpoint when evaluating a cyclic proposal.
4. Inject the serialized arrays directly into `LTXVDrawTracks.tracks`, replacing the editor link in the future API graph. Alternatively clear `points_store` and replace `coordinates`; otherwise the editor can recompute and overwrite the desired samples.
5. Set draw width/height to the exact canvas, not a browser preview’s dimensions. Save the rendered guide for inspection before generation.

The official Motion Track graph connects the editor, renderer, `LTXICLoRALoaderModelOnly`, and `LTXAddVideoICLoRAGuide`; it crops guide latents before decoding. The loader supplies the adapter’s reference scaling. [Motion graph](https://github.com/Lightricks/ComfyUI-LTXVideo/blob/61ee82b23b18b6d7665c665bef47dbc270215f7d/example_workflows/2.5/LTX-2.5_ICLoRA_Motion_Track_Distilled.json).

The `ref0.5` adapter card specifies a half-resolution reference, downscale factor 2. Preserve that loader-to-guide connection; do not independently halve coordinates or hard-code a second reduction. Inspect the resulting guide and latent dimensions. [Motion adapter card](https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-Motion-Track-Control).

## 9. What tracks may make the model obey

Documented intent is directing object/region motion. The proprietary training data and the card do not provide an anime-specific quantitative error bound, stationary-anchor guarantee, or pixel-preservation guarantee. [Motion adapter card](https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-Motion-Track-Control).

**Hypotheses requiring tests:** stationary tracks at hair roots, shoulders, and background corners may discourage drift; a cyclic tip trajectory may encourage returning hair motion; sparse nonconflicting points may outperform dense anchors. None is a hard lock. Do not treat a stationary dot as equivalent to copying the source pixels.

Likely anime failure modes to evaluate: eye/iris changes, altered face outline, line thickness fluctuation, hair strands merging, cel shading turning into textured shading, a moving point interpreted as an entire head, track leakage into the background, and unrequested camera movement. Tiny amplitudes may also be ignored or exaggerated.

An additional **code-derived limitation**: the renderer starts with a short history and accumulates trails. Even when coordinates return to their start, the first and last guide frames need not have identical history. A cyclic coordinate list therefore does not itself create a cyclic rendered conditioning signal. A warm-up or circular-history renderer would change the recipe and is experimental.

## 10. Loop closure must cover position and motion

Let the continuous scene state be `S(t)` with period `T`. Target:

`S(0)=S(T)` and `dS/dt(0)=dS/dt(T)`; preferably matched acceleration too.

Render unique samples `t=jT/N`, `j=0…N−1`. The conceptual endpoint at `T` equals frame zero but is not exported twice. The final stored frame should ordinarily differ slightly from frame zero: it is one time step earlier.

| Method | Position continuity | Motion continuity | Decision |
|---|---|---|---|
| Periodic analytic deformation | Guaranteed by chosen equations | Guaranteed by smooth periodic derivatives | Preferred for reversible hair/cloth/grass motion |
| Periodic procedural field/particle system | Guaranteed if all random state and wrap rules are periodic | Can preserve one-way velocities | Preferred for rain, sparkle, haze |
| Same-image FLF diffusion | Encouraged, not exact | Unconstrained | Accept only after measured boundary QC |
| Select an already matching interior cycle | Measured, not guaranteed | Requires velocity matching too | Allowed; duration must remain 4–10 s |
| Ping-pong | Usually matching positions at reversals | Velocity changes sign unless re-timed to zero | Only explicitly reversible motions; reject for rain/flow/smoke transport |
| End-to-start crossfade | Mixes endpoints | Ghosts or simultaneous incompatible motion | Not a default loop solution; reject if it merely hides a jump |
| Frame duplication / freeze at boundary | Endpoint can match | Produces a pause | Reject |
| Optical-flow bridge | Can interpolate position | Can bend shapes or invent velocity | Experimental; not a guaranteed repair |

The continuity assessment above follows from the temporal construction, not vendor performance claims.

## 11. Current Wan and other credible alternatives

This is a **desk comparison plus a specified test protocol**, not completed visual testing.

| Candidate | Verified capability / memory evidence | Preservation, control, loop, and cost assessment for this use |
|---|---|---|
| Wan2.2 TI2V-5B | Native I2V/T2V; Comfy docs describe 8 GB with offloading | Lower-memory diffusion baseline; no endpoint/velocity contract in ordinary I2V; artwork still regenerated |
| Wan2.2 I2V-A14B / FLF2V | Separate high/low-noise experts; native Comfy first/last node | Strong comparator for a regional FLF branch; endpoints do not fix seam velocity; large weights/offload costs |
| Wan2.7 hosted I2V | Current official guide supports first image, first+last, continuation | Include as current paid comparator; hosted recipe does not expose the local latent/track/mask controls required here |
| Wan2.6 I2V Flash | Hosted silent and audio variants | Potentially inexpensive regional comparator; ordinary first-frame route provides weaker closure control |
| HunyuanVideo-1.5 480p step-distilled I2V | 8.3B; official minimum 14 GB with offload; 8/12-step option | Credible economical generator; no verified equivalent sparse-track + cyclic recipe here |
| AnimateDiff + anime SD1.5 | Motion modules and SparseCtrl; anime community checkpoint ecosystem | Worth a legacy comparison, but matching model style matters and official limitations include flicker; arbitrary finished artwork remains at risk |
| LTX-2.5 Cinemagraph LoRA | Task-specific selective-motion adapter | More relevant than a generic ranking, but not evidence of exact isolation or endpoint derivatives; evaluate separately |

Sources: [Wan Comfy tutorial](https://docs.comfy.org/tutorials/video/wan/wan2_2), [Wan2.2 repository](https://github.com/Wan-Video/Wan2.2), [current Wan I2V guide](https://www.alibabacloud.com/help/en/model-studio/wan-image-to-video-guide), [Wan2.6 Flash card](https://www.alibabacloud.com/help/en/model-studio/wan2-6-i2v-flash), [Hunyuan repository](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5), [AnimateDiff](https://github.com/guoyww/AnimateDiff), [Cinemagraph card](https://huggingface.co/Lightricks/LTX-2.5-22b-LoRA-Cinemagraph).

For reproducible Wan comparisons use:

- 5B: `wan2.2_ti2v_5B_fp16.safetensors`, `wan2.2_vae.safetensors`, `umt5_xxl_fp8_e4m3fn_scaled.safetensors`; core `Wan22ImageToVideoLatent`. Start from `video_wan2_2_5B_ti2v.json`.
- 14B FLF: `wan2.2_i2v_high_noise_14B_fp16.safetensors`, `wan2.2_i2v_low_noise_14B_fp16.safetensors`, `wan_2.1_vae.safetensors`, same UMT5 encoder; core `WanFirstLastFrameToVideo`. Start from `video_wan2_2_14B_flf2v.json`.

Use the graphs’ actual samplers and expert switch, not a generic Wan preset. The tutorial’s 14B I2V step list names T2V files despite listing I2V downloads: resolve that inconsistency from the graph and file metadata. Do not substitute the T2V checkpoints for I2V. [5B graph](https://github.com/Comfy-Org/workflow_templates/blob/25ff90a51cc8f6ee56bd78ec3b11f294925fb36d/templates/video_wan2_2_5B_ti2v.json), [14B FLF graph](https://github.com/Comfy-Org/workflow_templates/blob/25ff90a51cc8f6ee56bd78ec3b11f294925fb36d/templates/video_wan2_2_14B_flf2v.json).

Cinemagraph’s exact asset is `ltx-2.5-22b-lora-cinemagraph-0.9.safetensors`, with trigger `CINEMAGRAPH_MOTION`, documented Comfy I2V use, and initial strength 1.0. Its card also gives 30 steps / CFG 4 from training validation, which differs from the distilled eight-step recipe. Treat those as separate evaluation recipes; do not change the distilled sampler to 30 steps by assumption. Its face-freeze claims remain learned behavior. [Cinemagraph card](https://huggingface.co/Lightricks/LTX-2.5-22b-LoRA-Cinemagraph).

No community anecdotes are used as quantitative evidence. Future issue/Discord claims must be labeled **anecdotal**, with hardware, versions, and reproducibility status. Generic video benchmark rankings cannot substitute for the preservation and boundary tests in section 24.

## 12. Rental prices, runtime evidence, and accepted-loop arithmetic

### Prices observed 26 September 2026

Runpod’s public price page is dated 13 September 2026. Listed Pod rates: RTX A5000 24 GB **$0.27/h**, RTX 4090 24 GB **$0.74/h**, RTX 5090 32 GB **$0.99/h**, L40S 48 GB **$1.09/h**, A100 PCIe 80 GB **$1.59/h**, H100 PCIe 80 GB **$2.89/h**, H200 141 GB **$4.59/h**. Network storage under 1 TB is **$0.07/GB/month**. These are page-listed rates, not a verified reservable quote in a specific region/cloud toggle. Confirm availability, RAM, and checkout rate. [Runpod pricing](https://www.runpod.io/pricing).

Vast is a market with changing host prices. Its fetched public page did not expose a usable current GPU quote, so this report does not invent a Vast rate. Compare verified host offers including storage, transfers, reliability, and download speed at booking time. [Vast pricing](https://vast.ai/pricing).

### Published runtime anchors — not interchangeable

| Source | Published measurement/claim | How it can be used |
|---|---|---|
| HunyuanVideo-1.5 maintainers | 480p step-distilled I2V within 75 s on RTX 4090; 8/12-step option | Evidence that economical I2V is plausible; timing recipe is insufficiently matched to these loops |
| Wan2.2 maintainers | TI2V-5B 5 s 720p in under 9 min on a consumer GPU without specific optimization | Broad runtime bound in a different implementation; not a Comfy 4090 measurement |
| vLLM-Omni maintainers | 768×512, 17-frame Full/SFT T2V on Intel Arc Pro B70: 163 s, 16.3 GiB | Explicitly different hardware/task; do not use to price LTX anime I2V |
| This report’s A/B/C | No execution | All times below are scenario inputs, not benchmarks |

Sources: [Hunyuan](https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5), [Wan](https://github.com/Wan-Video/Wan2.2), [vLLM recipe](https://github.com/vllm-project/vllm-omni/blob/main/recipes/LTX/LTX-2.5.md).

For scale only, reproducing a 75-second run on a $0.74/h 4090 costs `0.74×75/3600 ≈ $0.015` for that run. This does not include startup, retries, finishing, or acceptance. A 9-minute run at that rate would cost `$0.111`; the Wan source does not establish that exact rental pairing. These arithmetic examples are **not accepted-loop quotes**.

### General cost model

Track separately: billed startup/model loading, preview generation, rejected full candidates, decode, QC, interpolation, upscale, composite, encoding, transfers, and storage. CPU work counts as GPU rental time while the instance remains running.

For a cohort with at most `R` candidate attempts, assumed per-attempt success `p`, and constant attempt cost:

`q = 1−(1−p)^R` (probability an image yields an accepted candidate)

`E[attempts] = q/p`

`Caccepted = r/60 × [(S/K + Gfixed)/q + Tattempt/p + Tfinish] + Cstorage/q + Ctransfer/q`

Here times are minutes; `r` is hourly rent; `S` is billed startup for a batch of `K` images; `Gfixed` is per-image preparation/QC time on the instance; `Tattempt` includes a preview, generation, decode, and attempt QC; `Tfinish` runs only for accepted candidates. Allocate failed images’ costs to accepted outputs. Equal independent `p` is a sensitivity assumption: real retries are correlated and preview/final success differs. Record those stages separately in the pilot. Do not keep paying until a nominal `1/p` is achieved on one hopeless image.

### Transparent planning scenarios for 1440p export

Assume ten images per warm batch, startup `S=3–10 min`, `Gfixed=0` because masks/plans are prepared locally, three attempts maximum. Assume `pA=0.9`, `pB=pC=0.5` **only for budgeting**, never as claimed quality. Thus `qA=.999`, `qB=qC=.875`.

| Tier | Instance / rate | Attempt time: preview + render/generate + decode + QC | Accepted finishing: interpolation/upscale/composite/encode | Cached storage for one day / 10 outputs | Illustrative cost per accepted loop |
|---|---|---|---|---|---|
| A | A5000 / $0.27/h | 0.5–2 min | 1–4 min | 5 GB: `5×.07/30/10=$.00117` | Roughly **$0.01–0.04** |
| B | L40S / $1.09/h | 3–12 min | 1–4 min | 100 GB: `100×.07/30/10=$.02333` | Roughly **$0.15–0.60** |
| C | H200 / $4.59/h | 8–30 min | 2–8 min | 200 GB: `200×.07/30/10=$.04667` | Roughly **$1.5–5.5** |

Full arithmetic, before rounding:

- A: `.27/60 × [(.3–1)/.999 + (.5–2)/.9 + (1–4)] + .00117/.999 ≈ $.0095–.0337`.
- B: `1.09/60 × [(.3–1)/.875 + (3–12)/.5 + (1–4)] + .02333/.875 ≈ $.160–.556`.
- C: `4.59/60 × [(.3–1)/.875 + (8–30)/.5 + (2–8)] + .04667/.875 ≈ $1.46–5.34`.

These wide ranges are **what-if calculations**, not empirical estimates reliable enough for purchasing decisions. Rental rates are sourced; runtimes and acceptance inputs are design assumptions. Each tier runs sequential stages on the same chosen instance. Storage allocation assumes retained cache billed for one day; a month of idle cache costs 30× that line. Change the actual retention and number of accepted outputs.

For 4K, initially budget extra finishing time of A 1–3 min, B 0.5–3 min, C 1–5 min: incremental rents approximately A $0.005–.014, B $.009–.055, C $.077–.383. These increments also require measurement. A CPU/local renderer can avoid GPU rent entirely; electricity, equipment, and human time remain.

One-off startup (`K=1`) adds roughly A $.01–.04, B $.06–.19, C $.24–.79 relative to that batched scenario. Cold model downloads, installs, or compilation are additional: measure billed minutes; `extra cost = r×extra minutes/60`, allocated across accepted outputs. Add actual transfer fees; no transfer quote was obtained. Preview only at reduced resolution, retain the full temporal duration for final-candidate testing, and avoid compilation in a short one-off session.

If diffusion `p` falls from .5 to .25, attempt cost doubles and `q` falls to .578; fixed costs per accepted diffusion output rise too. A bounded fallback to A may be cheaper and more reliable than more seeds. When every source gets an A fallback, account for rejected B/C work as sunk cost **plus** the fallback cost; do not count the fallback as a diffusion success.

Hosted comparison: Singapore Wan2.7 I2V lists $.10/s at 720p and $.15/s at 1080p; Wan2.6 Flash silent lists $.025/s and $.0375/s. Six generated seconds therefore cost $.60/$.90 for 2.7 or $.15/$.225 for silent Flash **per successfully generated attempt**, before visual rejection and local finishing. At assumed visual acceptance .5 those generation costs double. Technical API failures and visually rejected successful outputs are different billing cases. [Alibaba pricing](https://www.alibabacloud.com/help/en/model-studio/model-pricing), [Wan billing behavior](https://www.alibabacloud.com/help/en/model-studio/wan-image-to-video-guide).

## 13. Scene analysis module

Input: original image, dimensions, color profile, preset, desired duration, output sizes. Output: scene inventory and a proposed motion plan.

Inventory: character face/eyes/hands/body; front/back hair; cloth roots and free edges; solid geometry; near/far plants; water/reflections; sky; light sources; window/glass; available occlusion boundaries. Identify text, intricate ornaments, and high-contrast outlines as preservation-sensitive.

Rank regions by safe movement opportunity, not semantic excitement. A one-pixel hair-tip move may matter more than a generated breathing torso. Require an environmental cause consistent with the still: rain needs a compatible window/weather plan; calm wind does not imply a moving camera. Determine whether outward silhouette motion reveals unknown background. Flag unresolved disocclusion before generation.

The analysis is advisory. No automatic detector should authorize motion over the face or invent hidden anatomy.

## 14. Segmentation, masks, and brief human review

Default segmentation is manually corrected alpha/mask painting. This avoids assuming a segmentation model understands anime linework. Automation can propose regions later, but model selection and its anime accuracy remain a separate validation task; **no segmentation model is required** by A/B/C.

Produce: immutable face/hands/geometry mask; per-region alpha; deformation influence field; root weights; approved output support; depth/occlusion ordering; clean plate if a silhouette exposes background. Store mask polarity explicitly: white means active/generate, black means preserve. A compositing alpha and a diffusion inpaint mask are different assets.

At 1080-equivalent short side, use a starting 1–3 px feather for interior blend edges and a 3–8 px guard around sensitive linework. Hair silhouettes need a proper cutout, not a broad blur. Dilate generated context only within the authorized safe area; subtract the locked guard after dilation. Check masks at actual final scale.

**Human checkpoint per new image, about 30–90 seconds:** inspect colored segmentation overlay and arrows/amplitude labels; approve animated regions, roots, face locks, rain occlusion, and motion direction. Correct crossed masks and exposed background. Then view one low-resolution cycle. This review authorizes the specific motion plan; it is not approval of uninspected generated output.

## 15. Conservative presets and periodic equations

These are proposed starting policies, not tested anime constants. All amplitudes below are maximum displacement in pixels at a **1080-pixel short side**; multiply by `actual short side / 1080`. Do not blindly multiply when a region is tiny: additionally cap displacement to 2% of its local width or 1 px at the preview scale, whichever is appropriate for visible structure.

For period `T`, define `θ=2πt/T`. A root-weighted displacement:

`d_r(x,y,t) = w_r(x,y)^2 × [a_r sin(θ) + b_r sin(2θ)]`

where `a_r,b_r` are 2D vectors and `|a_r|+|b_r|` stays within the region cap. `w=0` on locked roots/guards, rising smoothly toward tips. Integer harmonics keep the period exact. A phase variant uses `sin(kθ+φ)−sinφ`, with amplitudes reduced so its potentially doubled excursion remains within the cap.

| Preset | Period | Hair / cloth | Environment | Locks |
|---|---|---|---|---|
| Calm wind | 6–8 s | Tips 1–3 px; cloth free edges .5–1.5 px; roots 0 | Near foliage 1–3 px; distant foliage .2–.8 px | Face, eyes, hands, torso pose, architecture, horizon |
| Rainy window | 4–6 s | Default character motion 0; optional tips ≤1 px | Forward rain layer, sparse window droplets; reflection shimmer ≤1% luminance | Character, window frame, background objects, text |
| Sunset field | 6–10 s | Tips 1–2.5 px; loose cloth .5–1 px | Foreground grass 1–3 px, distant grass .2–.6 px; local light ≤1% luminance | Face/body, horizon, sun position, large clouds |

Calm wind: neighboring strands share most phase, with only modest offset; no independent noisy jitter. Cloth moves from an anchored edge. Sunset: taper grass displacement toward its base and toward the horizon. Do not move painted distant structures or shift the sun across the frame.

Rain: deterministic particles/tiles move downward. On a tile of height `Htile`, choose `vy = mHtile/T` for integer `m`; phase position is `(y0+vy t) mod Htile`. Render wrap-crossing streaks on both sides of the tile, then crop/occlude at window boundaries. Use repeated tiles or smooth periodic lifetimes for births/deaths. Every random attribute is seeded and periodic. Do not wrap a droplet visibly upward on the glass: let it leave behind an occluder or fade with a smooth lifetime and respawn invisibly.

Local shimmer can use `gain(t)=1+ε sin(θ)`, limited to an approved reflection/light mask. Linear-light compositing and smooth opacity are required. Keep the face free of cyclic whole-frame exposure shifts.

## 16. Track-generation module

Input: approved regions, roots, canvas transform, `T`, frame count, amplitudes. Output: per-frame track lists and a visual motion-plan overlay.

For model proposals, sample the same periodic equations at `t=jT/(F−1)` for `j=0…F−1`, so the candidate guide includes its conceptual endpoint. Limit each moving hair/cloth region to a few clearly attached points; include root anchors in a separate experimental variant. For deterministic rendering, sample unique frames with denominator `N`, not `N−1`.

Avoid Catmull–Rom for cyclic API paths: it is not implemented as a periodic spline with wrapped tangents. Supply evaluated per-frame coordinates directly. A closed polygon with the same first and last point is insufficient to establish smooth endpoint velocity.

Design validation before dispatch: equal array lengths; finite coordinates; in-bounds support; no incompatible paths on the same rigid object; no track through face guards; smooth speed; consistent resize/crop transform. Verify the guide at 0, quarter, half, three-quarter, and final time. The regional Motion Track branch remains optional, even when these checks pass.

## 17. Generation module and prompting

Use one static shot and disable prompt enhancement, auto-duration, multishot wording, cache acceleration, and speculative adapter stacks during baseline validation. Fix all seeds. Build an explicit text prompt from approved scene content and permitted motion.

Example regional FLF prompt: “Locked tripod view of this finished anime illustration. The character, face, eyes, hands, outlines, colors, horizon and background objects remain unchanged. Only the small reflected water region shimmers gently in a repeating six-second cycle. One continuous shot.” This is a **soft instruction**, not a lock.

Remove inherited negative text such as “cartoon” from the official example when adapting it for anime. At CFG 1 the standard positive/negative CFG path supplies no extra negative-guidance weight; negative wording cannot protect geometry. Preserve the distilled schedule rather than raising CFG and steps reflexively. [Two-stage graph](https://github.com/Lightricks/ComfyUI-LTXVideo/blob/61ee82b23b18b6d7665c665bef47dbc270215f7d/example_workflows/2.5/LTX-2.5_T2V_I2V_Two_Stage_Distilled.json), [two-stage guide](https://docs.ltx.io/open-source-model/usage-guides/two-stage-generation).

Generate **context-rich crops**, not a mask-only patch lacking object context. A crop is a regional processing domain; the output canvas still preserves the complete source aspect ratio. For a face-adjacent region, use source cutouts and deterministic deformation, not generative face repair.

## 18. Compositing and preservation module

Let `B(t)` be the deterministic source-based base, `G(t)` a generated regional crop mapped back to the source, and `M(t)` the approved safe support:

`C(t) = [1−M(t)] B(t) + M(t) G(t)`.

Use premultiplied alpha consistently while resampling cutouts, then supply **straight RGB plus its explicit mask** to `ImageCompositeMasked`, whose blend multiplies the source by that mask. Unpremultiply once before that node, with a zero-alpha guard; never multiply the same matte twice. Layer preparation must provide this conversion or edge-color extension in the next phase. Blend in linear light: core `ImageColorSpace(source=sRGB,destination=linear)` before compositing, then `source=linear,destination=sRGB` once for delivery. Never color-transform masks or displacement maps. For an immutable region, `M=0`, and `B` is the source through the same color/resize pipeline. This makes preservation outside support auditable independently of what diffusion did. [Color-space node](https://github.com/Comfy-Org/ComfyUI/blob/79be670e2d9be63e238785af307369d2b9039ed1/comfy_extras/nodes_images.py).

Warp cutout RGB and its alpha using the **same** field. The effect-mask output of a distortion node should not be assumed to be the geometrically warped silhouette. Process alpha as a grayscale image with the same operation and convert it back to MASK. Compose in approved depth order. Where a silhouette moves, remove its old footprint and use a manually prepared clean plate underneath; otherwise a duplicate edge will remain. If a clean plate cannot be made confidently, restrict deformation to the original silhouette’s interior.

Use core `ImageCompositeMasked` with `resize_source=false` and explicit crop placement after dimensions match. Reapply locked source layers after all model processing. Comfy’s mask/composite implementation is a known operation; the layer policy is this report’s design. [Core mask nodes](https://github.com/Comfy-Org/ComfyUI/blob/79be670e2d9be63e238785af307369d2b9039ed1/comfy_extras/nodes_mask.py).

Do not use a whole-frame generative upscaler after restoring locked pixels: it would reopen the preservation risk. Even Laplacian blending can extend beyond a nominal region; enforce the final safe support with source compositing.

## 19. Closure module by motion type

**Deterministic deformation:** evaluate periodic fields directly. Check that spatial roots remain fixed and that every layer has the same period or an integer harmonic. Use a smooth influence field; reject folded meshes or obvious stretching. Design threshold: deformation Jacobian determinant >0.5 wherever evaluated, and no overlapping or flipped mesh cells.

**Procedural overlays:** make the particle population, texture tiling, opacity envelope, and noise state periodic together. Position wrapping alone is insufficient if random density or opacity changes at the seam. Rain must retain downward velocity at the boundary. Render several repeats and inspect the window-mask entry/exit points.

**Diffusion:** test the raw regional output against the approved reference and cyclic boundary before doing any closure edit. Same-image FLF is B’s candidate mechanism; C’s periodic guide is a motion suggestion rather than an endpoint lock. Accept a naturally matching cycle only if its length is 4–10 s and the measured seam motion fits its neighbors. If it fails, change one permitted parameter or seed within the retry budget, then fall back.

Optional future hybrid: estimate generated flow, fit a low-order periodic displacement field, and animate the original source with that field. This preserves appearance better than accepting generated RGB but may lose occlusion/topology changes. It is **experimental** and requires a selected flow estimator and separate validation; it is not secretly assumed to exist in A/B/C.

## 20. Interpolation, upscaling, and export

Order for deterministic content: approve/upscale the source **once if needed** → prepare masks/clean plate at target scale → render periodic motion and rain directly at target FPS/resolution → composite → QC → encode. Do not generate 12 FPS rain and then interpolate it into 24 FPS; render rain at the final rate.

Order for generated regional content: decode → preservation + cyclic QC → optional cyclic interpolation → region-only upscale → target-scale source compositing + procedural overlays → QC again → encode. Keeping interpolation at the smaller patch resolution saves work; texture or silhouette artifacts after upscale still require review.

Optional 24→48 FPS interpolation uses API `class_type="RIFE VFI"` (Python implementation class `RIFE_VFI`), file `rife49.pth`, multiplier 2, scale 1.0, float32, batch size 1, compile off. B: fast mode true, ensemble false; C: fast mode false, ensemble true. Set cache clear interval 10. Prepend/append context across the cyclic boundary: at minimum append frame zero to the `N` unique frames, interpolate `N+1`, then drop the duplicate endpoint to produce `2N`. Interpolating only the ordinary `N−1` interior pairs omits the seam interval. The inspected node assembles `(input frames−1)×multiplier+1` output frames. [RIFE node source](https://github.com/Fannovel16/ComfyUI-Frame-Interpolation/blob/26545cc2dd95bc3d27f056016300673bdeee78f5/vfi_models/rife/__init__.py), [API registration](https://github.com/Fannovel16/ComfyUI-Frame-Interpolation/blob/26545cc2dd95bc3d27f056016300673bdeee78f5/__init__.py).

Default resizing is Lanczos, no learned model. Optional source-only enlargement: `RealESRGAN_x4plus_anime_6B.pth` from the official v0.2.2.4 release, core `UpscaleModelLoader` → `ImageUpscaleWithModel`, then downsize to target. Human-approve the enlarged still as the new reference; do not silently redefine preservation. The official model targets anime images. Core upscale uses tiled single-image processing; framewise processing can produce temporal variation, so patch video upscale remains optional. [Real-ESRGAN](https://github.com/xinntao/Real-ESRGAN), [Comfy upscale source](https://github.com/Comfy-Org/ComfyUI/blob/79be670e2d9be63e238785af307369d2b9039ed1/comfy_extras/nodes_upscale_model.py).

1440p examples: landscape 2560×1440; portrait 1440×2560. 4K examples: 3840×2160; portrait 2160×3840. For other ratios, size proportionally without crop/stretch. Pad model canvases to multiples of 32 (single stage) or 64 (two-stage final) and remove only that pad afterward. Use even export dimensions; where exact source aspect cannot be expressed in that raster, preserve the image rectangle and record its clean aperture rather than distort it.

Export settings: lossless PNG sequence master; MP4 H.264 `yuv420p`, CRF 16–18, preset medium, constant 24 FPS, no audio; optional HEVC CRF 18 for 4K. Use `VHS_VideoCombine` format `video/h264-mp4`, `pingpong=false`, `loop_count=0`, `save_output=true`, metadata on. Codec repeat flags do not prove a seamless loop. Validate decoded exports because chroma subsampling and compression change pixels. Avoid GIF as the master. [VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite).

## 21. QC module: measurable gates plus human judgment

All thresholds below are **proposed pilot gates**, not established universal anime tolerances. Evaluate a lossless working master at a normalized 1080-pixel short side and separately inspect the final-size export. Compare with a source reference passed through the identical color/resize pipeline.

| Test | Initial rejection / review rule |
|---|---|
| Locked pixel preservation | Lossless master: require equality in fully locked interiors within floating-point/quantization tolerance; a rendered 8-bit master allows ≤1 code value rounding, not newly painted details |
| Face, eyes, hands | Locked source-derived pixels; any generated substitution, outline/iris/topology change is a hard rejection; human confirm at 100% |
| Reference structure in moving region | Compare to the expected warped reference when available; proposed edge-distance p95 ≤1 px; unexplained contour/color change → review/reject |
| Perceptual reference distance | Optional LPIPS/DINO diagnostic later; no universal hard threshold and no required model in this phase; whole-image similarity cannot certify a face |
| Camera/background drift | Fit robust translation/affine transform on locked background; proposed translation >.25 px, scale change >.05%, rotation >.02° → reject; assess pre-restoration generator drift too |
| Temporal flicker | On static support, unexplained per-frame luminance/color change is rejection; in moving support compare motion-compensated residuals and edge stability |
| Mask boundary | Halos, green leakage, duplicate hair edge, exposed clean-plate hole, or moving blend band → reject |
| Motion envelope | Displacement/speed outside approved caps; moving roots; mesh fold → reject |
| Position at seam | Compare conceptual endpoint with first image where available; p95 approved-region residual >2/255 or unexplained edge shift >.5 px → reject/review |
| Motion at seam | Seam flow magnitude/direction must agree with adjacent motion; proposed difference ≤max(.25 px/frame, 25% of local nonzero speed) |
| Visible temporal discontinuity | Boundary residual or acceleration spike >2× nearby interval level → reject/review; add an absolute floor for near-still scenes |
| Export | Correct dimensions/aspect/duration/FPS; no duplicate terminal hold, dropped frames, decoder errors, or audio discontinuity |

Boundary diagnostics use a cyclic sequence: compare `N−2→N−1`, `N−1→0`, and `0→1`, not merely the last and first still images. On raw FLF output, inspect endpoint error and the two one-sided velocities before removing the endpoint. Low motion should not be rewarded for a frozen final frame.

Simple pixel/edge/registration checks can be implemented without a learned QC model. Flow-based diagnostics require an estimator and its own validation; initially retain a mandatory human boundary review instead of pretending that component is implemented. Record false positives and calibrate thresholds on the representative scene set.

Human final review: three repeats at real speed, one slowed repeat, face/linework at 100%, and the seam centered in a playback strip. Do not show the reviewer only an attractive middle frame. Review ambiguous detector results; hard geometry failures are not overridable by a high similarity score.

## 22. Retry policy and failure handling

Per image: one approved plan, one A preview, and at most **three diffusion candidate attempts total**, shared across B/C/track branches. An attempt may include one reduced preview and one final-resolution generation; if the preview fails, skip its final. Thus at most six generator jobs, with all previews included in the attempt cost. The cap is on candidate attempts, not an unlimited stream of preview seeds. No automatic escalation from failed B seeds to an unlimited C search.

1. Candidate 1: approved motion and documented baseline settings.
2. If motion is too large: reduce amplitude or generated support by 50%; if seam fails: change seed while keeping endpoint and geometry settings fixed; if masks fail: correct masks before spending another seed.
3. Candidate 3: only after inspecting the failure class; make one justified change. Do not combine adapter changes, CFG changes, decoder changes, and new masks in the same retry.
4. Exhaustion: return the accepted deterministic A loop, or request human motion-plan revision. Report generated candidates as rejected, not “repaired” by an unreviewed dissolve.

Hardware OOM is a technical failure, not a quality retry. First shrink frame-processing chunks / decode tiles; then reduce regional canvas or duration within the agreed range. A decoder/model substitution changes the recipe and needs a fresh candidate QC run. Log billed technical failures and stop repeated OOM rather than silently renting a bigger GPU.

## 23. Implementation modules, ContentSpec, and ComfyUI API flow

### Module contracts

| Module | Inputs → outputs | Implementation status |
|---|---|---|
| Scene analysis | Source + preset → inventory, motion proposal | Human-assisted design |
| Segmentation | Source + reviewed regions → alpha, locks, roots, clean plate | Manual masks supported; auto proposal optional |
| Motion policy | Region metadata + preset → amplitudes, periods, exclusions | Equations specified here; proposed component |
| Fields / overlays | Policy + time samples → displacement-map and rain/light frame sequences | **Must be authored or implemented in the next phase** |
| Tracks | Policy + canvas transform → per-frame point lists | Specification here; official renderer exists |
| Generation | Patch/reference/masks/tracks + pinned graph → candidate frames | Official LTX graph branches exist |
| Compositing | Source layers + candidate + support → master frames | Existing nodes; source-preserving policy specified |
| Closure | Candidate + timebase → accepted cyclic frame sequence or failure | Periodic construction defined; diffusion evaluated |
| QC | Reference + masks + master/export → metrics, rejection reasons, review status | Proposed module; simple checks + human fallback |
| Retry scheduler | Failure class + remaining budget → next parameters or A fallback | Specification only |
| Export | Accepted frames + output policy → PNG master, MP4, manifest | Existing core/VHS nodes; settings specified |

**No fictional node is presented as installed.** Periodic field creation, procedural rain, metric QC, and bounded dispatch are module specifications for the next implementation phase. A practical first implementation can write numbered PNG assets externally and import them with `VHS_LoadImagesPath`; a future custom-node package can implement the same contracts. No existing official LTX graph supplies this complete ambient-loop system. The blueprint is ready to implement, not ready to drag into ComfyUI.

Displacement-map contract: lossless RGB images at the rendering canvas; `R=(dx/Ax+1)/2`, `G=(dy/Ay+1)/2`, `B=.5`; clamp nothing silently, reject excursions outside range. Use a lossless representation with enough bit depth and verify loader precision. At small amplitudes, 8-bit maps quantize displacement to approximately `2A/255`; this can be adequate for previews, while a float tensor/custom node is preferable for final fields. The inspected VHS sequence loader converts images to RGB/RGBA and divides by 255: importing 16-bit PNG through it does **not** establish retained 16-bit map precision. Exact neutral .5 is also not representable in an 8-bit channel; measure that rounding or use float fields. Gray `.5` means no displacement; do not color-manage map values. Masks use the same timebase and transform. Plate sequences may be built manually with a compositor’s periodic curves until a renderer module is implemented. [VHS sequence loader](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite/blob/4d907bee61e92c2e65af3bd6383a4e4d356126d1/videohelpersuite/load_images_nodes.py).

### ContentSpec example — declarative data, not executable code

```yaml
schema: ambient-loop/1
source:
  asset: finished_anime.png
  sha256: computed_at_ingest
  dimensions: [3840, 2160]
  aspect: 16:9
  colorspace: sRGB
plan:
  preset: calm_wind
  duration_seconds: 6
  camera: locked
  review_status: requires_per_image_human_approval
  immutable: [face, eyes, hands, body_pose, horizon, buildings, text]
regions:
  - id: hair_tips
    alpha_asset: masks/hair_tips.png
    root_weight_asset: masks/hair_roots.png
    safe_support_asset: masks/hair_support.png
    mode: deterministic_deformation
    amplitude_px_at_short_side_1080: 2
    harmonics: [1, 2]
    seed: 42
  - id: water_reflection
    safe_support_asset: masks/reflection.png
    mode: optional_regional_diffusion
    generator: ltx25_flf_single_stage
    first_equals_last: true
    preserve_character: source_composite
render:
  tier: B
  model_frames: 145
  model_fps: 24
  unique_export_frames: 144
  diffusion_canvas: [512, 512]
  canvas_transform_asset: transforms/reflection_crop.yaml
  preview_seed: 42
  candidate_seeds: [42, 43, 44]
  max_diffusion_candidates_total: 3
  prompt_enhance: false
  audio_export: false
qc:
  locked_pixel_gate: required
  seam_position_gate: required
  seam_motion_review: required
  final_human_review: required
export:
  resolutions: [[2560, 1440], [3840, 2160]]
  fps: 24
  master: png_sequence
  delivery: h264_mp4
  terminal_duplicate: omit_only_after_qc
manifest:
  record: [source_hash, mask_hashes, graph_hash, repository_revisions,
           model_hashes, seeds, prompts, timebase, runtime, peak_vram,
           qc_results, accepted_tier, rejected_candidates, rental_cost]
```

Example image content is hypothetical; if no water reflection exists, omit that region. Do not invent it to fit the example.

### ComfyUI API data flow

1. Author/validate a graph interactively from a pinned template, then export the **API-format prompt**. The canvas JSON with `nodes`, links, and subgraph definitions is not the same submission format. Resolve subgraphs to the installed backend’s accepted API form and map semantic parameters to the actual node IDs/classes; do not hard-code IDs from this report across updates.
2. Upload the source and masks as multipart requests to `POST /upload/image`, using unique filenames and subfolders. Store the returned name/subfolder/type; replace `LoadImage.inputs.image` with that input-relative asset path. Explicit grayscale mask images → `ImageToMask` avoid ambiguity from PNG alpha polarity. Numbered field/overlay frames can be uploaded to a dedicated input subfolder and imported through the image-sequence node; directory assets require that additional provisioning.
3. Replace only allowlisted graph inputs: image paths, crop/dimensions, frame count, conditioning/export FPS, text, model filenames, seed, endpoint strength, masks, and tracks. Validate `/object_info` schemas and model availability. Keep semantic source dimensions, padded model dimensions, crop coordinates, and target dimensions distinct.
4. Open `ws://host:8188/ws?clientId=<UUID>` before queuing. Submit `POST /prompt` with API prompt and matching `client_id`; current official example also supplies a client-generated `prompt_id`. Check validation errors and retain the acknowledged execution identifier.
5. Filter events by job/prompt ID; report progress/current node, handle cached execution, interruption and errors. Binary preview frames are not final output. Completion follows the example’s `executing` event with `node=null` for the matching prompt; reconnect/poll history if the socket is lost.
6. Retrieve `GET /history/<prompt_id>`. Inspect actual output entries from the chosen save node, then fetch `GET /view?filename=...&subfolder=...&type=output`, with URL encoding. The example iterates `images`; video/VHS nodes can expose different output keys. Normalize descriptors from actual node output rather than assuming every output is an image or constructing filenames.
7. Run QC on retrieved lossless frames and decoded export; write the manifest and acceptance state. Only accepted outputs advance to delivery. A queue completion event is not quality acceptance.

The websocket/queue/history/view steps follow the [official API example](https://github.com/Comfy-Org/ComfyUI/blob/79be670e2d9be63e238785af307369d2b9039ed1/script_examples/websockets_api_example.py). Upload and schema routes are separately established by [server.py](https://github.com/Comfy-Org/ComfyUI/blob/79be670e2d9be63e238785af307369d2b9039ed1/server.py) and the [server routes guide](https://docs.comfy.org/development/comfyui-server/comms_routes). This section specifies data flow only; no automation code or workflow JSON is delivered.

## 24. Reproducible validation protocol and promotion criteria

Build a licensed 12-image set: four calm-wind images, four rainy-window images, four sunset-field images. Include close face, full figure, fine hair, flat cel shading, painterly background, dense grass, glass reflections, landscape, portrait, and difficult occlusion. Hold out at least one image per preset for final tuning checks.

First smoke-test each official generation branch unchanged on a suitable input to establish load/compatibility. Then change one component at a time: anime prompt, source alignment, duration, decoder, regional support. Keep the unchanged smoke test separate from artistic acceptance.

Run A, regional B, regional C, standalone Motion Track, Wan5B I2V, Wan14B FLF, and Hunyuan480p I2V. Add Wan2.7 hosted and Cinemagraph if budget allows. Use the same approved motions, equivalent visible amplitudes, locked-camera instruction, source-based composite policy, final duration, and outputs. Use three predetermined seeds for generators. Native generators use their supported dimensions/timebase and documented recipe; compare resized outputs and **record differences**, rather than pretending their internal settings are identical. Include a source-based still control to expose metrics that reward zero motion.

Two comparisons are necessary: raw generator preservation/control, and the final source-composited product. If only the composited output is scored, source restoration can conceal the generator’s drift. Likewise, compare 1440p and 4K exports to their resized approved references, not to a differently processed original.

Measure cold startup/download/load separately from warmed text encoding, sampling stages, guide encoding, decode, post-processing, interpolation, upscale, QC, and encoding. Synchronize GPU timing; log total billed wall time, peak allocated/reserved VRAM, host RAM, storage occupancy, hardware, attention backend, software/driver versions, node/model hashes, seeds and failures. Report median, p90/range, acceptance counts, and sample size; bootstrap intervals where useful. Never transfer native-Python timings to Comfy without a matched test.

Have two reviewers judge preservation, motion plausibility, temporal stability and seam over three cycles, blinded to model/tier when possible. Record disagreements and resolution. Report **accepted loops / attempted candidates** and **images successfully completed**, including A fallbacks as a separate outcome. Twelve images are a pilot, not sufficient evidence for every anime style.

Promote a diffusion region only when it improves a necessary motion over A without worsening preservation or boundary quality, on both tuned and held-out scenes. Require zero locked-face/topology failures in the accepted set, repeatable recipe execution, and measured all-in accepted-loop cost. Quantized IC-LoRA combinations, cyclic-history tracks, motion-field extraction, and any learned seam repair remain experimental until their own ablations pass.

## Workflow A — ultra cheap: deterministic ambient animation

**Production role:** first choice and fallback for every scene. No diffusion model, text encoder, VAE, segmentation model, sampler, or denoising steps. Optional source-only anime enlargement uses the exact Real-ESRGAN file in section 20 after human approval.

### Existing repositories and graph path

Core ComfyUI + VideoHelperSuite + Majoor ImageOps, pinned as section 2. Use:

`LoadImage` → proportional `ImageScale` / mask preparation → `ImageColorSpace` to linear → `RepeatImageBatch` → `ImageOpsDistort` (one branch per cutout) → matched alpha warp / straight-RGB layer preparation → `ImageToMask` → `ImageCompositeMasked` over clean plate/source → approved procedural layers imported with `VHS_LoadImagesPath` and converted to linear if they are sRGB color plates → `ImageColorSpace` to sRGB → `ImageFromBatch` / batch selection → `SaveImage` + `VHS_VideoCombine`.

Core `RepeatImageBatch` duplicates the source batch; `ImageFromBatch` selects a frame range. Process small chunks instead of materializing the entire 4K movie. [Core image nodes](https://github.com/Comfy-Org/ComfyUI/blob/79be670e2d9be63e238785af307369d2b9039ed1/comfy_extras/nodes_images.py). VHS sequence-loading and batching are provided by the referenced repository. [VHS loaders](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite/blob/4d907bee61e92c2e65af3bd6383a4e4d356126d1/videohelpersuite/load_images_nodes.py), [VHS node registration](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite/blob/4d907bee61e92c2e65af3bd6383a4e4d356126d1/videohelpersuite/nodes.py).

`ImageOpsDistort` exact settings: `bypass=false`, `map_source=displacement_channel`, `x_channel=Red`, `y_channel=Green`, `centered_map=true`, `invert_map=false`, `blur_map=0`, `filter=bilinear`, `edge_mode=border`, `invert_mask=false`; strengths `Ax,Ay` are canvas-pixel maximums used in the map contract. A zero-amplitude axis gets a constant .5 channel and strength 0. Use the same distortion for RGB and alpha. The node samples `source(x−dx,y−dy)` and blends through its effect mask; it does not generate the periodic displacement sequence. [Distort implementation](https://github.com/MajoorWaldi/ComfyUI-Majoor-ImageOps/blob/bf499d46247d6191c902b8240cadee40c5b7171c/nodes/distort.py).

### Preview and final settings

| Parameter | Preview | Final |
|---|---|---|
| Canvas | 960×540 for 16:9; proportional for source ratio | 2560×1440 and/or 3840×2160; proportional |
| Period / frames / FPS | 6 s; 72 unique frames; 12 FPS | 6 s; 144 unique frames; 24 FPS; optional 288 at 48 FPS |
| Processing chunk | 8 frames | 2–4 at 1440p; 1–2 at 4K |
| Motion | Section 15 caps, reduced if cutouts fail | Same equations at final sample times |
| Masks | Approved cutouts, root fields, locked guards | Rebuilt/scaled carefully at target size |
| Closure | Analytic periodic state | Same; no crossfade, no endpoint duplication |
| Interpolation | None | None; direct temporal render |
| Upscale | Lanczos | Source once before rendering; learned upscale only as approved optional variant |
| VRAM | Planning 1–2 GB | Planning 2–4 GB for small chunks; CPU possible |
| Cost | Included in A attempt scenario | Roughly 1–4 cents accepted in the assumed warm rental scenario; not measured |

**Required next-phase work:** author or implement the periodic displacement, overlay asset producer, QC, and chunk dispatch contracts. The Comfy graph consumes their assets; the report does not imply an existing all-in-one periodic node.

Weaknesses: elastic/flat motion if masks or roots are poor; limited topology/disocclusion; cutout edges need care. It cannot convincingly reveal hidden hair surfaces. For rain/light ambience and tiny tip motion, these limits are often acceptable; validate on the actual drawing.

## Workflow B — balanced: deterministic base + regional FLF candidate

**Production role:** add one small reflection/water/light region that needs more than a deterministic shimmer. Hair, face, body, background geometry and rain stay in A’s source-based/procedural path. The regional FLF output must close naturally; it has no guaranteed success rate.

### Exact assets and nodes

Start from pinned `video_ltx2_5_flf2v.json`, not the ordinary two-stage I2V graph. Models: INT8 ConvRot transformer, INT8 ConvRot Gemma4 encoder, `ltx-2.5-audio-vae-bf16.safetensors`; Conv VAE preview, DiffVAE final. No IC-LoRA and no latent upscaler. Repositories: core ComfyUI + official LTXVideo where needed by the exported template + A’s compositor/VHS repositories; optional Frame-Interpolation for 48 FPS.

Core/template nodes: `UNETLoader`, `CLIPLoader` (`type=ltxv`), `VAELoader`, `CLIPTextEncode`, `LTXVPreprocess`, `EmptyLTXVLatentVideo`, `LTXVEmptyLatentAudio`, two `LTXVAddGuide`, `LTXVConditioning`, `LTXVConcatAVLatent`, `RandomNoise`, `LTXVDualCFGGuider`, `SamplerEulerAncestral`, `ManualSigmas`, `SamplerCustomAdvanced`, `LTXVSeparateAVLatent`, `LTXVCropGuides`, `VAEDecodeTiled`, then source-safe compositor/export. Preserve all AV wiring; discard audio from delivery. [FLF template](https://github.com/Comfy-Org/workflow_templates/blob/25ff90a51cc8f6ee56bd78ec3b11f294925fb36d/templates/video_ltx2_5_flf2v.json).

### Settings

| Parameter | Preview | Final candidate |
|---|---|---|
| Regional model canvas | 384×384 context patch | 512×512 context patch; source/crop transform preserved |
| Frame count / FPS | 97 / 24; evaluate 4-second cycle | 145 / 24; evaluate 6-second cycle |
| Export after passed boundary QC | 96 unique frames / 24 | 144 unique frames / 24 |
| First / last | Same patch; `LTXVAddGuide` frame 0 and −1 | Same; initial strength .7 each |
| Prompt enhancer | Off | Off |
| Sampler | `SamplerEulerAncestral`, **eta 0, s_noise 1** as template | Same |
| CFG | Video 1, audio 1 | Same |
| Steps / sigmas | 8; `1,.99375,.9875,.98125,.975,.909375,.725,.421875,0` | Same; do not invent a low-denoise img2img knob |
| Seed | 42 fixed | Candidates 42,43,44 within global budget |
| Image preprocess | Template compression 18 initially | Same; reducing compression is an evaluated variant |
| Decoder tiles | `tile_size=512`, `overlap=64`, `temporal_size=64`, `temporal_overlap=16` | Same starting values |
| Mask/control | No masked LTX generation claimed; crop and final safe compositing mask | Same; generated footprint ideally ≤10% of source |
| Loop | Same-endpoint candidate + position/motion QC | Only naturally accepted closure; A fallback otherwise |
| Interpolation/upscale | None | Optional cyclic RIFE 24→48 → Lanczos patch resize → source composite → procedural rain at final FPS |
| VRAM | Planning 32–48 GB | Planning 32–48 GB; rent 48 GB initially |
| Output | Source-aspect preview | Full source-aspect 1440p / 4K |

The sigma schedule and FLF endpoints were inspected in the native graph. Its sampler widget values `[0,1]` map to `eta=0, s_noise=1`, in that order; do not reverse them or substitute the ordinary I2V sampler defaults. [Sampler schema](https://github.com/Comfy-Org/ComfyUI/blob/79be670e2d9be63e238785af307369d2b9039ed1/comfy_extras/nodes_custom_sampler.py). The reduced crop dimensions, same-endpoint test, and final safe-support policy are **design adaptations**, not personally validated configurations. Changing decoder between preview and final can change reconstruction; final acceptance must be repeated.

Cost uses section 12’s L40S $1.09/h scenario, approximately $0.15–.60 per accepted diffusion-assisted loop at the stated assumed timings/p=.5. If optional RIFE is enabled, its work belongs in `Tfinish`; exceed the assumed finishing range if measured time warrants it. Weaknesses: texture/line drift in the patch, little motion despite matching endpoints, speed discontinuity, altered reflections, and crop context loss. Reject rather than broaden the generated footprint.

## Workflow C — maximum quality under the preservation priority

**Production role:** higher-quality source cutouts/deformation and a carefully masked, context-rich regional LTX video inpaint where motion/texture genuinely requires it. Maximum quality here does not mean maximum whole-frame diffusion. If C harms preservation or closure, A is the higher-quality accepted output for that image.

### Exact graph, models, and nodes

Start from `LTX-2.5_ICLoRA_Inpaint_Two_Stage_Distilled.json`. BF16 transformer, BF16 Gemma4 encoder, DiffVAE video file, BF16 audio VAE; adapter `ltx-2.3-22b-ic-lora-in-outpainting-0.9.safetensors` from [Lightricks’ in/outpaint model repository](https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-In-Outpainting). Place the adapter in `models/loras`. Its declared model bundle includes the 2.5 latent spatial upscaler, but the inspected refinement path instead resizes blended pixels ×2 and VAE-encodes them; do not assume an unused loader proves latent upscale is happening. [Inpaint graph](https://github.com/Lightricks/ComfyUI-LTXVideo/blob/61ee82b23b18b6d7665c665bef47dbc270215f7d/example_workflows/2.5/LTX-2.5_ICLoRA_Inpaint_Two_Stage_Distilled.json).

Additional LTX nodes beyond loaders/samplers: `LTXICLoRALoaderModelOnly`, `LTXVInpaintPreprocess`, `LTXVDilateVideoMask`, `LTXAddVideoICLoRAGuideAdvanced`, `LTXVImgToVideoInplace`, `LTXVCropGuides`, `LTXVLaplacianPyramidBlend`, `VAEEncodeTiled`, `LTXVSetAudioRefTokens` / `VAEEncodeAudio` when preserving a source audio stream. Reference source is the deterministic periodic base video; mask video is lossless, time-aligned, white active/black locked. Keep native video loading/component extraction or supply equivalent IMAGE/MASK batches in the API graph.

No arbitrary sparse tracks or last-frame guide are added to this graph. Inpainting supplies regional editing control, not certified cyclic dynamics. [Inpainting guide](https://docs.ltx.io/open-source-model/feature-guides/editing-effects/in-outpainting).

### Preview and final settings

| Parameter | Preview | Final |
|---|---|---|
| Model domain | Context-rich square crop, base 256×256 → refined 512×512 | Base 512×512 → refined 1024×1024 |
| Reference / mask | A’s periodic guide, same crop, 97 frames | A’s guide, 145 frames including conceptual endpoint |
| FPS / export duration | 24; 4 seconds after closure acceptance | 24; 6 seconds; 144 unique final frames |
| Transformer/encoder/decoder | BF16 / BF16 / DiffVAE | Same |
| Adapter strength | 1.0 | 1.0; no quantized-adapter substitution |
| Stage 1 | CFG 1; `euler_ancestral`; 8 steps | Same |
| Stage 1 sigmas | `1,.99375,.9875,.98125,.975,.909375,.725,.421875,0` | Same |
| Stage 2 | CFG 1; `euler`; **2 steps** | Same |
| Stage 2 sigmas | `.7250,.4219,0` | Same |
| Seeds | Stage 1=43, Stage 2=42 fixed | Same first candidate; record both on retries |
| First-image conditioning | Enabled; stage 1 strength .7, stage 2 strength 1 | Same; no last-frame lock claimed |
| Mask dilation design | Stage 1 8 px spatial, stage 2 4 px; temporal 0 | Same in their respective processing rasters; subtract locked guards |
| Blend design | Start from graph’s Laplacian settings (low-res dilation 5/6 in the blend nodes) | Enforce final safe support afterward; reject halos |
| Decode tiles | 512 / 64 spatial; 128 / 32 temporal | Same starting values; measure peak and tile seams |
| Stage 2 encode tiles | 512 / 64 spatial; 500 / 64 temporal | Preserve graph recipe initially |
| Loop | Periodic reference suggestion + raw candidate seam QC | Natural closure or A fallback; no ping-pong rain/dissolve repair |
| Interpolation/upscale | None | Optional cyclic RIFE to 48; Lanczos patch placement; source rendered directly at 1440p/4K |
| VRAM | Planning 64–96 GB | Planning 80–120 GB; provision H200 141 GB for first audit |

All model widths/heights must be set explicitly: replace graph auto-resize branches so the approved crop reaches these sizes; do not leave a “shorter side 1024” node silently overriding the preview canvas. This is a graph adaptation to validate. Likewise, mask dilation values are this design’s conservative proposal, not claimed vendor defaults.

The actual inpaint schedule is 8+2; ordinary I2V’s latent-upscale branch is 8+3. Do not interchange them. Decode/blend/re-encode and high-resolution first-image conditioning do not mathematically constrain the end of the clip. [Inpaint graph](https://github.com/Lightricks/ComfyUI-LTXVideo/blob/61ee82b23b18b6d7665c665bef47dbc270215f7d/example_workflows/2.5/LTX-2.5_ICLoRA_Inpaint_Two_Stage_Distilled.json), [ordinary two-stage graph](https://github.com/Lightricks/ComfyUI-LTXVideo/blob/61ee82b23b18b6d7665c665bef47dbc270215f7d/example_workflows/2.5/LTX-2.5_T2V_I2V_Two_Stage_Distilled.json).

Audio: silent export still retains the official audio latent/model plumbing during the baseline run. For an audio-less deterministic reference, either provide an explicitly silent matching waveform to the reference path or validate bypassing that path while retaining the graph’s AV latent structure. This adaptation needs a smoke test; no free speedup from removing audio is assumed in cost estimates.

Cost: section 12’s H200 $4.59/h scenario yields roughly $1.5–5.5 per accepted candidate at assumed timings/p=.5, plus 4K increments or cold setup. A measured H100/A100 fit may lower cost later; choose by cost per accepted output rather than rent per hour.

Weaknesses: regional style drift, mask contamination, green edge remnants, heavier decode, noncyclic generated texture, and uncertain success near complex occlusion. Final source restoration protects locked regions but cannot make an unacceptable moving patch good. Greater GPU cost does not override the QC gates.

### Optional Motion Track branch — separate from B/C baseline

For a region whose motion plan needs a learned proposal, use the official single-stage Motion Track graph **without** adding FLF or refinement. Exact BF16 assets from section 5 plus `ltx-2.3-22b-ic-lora-motion-track-control-ref0.5.safetensors`; `LTXICLoRALoaderModelOnly` strength 1; loader-produced reference factor connected; `LTXVDrawTracks` → `LTXAddVideoICLoRAGuide` strength 1, frame_idx 0, crop disabled; image-conditioning strength .7. Use 512×512 canvas, 145 frames, 24 FPS, CFG 1, eight-step schedule above, `euler_ancestral`, fixed seed 42, tiled decode 512/64/64/8. Crop guide latents before decode. [Official Motion graph](https://github.com/Lightricks/ComfyUI-LTXVideo/blob/61ee82b23b18b6d7665c665bef47dbc270215f7d/example_workflows/2.5/LTX-2.5_ICLoRA_Motion_Track_Distilled.json).

The cyclic paths and anchors are experimental task adaptations. Compare generated tracks against the requested tracks, and assess raw drift before source compositing. An output is not accepted just because the guide looks correct. Provision an 80 GB GPU for the initial BF16 regional track test; actual peak and cost remain unmeasured. Its guide renderer uses a larger reference raster and retains a frame batch, so guide rendering is not free even at a small output size. This branch consumes the same three-candidate budget; there is no separate unlimited search allowance. If its motion is useful but RGB reconstruction is not, retain it only as a human motion reference until a validated motion-extraction module exists.

## Direct answer: the cheapest reliable method

**Animate the original image with tiny, periodic masked deformations and render rain/light overlays procedurally. Keep the face, camera, and most of the background as source pixels.** This gives explicit periodic motion and avoids repeatedly regenerating the drawing. GPU rental can be eliminated with a local/CPU compositor, or kept very small by chunking frames.

LTX-2.5 Motion Track is **optional regional control**, not the main production tool for near-pixel-level preservation. Use diffusion only when an approved small region demonstrably benefits, and accept it only after preservation and both seam-position and seam-motion checks. The cheapest reliable pipeline is A; B/C are bounded exceptions whose real cost and quality must be measured with the supplied validation protocol.
