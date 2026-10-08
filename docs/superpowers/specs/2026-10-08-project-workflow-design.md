# Project specification and research workflow

Date: 2026-10-08. Status: implemented and verified.

## Intent

The owner wants durable project context for the agent and an understandable product
specification for themselves. Every implementation must start from specifications,
use tests before production code, and check current library documentation while
planning. The owner also requested a complete, maintained `codemap.md` for navigation.

Source: the owner's instructions and
[their video reference](https://www.youtube.com/watch?v=tjsXxozGKdE).
YouTube metadata identifies Vibecoder School's video; its transcript was unavailable.
The workflow below implements the owner's stated requirements. Further details
from the video have not been verified.

## Artifacts and responsibilities

| Artifact | Responsibility |
| --- | --- |
| `AGENTS.md` | Mandatory discovery, specification, research, TDD and completion rules |
| `codemap.md` | Complete maintained source tree and guide to module ownership |
| `docs/product-spec.md` | Living owner-facing goals, user journeys, acceptance criteria and delivery status |
| `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` | Agent-facing design, contracts, constraints, research and test mapping |
| `docs/superpowers/plans/YYYY-MM-DD-<topic>.md` | Ordered implementation tasks with failing and passing test steps |
| `docs/superpowers/README.md` | Spec index, writing conventions and reusable outlines |
| `docs/qualification.md` | Actual deployment, GPU and visual evidence and remaining checks |

Seed the product and technical baseline from repository source and existing
documentation. Keep original plans and evidence intact. Baselines describe current
behavior; they do not retroactively prove TDD or cloud qualification.

## Working sequence

1. Read `AGENTS.md`, `codemap.md`, the product spec and the relevant technical spec.
2. Use Superpowers brainstorming for requirements and focused questions when needed.
   Carry forward existing authorization; ask about missing intent or a real decision.
3. Update the product spec and write/update the technical spec before implementation.
   Small changes may extend an existing spec; they still need explicit criteria.
4. Use Context7 MCP for relevant library, framework, SDK, API, CLI and cloud-service
   research. Resolve the library, then query one concept at a time. Inspect local
   pins; confirm release freshness from official release/package sources when
   necessary. Record versions, sources, lookup date and compatibility decisions.
5. Use Superpowers writing-plans for multi-step implementation and execution skills
   when carrying out the plan. Keep scope proportional to the change.
6. For production behavior, write a meaningful acceptance/regression test, run it
   and observe the expected behavioral failure, then implement the smallest change
   to pass. Refactor after green. Record red and green evidence.
7. Update both specs and the plan with delivered behavior and actual verification.
   Update the codemap whenever structure or module ownership changes.

Documentation-only work uses document, link and diff checks. Configuration setup
uses configuration inspection and a connection check. These are not production-code
TDD and must not be reported as a red/green implementation cycle.

## Context7 installation

Run `npx.cmd --yes ctx7@latest setup --codex --mcp --yes --api-key <key>` with the
owner's credential, redacting command output. Store credentials in the user's Codex
configuration outside the repository. Preserve unrelated settings. The resulting
MCP server uses `https://mcp.context7.com/mcp`; setup also installs its rule and skill.
Never copy credentials to specs, source, tracked configuration or evidence.

If the current session cannot load newly installed MCP tools, validate the configured
endpoint through MCP and report that a new Codex session is needed for native tools.
Future research must not silently claim Context7 was consulted if it was unavailable.

## Acceptance criteria

- Both spec audiences have concrete initial documents reflecting the current project.
- Every future feature, fix or refactor requires both spec updates, with scope and
  verification status; production behavior requires an observed failing test first.
- Agent rules require current, version-aware Context7 research during feature planning.
- Context7 setup succeeds and the authenticated MCP endpoint returns documentation.
- `codemap.md` covers every maintained project file and explains generated/local areas;
  agent rules require reading and maintaining it.
- README links to product spec, codemap and the workflow index.
- No credential is present in tracked changes. Existing product code is untouched.

## Verification boundary

### Context7 research and connection evidence, 2026-10-08

- Official [CLI setup](https://context7.com/docs/clients/cli) and
  [Codex setup](https://context7.com/docs/clients/codex) were consulted.
- `npx.cmd --yes ctx7@latest setup --help` confirmed supported flags.
  CLI version: 0.5.14. Setup returned exit 0.
- Authenticated hosted MCP initialization returned Context7 server 4.2.0;
  `tools/list` exposed `resolve-library-id` and `query-docs`.
- `resolve-library-id` for Context7 returned `/upstash/context7`, the official
  source with High reputation. `query-docs` returned Codex setup and API-key
  documentation from the official repository. The credential was used only in
  setup/authentication, never documentation query text or repository documents.
- MCP was verified through JSON-RPC HTTP because this session's native tool list
  was loaded before installation. Start a new Codex session for native MCP tools.

### Document verification, 2026-10-08

- Compared the parsed codemap tree against the maintained `rg --files` inventory:
  all 101 files mapped, with no missing or stale entries.
- Checked relative Markdown links and trailing whitespace in all eight changed/new
  documents; all resolved. Scanned maintained files: no Context7 API key present.
- Parsed the user's Codex TOML and confirmed the hosted endpoint and configured
  authentication without printing the credential. `git diff --check` passed.
- Product code was not changed and product test suites were not rerun. Documentation
  checks and authenticated MCP requests are this setup's verification evidence.

Completed plan: [Project workflow implementation](../plans/2026-10-08-project-workflow.md).

This work changes project documentation and agent configuration. It does not prove
GPU inference, model landmark quality, installed ComfyUI conversion or visual loop
quality. Those remain governed by `docs/qualification.md`.
