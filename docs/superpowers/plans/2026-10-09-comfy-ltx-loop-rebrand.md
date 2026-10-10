# Comfy LTX Loop Rebrand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or an explicitly selected equivalent execution workflow. Steps use checkbox syntax for tracking.

**Goal:** Replace every tracked legacy identity with the canonical Comfy LTX Loop identity.

**Architecture:** Rename physical paths first-class, update every textual contract
consistently, then regenerate the editable workflow from its renamed generator.
An inventory test makes complete removal of legacy branding a durable contract.

**Tech Stack:** Python unittest, Node test runner, ComfyUI custom nodes, JSON workflows.

**Spec:** [Comfy LTX Loop rebrand design](../specs/2026-10-09-comfy-ltx-loop-rebrand-design.md)

## Global constraints

- Canonical forms are `comfy-ltx-loop`, `comfy_ltx_loop`, `ComfyLTXLoop…` and `Comfy LTX Loop`.
- This is breaking: do not provide aliases or migration.
- Preserve product behavior, official LTX graph semantics and unrelated worktree edits.

## Review focus

- Persisted metadata/routes/env variables must use the new key even where no UI exposes them.
- The generated workflow must match the renamed generator.
- Legacy spelling must not survive in historic docs, fixtures, paths or test source.
- Existing external workflows/data are intentionally incompatible.

## Task 1: Establish the new public-contract tests

Files: `tests/test_rebrand.py`, `tests/test_rebrand_inventory.mjs`.

- [x] Write tests for the new package, CLI, ComfyUI asset path and legacy-free inventory.
- [x] Run them before the rename; expected failure is missing new package/path and legacy inventory hits.

## Task 2: Rename implementation, assets and contracts

Files: package/custom-node/workflow/generator paths; all tracked source, tests,
fixtures and documentation.

- [x] Rename paths and replace public/private identifier variants.
- [x] Regenerate the renamed editable workflow.
- [x] Run focused rebrand tests: Python 29/29 and Node 38/38, including inventory.

## Task 3: Reconcile documentation and verify

Files: product spec, design, plan, codemap and workflow index.

- [x] Update navigation and historical references to the new names.
- [x] Run Python suite (90/90), Node suite (38/38), editor fixture startup, Markdown-link, inventory and diff checks.
- [x] Record actual results and qualification boundary.

## Delivery evidence

- RED: `python -m unittest tests.test_rebrand -v` failed with
  `ModuleNotFoundError: No module named 'comfy_ltx_loop'` before the rename.
- GREEN: focused Python contracts passed 29/29; `node --test` passed 38/38,
  including the new tracked path/content inventory test.
- Full regression: `python -m unittest discover -s tests -v` passed 90 tests in
  116.127 seconds. `python tests/editor_harness.py` served its local fixture at
  `http://127.0.0.1:8766`; its persistent fixture processes were stopped after
  startup confirmation.
- Markdown local links resolved across 20 files. A case-insensitive repository
  scan found no legacy-brand occurrence; `git diff --check` passed. The editable
  workflow was regenerated from `tools/build_comfy_ltx_loop_workflow.mjs`.
- No deployed ComfyUI conversion, cloud/GPU inference or visual-quality result was
  produced by this repository-local rename; those qualification gaps remain pending.
