# Comfy LTX Loop rebrand design

Date: 2026-10-09. Status: implemented locally; deployment/GPU qualification unchanged and pending. Product requirements: P-13 in
[the product specification](../../product-spec.md).

## Intent and scope

Replace every tracked legacy-brand filename, directory, identifier, string and
persisted key with the canonical Comfy LTX Loop forms. This is a deliberate
breaking change: old commands, imports, workflows, records, routes, output paths
and environment variables receive neither aliases nor migration.

## Behavior and acceptance criteria

- Hyphenated identifiers and filesystem names use `comfy-ltx-loop`; Python and
  path identifiers use `comfy_ltx_loop`; node classes use `ComfyLTXLoop…`; user
  display text uses `Comfy LTX Loop`.
- The package/module and CLI are `comfy_ltx_loop` and `comfy-ltx-loop`.
- ComfyUI custom-node assets, routes, persisted records, schemas, cloud scripts,
  generated editable workflow and node types use only the canonical forms.
- All tracked paths and textual contents are clear of the former brand. The
  official LTX baseline remains unchanged except for references outside it.

## Architecture and contracts

Rename the package, ComfyUI custom-node directory/editor asset, workflow and
workflow generator. Rewrite imports and configuration mechanically, then
regenerate the editable workflow from the renamed generator. Tests and fixtures
assert the new external contracts and a repository inventory test prevents
reintroduction. Existing serialized artifacts intentionally fail to load.

## Library research

No external library/API contract changes: this is a repository-local naming
change. Context7 is not applicable.

## Test strategy

Before the rename, add a Python rebrand-contract test and a Node inventory test;
both must fail because the new package/path and all-clear inventory do not yet
exist. Update existing tests and fixtures with the new public contracts. Verify
the generated workflow byte-for-byte against its generator, then run Python,
Node, editor-harness, Markdown-link, inventory and whitespace checks. Deployment,
GPU inference and visual qualification remain outside this naming change.

## Delivery and evidence

Plan: [Comfy LTX Loop rebrand implementation](../plans/2026-10-09-comfy-ltx-loop-rebrand.md).
Evidence and any remaining verification gaps are recorded in that plan at handoff.
