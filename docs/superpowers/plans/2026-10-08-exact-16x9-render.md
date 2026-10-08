# Exact 16:9 render Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Save exact 16:9/9:16 frames for near-16:9 sources and correctly finish existing legacy candidates.

**Architecture:** Centralize the tolerance and centered crop in `ambient_loop.candidates`, applying it after padding removal on candidate export and before enhancement on finish. Persist dimensions from the actual written frame.

**Tech Stack:** Python 3.11+, NumPy 2.2.6, Pillow 11.3.0, FFmpeg when available.

**Spec:** [Exact 16:9 render design](../specs/2026-10-08-exact-16x9-render-design.md).

## Global Constraints

- Retain raw frames, reviewed canvas, candidate files, count, FPS, silence and node interfaces.
- Treat the 2% long-to-short tolerance as inclusive and center crop only output images.
- Do not modify dependencies or the official LTX baseline.

## Review Focus

- Portrait near-16:9 images must use 9:16 dimensions.
- Exact 16:9 must be unchanged; ratios beyond tolerance must retain existing sizing.
- Existing saved 1290x720 frames must finish correctly without being overwritten.
- All three finishing resolutions must use exact dimensions.
- Preview MP4 metadata must match written frame dimensions when FFmpeg is installed.

### Task 1: Regression coverage and exact-dimension implementation

**Files:** Modify `tests/test_candidates.py`, `ambient_loop/candidates.py`, and this plan.

**Interfaces:** `save_candidate(images, plan, seed, root, settings)` continues to return a record; `finish_candidate(handle, root, resolution, chunk_size, enhancer)` continues to accept legacy records.

- [x] Write failing candidate and legacy-finish regression tests checking dimensions, pixels, metadata and immutability.
- [x] Run `python -m unittest tests.test_candidates -v`; observed 1290x720 export, 1936x1080 legacy finish and 720x1290 portrait failures.
- [x] Implement a centered exact-aspect crop helper and apply it to export and finish frames.
- [x] Re-run `python -m unittest tests.test_candidates -v`; 8 tests passed.
- [x] Run the project Python/Node suites, `git diff --check`, and FFmpeg-backed probe where available; record outcomes below.

## Verification and handoff

- Red: the three new regressions failed for the missing crop behavior (the initial exported-frame assertion also exposed an unclosed test image handle, fixed before green).
- Green: `python -m unittest tests.test_candidates -v` passed 8 tests.
- Full suites: `python -m unittest discover -s tests` passed 83 tests; `node --test $nodeTests` passed 35 tests; `git diff --check` passed.
- FFmpeg probe: a locally generated near-16:9 candidate encoded at 1280x720 and its 1080p finish at 1920x1080; each had 8 frames at 8 FPS.
- GPU inference and visual acceptance remain pending; local evidence does not qualify them.
