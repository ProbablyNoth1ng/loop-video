# Ambient Loop product specification

Updated: 2026-10-08.

This is the living product agreement for the owner. Technical designs and task
plans are indexed in [Superpowers documents](superpowers/README.md).
[The codemap](../codemap.md) explains where the implementation lives.

## Purpose

Turn one anime illustration into a short, silent animation in ComfyUI. The owner
can direct character and selected scenery motion, correct control points before
generation, inspect the loop and finish a saved render at a higher resolution.

The desired result preserves recognizable faces, clean linework, the original
composition and a stable camera. These are visual acceptance goals; model guidance
does not guarantee them. Real anime and GPU qualification is still pending.

## User journey and requirements

| ID | Requirement and acceptance criteria | Delivery status |
| --- | --- | --- |
| P-01 | Load exactly one source image. Preserve orientation and aspect ratio through preparation, rendering and finishing. | Implemented; deployment qualification pending |
| P-02 | Enter character motion and optionally requested parts. Prepare suggestions with local Qwen3.5, local Qwen3-VL or manual editing. Automatic failures show actionable feedback and leave manual correction available. Useful visible suggestions survive partial responses; hidden anatomy is omitted. | Implemented; real model accuracy pending |
| P-03 | Enter background motion to enable scenery animation. Choose Model or Manual; prepare Character, Background or both. Each preparation changes its own group. Clearing background motion excludes background tracks and retains saved points. Failed automatic preparation preserves existing points. | Implemented; deployed scenery render pending |
| P-04 | Review/edit points on the source image. Filter Character, Background or All; hidden points cannot be selected. Choose the group for new points. Add, move, delete or disable points, edit labels/objects/roles/reasons/strengths and inspect trajectories. Moving points are green, stationary anchors blue, disabled points gray; character points are circles and background points squares. | Implemented; installed frontend qualification pending |
| P-05 | Accept point review before Render. Changed image clears groups; changed instructions or preparation settings require preparing the affected group again. Point edits invalidate review. Timing/canvas changes keep normalized paths and require renewed review in the editor. Enabled background animation needs an enabled moving background point. | Implemented; installed frontend qualification pending |
| P-06 | Run offers an explicit choice of Prepare character, Prepare background, Prepare both, Render or Upscale. One choice queues one isolated stage. Prepare cannot generate; Render cannot upscale; Upscale reads only a saved candidate. Cancel queues nothing. | Implemented; deployed conversion/queue qualification pending |
| P-07 | Render with the official LTX-2.5 single-stage Motion Track pipeline. Show continuous and forward seam previews, allow another seed/candidate, and retain original lossless frames. Returning trajectories guide closure; the owner checks the seam. | Implemented; GPU and visual acceptance pending |
| P-08 | Select original saved candidates after reopening; automatically select the newest completed render and refresh the list when requested. Preserve reviewed points in the saved workflow. | Implemented; real ComfyUI restart qualification pending |
| P-09 | Optionally upscale a selected candidate to short sides of 1080, 1440 or 2160 pixels. Preserve aspect ratio, even dimensions, frame count, FPS, timing and original candidate files. Default to 1440. Save a silent MP4 with lossless frames alongside it. | Implemented; GPU and temporal-flicker qualification pending |
| P-10 | Support documented cloud installation and retain the existing CLI. Record deployment/model versions and actual runtime evidence before promising supported hardware or performance. | Implemented setup paths; provider qualification pending |

"Implemented" describes repository behavior and existing evidence. It does not
mean this session reran all tests or that a production GPU run was accepted.
See [qualification](qualification.md) for dated checks and unresolved deployment work.

## Current defaults

| Setting | Default |
| --- | --- |
| Duration / playback FPS | 6 seconds / 24 FPS |
| Seed / motion strength | 42 / 0.01 |
| Generation short side | Near 720 pixels, with internal alignment padding |
| Character preparation | Local Qwen3.5 (`Qwen/Qwen3.5-9B`) |
| Background preparation | Model; animation enabled only by nonblank background motion |
| Finishing short side | 1440 pixels |
| Camera intent | Stationary |
| Default generated / playback frames | 145 / 144 |

## Quality acceptance

Before accepting a real output, inspect repeated playback and its forward seam
for face identity, hair motion and overlap, stationary anchors, camera/background
drift, line preservation and flicker. Compare the higher-resolution finish to
the original render. A numerical closure measurement supports review and cannot
replace it. Retry visibly poor candidates; never automatically reverse frames
to manufacture ping-pong playback.

No supported GPU minimum, measured inference runtime or guaranteed seamless loop
is established. Cloud and real anime checks remain in [qualification](qualification.md).
Strict masks and source compositing belong to other workflows and are not part
of the current LTX animation journey.

## How we implement changes

Every implementation updates this product spec and its corresponding technical
spec before code and again as behavior or evidence changes. New requirements get
stable IDs continuing after P-10; existing IDs retain their meaning.

Use Superpowers to clarify requirements, design and plan. Check relevant current
library documentation through Context7 during planning. Write and run a failing
behavioral test first, implement code to make it green, then refactor and verify.
Update [codemap.md](../codemap.md) whenever project structure changes.

## Delivery notes

- 2026-10-08: Established this baseline from current source, README and existing
  qualification records. Added owner/agent specs, maintained code navigation,
  mandatory test-first rules and Context7 research configuration. This setup changes
  the development workflow; product requirements P-01 through P-10 retain their current scope.
  See the [workflow design and verification](superpowers/specs/2026-10-08-project-workflow-design.md).
- Current priorities requiring external evidence: installed ComfyUI conversion and
  queues, actual Qwen placement and memory release, LTX render quality, seams, and
  all supported finishing sizes. There is no active feature implementation plan
  selected by this baseline.
