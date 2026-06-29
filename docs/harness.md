# Harness Engineering Guide

This project uses a narrow Harness Engineering layer so agents can verify the demo without relying on hidden human context.

## Command Surface

Run profiles through:

```powershell
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile boundaries
python scripts/verification/harness.py --profile drift
python scripts/verification/harness.py --profile backend-contract
python scripts/verification/harness.py --profile godot-project
python scripts/verification/harness.py --profile character-agent-execution
python scripts/verification/harness.py --profile release-gate
python scripts/verification/harness.py --profile harness-lifecycle
python scripts/verification/harness.py --profile change-lifecycle
python scripts/verification/harness.py --profile harness-reference
python scripts/verification/harness.py --profile harness-evolution
python scripts/verification/harness.py --profile phase0
python scripts/verification/harness.py --profile phase1-slice
python scripts/verification/harness.py --profile siming-backend-chain
python scripts/verification/harness.py --profile all
```

Every run writes an aggregate summary:

- `.harness/verification/harness-run-report.json`
- `.harness/verification/harness-run-report.md`

Every run also writes an immutable run-id archive:

- `.harness/verification/runs/<run-id>/harness-run-report.json`
- `.harness/verification/runs/<run-id>/harness-run-report.md`
- `.harness/verification/runs/<run-id>/run-manifest.json`
- `.harness/verification/runs/<run-id>/harness-run-diff.json`

The latest files are for quick inspection. The run-id archive is the durable evidence trail for later comparison, review, or regression investigation.

Latest evidence state also includes:

- `.harness/verification/harness-run-manifest.json`
- `.harness/verification/baseline.json`
- `.harness/verification/harness-run-diff.json`

Runtime profiles also write structured NDJSON traces:

- `.harness/verification/phase0-runtime-trace.ndjson`
- `.harness/verification/phase1-slice-runtime-trace.ndjson`

Trace rows always include `sequence`, `source`, `line_number`, `event_type`, `result_id`, `subject`, and `raw`. When a backend JSON payload is present, rows also project stable fields such as `message_type`, `actor_id`, `target_actor_id`, `target_object_id`, `candidate_actor_ids`, `candidate_object_ids`, `room_id`, `scene_id`, `zone_id`, `causation_id`, and `correlation_id`.

Optional executable overrides:

```powershell
python scripts/verification/harness.py --profile phase0 --godot-exe C:\path\to\Godot_console.exe
python scripts/verification/harness.py --profile phase0 --python-exe C:\path\to\python.exe
```

On this workspace, the harness auto-detects `D:\godot\Godot_v4.6.3-stable_win64.exe` when it exists. Use `--godot-exe` only when running from a different Godot install.

## Registry

Harness inputs are versionable project files, while generated evidence stays ignored.

- `.harness/profiles/`: profile manifests. The runner reads profile order, dispatch script, Godot requirement, and narrow runner policy such as per-profile retry budgets from these files.
- `.harness/rules/`: rule manifests. These map stable rule IDs to the profile/check evidence that proves them.
- `.harness/templates/`: starter manifests for future formal product modules.
- `.harness/references/`: adapted external harness reference taxonomies.
- `.harness/evolution/`: versionable evolution config, replay sets, and candidate mutation manifests.
- `.harness/ci/`: release gate metadata and the local CI-equivalent gate.
- `.harness/verification/`: generated evidence, reports, screenshots, logs, traces, and run archives.

Do not add a broad `.harness/` ignore rule. Only generated evidence under `.harness/verification/` should be ignored so profile and rule manifests can be reviewed with the project.

## Profiles

### `docs`

Static documentation freshness checks. Use this before and after edits that touch docs, plans, specs, or harness profile names.

Current mechanical invariants include:

- all local paths referenced by `docs/INDEX.md` exist
- every approved `docs/superpowers/specs/*-design.md` has a matching implementation plan
- specs marked `Status: awaiting-user-review` are allowed to pause at the Superpowers brainstorming review gate before planning
- every harness profile is documented in this guide

Output:

- `.harness/verification/docs-report.json`
- `.harness/verification/docs-report.md`
- `.harness/verification/harness-run-report.json`
- `.harness/verification/harness-run-report.md`

### `boundaries`

Static checks that do not start Godot or the backend. Use this before and after edits that touch docs, protocol boundaries, visual fact routing, or verification scripts.

Current mechanical invariants include:

- docs index and harness guide exist
- visual facts use the approved emitter path
- WebSocket messages keep an explicit envelope model
- harness artifacts use `.harness/verification`
- runtime profiles write structured NDJSON traces
- runtime trace projects stable message and payload fields
- backend parses `player_input` payloads into explicit models
- Godot player input emits structured intents rather than raw controls
- Godot object/environment changes consume backend `world_result` messages
- Siming emits high-level `AttentionPrompt` outputs only
- Siming integrates through the backend authority event bus port and emits concrete high-level event families

Output:

- `.harness/verification/boundary-report.json`
- `.harness/verification/boundary-report.md`
- `.harness/verification/harness-run-report.json`
- `.harness/verification/harness-run-report.md`

### `drift`

Static cleanup checks for local artifact drift and harness test coverage.

Current mechanical invariants include:

- temporary browser/snapshot artifacts are absent from the workspace root
- `.harness/verification/`, Python cache, and pytest cache artifacts are gitignored
- `.harness/profiles/` and `.harness/rules/` remain versionable project inputs
- harness verification helpers have focused tests

Output:

- `.harness/verification/drift-report.json`
- `.harness/verification/drift-report.md`
- `.harness/verification/harness-run-report.json`
- `.harness/verification/harness-run-report.md`

### `backend-contract`

Static backend protocol contract checks. Use this when backend models, WebSocket messages, route handling, or protocol tests change.

Current mechanical invariants include:

- backend protocol model files and explicit WebSocket envelope exist
- cross-boundary contracts use Pydantic `BaseModel` types
- authority event envelope rejects forbidden public fields and legacy flat fields
- backend tests cover protocol shapes and WebSocket boundary behavior

Output:

- `.harness/verification/backend-contract-report.json`
- `.harness/verification/backend-contract-report.md`
- `.harness/verification/harness-run-report.json`
- `.harness/verification/harness-run-report.md`

### `godot-project`

Static Godot project integrity checks. Use this before runtime profiles when scene files, scripts, autoloads, or resource references change.

Current mechanical invariants include:

- `project.godot` declares an existing main scene
- autoload entries point at existing scripts
- scenes and scripts reference existing `res://` resources
- `.blend` source files do not trigger interactive Godot import prompts during harness runs

Output:

- `.harness/verification/godot-project-report.json`
- `.harness/verification/godot-project-report.md`
- `.harness/verification/harness-run-report.json`
- `.harness/verification/harness-run-report.md`

### `character-agent-execution`

Narrow runtime validation for the shared CharacterActor `character_agent_execution` path. Use this when tightening the execution payload seam or proving that Godot still consumes the execution contract instead of the legacy output runtime path.

Current mechanical invariants include:

- Godot connects to the backend during the runtime run
- runtime emits `character_agent_execution`
- runtime payload keeps `controller_source=agent` and `control_mode=agent_controlled`
- runtime payload keeps `focus_state`, `action_state`, and `speech_state`
- runtime proves `CharacterA` is the current `CharacterReplica` consumer for that execution path
- runtime proves `CharacterA.has_external_look_target == true` after the execution contract is consumed
- runtime main path does not fall back to `character_agent_output` handling

Output:

- `.harness/verification/character-agent-execution-report.json`
- `.harness/verification/character-agent-execution-report.md`
- `.harness/verification/character-agent-execution-runtime-trace.ndjson`
- `.harness/verification/harness-run-report.json`
- `.harness/verification/harness-run-report.md`

### `release-gate`

Static CI and release gate checks. Use this when changing harness workflow, release requirements, or CI metadata.

Current mechanical invariants include:

- `.harness/ci/release-gate.json` points at the full `all` profile
- `.github/workflows/harness.yml` exists
- CI invokes `python scripts/verification/harness.py --profile all`
- local CI-equivalent gate exists and invokes the same full harness profile

Output:

- `.harness/verification/release-gate-report.json`
- `.harness/verification/release-gate-report.md`
- `.harness/verification/harness-run-report.json`
- `.harness/verification/harness-run-report.md`

### `harness-lifecycle`

Static lifecycle checks adapted from the `walkinglabs/learn-harness-engineering` Project 06 solution pattern. Use this when changing feature/evidence ledgers, local CI gate behavior, clean-state docs, retention policy, future profile templates, or handoff docs.

Current mechanical invariants include:

- `.harness/features.json` records harness features with pass/evidence entries
- `.harness/ci/local-ci-gate.ps1` runs focused tests, compile, and full harness
- `.harness/templates/` contains profile and rule templates for future modules
- `.harness/retention-policy.json` defines baseline, diff, and run archive handling
- lifecycle quality, handoff, architecture, and reliability docs exist

Output:

- `.harness/verification/harness-lifecycle-report.json`
- `.harness/verification/harness-lifecycle-report.md`
- `.harness/verification/harness-run-report.json`
- `.harness/verification/harness-run-report.md`

### `change-lifecycle`

Static workflow checks for the OpenSpec, Superpowers, Harness, Goal, and native subagent development chain. Use this when changing `AGENTS.md`, workflow docs, Superpowers plan/spec policy, Goal usage, native subagent routing, or reusable harness templates.

Current mechanical invariants include:

- `docs/ai-engineering-workflow.md` exists with matching design and implementation plan artifacts
- `.harness/profiles/change-lifecycle.json` and `.harness/rules/change-lifecycle-rules.json` are registered
- OpenSpec/design, Superpowers, Harness, and Goal handoff rules are documented
- Goal records active task continuity while `.harness` records durable acceptance evidence
- templates require the relevant workflow gates before execution and handoff
- `AGENTS.md` routes large work through Goal, Superpowers, Harness, and native subagents
- archived OpenSpec changes keep required lifecycle files, completed tasks, delta specs, and a Superpowers/Harness evidence link

Output:

- `.harness/verification/change-lifecycle-report.json`
- `.harness/verification/change-lifecycle-report.md`
- `.harness/verification/harness-run-report.json`
- `.harness/verification/harness-run-report.md`

### `harness-reference`

Static external reference coverage checks adapted from `ai-boost/awesome-harness-engineering`. Use this when changing external reference mappings, planning/implementation/checklist templates, or the way this harness documents context, tools, permissions, memory/state, orchestration, verification, observability, debugging, and human-in-the-loop coverage.

Current mechanical invariants include:

- `.harness/references/awesome-harness-engineering.json` records the external taxonomy source
- every required external category maps to current Paralls harness artifacts
- adapted `PLAN.md`, `IMPLEMENT.md`, `HARNESS_CHECKLIST.md`, and `AGENTS.md` templates exist
- docs describe the reference taxonomy and template coverage

Output:

- `.harness/verification/harness-reference-report.json`
- `.harness/verification/harness-reference-report.md`
- `.harness/verification/harness-run-report.json`
- `.harness/verification/harness-run-report.md`

### `harness-evolution`

Governed Harness Evolution Agent checks for the versioned evolution config, replay set, candidate manifest surface, and generated report trail. Use this when changing the evolution lane, candidate governance, or proposal workflow.

Current mechanical invariants include:

- `.harness/evolution/config.json` exists and validates
- `.harness/evolution/replay-sets/default.json` exists and validates
- candidate manifests under `.harness/evolution/candidates/` are schema-valid, harness-scoped, and approval-gated
- `.harness/verification/harness-evolution-report.json` exists after analyzer execution

Analyzer commands:

```powershell
python scripts/verification/analyze_harness_evolution.py --mode analyze
python scripts/verification/analyze_harness_evolution.py --mode propose --candidate-id evo-20260625-example-failure-digest
```

Output:

- `.harness/verification/harness-evolution-report.json`
- `.harness/verification/harness-evolution-report.md`
- optional `.harness/evolution/candidates/<id>.json` in propose mode

### `phase0`

Strict Phase 0 runtime validation. This starts or reuses the backend, runs backend tests, launches the Godot Phase 0 scene, captures logs/screenshots, and evaluates the full Phase 0 acceptance loop.

Use this before claiming Phase 0 runtime completion.

The current profile manifest also carries a retry budget (`max_attempts`) so the harness runner can absorb known intermittent runtime-start flakes without masking persistent failures.

Trace output:

- `.harness/verification/phase0-runtime-trace.ndjson`

### `phase1-slice`

Runtime validation for the current Phase1-shaped slice around visual facts, authority routing, runtime projection, and Siming consumption.

Use this before claiming Phase 0.5 runtime alignment progress.

This profile launches `scenes/phase0/Phase1SliceRuntimeProbe.tscn`, a lightweight Godot probe that uses the existing autoload `BackendBridge` plus the existing L1 raw fact emitters. It avoids `MainDemo.tscn` environment texture imports so clean workspaces do not depend on generated `.godot/imported` cache files for Phase1-slice evidence.

Current mechanical/runtime evidence includes:

- visual fact authority routing remains wired
- Siming event bus pipeline consumes and produces through `AuthorityEventBus`
- LLM-assisted Siming candidate generation is verified with deterministic fake providers
- static boundary audits prove LLM provider calls stay inside `SimingRuntime`

Trace output:

- `.harness/verification/phase1-slice-runtime-trace.ndjson`

### `siming-backend-chain`

Explicit-only backend architecture proof for Siming. This profile does not start Godot and does not rely on frontend `siming_output` projection. It proves deterministic component-chain scenarios and a real app-wiring DeepSeek path through `backend/app/main.py`.

This profile is intentionally excluded from `all` by `include_in_all=false` because it requires a real `SIMING_LLM_API_KEY` and a live DeepSeek request:

```powershell
python scripts/verification/harness.py --profile siming-backend-chain
```

Required configuration:

```env
SIMING_LLM_MODE=http
SIMING_LLM_PROVIDER_ORDER=deepseek_chat
SIMING_LLM_API_KEY=<real DeepSeek key>
SIMING_LLM_ENDPOINT=https://api.deepseek.com/chat/completions
SIMING_LLM_MODEL=deepseek-chat
SIMING_LLM_TIMEOUT_SECONDS=8.0
```

Output:

- `.harness/verification/siming-backend-chain-report.json`
- `.harness/verification/siming-backend-chain-report.md`

### `all`

Runs `docs`, `boundaries`, `drift`, `backend-contract`, `godot-project`, `character-agent-execution`, `release-gate`, `harness-lifecycle`, `change-lifecycle`, `harness-reference`, `harness-evolution`, `phase0`, and `phase1-slice` in order. It stops on the first failed profile.

## Harness Evolution

The Harness Evolution Agent is a governed proposal lane. It reads existing harness telemetry, writes an evolution report, and may create candidate mutation manifests under `.harness/evolution/candidates/`.

It does not apply patches or promote its own proposals. A candidate must be converted into a normal implementation plan, implemented through the repository workflow, and verified through its promotion profiles before it can become operational harness behavior.

First-version candidates may target harness-owned surfaces such as `.harness/`, `scripts/verification/`, `docs/harness.md`, `docs/ai-engineering-workflow.md`, and `.github/workflows/harness.yml`. Product runtime paths such as `backend/`, `scenes/`, character scripts, or Siming runtime modules are outside the mutation scope.

## Decision Observability

Harness-facing changes can be recorded under `.harness/changes/` as decision manifests. These manifests are project inputs, not generated evidence. An active manifest records the evidence that motivated a Harness change, the root-cause hypothesis, predicted fixes, predicted regressions, and the profiles that should verify the change.

The Harness runner includes active manifests in `harness-run-manifest.json` under `harness_changes`. Malformed manifests are reported under `harness_change_errors` so normal profile runs remain usable while evidence problems stay visible.

When a profile fails, the runner writes a deterministic failure digest such as `.harness/verification/phase0-failure-digest.json` and archives the same digest under that run's `.harness/verification/runs/run-.../` directory. A digest is an index into existing reports and traces; it does not replace the original profile report or runtime trace.

## Evidence Rules

- Static checks prove only static wiring.
- Runtime claims require `phase0` or `phase1-slice`.
- Backend-only live Siming/DeepSeek architecture claims require explicit `siming-backend-chain`.
- Godot claims require scene execution or Godot MCP/editor inspection.
- Generated evidence should stay under `.harness/verification/`.
- Profile and rule manifests stay under `.harness/profiles/` and `.harness/rules/`.
- CI/release gate metadata stays under `.harness/ci/`.
- Baseline/diff artifacts are evidence helpers, not source-of-truth design docs.

## Adapted Reference Pattern

This harness adapts the `walkinglabs/learn-harness-engineering` Project 06 solution pattern to Paralls:

- Project 06 `feature_list.json` -> `.harness/features.json`
- Project 06 `init.sh` -> `.harness/ci/local-ci-gate.ps1`
- Project 06 `clean-state-checklist.md` -> `.harness/clean-state-checklist.md`
- Project 06 `session-handoff.md`, quality document, and evaluator rubric -> `.harness/` lifecycle docs
- Project 06 benchmark/cleanup scripts -> Paralls profile reports, drift checks, runtime profiles, and evidence diffing

It also adapts `ai-boost/awesome-harness-engineering` as a reference taxonomy rather than a copied reading list:

- context delivery -> `docs/INDEX.md`, `.harness/session-handoff.md`
- planning artifacts -> `docs/superpowers/plans/`, `.harness/templates/PLAN.md`
- tools/MCP/permissions -> `AGENTS.md`, `.harness/templates/AGENTS.md`, `.harness/templates/HARNESS_CHECKLIST.md`
- memory/state -> Goal, `.harness/features.json`, `.harness/verification/baseline.json`
- agent workflow -> `docs/ai-engineering-workflow.md`, `change-lifecycle`
- verification/CI -> `.github/workflows/harness.yml`, `.harness/ci/local-ci-gate.ps1`
- observability/debugging -> runtime traces, run manifests, baseline, and diff artifacts

## Agent Workflow

1. Read `AGENTS.md`.
2. Read `docs/INDEX.md`.
3. Select the smallest relevant harness profile.
4. Run the profile.
5. Read the generated report before claiming success.
6. If a profile fails, fix the missing invariant or runtime behavior and rerun the same profile.
