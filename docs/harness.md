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
python scripts/verification/harness.py --profile harness-execution-contract
python scripts/verification/harness.py --profile harness-embodied-task
python scripts/verification/harness.py --profile character-behavior-evaluation
python scripts/verification/harness.py --profile character-policy-calibration
python scripts/verification/harness.py --profile phase0
python scripts/verification/harness.py --profile phase1-slice
python scripts/verification/harness.py --profile phase2a-actor-to-gameplay-participation
python scripts/verification/harness.py --profile phase2b-organization-work-lifecycle
python scripts/verification/harness.py --profile phase2c-payroll-operating-window
python scripts/verification/harness.py --profile phase2-bakery-authored-agents
python scripts/verification/harness.py --profile p2dr-authored-bakery-authority-reclosure
python scripts/verification/harness.py --profile phase4a-dynamic-quote-clearing
python scripts/verification/harness.py --profile phase4b-multi-organization-commerce
python scripts/verification/harness.py --profile phase4c-government-credit
python scripts/verification/harness.py --profile phase4d-commercial-ecosystem
python scripts/verification/harness.py --profile phase5a-quest-objective-evidence
python scripts/verification/harness.py --profile phase5b-relationship-reputation-knowledge
python scripts/verification/harness.py --profile phase5c-investigation-stealth-conflict
python scripts/verification/harness.py --profile phase5d-investigation-vertical-slice
python scripts/verification/harness.py --profile post-p5-capability-foundation-docs
python scripts/verification/harness.py --profile post-p5-f1a-foundation
python scripts/verification/harness.py --profile post-p5-f1b-foundation
python scripts/verification/harness.py --profile post-p5-f1c-foundation
python scripts/verification/harness.py --profile post-p5-f2-gates
python scripts/verification/harness.py --profile infra-payroll-operating-window-closure
python scripts/verification/harness.py --profile infra-event-derived-bounded-due-lifecycle-view
python scripts/verification/harness.py --profile infra-economy-government-tax-payment
python scripts/verification/harness.py --profile infra-package-declared-negotiated-exchange
```

`phase2-bakery-authored-agents` is retained as a historical sample profile only. Its direct-batch
verification does not prove an authority-driven P2D close. Use
`p2dr-authored-bakery-authority-reclosure` for the current narrow owner-driven evidence: each of
the nine reported capabilities is an independently selected focused test.

### Phase Four Profiles

- `phase4a-dynamic-quote-clearing`
- `phase4b-multi-organization-commerce`
- `phase4c-government-credit`
- `phase4d-commercial-ecosystem`

### Phase Five Profiles

- `phase5a-quest-objective-evidence`
- `phase5b-relationship-reputation-knowledge`
- `phase5c-investigation-stealth-conflict`
- `phase5d-investigation-vertical-slice`

### Post-P5 Documentation Gate

`post-p5-capability-foundation-docs` is a static documentation gate for the
P5-follow-up foundation. It checks the F0 source ledger, matching formal
spec/plan set, execution prompt, and P6/P7 evidence-aware opening matrix. It
does not prove F0-F2, P6, or P7 runtime completion, and it is intentionally
excluded from `all` until a future implementation plan promotes its runtime
profiles.

`post-p5-f1a-foundation`, `post-p5-f1b-foundation`, and
`post-p5-f1c-foundation` are bounded partial-foundation profiles over existing
owners. `post-p5-f2-gates` aggregates their evidence with fresh P5 reports and
records replay/privacy/zero-write taxonomy. None of these profiles claims the
generic F1 tracks, P6, or P7 are complete.

```powershell
python scripts/verification/harness.py --profile siming-backend-chain
python scripts/verification/harness.py --profile character-model-live
python scripts/verification/harness.py --profile llm-integration-closure
python scripts/verification/harness.py --profile l1-world-fact-runtime
python scripts/verification/harness.py --profile mainline-unified-runtime
python scripts/verification/harness.py --profile model-provider-readiness
python scripts/verification/harness.py --profile godot-sampling-production-grade-providers
python scripts/verification/harness.py --profile embodied-skeletal-debug-replay
python scripts/verification/harness.py --profile tts-voice-profile-adapter
python scripts/verification/harness.py --profile vla-provider-backend
python scripts/verification/harness.py --profile non-runtime-production-pipeline
python scripts/verification/harness.py --profile perception-input-alignment
python scripts/verification/harness.py --profile embodied-interaction-contracts
python scripts/verification/harness.py --profile embodied-affordance-registry
python scripts/verification/harness.py --profile embodied-bridge-attestation
python scripts/verification/harness.py --profile embodied-action-controller
python scripts/verification/harness.py --profile embodied-authority-settlement
python scripts/verification/harness.py --profile embodied-interaction-replay
python scripts/verification/harness.py --profile obj-archive-door-physical-embodiment
python scripts/verification/harness.py --profile gameplay-foundation-contract
python scripts/verification/harness.py --profile gameplay-event-replay
python scripts/verification/harness.py --profile gameplay-foundation-event-spine
python scripts/verification/harness.py --profile gameplay-state-groups
python scripts/verification/harness.py --profile gameplay-resource-body
python scripts/verification/harness.py --profile gameplay-effective-stats
python scripts/verification/harness.py --profile gameplay-status-tags
python scripts/verification/harness.py --profile gameplay-ability-affordance
python scripts/verification/harness.py --profile gameplay-inventory
python scripts/verification/harness.py --profile gameplay-possession-equipment
python scripts/verification/harness.py --profile gameplay-ownership-authority
python scripts/verification/harness.py --profile gameplay-economy-authority
python scripts/verification/harness.py --profile godot-gameplay-mirror
python scripts/verification/harness.py --profile adventure-basic
python scripts/verification/harness.py --profile gameplay-foundation-all
python scripts/verification/harness.py --profile embodied-interaction-session
python scripts/verification/harness.py --profile embodied-handoff-authority
python scripts/verification/harness.py --profile embodied-grab-carry-place-authority
python scripts/verification/harness.py --profile embodied-interaction-foundation-all
python scripts/verification/harness.py --profile siming-heavenly-graph-foundation
python scripts/verification/harness.py --profile siming-six-domain-memory
python scripts/verification/harness.py --profile siming-actor-memory-read
python scripts/verification/harness.py --profile siming-story-runtime
python scripts/verification/harness.py --profile siming-resource-staging
python scripts/verification/harness.py --profile siming-adaptive-bridge
python scripts/verification/harness.py --profile behavior-turn-runtime
python scripts/verification/harness.py --profile character-continuity-recovery
python scripts/verification/harness.py --profile authority-graph-projection
python scripts/verification/harness.py --profile siming-behavior-turn-runtime
python scripts/verification/harness.py --profile siming-led-population-seed-continuity
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
- candidate lifecycle stages are governed; `promotion-ready` and `promoted` candidates require non-empty `qa_review_artifacts`
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

### `character-behavior-evaluation`

Backend-only replay of one character turn. It proves the durable evidence chain
from L2 context and interpretation through goal/intent, execution request,
authoritative settlement, behavior score, and source-linked candidate policy.
Candidates are `candidate_only`; this profile never mutates authored character
profiles.

Output:

- `.harness/verification/character-behavior-evaluation-report.json`
- `.harness/verification/character-behavior-evaluation-report.md`

### `character-policy-calibration`

Backend-only calibration proof for context-recall and recovery candidates. It
checks that a low-scoring turn yields a deterministic policy candidate with
`context_hash`, selected memory refs, and an explicit hypothesis while keeping
profile mutation outside runtime evaluation.

Output:

- `.harness/verification/character-policy-calibration-report.json`
- `.harness/verification/character-policy-calibration-report.md`

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

### `l1-world-fact-runtime`

Compatibility runtime-verification profile for the System L1 world fact subsystem. The profile name is historical and means "verify the runtime-facing integration"; it is not permission to introduce a product `L1Runtime`.

This profile verifies that L1 is wired as services on the existing `world_runtime` / ESM / `raw_fact_event` / candidate / private percept / character or Siming runtime chain, not as a second runtime loop or parallel fact bus.

Hard boundary:

- do not add an L1 main loop
- do not add an L1 event bus
- do not add an L1 scheduler
- do not add L1 authority
- do not bypass `raw_fact_event -> candidate percept -> CharacterPerceivedEvent`

Current proof includes:

- `Scene3DSpaceModel` extraction artifacts with Godot node path, group/metadata, collision-shape, and navigation/walkable source refs
- `SpatialOccupancyField` / `SpatialOccupancyService` dirty-zone/event-driven updates for actor zone, object state, and environment field changes
- environment field merge into L1 projection inputs
- `FactProjectionLayer` outputs for LOS, reachability, affordance, and negative facts using existing `raw_fact_event` shape
- projected facts entering candidate/private percept path unless explicitly system-only
- provider runtime source refs for visual, spatial, auditory, and embodied inputs
- real `PerceptionQueryFrame` / `CanonicalPerceptBundle` backend assembly and character or Siming runtime consumption
- optional Godot probe evidence from `scenes/phase0/L1WorldFactRuntimeProbe.tscn`

If Godot cannot be launched, the report marks `godot-runtime-unverified`; do not use that state to claim a fully Godot-verified L1 subsystem integration.

Output:

- `.harness/verification/l1-world-fact-runtime-report.json`
- `.harness/verification/l1-world-fact-runtime-report.md`
- `.harness/verification/l1-space-model-runtime.json` when the Godot probe runs
- `.harness/verification/l1-space-model-backend-contract.json` for backend contract proof
- `.harness/verification/harness-run-report.json`
- `.harness/verification/harness-run-report.md`

### `harness-execution-contract`

Backend-only Harness contract proof for the domain-neutral task lifecycle and
trace seam. It verifies the declared execution phases, deterministic failure
disposition mapping, terminal-phase write rejection, and preservation of
`task_id`/`run_id`/`correlation_id` across an append-only process-local trace.
It does not execute Gameplay or ESM commands, persist tasks, or provide
automatic retries.

Run:

```powershell
python scripts/verification/harness.py --profile harness-execution-contract
```

Output:

- `.harness/verification/harness-execution-contract-report.json`
- `.harness/verification/harness-execution-contract-report.md`

### `harness-embodied-task`

Backend proof that the Harness contract is consumed by the real embodied
interaction session path. It covers the Gameplay authority append, outbox and
evidence correlation, domain failure mapping, persistent terminal recovery,
phase capability ordering, metadata redaction, and safe Godot projection refs.
The existing `embodied-interaction-session` profile remains the runtime/Godot
proof; this profile verifies the Harness control/evidence layer around it.

```powershell
python scripts/verification/harness.py --profile harness-embodied-task
```

Output:

- `.harness/verification/harness-embodied-task-report.json`
- `.harness/verification/harness-embodied-task-report.md`

### `siming-backend-chain`

Explicit-only backend architecture proof for Siming. This profile does not start Godot and does not rely on frontend `siming_output` projection. It proves deterministic component-chain scenarios and real app-wiring model-provider paths through `backend/app/main.py`.

This profile is intentionally excluded from `all` by `include_in_all=false` because live provider proof requires real model credentials and network calls. By default it still requires the legacy DeepSeek live proof:

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

Qwen and Seed/Doubao live proofs are additive, not replacements for DeepSeek. Require them explicitly with `--live-provider` or `SIMING_BACKEND_CHAIN_LIVE_PROVIDERS`:

```powershell
python scripts/verification/verify_siming_backend_chain.py --live-provider deepseek_chat --live-provider qwen --live-provider seed_doubao
```

Provider-specific environment variables are preferred for the additive matrix:

```env
SIMING_LLM_QWEN_API_KEY=<real Qwen key>
SIMING_LLM_QWEN_ENDPOINT=https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
SIMING_LLM_QWEN_MODEL=qwen3.7-plus

SIMING_LLM_SEED_DOUBAO_API_KEY=<real Seed/Doubao key>
SIMING_LLM_SEED_DOUBAO_ENDPOINT=<real Seed/Doubao chat-completions endpoint>
SIMING_LLM_SEED_DOUBAO_MODEL=doubao-seed-2.0-pro
```

For actual runtime multi-route configuration, set `SIMING_LLM_ROUTES_JSON` to a JSON array of route objects using providers `deepseek_chat`, `qwen`, and `seed_doubao`. Route-level keys are excluded from settings dumps.

Output:

- `.harness/verification/siming-backend-chain-report.json`
- `.harness/verification/siming-backend-chain-report.md`

### `character-model-live`

Explicit-only real-provider proof for Character dialogue, L2 reasoning, and L3 planning. This profile is excluded from `all` because it requires live model credentials and network access.

Required configuration uses only the canonical Character runtime surface:

```env
DIALOGUE_MODE=online
CHARACTER_MODEL_PROVIDER_KIND=deepseek
CHARACTER_MODEL_ENDPOINT=https://api.deepseek.com
CHARACTER_MODEL_API_KEY=<real Character model key>
CHARACTER_MODEL_MODEL=deepseek-chat
CHARACTER_MODEL_TIMEOUT_SECONDS=30.0
```

Provider-specific aliases such as `DEEPSEEK_*` and `QWEN_*` are not consumed by the Character runtime. The verifier rejects `DIALOGUE_MODE=stub`, non-DeepSeek provider identity, missing `CHARACTER_MODEL_API_KEY`, and `CHARACTER_MODEL_ROUTE_OVERRIDE`.

`CHARACTER_DIALOGUE_CASCADE_LIMIT` is an optional runtime safety fuse for autonomous character-to-character reply cascades. It defaults to `180`, which is intended to support extended room dialogue while still preventing unbounded recursive reply loops.

Output:

- `.harness/verification/character-model-live-report.json`
- `.harness/verification/character-model-live-report.md`

### `script-evolution-proof`

Static proof that script-evolution rules and their regression coverage remain
present. This profile is part of the normal registry order and should be run
when changing governed script-evolution behavior.

### `siming-heavenly-graph-foundation`

Backend proof for namespace-safe, owner-isolated, bi-temporal, bounded,
restart-durable Heavenly Graph adapters.

```powershell
python scripts/verification/harness.py --profile siming-heavenly-graph-foundation
```

### `heavenly-graph-semantic-foundation`

Graph-only proof for the semantic Heavenly Graph foundation. This focused
profile uses a verifier-owned temporary SQLite database and checks adapter
parity, semantic metadata, explicit scope denial, bounded reads, stale-write
rejection, append-only correction chains, branch isolation, and checkpoint
replay digest equivalence. It does not use role, Siming runtime, LLM, or Godot
evidence.

Semantic relations may carry explicit source and target endpoint scopes.
Cross-namespace relations are admitted only when both endpoint scopes are
present and each endpoint passes referential-integrity and visibility checks.
Legacy same-scope relations remain compatible when those fields are absent.

```powershell
python scripts/verification/harness.py --profile heavenly-graph-semantic-foundation
```

Output:

- `.harness/verification/heavenly-graph-semantic-foundation-report.json`
- `.harness/verification/heavenly-graph-semantic-foundation-report.md`

### `behavior-turn-runtime`

Backend proof for the first shared typed behavior turn（行为回合）runtime
vertical. It records one character-owned eight-stage chain, preserves accepted
and rejected Authority settlement outcomes as actor-private projections, and
proves scope isolation plus idempotent recorder replay.

This profile does not prove character restart continuity, Siming turn
integration, six-domain Authority projection, online LLM execution, or Godot
presentation.

```powershell
python scripts/verification/harness.py --profile behavior-turn-runtime
```

Output:

- `.harness/verification/behavior-turn-runtime-report.json`
- `.harness/verification/behavior-turn-runtime-report.md`

### `character-continuity-recovery`

Backend proof that dynamic state, need/tension, goal state, continuity state,
working memory, and the next session input rebuild from an actor-private graph
snapshot after the legacy session timeline file is removed. This profile does
not prove Siming, six-domain Authority projection, online LLM, or Godot closure.

```powershell
python scripts/verification/harness.py --profile character-continuity-recovery
```

### `authority-graph-projection`

Backend proof for committed Authority events projected into Heavenly Graph
across ESM/world, Inventory, Ownership, Economy, Survival/body, and
resource/scene domains, retaining owner, source vector, settlement, and replay
linkage. It does not prove online LLM or Godot closure.

```powershell
python scripts/verification/harness.py --profile authority-graph-projection
```

### `siming-behavior-turn-runtime`

Backend proof that `SimingRuntime.tick(...)` uses the shared eight-stage
behavior-turn contract on its decision path. It does not prove online LLM or
Godot closure.

```powershell
python scripts/verification/harness.py --profile siming-behavior-turn-runtime
```

### `siming-led-population-seed-continuity`

Backend-only direct profile for the bounded Siming-led bakery population seed handoff. It proves
one game-start cadence entering the existing `SimingRuntime.tick()` path, Organization owner
settlement, Character Core seed continuity, and player-triggered activation of the same character
identity. It also checks full versus checkpoint-tail replay and stale/private/duplicate/unknown
zero-write cases.

```powershell
python scripts/verification/harness.py --profile siming-led-population-seed-continuity
```

Output:

- `.harness/verification/siming-led-population-seed-continuity-report.json`

The manifest intentionally keeps `include_in_profile_order=false` and `include_in_all=false`.
Run it directly by name; aggregate profiles do not include this bounded evidence yet.

### `siming-heavenly-runtime`

Godot-required live proof for the complete Siming heavenly runtime. It requires
an active online HTTP provider, a verifier-owned SQLite database, all 17 result
IDs, and three meaningful Godot captures. Preflight output contains only
presence booleans, route IDs, and model names.

```powershell
python scripts/verification/verify_siming_heavenly_runtime.py --preflight
python scripts/verification/harness.py --profile siming-heavenly-runtime
```

Output:

- `.harness/verification/siming-heavenly-runtime-report.json`
- `.harness/verification/siming-heavenly-runtime-report.md`

### `siming-six-domain-memory`

Backend proof that all six durable Siming memory domains persist through a
SQLite restart, that a fresh compiler reconstructs the same bounded context
without a summary cache, and that compatibility projections remain derived
read models rather than canonical graph truth.

```powershell
python scripts/verification/harness.py --profile siming-six-domain-memory
```

### `siming-actor-memory-read`

Backend proof that `char_b` persists actor-private graph memory, `char_a`
remains light-store backed, restart recalls `char_b`, and Siming reads only
through the revision-vector gateway.

```powershell
python scripts/verification/harness.py --profile siming-actor-memory-read
```

### `siming-story-runtime`

Backend proof that immutable authored blueprints remain separate from
branch-scoped runtime nodes, Authority-confirmed evidence closes terminal paths,
obligations transform without false fulfillment, and fresh causal basis can
reopen an alternate attractor route without resurrecting the closed instance.

```powershell
python scripts/verification/harness.py --profile siming-story-runtime
```

### `siming-resource-staging`

Backend and repository-static proof that existing MainDemo resources can be
reused by distinct story semantics, exact-signature fatigue remains narrow, a
resource score cannot bypass story hard gates, and Godot/Character/ESM staging
acknowledgements preserve truthful node and obligation state.

```powershell
python scripts/verification/harness.py --profile siming-resource-staging
```

### `siming-adaptive-bridge`

Backend proof that a deterministic typed proposal is grounded in existing
facts, char_b's observed memory, an open O6 obligation, and an available
resource package. It proves no terminal branch is resurrected, actor-private
memory remains read-only, and acceptance creates one latent runtime node. This
profile does not make a live LLM call.

```powershell
python scripts/verification/harness.py --profile siming-adaptive-bridge
```

### `llm-integration-closure`

Explicit-only fresh-evidence aggregator for the approved LLM closure claims. It reads existing reports and does not make provider calls. It passes only when one `LLM_CLOSURE_RUN_ID` binds:

- model-provider readiness identity
- `dialogue_live_deepseek`
- `l2_live_deepseek`
- `l3_live_deepseek`
- `app_wiring_live_deepseek_chain`

Readiness remains non-live evidence; the closure report keeps `readiness_is_live_proof=false`.

Output:

- `.harness/verification/llm-integration-closure-report.json`
- `.harness/verification/llm-integration-closure-report.md`

### `model-provider-readiness`

Static/readiness verification for current project model provider entry points. This profile does not start Godot and does not use mock providers as completion evidence.

Current proof includes:

- a redacted model provider ledger for `character_text`, `siming_candidate`, `vla_spatial`, and `production_multimodal`
- clear status separation between `disabled`, `blocked_missing_credentials`, `blocked_missing_artifacts`, `http_configured_unverified`, `contract_ready`, and `real_provider_verified`
- Qwen/Seed/Doubao preferred configuration examples without API key leakage
- boundary evidence that model outputs cannot directly write world truth, ESM authority, object/environment state, body state, or shared private context/cache/history

Output:

- `.harness/verification/model-provider-readiness-report.json`
- `.harness/verification/model-provider-readiness-report.md`

### `godot-sampling-production-grade-providers`

Runtime and backend verification for production-grade Godot sampling provider refs.

Current proof includes:

- visual, spatial, auditory, embodied, skeletal, and environment provider refs from a Godot runtime probe
- provider sample status, freshness, throttle, retention, stable source refs, and structured failure fields
- schema-valid `PerceptionQueryFrame` assembly from provider refs
- no heavy inference, heavy voxelization, or full-scene runtime rescan in providers
- debug replay retention for skeletal snapshot refs

Output:

- `.harness/verification/godot-sampling-production-grade-providers-report.json`
- `.harness/verification/godot-sampling-production-grade-providers-report.md`
- `.harness/verification/godot-sampling-production-grade-providers-runtime.json`

### `embodied-skeletal-debug-replay`

Runtime and backend verification for the embodied skeletal debug replay pipeline.

Current proof includes:

- Godot runtime binding from `PlayerCharacter` to `CharacterReplica` and a real `Skeleton3D`
- high-level embodied state and mid-level skeletal parameters entering the main perception payload
- anchor refs, facing vectors, reach envelope, balance/strain hints, hand readiness, contact candidates, and pose feature tags
- full bone snapshot exclusion from the main chain
- `.harness/verification/skeletal-replay-*.json` debug replay artifacts with `debug_replay_only` retention and failure trace refs

Output:

- `.harness/verification/embodied-skeletal-debug-replay-report.json`
- `.harness/verification/embodied-skeletal-debug-replay-report.md`
- `.harness/verification/embodied-skeletal-debug-replay-runtime.json`

### `tts-voice-profile-adapter`

Backend-only proof for the presentation-only TTS voice-profile adapter.

Current proof includes:

- `tts_voice_profile.v1` catalog/binding parsing, adapter provider-model-catalog
  capability compatibility, configured catalog-revision pinning,
  required-language rejection, legacy-map fallback, and provider-call blocking
  on invalid bindings
- controlled first-worksheet XLSX catalog normalization with explicit provider,
  model, and catalog-revision inputs; malformed and duplicate voice IDs reject
- deterministic advisory candidate ranking from explicit presentation criteria
  only; ranking cannot create or approve a runtime binding
- authorized-source enrollment validation and its non-approved candidate handoff

It does not make a live synthesis call, audition voices, approve a production
binding, derive expressive instructions from runtime cognition, or change
dialogue/authority state.

Output:

- `.harness/verification/tts-voice-profile-adapter-report.json`
- `.harness/verification/tts-voice-profile-adapter-report.md`
- `.harness/verification/tts-voice-profile-adapter-pytest.log`

### `vla-provider-backend`

Backend verification for the advisory-only VLA provider slow path. It verifies the OpenAI-compatible adapter contract with a stubbed HTTP transport, but does not claim real Qwen3-VL or Seed provider verification without a credentialed, explicit live proof.

Current proof includes:

- `PerceptionQueryFrame` to `VLAProviderRequest` conversion using artifact refs and structured fact refs only
- advisory-only `VLAProviderResult` validation
- Qwen3-VL and Seed model registry entries with license/deployment/runtime boundary metadata
- per-owner slow-path scheduler queues with character/Siming separation, timeout/degrade traces, dedupe, stale discard, and max queue behavior
- cache keys with context namespace, artifact refs hash, structured fact refs hash, model version, and freshness checks
- `VLAProviderResult -> ModalityInterpretationResult -> CrossModalUnderstandingResult -> CanonicalPerceptBundle` advisory bridge
- OpenAI-compatible non-streaming request formation from PQF plus eligible direct image artifact refs; opaque refs fail closed without a network call
- provider response projection that discards action, authority, world-state, and actor-control fields
- explicit real-provider readiness states such as `blocked_missing_credentials`, `configured_unverified`, or `real_provider_verified`

Output:

- `.harness/verification/vla-provider-backend-report.json`
- `.harness/verification/vla-provider-backend-report.md`
- `.harness/verification/vla-provider-backend-trace.json`

The explicit-only external proof command is:

```powershell
python scripts/verification/verify_vla_provider_live.py --allow-live-call
```

It requires `VLA_PROVIDER_*` credentials, an eligible URL or repository-local
image path, and a non-empty `VLA_PROVIDER_LIVE_PROOF_RUN_ID`. For actual Godot
viewport evidence, first run `verify_godot_sampling_production_grade_providers.py`
with a Godot console executable, then run
`verify_vla_provider_live.py --allow-live-call --use-godot-runtime-capture`.
That mode rejects missing, stale, or runtime-report-mismatched captures and
redacts inline image data from its report. It writes
`vla-provider-live-report.*`; readiness promotes only a matching provider/model/
endpoint/run evidence record, and a blocked report is not a verified-provider claim.

The default benchmark follows the online `fast-only` policy:

```powershell
python scripts/verification/benchmark_vla_advisory_routes.py --allow-live-call --samples 3
```

It replays the fresh Godot capture through `advisory-fast` and archives only
redacted per-attempt reports. Fewer than 20 samples are explicitly insufficient
for latency-percentile or semantic-quality claims. To compare the parked deep
route, opt in to both routes explicitly:

```powershell
python scripts/verification/benchmark_vla_advisory_routes.py --allow-live-call --route advisory-fast --route advisory-deep --samples 3
```

To replay a reviewed scene with its own PQF scope instead of MainDemo defaults:

```powershell
python scripts/verification/benchmark_vla_advisory_routes.py --allow-live-call --route advisory-fast --annotation-sample-id throne-hall-walk-preview-001 --samples 3
```

The review-control baseline is verified with:

```powershell
python scripts/verification/verify_vla_replay_annotations.py
```

Its initial MainDemo annotation is intentionally bootstrap-only. It validates
that scene truth is human-reviewed and that PQF/structured facts cannot receive
model credit; it does not certify multi-scene coverage or semantic accuracy.

The second reviewed capture is obtained with:

```powershell
python scripts/verification/verify_vla_replay_second_scene_capture.py --godot-exe <Godot-console-exe>
```

The verifier rejects nonempty but visually flat viewport files; successful output
is only a candidate for human annotation, not provider-quality proof.

### `actor-scene-knowledge-lifecycle`

Backend verification for actor-private Actor Scene Knowledge lifecycle and active perception.

Current proof includes:

- actor/session/scene-isolated ASK entries
- revision, conflict, stale, and expiry lifecycle behavior
- VLA advisory conflict recording without overwriting L1 projected fact truth
- active perception requests returning to `PerceptionQueryFrame` and provider refs

Output:

- `.harness/verification/actor-scene-knowledge-lifecycle-report.json`
- `.harness/verification/actor-scene-knowledge-lifecycle-report.md`
- `.harness/verification/actor-scene-knowledge-lifecycle-trace.json`

### `siming-global-situation-layer`

Backend verification for Siming's global situation layer.

Current proof includes:

- global situation snapshots assembled from public L1 facts, authority events, world results, environment/evidence events, VLA global advisory findings, and multi-actor patches
- `siming_mm:*` context isolation and character private cache rejection
- visibility imbalance, fairness pressure, evidence chain, and intervention candidate evidence
- advisory findings enhancing pressure/conflict metadata without overriding world truth

Output:

- `.harness/verification/siming-global-situation-layer-report.json`
- `.harness/verification/siming-global-situation-layer-report.md`
- `.harness/verification/siming-global-situation-layer-trace.json`

### `interaction-orchestration-service`

Backend verification for structured interaction orchestration.

Current proof includes:

- semantic-only, physical-only, mixed, denied-by-constraint, requires-active-perception, and requires-authority-confirmation policies
- semantic-only path using existing ESM settlement
- structured intent boundary that rejects raw keyboard/mouse/camera noise
- mixed semantic/physical merge into one unified result family
- degrade paths that do not apply physical effects

Output:

- `.harness/verification/interaction-orchestration-service-report.json`
- `.harness/verification/interaction-orchestration-service-report.md`
- `.harness/verification/interaction-orchestration-service-trace.json`

### `esm-physical-channel-world-actuation`

Backend and Godot runtime verification for the ESM physical channel.

Current proof includes:

- contact, push, pull, carry, grab, and blocking physical effect kinds
- Godot runtime adapter/probe scene that emits structured contact/body/object/environment refs only
- constraint failures preventing physical effect application
- object/environment/body state observation refs visible in the unified result family
- mixed physical effects entering through Interaction Orchestration Service

Output:

- `.harness/verification/esm-physical-channel-world-actuation-report.json`
- `.harness/verification/esm-physical-channel-world-actuation-report.md`
- `.harness/verification/esm-physical-channel-world-actuation-trace.json`
- `.harness/verification/esm-physical-channel-godot-runtime.json`

### `non-runtime-production-pipeline`

Backend/offline verification for the non-runtime production pipeline. This profile does not start Godot and does not claim runtime completion.

Current proof includes:

- scene semantic draft, spatial bake, multimodal classification, affordance annotation, review report, and replay dataset artifact contracts
- `draft` / `review` / `approved` / `rejected` review gate states
- approved artifacts can become reviewed L1 seed inputs or verification replay datasets
- rejected drafts are blocked from runtime, L1 seed, and replay dataset consumption
- runtime private context, private cache, and inference history markers are rejected
- production multimodal model status follows `model-provider-readiness`; mock providers are not accepted as completion evidence

Output:

- `.harness/verification/non-runtime-production-pipeline-report.json`
- `.harness/verification/non-runtime-production-pipeline-report.md`
- `.harness/verification/non-runtime-production-pipeline-trace.json`

### `perception-input-alignment`

Backend verification for the perception identity alignment behavior matrix. This profile does not start Godot and does not claim visual model quality; it proves capture/object/view/advisory/Siming identity behavior from structured facts, provider refs, PQFs, canonical bundles, and downstream read models.

Current proof includes:

- fact chain and provider chain same capture/same object resolve to one `world_anchor_id`
- fact chain and provider chain across captures are not treated as same tick
- actor A/B same capture can share an object anchor while retaining different private attributes
- actor A/B same capture looking at nearby different objects retain separate object anchors
- VLA slow-path timeout keeps capture identity but marks itself `late_advisory`
- Siming multi-actor summary retains object and time identity

Output:

- `.harness/verification/perception-input-alignment-report.json`
- `.harness/verification/perception-input-alignment-report.md`
- `.harness/verification/perception-input-alignment-matrix-trace.json`

### `embodied-interaction-contracts`

Backend-only Phase 0 verification for the embodied-interaction product foundation contract freeze. This profile does not start Godot and does not claim local controller/runtime completion.

Current proof includes:

- `EmbodiedActionRequest` rejects raw input, node-path, bone, rigid-body, and world-truth fields
- `LocalExecutionOutcome` requires controller grant, connection epoch, terminal sequence, nonce, and digest attestation
- `SceneAffordanceRecord` preserves reviewed grounding catalog entity/collider/anchor IDs
- first-closure settlement selects only `esm_compatibility_adapter` for `kick-chair`
- cross-domain writer requests fail closed until `gameplay_event_batch_writer` exists
- public Observatory projection is field-level allowlist filtered

Output:

- `.harness/verification/embodied-interaction-contracts-report.json`
- `.harness/verification/embodied-interaction-contracts-report.md`
- `.harness/verification/embodied-interaction-contracts-trace.json`

### `embodied-affordance-registry`

Backend and Godot runtime verification for Phase 1 `SceneAffordanceRegistry`.

Current proof includes:

- reviewed `chair_01` record resolves through catalog-backed entity/collider/anchor IDs
- registry resolution pins `scene_instance_id`, binding revision, required anchors, and affordance ID
- stale revision, missing collider, stale occupancy, unknown affordance, and cross-scene binding fail before controller start
- public and controller projections expose different field sets
- Godot runtime probe uses `SceneSpaceModelExtractor` and `RuntimeOccupancySampler` to resolve the same `chair_01` binding
- VLA advisory conflict is recorded without overwriting known registry truth
- the actual default-main-scene `obj_letter` fixture resolves through reviewed
  grounding refs, collider/anchors, and local registry preflight; the same
  bridge contract also has Godot-runtime-verified `obj_plaque` `inspect/read`,
  `obj_lamp_switch` `press`, stateful `obj_archive_door` `open_close`, and
  stateful single-actor `obj_worktable` `use` / `finish_use`, actor-scoped
  `obj_observation_bench` `sit` / `stand`, custody-only
  `obj_archive_token` `grab`, and restricted `stow_intent` presentation
  bindings
- real ESM websocket success and distance-constraint coverage exist for
  `obj_letter`; the `obj_plaque` ESM policy has focused success/rejection tests,
  and the switch path proves `switch: idle -> activated` plus its approved lamp
  environment result. The door path proves `door: closed -> open -> closed`
  and an authority state mismatch constraint. The worktable path proves
  `work_surface: ready -> engaged -> ready` and its state mismatch constraint;
  it does not claim seating, shared occupancy, ownership, occlusion, or
  animation. The bench path proves owner-only `stand` and
  `posture: standing -> seated -> standing`; it does not claim seated
  animation, shared seat allocation, or session semantics. The token path
  resolves world refs from backend policy, rejects unsafe/non-authoritative
  inputs, and changes presentation only after an authority-only carry/place
  directive. Its restricted stow continuation resolves asset/item/backpack
  server-side, atomically commits custody/location/evidence, and advances the
  local marker only for an accepted `authority_only` directive; it does not
  prove scene container/retrieve, inventory UI, ownership, hand animation, or
  generalized pickup/store. All seven local displays change only from an authority
  `object_state_result`, and a later constraint result leaves current local
  state unchanged.

Output:

- `.harness/verification/embodied-affordance-registry-report.json`
- `.harness/verification/embodied-affordance-registry-report.md`
- `.harness/verification/embodied-affordance-registry-trace.json`
- `.harness/verification/embodied-affordance-registry-godot-runtime.json`
- `.harness/verification/default-scene-letter-affordance-godot-runtime.json`

### `embodied-bridge-attestation`

Backend and Godot runtime verification for Phase 2 embodied transport and controller attestation.

Current proof includes:

- `trusted_local_launch` is loopback-only, one-time, actor/controller scoped, and expires
- `authenticated_session` remains fail-closed until a production verifier adapter is configured
- controller binding issues monotonic connection epochs
- execution grants require grant ID, controller binding, epoch, nonce, terminal sequence, payload digest, and revocation state
- duplicate phase/outcome messages are idempotent only when the digest matches
- reconnect/epoch revocation prevents old local motion from resuming
- realization route gate prevents one attempt from starting both `legacy_character_replica` and `embodied_controller_v1`
- Godot `BackendBridge` has dedicated embodied routes and does not use `character_actor_status` as the embodied outcome channel

Output:

- `.harness/verification/embodied-bridge-attestation-report.json`
- `.harness/verification/embodied-bridge-attestation-report.md`
- `.harness/verification/embodied-bridge-attestation-godot-runtime.json`

### `embodied-action-controller`

Godot runtime verification for Phase 3 `EmbodiedActionController` and local observation.

Current proof includes:

- local state machine phases from target acquisition through recover/terminal
- grant, connection epoch, nonce, route, and terminal sequence fields retained in terminal observations
- success emits bounded contact/object observation
- miss, no-path, fixed-target, target-moved, cancelled, failed-alignment, and occupied-stance paths emit distinct terminal statuses
- failure paths restore local ownership
- runtime uses Godot `NavigationAgent3D` and `CollisionShape3D` classes in the probe
- no `character_actor_status`, raw bone stream, raw rigid-body stream, or impulse transport is present in the controller script

Output:

- `.harness/verification/embodied-action-controller-report.json`
- `.harness/verification/embodied-action-controller-report.md`
- `.harness/verification/embodied-action-controller-godot-runtime.json`

### `embodied-authority-settlement`

Backend-only verification for Phase 4 authority settlement from an attested local physical observation.

Current proof includes:

- fabricated, stale-epoch, duplicate, missing-contact, target-mismatched, and revision-conflict observations produce zero unintended mutation
- valid `kick-chair` contact settles exactly once through `esm_compatibility_adapter`
- duplicate terminal observation returns the original receipt without a second physical-channel application
- settlement writer kind is recorded and no dual-write path exists
- cross-domain writer requests fail closed until `gameplay_event_batch_writer` exists

Output:

- `.harness/verification/embodied-authority-settlement-report.json`
- `.harness/verification/embodied-authority-settlement-report.md`
- `.harness/verification/embodied-authority-settlement-trace.json`

### `embodied-interaction-replay`

Backend and Godot runtime verification for Phase 5 `kick-chair` closure and evidence replay.

Current proof includes:

- backend-assigned `server_ledger_sequence` orders request, registry binding, controller phase, terminal observation, settlement, and presentation
- source sequence duplicate-with-same-digest is idempotent, duplicate-with-different-digest rejects, and source gaps reject
- public Observatory projection filters private participant terms and VLA prompt context
- Godot runtime probe shows chair state changing only after backend settlement projection
- failure path produces no visible world-state change
- screenshot and JSON artifacts are written for runtime inspection

Output:

- `.harness/verification/embodied-interaction-replay-report.json`
- `.harness/verification/embodied-interaction-replay-report.md`
- `.harness/verification/embodied-interaction-replay-ledger-trace.json`
- `.harness/verification/embodied-kick-chair-vertical-slice-godot-runtime.json`
- `.harness/verification/embodied-kick-chair-vertical-slice.png`

### `obj-archive-door-physical-embodiment`

Real MainDemo-wrapper verification for the reviewed `obj_archive_door` physical
embodiment vertical slice. It starts a localhost backend, obtains a one-time
trusted-local embodied-controller enrollment, and runs the Godot probe through
the real WebSocket route. It is distinct from the existing semantic door probe:
success requires physical PlayerShell approach/align, registered atoms,
reachable local hand/anchor alignment, settlement-gated door presentation, and
correlated attempt/grant/settlement/ledger evidence.

The profile runs four scenarios: authoritative open, preflight
`out_of_range`, stale binding/revision rejection, and `stance_occupied`. Each
failure must show local recovery and a closed door without a world-result
write. A scenario is accepted only when its Godot runtime payload, viewport
screenshot, backend settlement trace, and replay trace agree. It does not
permit a local animation or an older semantic probe to stand in for authority
or physical proof.

Output:

- `.harness/verification/obj-archive-door-physical-embodiment-report.json`
- `.harness/verification/obj-archive-door-physical-embodiment-report.md`
- `.harness/verification/obj-archive-door-physical-embodiment-runtime.json`
- `.harness/verification/obj-archive-door-physical-embodiment-backend-settlement-trace.json`
- `.harness/verification/obj-archive-door-physical-embodiment-replay-trace.json`
- `.harness/verification/obj-archive-door-physical-embodiment-*.png`

### `gameplay-foundation-contract`

Backend-only contract proof for the Gameplay Foundation authority event store and atomic event-batch writer.

Current proof includes:

- `append_batch` commits events, idempotency results, and outbox entries atomically
- duplicate idempotency key plus same payload digest returns the original result without new events
- duplicate idempotency key plus different payload digest rejects with zero mutation
- stream revision conflicts reject the whole batch
- invalid event schema and outbox projection construction failures are typed and non-mutating

Output:

- `.harness/verification/gameplay-foundation-contract-report.json`
- `.harness/verification/gameplay-foundation-contract-report.md`
- `.harness/verification/gameplay-foundation-contract-pytest.log`

The 2026-08-07 Phase One Gameplay closure extends this profile with shared
identity/semantic/revision/replay/permission focused tests and emits:

- `.harness/verification/gameplay-foundation-contract-evidence.ndjson`

### `phase1b-contract-verification`

P1B reuses the shared contract through deterministic effect/resistance and
object/ownership fixtures. It fails closed when the P1A predecessor is absent,
records stale-revision zero-write checks, and emits JSON/Markdown/NDJSON evidence.

### `phase1c-frost-farm`

Bounded frost-farm environment-effect and resistance sample. The package owns
only farm/crop facts and maps accepted results through the existing event store;
it does not own weather, Survival, or a scheduler.

### `econ1-construction-production`

Proves plot, facility, recipe, and explicit production-run ownership for the
bakery reference configuration.

### `econ1-survival-profile`

Proves disabled/narrative/lightweight/simulation Survival mode boundaries and
proposal-only consumption ticks.

### `econ1-economy-period-settlement`

Proves fixed supplier quote validation and three deterministic business-period
closures without dynamic market or order-book state.

### `econ1-organization-government`

Proves permit, inspection, tax-policy, organization-role, and existing-character
constraints.

### `phase1d-econ1-bakery`

Composes the four Econ-1 owner profiles into three replayable bakery periods, runs
the failure/recovery and stale/duplicate matrix on isolated/committed ledgers, checks
full/checkpoint-tail replay equality, and requires a real Godot headless probe to
consume the committed facility/output mirror view. It records the explicit
deferred-domain non-claims. Pass `--godot-exe` (or set `GODOT_EXE`) because this
profile is `requires_godot: true`.

### `phase1e-generalization-gate`

Compares Frost Farm, Bakery, and ownership-contract-debt fixtures for shared
contract fields, owner boundaries, profile-backed CharacterRecord input,
full/checkpoint-tail replay equality, scope-filtered projection, stale/duplicate/
permission/custody/term zero-write failures, and deferred scopes.

### `phase5a-quest-objective-evidence`

Backend-only phase-gate proof for the P5A quest objective evidence authority
slice.

It runs:

- `backend/tests/test_p5_quest_evidence.py`
- `backend/tests/test_p5_contracts.py`
- `backend/tests/test_gameplay_p5_batch_contract.py`

Current proof includes:

- committed provenance from the canonical evidence/objective event pair
- explicit permission redaction, objective visibility, event visibility, and hidden-evidence rejection evidence
- committed decision receipt plus duplicate idempotency replay evidence
- full replay and checkpoint-tail replay hash equivalence for the committed event log
- typed zero-write rejection evidence for the hidden-visibility failure path

Command:

```powershell
python scripts/verification/harness.py --profile phase5a-quest-objective-evidence
```

Output:

- `.harness/verification/phase5a-quest-objective-evidence-report.json`

### `phase5b-relationship-reputation-knowledge`

Backend-only phase-gate proof for the P5B relationship, reputation, and
knowledge authority slice.

It runs:

- `backend/tests/test_p5_social_knowledge.py`
- `backend/tests/test_p5_quest_evidence.py`
- `backend/tests/test_p5_contracts.py`
- `backend/tests/test_gameplay_p5_batch_contract.py`

Current proof includes:

- concrete public and private recipient views for one committed relationship plus one private knowledge observation
- explicit redaction evidence showing the public relationship view omits evidence payload while the private recipient keeps the knowledge fact
- conflicting public observations with deterministic decay and reputation projection facts
- committed decision receipt plus duplicate idempotency replay evidence
- revocation receipt evidence with `godot_mirror` refresh hints and post-revocation recipient-view invalidation
- real full replay, checkpoint-tail replay, and recipient-authorized projection-hash equivalence evidence
- typed zero-write rejection evidence for the stale-revision path

Command:

```powershell
python scripts/verification/harness.py --profile phase5b-relationship-reputation-knowledge
```

Output:

- `.harness/verification/phase5b-relationship-reputation-knowledge-report.json`

### `phase5c-investigation-stealth-conflict`

Backend-only phase-gate proof for the P5C investigation, stealth/conflict, and
nonlethal adverse-outcome authority slice.

It runs:

- `backend/tests/test_p5_investigation_conflict.py`
- `backend/tests/test_p5_social_knowledge.py`
- `backend/tests/test_p5_quest_evidence.py`
- `backend/tests/test_p5_contracts.py`
- `backend/tests/test_gameplay_p5_batch_contract.py`

Current proof includes:

- concrete provenance from a committed public perception resolution, including the canonical investigation/conflict streams and hidden-clue source
- explicit recipient privacy/redaction evidence showing the public view omits hidden clue payload while the investigator and authority views retain it
- skill-gate rejection and unregistered-resistance zero-write evidence
- committed adverse-outcome evidence for conflict, alarm, and registered nonlethal status-tag application
- duplicate idempotency replay evidence plus atomicity violation zero-write rejection evidence
- real full replay and checkpoint-tail replay hash equivalence evidence for the committed event log
- typed zero-write rejection evidence for hidden-perception, malformed-input, invalid-owner-visibility, and atomicity-failure paths

Command:

```powershell
python scripts/verification/harness.py --profile phase5c-investigation-stealth-conflict
```

Output:

- `.harness/verification/phase5c-investigation-stealth-conflict-report.json`

### `phase5d-investigation-vertical-slice`

Backend-only closure proof for the bounded bakery-theft investigation. The
profile records provenance and registry pins, public/private redaction,
decision receipts, stealth alarm and nonlethal consequence, hidden-clue and
unsupported-Survival zero-write failures, and equal full/checkpoint-tail
replay hashes.

Run:

```powershell
python scripts/verification/harness.py --profile phase5d-investigation-vertical-slice
```

Output:

- `.harness/verification/phase5d-investigation-vertical-slice-report.json`

### `gameplay-event-replay`

Backend-only replay proof for Gameplay committed events and projection recovery.

Current proof includes:

- full replay and checkpoint-plus-tail replay produce identical deterministic projection hashes
- duplicate event delivery is idempotent for projectors
- stream revision gaps block replay with a typed failure
- unknown event versions without an upcaster chain block replay rather than being skipped
- an opt-in schema registry is persisted with a durable store snapshot and restored as the same append gate
- a registered, digest-matched, continuous one-step trusted upcaster can replay a fixed historical fixture without mutating stored event bytes
- projection checkpoints persist with their compatibility metadata; the newest checksum-valid, event-prefix-valid compatible cache is selected and invalid or incompatible caches fall back to full replay
- an opt-in single-store startup coordinator closes writes until replay succeeds; replay failure retains the retriable `projection_not_ready` gate

It also proves the first bounded resource Patch migration can rebuild its
versioned resource/state-group façade through full and checkpoint-plus-tail
replay. It does not prove a persistent executable upcaster manifest, general
patch migration, global multi-projector readiness orchestration, a production
startup control plane, or live Godot recovery.

Output:

- `.harness/verification/gameplay-event-replay-report.json`
- `.harness/verification/gameplay-event-replay-report.md`
- `.harness/verification/gameplay-event-replay-pytest.log`

### `gameplay-foundation-event-spine`

Backend-only aggregate proof for the coupled Gameplay event store, committed outbox, and existing authority event bus delivery path.

Current proof includes:

- committed outbox entries are published only after `append_batch` commits
- every bus payload carries `transaction_id`, `event_id`, `stream_revision`, and `global_sequence`
- bus delivery failure keeps event truth committed and retries the same outbox entry identity
- rejected batches create no publishable outbox
- consumers can detect global sequence gaps and resync from store-backed events
- Gameplay package authority bus publishing is scoped to the after-commit dispatcher

Output:

- `.harness/verification/gameplay-foundation-event-spine-report.json`
- `.harness/verification/gameplay-foundation-event-spine-report.md`
- `.harness/verification/gameplay-foundation-event-spine-pytest.log`

### `gameplay-patch-runtime`

Backend-only proof for the implemented minimum governed Gameplay patch runtime.

Current proof includes:

- immutable digest-checked manifests from configured trusted authors only
- atomic candidate registration with missing/cyclic/ambiguous dependency and
  schema-collision rejection
- explicit active-set selection; installation alone cannot activate behavior
- versioned JSON snapshot recovery of candidates and recomputed active-set
  identity; tampered manifest digests or active-set revisions fail closed
- deterministic proposal-only trigger rules with bounded conditions,
  effect-proposal count, and capability calls
- deterministic, side-effect-free capability registration and manifest/call-site
  authorization; unsafe, unauthorized, or failing handlers cannot reach a
  settlement path
- authority-ledger candidate install plus complete-active-set enable/disable;
  registry cutover occurs only after the lifecycle batch commits, while stale
  revisions or storage rejection leave it unchanged
- a bounded stateful enable/disable path: explicitly supplied trusted actor
  contexts plan only declared state groups and dependencies; enable pins the
  target patch-set revision, while disable requires the current source revision
  and unique ownership. Both lifecycle changes commit with the Patch cutover in
  one batch; actor discovery, policy expansion, domain-effect revocation,
  compensation, and migration remain rejected or unimplemented
- compatible same-patch revision upgrade/rollback can use a manifest-declared
  unchanged-definition `identity_rebind`; every explicit actor records the
  source-revision change with the Patch cutover in one batch
- the first bounded data-transform upgrade: a manifest-declared
  `core.resources` `resource_bounds_clamp` uses version-addressable resource
  and state-group definitions, a trusted projection-pinned resource planner,
  explicit loss/reservation policy, and one batch containing the resource fact,
  state-group definition/source transition and Patch cutover. Its potentially
  lossy rollback, shared ownership, multi-Patch replacement and all other
  data-transform policies reject before append
- rule-only, compatible identity-rebind, and the bounded resource-clamp
  same-patch upgrade follow their valid version direction; unrecognized
  migration contracts reject before append
- control-plane lifecycle replay rebuilds candidate identities and active-set
  state while digest/order/revision mismatches fail closed
- an evaluated `resource.consume` proposal is revalidated against the current
  actor resource projection and committed with settlement evidence in one batch;
  every other effect type is rejected before append

It does not prove a database-backed registry or handler artifacts, full Rule
IR, general authority settlement conversion beyond `resource.consume`,
state-group domain-effect revocation, grant/modifier lifecycle effects,
data-transform stateful migration beyond the bounded resource clamp,
cross-version reader/rollback compatibility, privacy views, or a live Godot
process proof for Patch migration delivery. The bounded resource clamp does
prove a backend-owned, post-commit filtered Godot mirror projection.

Output:

- `.harness/verification/gameplay-patch-runtime-report.json`
- `.harness/verification/gameplay-patch-runtime-report.md`
- `.harness/verification/gameplay-patch-runtime-patch-contract-and-lifecycle.log`
- `.harness/verification/gameplay-patch-runtime-migration-replay-and-zero-write-rejection.log`
- `.harness/verification/gameplay-patch-runtime-post-commit-godot-projection.log`
- `.harness/verification/gameplay-patch-runtime-patch-rule-ir-and-capability-boundary.log`

### `gameplay-state-groups`

Backend-only proof for the implemented minimum `StateGroupRegistry` and
read-only `CharacterGameRuntimeState` composition core.

Current proof includes:

- immutable state-group definitions and deterministic dependency load order
- missing dependency and enabled-conflict rejection
- event-derived materialized/enabled/dormant/disabled lifecycle read projection
  with actor, definition-version, and source-patch-revision validation
- trusted explicit-context enable/dormant/disable commands append lifecycle
  events only through `GameplayEventStore.append_batch`; dependency-in-use and
  ineligible requests reject before mutation
- versioned declarative eligibility catalog compiles actor archetype, world
  revision, and patch revision inputs to that context and fails closed when a
  required group's dependency is unavailable
- immutable facade envelopes containing only lifecycle-enabled groups, source
  revisions, and a stable snapshot checksum
- Phase 3 resource/body/status-tag/effective-stat read projections compose
  only into lifecycle-enabled façade groups and reject cross-actor inputs
- in-memory lifecycle/resource/body/status-tag checkpoint-plus-tail rebuild
  composes to the same Phase 3 façade checksum as full reconstruction
- immutable authority/Godot/mind/debug view projection: non-authority views
  can only retain policy-allowlisted existing top-level fields, debug requires
  a policy-listed principal, and missing policy fails closed
- backend-only full snapshot and exact-base delta reconstruction: unsupported
  capabilities, mismatched base revisions, overlapping changes/removals, and
  target checksum mismatches fail closed

It does not prove policy-catalog persistence/loading from world or patch
activation, persistent replay rebuild, consumer capability negotiation,
transport delivery, client prediction, persistence, or Godot mirror delivery.

Output:

- `.harness/verification/gameplay-state-groups-report.json`
- `.harness/verification/gameplay-state-groups-report.md`
- `.harness/verification/gameplay-state-groups-pytest.log`

### `gameplay-resource-body`

Backend-only proof for the initial resource/body action gate.

Current proof includes:

- committed event projection for integer resource entries and injury-derived
  functional capacity
- backend-only reserve/consume/release authority commands validate the current
  projection; their explicit events derive `reserved` and `available`, without
  leaving a consumed or released reservation balance
- an ineligible existing skill path, right-arm function unavailable, and
  insufficient stamina reject before any action/resource event is appended
- recovery restores a previously blocked function without changing the action
  requirement
- successful action settlement atomically appends the resource cost and action
  event; stale resource/body projections fail closed

It does not prove reservation timeouts, status-tag lifecycle,
needs/posture, effective-stat modifiers, skill-state writes/grants, replay/checkpoint
equivalence, transport delivery, or Godot mirror behavior.

Output:

- `.harness/verification/gameplay-resource-body-report.json`
- `.harness/verification/gameplay-resource-body-report.md`
- `.harness/verification/gameplay-resource-body-pytest.log`

### `gameplay-effective-stats`

Backend-only proof for the pure effective-stat resolver and registered
equipment-modifier source replay.

Current proof includes canonical modifier ordering, inactive-condition rejection,
declared stacking policy, unresolved override conflict rejection, and a stable
explanation digest independent of input enumeration order. It also covers
event-derived activation/deactivation of two registered modifier instances,
where deactivating one source preserves the other.

It does not prove generic environment source lifecycle, runtime state-group
composition, consumer views, transport, or Godot mirror delivery.

Output:

- `.harness/verification/gameplay-effective-stats-report.json`
- `.harness/verification/gameplay-effective-stats-report.md`
- `.harness/verification/gameplay-effective-stats-pytest.log`

### `gameplay-ability-affordance`

Backend-only proof for the implemented stable ability and current-affordance
core.

Current proof includes:

- explicit Gameplay event materialization of learned skill truth
- versioned skill/action-path definitions with unknown definitions rejected
- read-only affordance resolution from stable skill state, current resource,
  and body-function projections
- a body-function block that leaves learned ability intact
- cross-actor inputs and missing required resource projections fail closed

It does not prove promotion, restriction command APIs, equipment/inventory,
environment/permission predicates, persistence, transport, or Godot mirror
delivery.

Output:

- `.harness/verification/gameplay-ability-affordance-report.json`
- `.harness/verification/gameplay-ability-affordance-report.md`
- `.harness/verification/gameplay-ability-affordance-pytest.log`

### `gameplay-inventory`

Backend-only proof for the minimum event-sourced inventory authority: item
identity, single location, container capacity, sealed rejection, and atomic
move. It excludes nesting, encumbrance, ownership, equipment, transport, and
Godot mirror delivery.

### `gameplay-possession-equipment`

Backend-only proof for the initial equipment authority slice. It verifies that
validated inventory placement, equipment activation/deactivation,
activation-scoped ability-path grant activation/revocation, and registered
modifier-source activation/deactivation commit in one batch. A multi-slot item
occupies every declared slot through one activation; a conflict in a secondary
slot does not create a partial primary-slot result. Incompatible slots,
unavailable body functions, stale body revisions, and duplicate commands do not
create a partial second state. The grant remains distinct from learned skill
truth, while the modifier only becomes a typed input to the read-only
effective-stat resolver.

The minimum swap path validates the outgoing destination plus every incoming
slot before it writes anything. It then revokes old activation effects, returns
the old item, and activates the new item through the same batch.

It does not prove generic modifier lifecycle, skill/action grant forms beyond
the implemented path grant, container access or propagation, ownership/control,
presentation binding, replay/checkpoint
equivalence, transport, or Godot delivery.

Output:

- `.harness/verification/gameplay-possession-equipment-report.json`
- `.harness/verification/gameplay-possession-equipment-report.md`
- `.harness/verification/gameplay-possession-equipment-pytest.log`

### `gameplay-ownership-authority`

Backend-only proof for exclusive full-title grant, independent transfer, holder
rejection, and idempotent replay, plus credential issue/revoke/supersede. A
credential is a replayable right reference: issue/supersede validates the
declared holder's current inventory location and retains that holder plus the
pinned inventory revision as issuance evidence, but does not move custody,
inventory, funds, or title. The evidence is not a current-holder projection.
Its read-only presentation
check requires that the presenter currently has the linked item and is the
current right holder.

It does not prove custody writes, accounts, ledger balance, offers, debt,
contracts, privacy views, checkpoint replay, transport, or Godot delivery.

Output:

- `.harness/verification/gameplay-ownership-authority-report.json`
- `.harness/verification/gameplay-ownership-authority-report.md`
- `.harness/verification/gameplay-ownership-authority-pytest.log`

### `gameplay-economy-authority`

Backend-only proof for event-derived account balances, atomic same-currency
debit/credit transfer, a fixed-offer purchase, a zero-consideration gift, and
simple-debt issue/payment and a policy-authorized correction of one payment.
Purchase proves exact-price and pinned-offer
settlement of debit/credit, cross-actor item transfer, exclusive full-title
transfer, offer consumption, and a transaction record in one batch. Gift proves
its corresponding item/title transfer and zero-consideration record in one
batch. Simple debt proves principal funding, simple contract, debt claim, issue
record, partial repayment, final satisfaction, policy cancellation without
balance mutation, overpayment rejection, and a payment-record-specific,
append-only correction. The correction reverses the original payment's funds,
restores outstanding amount, records a one-to-one correction link, and rejects
duplicate correction. A correction after final payment reopens the satisfied
claim and fulfilled simple-debt contract in the same batch. A distinct policy
cancellation reversal restores the original cancellation's pinned outstanding
amount and reopens its claim/contract pair without account movement; it cannot
be substituted for payment correction.

The backend query service exposes an account only to its owner or configured
authority principal, and a debt only to its creditor, debtor, or configured
authority principal. Third-party rejection returns no balance, outstanding
amount, or private party data.

The same backend query service can produce configured field-allowlisted
payloads after authorization: the default owner account view omits `owner_ref`,
the default debt-party view omits contract ID, counterparty identities, and
principal, and authority policy may allow the complete view. This is not
transport authentication or a session/Godot scope grant.

The contract service accepts only registered typed `simple_transfer` or
`simple_service` terms, records an active contract, and permits fulfill or
terminate only from a configured policy authority. A registered service term
with a matching completion evidence kind can atomically record its evidence
and fulfill. It does not execute arbitrary terms or settle inventory,
ownership, or funds.

It does not prove credential settlement, broader cross-domain contract
execution, interest/default handling, transport authorization,
persistence, checkpoint replay, or Godot delivery.

Output:

- `.harness/verification/gameplay-economy-authority-report.json`
- `.harness/verification/gameplay-economy-authority-report.md`
- `.harness/verification/gameplay-economy-authority-pytest.log`

### `godot-gameplay-mirror`

Backend plus local-Godot proof for the gameplay-mirror foundation.

Current proof includes policy-filtered Godot envelope serialization,
backend-issued trusted-local session identity, explicit multi-actor read scope,
transport-neutral subscribe/snapshot/unsubscribe access, a backend-published
generic projection repository, a backend-configured Phase 3 source rebuilt
only from committed events, `/ws` trusted-local bind/subscribe snapshot wiring,
live reconnect with fresh enrollment and narrowed scope, gap/resync, bounded
queue/backpressure recovery, server-issued stamina prediction
confirmation/rejection rollback, and a local Godot bridge probe that routes
only granted actors and clears state on disconnect.

It does not prove a production identity adapter, production command routing,
persistence, or migration behavior.

Output:

- `.harness/verification/godot-gameplay-mirror-report.json`
- `.harness/verification/godot-gameplay-mirror-report.md`
- `.harness/verification/godot-gameplay-mirror-pytest.log`

### `adventure-basic`

Validates the strict, digest-checked governed `adventure-basic` manifest before
Patch activation plus Scenario 1 fixed-offer purchase/equip, Scenario 2
body/resource constraints, Scenario 3 equipment-gated storage-ring, Scenario 4
physical-deed/land-title separation, and Scenario 5 gift/debt/typed-contract
lifecycle compositions. Each scenario must prove a rebuilt authoritative
facade with revision/result metadata, online/full/checkpoint-tail canonical
replay hashes, a filtered backend mirror source, and a server-selected
canonical commit delivered to a fresh trusted-local Godot mirror. It does not
prove Patch activation, client authority, generic transport durability,
production identity, or migration closure.

Output:

- `.harness/verification/adventure-basic-report.json`
- `.harness/verification/adventure-basic-report.md`
- `.harness/verification/adventure-basic-pytest.log`

### `gameplay-foundation-all`

Fail-closed aggregate for the Gameplay Foundation dependency chain. It runs
each child profile in dependency order and accepts a child only when both the
harness invocation and that child's own overall report are green. The aggregate
does not elevate a child's documented exclusions into a completion claim.

The aggregate itself does not require a Godot executable so that it can write
a fresh blocked report. Its `godot-gameplay-mirror` child remains mandatory:
without a real Godot executable the aggregate fails after recording the child
failure, rather than skipping the runtime gate.

Output:

- `.harness/verification/gameplay-foundation-all-report.json`
- `.harness/verification/gameplay-foundation-all-report.md`
- `.harness/verification/gameplay-foundation-all-<child-profile>.log`

### `gameplay-status-tags`

Backend-only proof for the initial registered status-tag lifecycle.

Current proof includes explicit apply/remove/expire events, deterministic replay,
stack-count limits, exclusivity rejection before an invalid event is written,
active declarative tag modifiers becoming inactive on expiry, backend-principal
rejection, and idempotent receipt replay without a second event.

It does not prove refresh policies, timed/source-bound durations, dispel,
arbitrary modifier-template execution, consumer views, transport, or Godot
mirror behavior.

Output:

- `.harness/verification/gameplay-status-tags-report.json`
- `.harness/verification/gameplay-status-tags-report.md`
- `.harness/verification/gameplay-status-tags-pytest.log`

### `embodied-interaction-session`

Backend and Godot runtime proof for Phase 6 authority-owned `InteractionSession` handshake lifecycle over the Gameplay event spine, committed outbox/bus delivery, websocket projection, `BackendBridge`, and local slot consumer.

Current proof includes:

- proposal, acceptance, authorization, realizing, terminal participation observations, and committed session events write through `GameplayEventStore.append_batch`
- committed session outbox entries are delivered through the existing authority event bus
- committed outbox/bus session events are projected to `embodied_interaction_session_event` websocket envelopes with `transaction_id`, `event_id`, `stream_revision`, and `global_sequence`
- Godot headless runtime connects to the live backend through `BackendBridge`, sends `embodied_interaction_session_probe`, receives the session events on `LocalPresentationBus`, and feeds a live `InteractionSessionSlotConsumer`
- refusal prevents authorization and local realization
- target departure and third-party interruption terminate the session and release reservations
- two participants cannot commit a shared action until both valid terminal observations are recorded
- session lifecycle and terminal observations use the embodied evidence ledger
- public projection and bus delivery filter private participant terms
- Godot `InteractionSessionSlotConsumer` accepts backend-safe session projections, tracks local slot/reservation state, emits one bounded terminal participation observation, rejects private participant terms, and releases reservations after interruption

Output:

- `.harness/verification/embodied-interaction-session-report.json`
- `.harness/verification/embodied-interaction-session-report.md`
- `.harness/verification/embodied-interaction-session-pytest.log`
- `.harness/verification/embodied-interaction-session-trace.json`
- `.harness/verification/embodied-interaction-session-websocket-trace.json`
- `.harness/verification/embodied-interaction-session-godot.log`
- `.harness/verification/embodied-interaction-session-godot-runtime.json`

### `embodied-handoff-authority`

Backend and Godot runtime proof for the Phase 7 narrow handoff authority slice. This is not the full inventory/economy package; it proves that handoff crosses the authority boundary through Gameplay `append_batch`, not Godot attachment.

Current proof includes:

- backend handoff settlement writes `embodied.interaction_session.participant_observed`, `inventory.custody_changed`, `ownership.right_transferred`, `embodied.handoff.settled`, and `embodied.interaction_session.committed` in one Gameplay transaction
- local attachment hints are accepted only as `presentation_hint_only` and do not alter custody or ownership projection
- duplicate idempotency replays the original transaction without a second mutation
- revision conflict rejects without partial session/custody/ownership commit
- committed handoff events are projected to `embodied_handoff_event` websocket envelopes without `world_truth_claim`, `character_actor_status`, or private participant terms
- Godot headless runtime connects to the live backend through `BackendBridge`, sends `embodied_handoff_probe`, receives `embodied_handoff_event`, and feeds a live `HandoffMirrorConsumer`
- Godot `HandoffMirrorConsumer` requires `attachment_directive.authority_only == true` before presentation attachment and rejects unsafe projections

Output:

- `.harness/verification/embodied-handoff-authority-report.json`
- `.harness/verification/embodied-handoff-authority-report.md`
- `.harness/verification/embodied-handoff-pytest.log`
- `.harness/verification/embodied-handoff-websocket-trace.json`
- `.harness/verification/embodied-handoff-godot.log`
- `.harness/verification/embodied-handoff-godot-runtime.json`

### `embodied-grab-carry-place-authority`

Backend and Godot runtime proof for the Phase 7 `grab-carry-place` authority slice. It proves that local grab/carry/place attachment is only presentation until backend settlement commits custody and occupancy through Gameplay `append_batch`. Its focused backend suite also proves the restricted default-scene `stow_intent` reference and the transport-free internal `retrieve_to_custody` inverse: server-owned policy resolution or internal resolved refs, atomic custody/inventory/occupancy append, structured rejection, idempotent replay, and an accepted-only local stow presentation directive.

Current proof includes:

- backend carry-place settlement writes `embodied.interaction_session.participant_observed`, `inventory.custody_changed`, `embodied.carry.started`, `scene.occupancy.changed`, `embodied.place.settled`, and `embodied.interaction_session.committed` in one Gameplay transaction
- local carry hints are accepted only as `presentation_hint_only` and do not alter custody or occupancy projection
- occupied drop targets and invalid source custody reject before any cross-domain commit
- duplicate idempotency replays the original transaction without a second mutation
- revision conflict rejects without partial session/custody/occupancy commit
- committed place events are projected to `embodied_carry_place_event` websocket envelopes without `world_truth_claim`, `character_actor_status`, or private participant terms
- Godot headless runtime connects to the live backend through `BackendBridge`, sends `embodied_grab_carry_place_probe`, receives `embodied_carry_place_event`, and feeds a live `CarryPlaceMirrorConsumer`
- Godot `CarryPlaceMirrorConsumer` requires `placement_directive.authority_only == true` before presentation placement and rejects unsafe projections
- default-scene `stow_intent` accepts only normal context and a reviewed object ID, rejects client-injected custody/container references, and commits `inventory.custody_changed`, `gameplay.inventory.item_transferred_in`, and `embodied.inventory.stowed` in one transaction after pickup custody exists; a backend-tracked hand source also releases `scene.occupancy.changed` in that same batch
- internal `retrieve_to_custody` accepts only policy/settlement-resolved actor/container/item/receiver refs, preserves the item instance while removing its inventory location, and commits `inventory.custody_changed`, `gameplay.inventory.item_transferred_out`, receiver `scene.occupancy.changed`, and `embodied.inventory.retrieved` in one batch; it has no client transport claim

Output:

- `.harness/verification/embodied-grab-carry-place-authority-report.json`
- `.harness/verification/embodied-grab-carry-place-authority-report.md`
- `.harness/verification/embodied-carry-place-pytest.log`
- `.harness/verification/embodied-carry-place-websocket-trace.json`
- `.harness/verification/embodied-carry-place-godot.log`
- `.harness/verification/embodied-carry-place-godot-runtime.json`

### `embodied-interaction-foundation-all`

Dependency-ordered aggregate for embodied-interaction product foundation Phase 0 through Phase 7 backend `InteractionSession`, narrow handoff authority, and `grab-carry-place` authority.

It runs:

- `embodied-interaction-contracts`
- `embodied-affordance-registry`
- `embodied-bridge-attestation`
- `embodied-action-controller`
- `embodied-authority-settlement`
- `embodied-interaction-replay`

It then checks the Phase 6 gate:

- `gameplay-foundation-event-spine`

It then runs:

- `embodied-interaction-session`
- `embodied-handoff-authority`
- `embodied-grab-carry-place-authority`

Phase 6 session work starts only after that gate passes, proving the Gameplay event store, atomic event-batch writer, committed outbox, and after-commit authority bus dispatcher.
Phase 7 object work then proves handoff and grab-carry-place settle through Gameplay atomic event batches before Godot mirrors attachment or placement. The restricted custody-to-inventory stow reference is exercised inside the grab-carry-place profile; it is not a separate claim of generalized scene inventory closure.

Output:

- `.harness/verification/embodied-interaction-foundation-all-report.json`
- `.harness/verification/embodied-interaction-foundation-all-report.md`

### `all`

Runs `docs`, `boundaries`, `drift`, `backend-contract`, `godot-project`, `character-agent-execution`, `release-gate`, `harness-lifecycle`, `change-lifecycle`, `harness-reference`, `harness-evolution`, `phase0`, `siming-backend-chain`, `character-model-live`, `l1-world-fact-runtime`, `llm-integration-closure`, `phase1-slice`, `mainline-unified-runtime`, `model-provider-readiness`, `godot-sampling-production-grade-providers`, `embodied-skeletal-debug-replay`, `tts-voice-profile-adapter`, `vla-provider-backend`, `actor-scene-knowledge-lifecycle`, `siming-global-situation-layer`, `interaction-orchestration-service`, `esm-physical-channel-world-actuation`, `non-runtime-production-pipeline`, `perception-input-alignment`, `embodied-interaction-contracts`, `embodied-affordance-registry`, `embodied-bridge-attestation`, `embodied-action-controller`, `embodied-authority-settlement`, `embodied-interaction-replay`, `gameplay-foundation-contract`, `gameplay-event-replay`, `gameplay-foundation-event-spine`, `gameplay-state-groups`, `embodied-interaction-session`, `gameplay-resource-body`, `embodied-handoff-authority`, `gameplay-effective-stats`, `embodied-grab-carry-place-authority`, `gameplay-status-tags`, `embodied-interaction-foundation-all`, `gameplay-ability-affordance`, `godot-gameplay-mirror`, `obj-archive-door-physical-embodiment`, `gameplay-inventory`, `gameplay-possession-equipment`, `gameplay-ownership-authority`, `gameplay-economy-authority`, `gameplay-patch-runtime`, `adventure-basic`, and `gameplay-foundation-all` in profile order. It stops on the first failed profile.

`siming-backend-chain` is excluded from `all` because it requires live model-provider credentials.
`character-model-live` and `llm-integration-closure` are also excluded from `all`; they require fresh live provider artifacts and an explicit closure run ID.
`gameplay-patch-runtime` follows `gameplay-economy-authority` by profile order
and verifies the current Patch Rule IR/lifecycle foundation. `adventure-basic`
follows it and proves its strict digest-valid manifest, all five scenario
facade/replay/mirror chains, and their fresh Godot delivery; it does not make
Patch activation, client authority, production identity, generic transport
durability, persistence, or migration part of the repository-wide closure.
`gameplay-foundation-all` then re-runs the complete Gameplay Foundation
dependency chain fail-closed; it does not convert the documented partial Patch
or transport scopes into broader domain closure.

### `mainline-unified-runtime`

Higher-level runtime proof that composes:

- actor-local perception
- autonomous social contact
- shared actor execution ingress
- phase1-shaped runtime slice
- authority settlement writeback
- asset registry and Kimodo adapter contracts
- world-runtime policy/model focused tests
- degraded-mode perception/cognition deferral
- continuity recovery across renewed social contact
- scheduling round state, round trace, debug-stream, script-beat, websocket, and frontend signal/state chain evidence

Use this when you need one report that is closer to the repository's new mainline than any single narrow verifier.

Output:

- `.harness/verification/mainline-unified-runtime-report.json`
- `.harness/verification/mainline-unified-runtime-report.md`
- `.harness/verification/harness-run-report.json`
- `.harness/verification/harness-run-report.md`

## Harness Evolution

The Harness Evolution Agent is a governed proposal lane. It reads existing harness telemetry, writes an evolution report, and may create candidate mutation manifests under `.harness/evolution/candidates/`.

It does not apply patches or promote its own proposals. A candidate must be converted into a normal implementation plan, implemented through the repository workflow, and verified through its promotion profiles before it can become operational harness behavior.

Candidate manifests may carry lifecycle metadata: `proposed`, `qa-review`, `promotion-ready`, `promoted`, or `rejected`. Generated candidates start as `proposed` with `qa_review_required=true` and empty `qa_review_artifacts`; moving a candidate to `promotion-ready` or `promoted` requires at least one QA/replay artifact reference so promotion is attributable and reviewable.

First-version candidates may target harness-owned surfaces such as `.harness/`, `scripts/verification/`, `docs/harness.md`, `docs/ai-engineering-workflow.md`, and `.github/workflows/harness.yml`. Product runtime paths such as `backend/`, `scenes/`, character scripts, or Siming runtime modules are outside the mutation scope.

## Decision Observability

Harness-facing changes can be recorded under `.harness/changes/` as decision manifests. These manifests are project inputs, not generated evidence. An active manifest records the evidence that motivated a Harness change, the root-cause hypothesis, predicted fixes, predicted regressions, and the profiles that should verify the change.

The Harness runner includes active manifests in `harness-run-manifest.json` under `harness_changes`. Malformed manifests are reported under `harness_change_errors` so normal profile runs remain usable while evidence problems stay visible.

When a profile fails, the runner writes a deterministic failure digest such as `.harness/verification/phase0-failure-digest.json` and archives the same digest under that run's `.harness/verification/runs/run-.../` directory. A digest is an index into existing reports and traces; it does not replace the original profile report or runtime trace.

### `infra-frost-production-admission`

Backend-only proof for INF-3R-A. It verifies the committed ecology frost source,
authority/public redaction, deterministic due construction-run selection,
zero-write source and target rejections, idempotency, and source/target
full/checkpoint-tail reconstruction. It does not write a production outcome.

Output:

- `.harness/verification/infra-frost-production-admission-report.json`

### `infra-obligation-lifecycle`

Backend-only INF-2X proof for the sole registered
`policy:construction_due_completion@1` construction row. Its independent
assertions cover owner/stream registration, fragment stream and revision,
lifecycle correlation, committed source obligation identity, idempotency,
revision and terminal zero-write rejection, registered project scope, and
full/checkpoint-tail replay. Cancellation can only correlate an obligation
identity committed on the construction `run_started` source fact.

It does not admit retry, failure, compensation, ecology lifecycle policies,
other owner rows, a second scheduler, or a new event store.

Output:

- `.harness/verification/infra-obligation-lifecycle-report.json`

### `infra-survival-state-obligation`

Backend-only INF-1A proof for exactly one `SurvivalAuthority` row:
`state:cold@1` on `gameplay:survival:{actor_ref}`. Independent assertions cover
the formal owner matrix, scheduled apply/open, caller-driven due selection,
owner expiry settlement, each closed stack policy, idempotency/revision/forged
owner zero-write, event-derived dispel/transform cancellation, scoped public
redaction, and checkpoint-tail replay. The pure semantic evaluator remains
proposal-only and cannot append Survival truth; the separately evidenced closed
semantic bridges may only hand their registered cold/heat proposals to the
Survival owner.

It does not prove generic state ownership, periodic effects, retry,
compensation, other domain rows, or a second scheduler/store.

- `.harness/verification/infra-survival-state-obligation-report.json`

### `infra-semantic-survival-state-bridge`

Backend-only INF-1B proof for exactly two closed handoffs:
`authority:semantic -> effect:cold_exposure -> state:cold@1 -> SurvivalAuthority`
and `authority:semantic -> effect:heat_exposure -> state:overheated@1 ->
SurvivalAuthority`. Separate assertions prove each row's owner submission,
duplicate replay,
altered-idempotency-payload zero-write, target revision zero-write, privacy
zero-write, unmapped-owner zero-write and checkpoint-tail replay. The pure
semantic evaluator remains proposal-only; this does not
authorize a generic semantic writer or owner matrix.

- `.harness/verification/infra-semantic-survival-state-bridge-report.json`

### `infra-semantic-state-owner-matrix`

Backend-only INF-1F proof that the three existing Survival state/effect rows
are represented by one registered lifecycle-owner matrix, not by a second
hard-coded bridge mapping. Independent assertions cover exact row lookup,
effect/state mismatch and unregistered-owner denial, deterministic row listing,
owner append, duplicate idempotency, revision/privacy zero writes and
checkpoint-tail replay. It does not add an owner, stream or cross-domain
effect/state lifecycle.

- `.harness/verification/infra-semantic-state-owner-matrix-report.json`

### `infra-generic-obligation-lifecycle`

Backend-only INF-2A proof for the read-only two-owner obligation lifecycle
projection over existing construction and Survival streams. Separate assertions
cover canonical statuses, due derivation without lifecycle writes, Survival
settled projection, bounded retry re-entering the one shared clock and owner
settlement path, settled-only explicit Survival compensation, revision and
unregistered/exhausted zero writes, idempotency, privacy and checkpoint-tail
replay.

It does not admit construction or ecology retry/compensation, an obligation
store, second scheduler, or a generic population activation-obligation pending
merge. The separately verified INF-2B/2E/2F `survival_state_expiry` rows are
the only registered exceptions for `state:cold@1`, `state:dehydrated@1`, and
`state:overheated@1`, and do not widen this profile.

- `.harness/verification/infra-generic-obligation-lifecycle-report.json`

### `infra-frost-production-recipe-admission`

Backend-only proof for INF-3R-B. It verifies the existing construction owner's
immutable recipe snapshot on `run_started`, authority-only revisioned reads,
legacy/missing/stale/privacy zero-write behavior, idempotency, and
full/checkpoint-tail reconstruction. It does not write a frost consequence.

Output:

- `.harness/verification/infra-frost-production-recipe-admission-report.json`

### `infra-regional-ecology`

Backend-only proof for the sole INF-3R edge: one committed frost source becomes
one construction-owner due-finish fragment and one existing `append_batch`,
with a scoped outbox, public redaction, authority provenance, idempotency,
source/target/privacy/retry/compensation zero-write fences, and full/checkpoint-tail
replay. It does not prove other hazards, generic consumers, regional truth,
retry/compensation implementation, market/body/social/population effects, or
Godot presentation.

Output:

- `.harness/verification/infra-regional-ecology-report.json`

### `infra-regional-ecology-truth`

Backend-only INF-3X proof for `EcologyHazardAuthority`'s sole
`gameplay:ecology:{region_ref}` stream. It separately asserts each canonical
region/environment/resource/crop/hazard recorded and retired event row, then
proves the one-fragment/one-append/outbox path, record/revision/unknown/privacy
zero-write fences, idempotency, scoped public/authority projection, a
revisioned resource update, and full/checkpoint-tail replay.

It does not authorize an ecology scheduler, regeneration/growth obligation,
retry, compensation, weather algorithm, or hazard consumer edge.

Output:

- `.harness/verification/infra-regional-ecology-truth-report.json`

### `infra-ecology-seasonal-process`

Independent INF-3A evidence for the closed `EcologyHazardAuthority` seasonal
process. Each Harness check runs a distinct focused pytest assertion for the
atomic environment/resource/crop owner batch and the independent idempotency,
revision, privacy, forged-principal, public-scope and checkpoint-tail replay
boundary. It does not claim scheduler, generic weather, fanout or a consumer
edge.

- `.harness/verification/infra-ecology-seasonal-process-report.json`

### `infra-seasonal-construction-maintenance`

Backend-only INF-3B proof for one non-frost ecology process edge. A committed,
project-visible seasonal process event becomes ecology proposal/admission only;
the existing Construction owner revalidates it and writes its own maintenance
obligation event. Independent checks cover success, closed admission,
stale-source and target-revision zero-write, idempotency, outbox privacy and
checkpoint-tail replay. It does not prove generic propagation, fanout, another
target owner, scheduler, market/body/social/population effects, or P6/P7.

- `.harness/verification/infra-seasonal-construction-maintenance-report.json`

### `infra-schedule-gated-supply`

Independent INF-4A evidence for one real existing-owner household/organization
schedule input. Separate checks prove combined planner source pins, the
Organization supply fragment settlement, and missing-work-order/activation-lock
zero-write boundaries. It does not admit generic `work`; the former universal
pending-merge limitation is superseded only by INF-4C's named row.

- `.harness/verification/infra-schedule-gated-supply-report.json`

### `infra-activation-pending-schedule-merge`

Backend-only INF-4C proof for one activation-owned, event-derived pending
admission: released `schedule_gated_supply` is revalidated before the existing
Organization supply fragment can write. Separate assertions cover pending and
release events, unsupported zero-write, duplicate idempotency, privacy,
checkpoint-tail replay, existing-owner merge, and forged/stale zero-write.
It does not admit generic pending payloads, ScheduledObligation activation
integration, branch promotion, or a population truth owner.

- `.harness/verification/infra-activation-pending-schedule-merge-report.json`

### `infra-activation-survival-expiry`

Backend-only INF-2B proof for one released `survival_state_expiry` pending row.
The activation projection is revalidated, then the existing Survival expiry
fragment is settled through the existing coordinator. Independent assertions
cover success, duplicate idempotency, revision conflict, privacy and terminal
zero-write, and checkpoint-tail replay. Activation and Survival remain separate
append-derived receipts; this is not generic cross-domain atomic settlement.

- `.harness/verification/infra-activation-survival-expiry-report.json`

### `infra-released-survival-expiry-batch-closure`

Backend-only INF-4AB proof for the second exact released-pending batch row:
`ContinuityMergeAuthority` reads one released project-scoped activation record,
then the existing `SurvivalAuthority` alone builds and commits the state-expiry
fragment. Separate selectors prove the existing-owner path, a receipt derived
from only the Survival append, idempotency, revision/privacy/terminal zero-write,
and full versus checkpoint-tail replay. It does not admit a generic pending
merge, cross-stream atomic receipt, branch promotion or a population truth owner.

- `.harness/verification/infra-released-survival-expiry-batch-closure-report.json`

### `infra-activation-dehydration-expiry`

Backend-only INF-2E proof for one released `survival_state_expiry` pending row
for `state:dehydrated@1`. The activation projection is revalidated, then the
existing Survival expiry fragment is settled through the existing coordinator.
Independent assertions cover success, duplicate and changed-duplicate behavior,
revision/privacy/unregistered-state/terminal zero-write, checkpoint-tail replay,
and the distinct activation versus Survival append receipts. This is not generic
activation-obligation binding or a cross-stream atomic receipt.

- `.harness/verification/infra-activation-dehydration-expiry-report.json`

### `infra-activation-overheated-expiry`

Backend-only INF-2F proof for one released `survival_state_expiry` pending row
for `state:overheated@1`. The activation projection is revalidated, then the
existing Survival expiry fragment settles through the existing coordinator.
Independent assertions cover success, exact and changed duplicate behavior,
changed pending zero activation write, revision/privacy/unsupported-state/
terminal zero-write, scoped project outbox, checkpoint-tail replay and the
distinct activation versus Survival append receipts. This is not generic
activation-obligation binding or a cross-stream atomic receipt.

- `.harness/verification/infra-activation-overheated-expiry-report.json`

### `infra-activation-obligation-binding-contract`

Backend-only INF-2G proof for a finite activation pending binding reader. Each
check independently covers the exact four existing-owner rows, unknown kind,
event-derived binding reference, forged binding zero-write, idempotency,
privacy, replay, the three existing Survival handoffs, and the existing
Organization schedule handoff. Activation and target receipts remain separate;
this is neither registration nor a generic dispatcher or cross-stream receipt.
It also proves an unbound historical pending cannot replay a valid Survival
settlement receipt.

- `.harness/verification/infra-activation-obligation-binding-contract-report.json`

### `infra-economy-wage-obligation`

Backend-only INF-2C proof for one existing Economy owner wage-accrual
obligation row. Independent assertions cover opening projection, caller due
selection and owner settlement receipt, duplicate handling, revision/privacy/
terminal/reopened-identity zero-write, settlement revision zero-write, project outbox scope, and
checkpoint-tail replay. It does not admit payment, accounts, cancellation,
retry, compensation, generic work, activation binding, or cross-stream atomic
receipts.

- `.harness/verification/infra-economy-wage-obligation-report.json`

### `infra-semantic-closed-guard-composition`

Backend-only INF-1C proof for finite proposal-only `all(...)` and `any(...)`
composition over existing tag/status/numeric guards. Separate assertions cover
true and false `all`, true `any`, and malformed/script rejection. This profile
does not append domain events or prove any additional effect/state owner row.

- `.harness/verification/infra-semantic-closed-guard-composition-report.json`

### `infra-isolated-branch-evolution`

Independent INF-4B evidence for deterministic isolated branch descriptor and
candidate records, local checkpoint-tail projection equivalence, invalid base/
profile zero-write, and unsupported promotion. The branch buffer is explicitly
not a production event store or writer.

- `.harness/verification/infra-isolated-branch-evolution-report.json`

### `infra-isolated-branch-owner-disposition`

Backend-only INF-4D proof for branch-local analysis records that label a
candidate as mapped to an existing Organization/Government owner or blocked.
Separate assertions prove zero production write, checkpoint-tail replay, base
and profile rejection, and unsupported promotion. An admitted disposition does
not execute a fragment, settle a domain consequence, or enable promotion.

- `.harness/verification/infra-isolated-branch-owner-disposition-report.json`

### `infra-isolated-branch-owner-fragment-evaluation`

Backend-only INF-4F proof that the isolated branch buffer can validate the two
closed Organization/Government fragment-builder mappings and record only a
branch-local disposition and fragment digest. It independently asserts accepted
evaluation, rejected/stale evaluation, branch replay, base/profile rejection,
and production zero writes. It does not settle a fragment, create a production
receipt, mutate a domain projection, or enable promotion.

- `.harness/verification/infra-isolated-branch-owner-fragment-evaluation-report.json`

### `infra-isolated-branch-owner-consequence-projection`

Backend-only INF-4G evidence that an already accepted Organization `supply` or
Government `inspection` fragment evaluation can yield exactly one redacted,
branch-local planned consequence. Independent assertions cover supply,
inspection, rejection without projection, owner-only-reference redaction,
checkpoint-tail replay, base/profile zero writes, and unsupported promotion.
The buffer remains non-production: it never appends a `GameplayEvent`, creates
an outbox row, settles a fragment, emits a receipt, or permits promotion.

- `.harness/verification/infra-isolated-branch-owner-consequence-projection-report.json`

### `infra-durable-isolated-branch-snapshot`

Backend-only INF-4M proof that the existing `BranchPreviewAuthority` can
explicitly persist its already accepted, redacted analysis buffer to the
existing creator-debug `gameplay:branch_preview:{branch_ref}` stream. Independent
assertions cover append/fresh-instance reconstruction, missing-buffer and
privacy zero writes, idempotency and stale revision, redaction, and
checkpoint-tail replay. It never settles a domain fragment, creates a
production receipt, or permits promotion.

- `.harness/verification/infra-durable-isolated-branch-snapshot-report.json`

### `infra-organization-branch-scenario-settlement`

Backend-only INF-4H proof for one accepted `supply` candidate settled by the
existing `OrganizationAuthority` onto its non-production scenario stream in the
same `GameplayEventStore`. Independent assertions cover Organization ownership,
duplicate idempotency, privacy/unknown-candidate/revision zero writes, scoped
outbox, checkpoint-tail scenario replay, production replay isolation and
unsupported promotion. It does not create a branch authority/store, write a
production organization stream, admit inspection/generic scenario settlement,
issue a cross-domain receipt or permit promotion.

- `.harness/verification/infra-organization-branch-scenario-settlement-report.json`

### `infra-government-branch-scenario-settlement`

Backend-only INF-4I proof for one accepted, passed `inspection` candidate
settled by the existing `GovernmentAuthority` onto its non-production scenario
stream in the same `GameplayEventStore`. Independent assertions cover Government
ownership, duplicate and changed-duplicate idempotency, privacy/unknown-candidate/
failed-inspection-at-this-passed-endpoint/revision zero writes, scoped outbox,
checkpoint-tail scenario replay, production replay isolation and unsupported
promotion. INF-4J separately proves the fixed failed-inspection remediation row;
neither package creates a remediation obligation, generic scenario settlement,
cross-domain receipt or promotion path.

- `.harness/verification/infra-government-branch-scenario-settlement-report.json`

### `infra-government-inspection-promotion`

Backend-only INF-4N proof for one durable passed-inspection admission and
Government scenario event revalidated by the existing `GovernmentAuthority`
before it writes the existing production Government inspection event. Each
capability has an independent focused assertion: production append,
append-derived duplicate receipt, changed-idempotency zero write, stale source
zero write, privacy zero write, forged scenario zero write, and scoped outbox
with production checkpoint-tail replay. It admits no Organization/remediation/
generic promotion row and does not create a second store, receipt store or
population truth owner.

- `.harness/verification/infra-government-inspection-promotion-report.json`

### `infra-organization-supply-promotion`

Backend-only INF-4O proof for one durable supply admission emitted on the
existing creator-debug `gameplay:branch_preview:{branch_ref}` stream and one
matching Organization branch scenario row revalidated by the existing
`OrganizationAuthority` before it writes the existing production Organization
commerce event. Each capability has an independent focused assertion:
production append, append-derived duplicate receipt, changed-idempotency zero
write, stale source zero write, privacy zero write, forged source/scenario zero
write, and scoped outbox with production checkpoint-tail replay. It admits no
Government/remediation/generic promotion row and does not create a second
store, receipt store or promotion coordinator.

- `.harness/verification/infra-organization-supply-promotion-report.json`

### `infra-government-failed-inspection-promotion`

Backend-only INF-4S proof for one durable failed-inspection admission and one
matching Government remediation scenario event revalidated by the existing
`GovernmentAuthority` before it writes the existing production Government
inspection event with `passed=False`. Each capability has an independent
focused assertion: production append, append-derived duplicate receipt,
changed-idempotency zero write, stale source zero write, privacy zero write,
forged scenario zero write, catalog pre-append admission, and scoped outbox
with production checkpoint-tail replay. It admits no Organization/remediation
generic promotion row and does not create a second store, receipt store or
population truth owner.

- `.harness/verification/infra-government-failed-inspection-promotion-report.json`

### `infra-government-failed-inspection-remediation-scenario`

Backend-only INF-4J proof for one accepted failed `inspection` candidate
settled by the existing `GovernmentAuthority` as a fixed
`follow_up_required` remediation record on its non-production scenario stream
in the same `GameplayEventStore`. Independent assertions cover owner append,
derived immutable remediation identity/action, exact and changed-duplicate
behavior, privacy/unknown/passed/source/scenario-revision zero writes,
checkpoint-tail scenario replay, production replay isolation and unsupported
promotion. It does not create a branch authority/store, a remediation
`ScheduledObligation`, generic scenario receipt, production Government write or
promotion path.

- `.harness/verification/infra-government-failed-inspection-remediation-scenario-report.json`

### `infra-durable-branch-preview-admission`

Backend-only INF-4L proof that an accepted inspection is first recorded as a
`creator_debug` BranchPreview evidence event in the sole gameplay store, then
reloaded and revalidated by the existing Government owner before either passed
inspection or fixed failed-inspection remediation scenario append. Independent
assertions cover both outcomes, missing/primitive provenance and passed/failed
forged cross-branch zero writes, duplicates, source revision, scoped outbox, replay, production isolation and
unsupported promotion. The evidence is not production/population/social truth
and creates no receipt, lifecycle, scheduler, second store or promotion path.

- `.harness/verification/infra-durable-branch-preview-admission-report.json`

### `infra-ecology-weather-front-propagation`

Backend-only INF-3C proof for one closed, project-visible weather-front step
between two mutually adjacent existing ecology regions. It independently asserts
the source propagation event, target environment record, source/target revision
checks, privacy, idempotency and checkpoint-tail replay. It does not admit a
scheduler, fanout, multi-hop propagation, retry/compensation, or any consumer
domain write.

- `.harness/verification/infra-ecology-weather-front-propagation-report.json`

### `infra-ecology-weather-front-path-propagation`

Backend-only INF-3D proof for one caller-submitted, no-repeat, symmetric
Ecology path of one to three weather-front hops. Eight independent selectors
cover the three-hop one-batch result, exact/changed idempotency, stale vector,
repeated path, nonadjacent hop, privacy zero-write, and full/checkpoint-tail
replay. It does not admit a fanout set, scheduler, third consumer edge, or
non-Ecology write.

- `.harness/verification/infra-ecology-weather-front-path-propagation-report.json`

### `infra-ecology-weather-front-fanout`

Backend-only INF-3E proof for one caller-named root and one to three symmetric
Ecology neighbors. Seven independent selectors cover one-batch fanout and full
edge projection, exact/changed idempotency, stale vector, duplicate target,
privacy zero-write, and full/checkpoint-tail replay. It does not admit
multi-round fanout, a consumer edge, a scheduler, or non-Ecology writes.

- `.harness/verification/infra-ecology-weather-front-fanout-report.json`

### `infra-ecology-weather-front-wave-fanout`

Backend-only INF-3F proof for a closed two-wave Ecology-only weather-front
fanout. Nine independent selectors prove the one-batch transaction and chained
environment revision, exact and changed idempotency, stale vector, invalid
second wave, adjacency and privacy zero writes, redacted project outbox, and
full versus checkpoint-tail replay. It admits only the existing Ecology owner,
streams and event family; it does not create a scheduler, generic graph
runtime, third consumer edge, retry/compensation, or non-Ecology write.

- `.harness/verification/infra-ecology-weather-front-wave-fanout-report.json`

### `infra-ecology-weather-front-construction-edge`

Backend-only INF-3G proof for one exact project-visible weather-front to
Construction maintenance consumer edge. Nine independent selectors cover the
Construction owner append, closed opaque admission, exact and changed
idempotency, source and target revision zero-write, source privacy, redacted
project outbox, and full/checkpoint-tail replay. The edge reuses only the
existing Ecology source event, Construction facility stream and maintenance
obligation event; it does not create a generic consumer registry, scheduler,
retry/compensation path, or Economy/Organization/population writer.

- `.harness/verification/infra-ecology-weather-front-construction-edge-report.json`

### `infra-ecology-weather-front-construction-fanout`

Backend-only INF-3H proof for one fixed two-facility, same-owner Construction
consumer fanout from a single Ecology weather-front source event. Four
independent selectors cover the two-stream one-batch append, closed admission
zero-write, changed duplicate/privacy zero-write, and revision/idempotency/
project-outbox/full-checkpoint replay. It is not a generic fanout registry or
cross-domain settlement writer.

- `.harness/verification/infra-ecology-weather-front-construction-fanout-report.json`

### `infra-ecology-weather-front-organization-supply-edge`

Backend-only INF-3I proof for one fixed project-visible Ecology
weather-front source to the existing Organization commerce commitment owner.
Four independent selectors cover the owner fragment append, exact and changed
duplicate behavior, forged/privacy/stale-source zero-write, and the existing
Organization commitment projection full/checkpoint-tail replay. The edge uses
the existing Organization event family and append spine; it is not a generic
consumer registry, direct Ecology write, payment path, or arbitrary fanout.

- `.harness/verification/infra-ecology-weather-front-organization-supply-edge-report.json`

### `infra-ecology-weather-front-organization-supply-fanout`

Backend-only INF-3O proof for one fixed project-visible weather-front source
to exactly two existing Organization commitment targets in one owner batch.
Independent checks cover the two-stream one-batch append, exact opaque pair
admission and arity, catalog/source/revision zero-write, idempotency,
project-only privacy, and full/checkpoint-tail replay. It does not admit a
generic consumer registry, arbitrary fanout, payment, pricing, scheduler, or a
new owner/store.

- `.harness/verification/infra-ecology-weather-front-organization-supply-fanout-report.json`

### `infra-durable-branch-evolution`

Backend-only INF-4P proof that the existing branch-preview authority can append
one fixed, redacted owner-consequence evolution event after its durable
creator-debug snapshot, then rebuild it in a fresh authority. Four independent
selectors cover branch-stream append/projection, unsupported or private
zero-write, exact idempotency and revision, and checkpoint-tail replay. The
event remains isolated branch evidence; it does not write production truth,
create a branch-domain receipt, or enable generic promotion.

- `.harness/verification/infra-durable-branch-evolution-report.json`

### `infra-survival-heat-state-obligation`

Backend-only INF-1D proof for the single closed semantic row
`effect:heat_exposure -> state:overheated@1 -> SurvivalAuthority`. It
independently asserts owner admission, state/open-obligation append, settlement,
duplicate/revision/privacy rejection and replay. It does not establish generic
effect/state ownership or a general semantic lifecycle.

- `.harness/verification/infra-survival-heat-state-obligation-report.json`

### `infra-survival-dehydration-state-obligation`

Backend-only INF-1E proof for the single closed semantic row
`effect:dehydration_exposure -> state:dehydrated@1 -> SurvivalAuthority`. It
independently asserts owner append, duplicate and changed-duplicate behavior,
revision/privacy/unmapped-pair zero writes, due settlement with checkpoint-tail
replay, and project-scoped outbox. It does not establish generic effect/state
ownership or a general semantic lifecycle.

- `.harness/verification/infra-survival-dehydration-state-obligation-report.json`

### `infra-survival-fatigue-owner-row`

Backend-only INF-1S proof for the one explicit closed semantic row
`effect:fatigue_exposure -> state:fatigued -> SurvivalAuthority`. Its selectors
independently assert the closed matrix, owner-spine append, duplicate and
changed-duplicate behavior, stale/forged-contract zero write, semantic owner
dispatch, and non-project privacy zero write. It does not admit generic effect,
state, owner, stream, or event registration.

- `.harness/verification/infra-survival-fatigue-owner-row-report.json`

### `infra-survival-fatigue-state-action`

Backend-only INF-1T proof that the already-admitted fatigue row can use only
the existing Survival dispel and fixed recovery-transform actions. Independent
selectors cover both owner-event paths, non-project privacy zero write, and
duplicate/revision/replay closure. It does not admit generic state actions.

- `.harness/verification/infra-survival-fatigue-state-action-report.json`

### `infra-activation-fatigue-expiry`

Backend-only INF-2N proof for the fourth explicit released Survival expiry
binding. It independently asserts owner-fragment settlement, duplicate/revision
zero write, privacy rejection, and checkpoint-tail replay. It does not prove or
admit generic activation-obligation binding.

- `.harness/verification/infra-activation-fatigue-expiry-report.json`

### `infra-construction-maintenance-state-owner`

Backend-only INF-1G proof for one closed semantic proposal,
`effect:maintenance_required -> state:maintenance_due@1`, settled by the
existing `ConstructionProductionAuthority` on an already acquired facility
stream. Sixteen independent assertions cover the owner append, duplicate and
changed-duplicate behavior, revision/privacy/mapping/vector/unacquired-facility
zero writes, an acquired facility without a started run, project-scoped
outbox/projection, and full/checkpoint-tail replay. It does not admit a generic
cross-owner matrix, construction state expiry, scheduler, retry, compensation,
or a cross-stream receipt.

- `.harness/verification/infra-construction-maintenance-state-owner-report.json`

### `infra-construction-maintenance-state-obligation`

Backend-only INF-1N proof for the fixed existing Construction facility-stream
state lifecycle: committed `maintenance_state_applied` source -> owner-owned
obligation open -> `maintenance_state_expired` plus settled event in one
append-derived receipt. Nineteen independent selectors cover owner append,
unknown/duplicate/stale/wrong-source/second-active zero writes, exact duplicate
behavior and each changed-duplicate rejection, committed-open admission,
paired-expiry and direct non-owner zero-write rejection, unsupported
cancel/retry/compensation, lifecycle projection,
project-scoped outbox, receipt privacy, and full/checkpoint-tail replay. It is
one fixed owner policy, not generic effect/state dispatch or a scheduler.

- `.harness/verification/infra-construction-maintenance-state-obligation-report.json`

### `infra-semantic-registered-state-owner-dispatch`

Backend-only INF-1H/INF-1I proof for the exact four-row owner matrix and closed
dispatch of the three registered Survival rows and the Construction
maintenance row to their existing owners. Independent assertions cover
matrix shape, Survival/Construction dispatch, unknown and
mismatched routes, duplicate/revision/privacy zero writes, direct-helper stale
semantic-vector rejection, non-canonical Survival definition rejection, and
checkpoint-tail replay. The profile remains a closed adapter route; it does
not establish generic owner dispatch, a new lifecycle policy, scheduler,
clock, event store, or cross-stream receipt.

- `.harness/verification/infra-semantic-registered-state-owner-dispatch-report.json`

### `infra-semantic-economy-wage-obligation`

Backend-only INF-1J proof for the exact semantic
`effect:wage_accrual_due -> EconomyAuthority` obligation row. Fourteen independent
assertions cover owner submission, unknown/unregistered effect, owner/stream/
privacy/vector zero writes, duplicate and malformed-input zero writes,
idempotency, revision conflict, project outbox scope, full/checkpoint-tail
lifecycle replay and the bare-`pytest` Economy terminal-lifecycle import path.
It does not admit payment, account
truth, generic wage policy or generic semantic effect routing.

- `.harness/verification/infra-semantic-economy-wage-obligation-report.json`

### `infra-semantic-survival-state-action`

Backend-only INF-1K proof for the two closed semantic Survival state-action
rows: dispel and fixed recovery transform. Fifteen independent assertions
cover each success action, unknown/unregistered routes, owner/stream/privacy/
vector/reason zero-write fences, revision conflict, exact and changed
idempotency behavior (including changed semantic snapshot), project outbox
scope, and full/checkpoint-tail replay.
It does not claim generic state actions, arbitrary replacement states, or a
generic semantic owner router.

- `.harness/verification/infra-semantic-survival-state-action-report.json`

### `infra-state-action-lifecycle-closure`

Backend-only INF-1O proof that the closed `StateDefinition` contract decides
dispel and fixed recovery transform before the existing Survival owner fragment
is built. Thirteen independent selectors cover each pure action decision,
each policy rejection, fixed contract target, contract-before-fragment
zero-write, both owner settlements, idempotency, revision/privacy zero-write,
and full/checkpoint-tail replay. It does not admit a generic action registry,
state writer, arbitrary transform target, scheduler, or new owner row.

- `.harness/verification/infra-state-action-lifecycle-closure-report.json`

### `infra-construction-maintenance-state-action`

Backend-only INF-1P proof for the one closed Construction action row:
`effect:maintenance_state_dispel` over an existing project-scoped
`state:maintenance_due` and its exact committed open obligation. Ten
independent selectors prove the single owner cancellation batch, exact and
changed idempotency, revision/privacy/closed-contract/transform/unknown-effect
zero-write, full/checkpoint-tail replay, and that ordinary Construction
lifecycle cancel is still unsupported. It does not claim repair, payment,
material, transform, generic state actions or generic cancellation.

- `.harness/verification/infra-construction-maintenance-state-action-report.json`

### `infra-government-policy-registration`

Backend-only INF-2K proof for the one existing-Government-owner commercial
 inspection policy registration row. Eight independent selectors cover separate
 register/revoke formal appends, exact and changed duplicate behavior,
 revision/privacy/unknown-kind zero writes and full/checkpoint-tail replay. It does not admit arbitrary policy kinds,
obligation settlement, payment or a generic cross-domain writer.

- `.harness/verification/infra-government-policy-registration-report.json`

### `infra-debt-settlement-formal-spine`

Backend-only INF-2L proof that the existing fixed simple-debt owner now uses
`GameplayCommandEnvelope -> DebtSettlementPlan -> owner fragments -> one
GameplayEventStore.append_batch()` across its existing Economy, Contract, Debt
and Commerce streams. Ten independent selectors prove issue/payment formal
fragments and redacted authority outboxes, legacy event compatibility, exact
duplicate zero-write, changed-idempotency zero-write, stale revision zero-write,
closed event/type-to-stream admission zero-write, generic full/checkpoint-tail
replay, and the owner-local `DebtAuthorityService.replay_projection`
full/checkpoint-tail reader. It does not admit arbitrary payment, caller-open
policy registration, or a generic cross-domain writer.

- `.harness/verification/infra-debt-settlement-formal-spine-report.json`

### `infra-governed-authority-contract-catalog`

Backend-only cross-INF proof for the immutable, read-only catalog that binds
existing lifecycle, Government policy, Debt settlement, Ecology-to-Organization
consumer, and Organization branch-promotion contracts. Eight independent
selectors prove the fixed catalog shape, unknown/kind rejection, owner/stream/
event/privacy fences, the fixed debt replay-reader surface, and each existing
owner path. The catalog cannot register contracts, append events, create a
coordinator, or authorize arbitrary policy, settlement, fanout, promotion, or
population truth.

- `.harness/verification/infra-governed-authority-contract-catalog-report.json`

### `infra-ecology-weather-front-economy-quote-edge`

Backend-only INF-3J proof for one sealed weather-front source to one existing
Economy quote owner. Independent selectors cover success, forged admission,
stale source, cross-quote reuse, exact duplicate/replay, changed-source
idempotency and authority-only source privacy. It does not admit generic
pricing, consumer registration, or Ecology economic writes.

- `.harness/verification/infra-ecology-weather-front-economy-quote-edge-report.json`

### `infra-ecology-weather-front-economy-quote-fanout`

Backend-only INF-3N proof for one fixed project-visible weather-front source
to exactly two existing Economy quotes in one owner batch. Independent checks
cover the two-event batch, opaque pair admission and arity, source/target/
catalog zero-write, idempotency with checkpoint-tail replay, and project-source
privacy. It does not admit a generic consumer registry, arbitrary fanout,
pricing formulas, account mutation, payment or a scheduler.

- `.harness/verification/infra-ecology-weather-front-economy-quote-fanout-report.json`

### `infra-ecology-weather-front-owner-contract-matrix`

Backend-only INF-3L proof that the immutable catalog contains distinct existing
Construction, Organization and Economy weather-front consumer contracts,
including INF-3N's fixed two-quote Economy row.
Separate selectors prove each row's metadata, each target owner's pre-append
zero-write mismatch fence, and the existing fixed two-facility Construction
batch. It does not register consumers, widen fanout, add retry/compensation,
or let Ecology append target-domain truth.

- `.harness/verification/infra-ecology-weather-front-owner-contract-matrix-report.json`

### `infra-economy-dynamic-quote-formal-spine`

Backend-only INF-2O proof that the existing Economy dynamic quote family uses
the formal owner append spine. Independent selectors cover owner/outbox,
idempotency, revision conflict, account-truth privacy rejection and replay. It
does not itself admit an Ecology consumer or a generic settlement writer.

- `.harness/verification/infra-economy-dynamic-quote-formal-spine-report.json`

### `infra-payroll-operating-window-closure`

Backend-only INF-2P/INF-2V proof that `OrganizationAuthority` is the sole
writer for `gameplay:organization:window:{window_ref}` open/close/due facts
while `EconomyAuthority` remains limited to wage
obligation/accrual/payment/overdue and the existing account transfer path.
Independent selectors cover the verified-completed-evidence
schedule-view-to-window/wage happy path, formal wage accrual/overdue append
path, paid-wage command-plan materialization, paid wage scoped outbox,
append-derived authority receipt, invalid or unverified evidence zero-write,
compatibility-wrapper delegation, duplicate idempotency, changed-key
open/close/due revision-conflict reuse, stale revision zero-write, privacy
scope, explicit overdue after close, and full/checkpoint-tail replay. It does
not admit a scheduler, generic payroll policy, or arbitrary cross-domain
settlement.

- `.harness/verification/infra-payroll-operating-window-closure-report.json`

### `infra-payroll-owner-contract-catalog`

Backend-only INF-2R proof that the immutable governed catalog records two
already-existing payroll owner rows and that each owner rejects a mismatched
catalog admission before append. Separate selectors prove Organization window
metadata, Economy wage-payment metadata, both zero-write fences, scoped
receipt/outbox, duplicate/revision behavior, and full/checkpoint-tail replay.
It is an extension admission substrate, not caller-open registration, a
generic payroll policy, a scheduler, or arbitrary cross-domain settlement.

- `.harness/verification/infra-payroll-owner-contract-catalog-report.json`

### `infra-government-promotion-owner-contract-catalog`

Backend-only INF-4Q proof that the immutable catalog records the one existing
Government passed-inspection production-promotion row and that
`GovernmentAuthority` rejects a catalog mismatch before it constructs a
fragment or appends. Nine independent selectors prove metadata, pre-append
zero-write, success, duplicate receipt replay, changed duplicate, stale source,
privacy, forged scenario identity and scoped checkpoint-tail production replay.
It does not admit generic promotion, a branch-domain writer, or group
simulation.

- `.harness/verification/infra-government-promotion-owner-contract-catalog-report.json`

### `infra-survival-unregistered-state-fence`

Backend-only INF-1V admission proof that an unregistered `reject` StateDefinition
cannot reach the existing Survival owner append path. It records a blocker, not
a newly admitted state row.

- `.harness/verification/infra-survival-unregistered-state-fence-report.json`

### `infra-ecology-frost-state-obligation`

Backend-only INF-1L proof for the fixed existing-ecology-owner
`effect:frost -> state:frosted@1` row. Twelve independent assertions cover
apply, refresh, exact and changed idempotency behavior, revision, command/source privacy,
unknown-row zero writes, caller-driven due expiry through the existing
coordinator, project-scoped outbox, and full/checkpoint-tail replay. It does
not authorize an ecology scheduler, retry/compensation, a new consumer edge,
or generic effect/state routing.

- `.harness/verification/infra-ecology-frost-state-obligation-report.json`

### `infra-ecology-drought-state-obligation`

Backend-only INF-1AA proof for the seventh finite Ecology state-owner row
`effect:drought -> state:drought@1`. Independent selectors cover owner apply,
missing/private/forged/stale source rejection, wrong effect/definition,
revision/privacy/catalog/second-active-obligation zero write, owner-only due
expiry, append-derived outbox/receipt, full/checkpoint-tail replay, strict
semantic command/admission, and the finite state/lifecycle/adapter catalog
rows. It does not authorize generic lifecycle closure, a scheduler, direct
semantic append, or a new Ecology consumer edge.

- `.harness/verification/infra-ecology-drought-state-obligation-report.json`

### `infra-ecology-frost-state-action`

Backend-only INF-1Z proof for the one fixed semantic frost dispel proposal.
The existing Ecology authority alone appends `crop_state_dispelled` and the
exact open obligation cancellation in one existing canonical stream batch.
Eight independent selectors cover owner append, exact and changed duplicate,
inactive source, revision, privacy, lifecycle-action contract rejection, and
full/checkpoint-tail replay. It does not admit generic Ecology actions,
repair/transform semantics, a scheduler, or cross-domain writes.

- `.harness/verification/infra-ecology-frost-state-action-report.json`

### `infra-closed-state-owner-contract-matrix`

Backend-only INF-1M proof for the finite seven-row StateDefinition owner
matrix. Independent checks prove its exact shape, unknown-row rejection,
fixed Ecology event/privacy contract, and zero-write rejection of forged
contract metadata at the Survival, Construction and Ecology append boundaries,
plus existing replay/privacy evidence. It is not open registration, generic
dispatch or a writer.

- `.harness/verification/infra-closed-state-owner-contract-matrix-report.json`

### `infra-finite-lifecycle-contract-closure`

Backend-only INF-1Q proof for one immutable reader over the five existing
StateDefinition rows and the existing Economy wage-obligation row. Separate
selectors prove exact shape, unknown-contract rejection, action/terminal-event
admission, fixed metadata, and each existing owner family's fence and
checkpoint-tail replay. The reader neither registers rows nor writes world
truth; Ecology frost remains owner-local rather than a generic semantic route.

- `.harness/verification/infra-finite-lifecycle-contract-closure-report.json`

### `infra-closed-lifecycle-registration-admission`

Backend-only INF-2M proof that the obligation coordinator accepts only six
existing owner lifecycle registrations and their closed owner-local event
families. Independent selectors prove closed
policy shape, policy-less/unknown/forged/widened registration zero-write,
terminal-plus-smuggled-event zero-write, and existing Construction and Survival
owner success plus replay. It separately proves that a project-scoped owner
fragment cannot override its event visibility to `authority_only`. Historical
caller-generated generic fragments are explicitly rejection evidence; this does
not add open policy registration or generic cross-domain settlement.
The Construction due-completion selector separately proves that no terminal
fragment can append without its exact committed `run_started` source event.

- `.harness/verification/infra-closed-lifecycle-registration-admission-report.json`

### `infra-economy-wage-terminal-lifecycle`

Backend-only INF-2D proof for the existing Economy wage-accrual owner row's
authority-owned closed registration, retry, cancel, expiry and accrual-only
compensation fragments. It independently asserts registration ownership,
one-store append receipts, exact and changed-duplicate idempotency, revision,
privacy and replay.
Expiry closes only the unpaid obligation and writes no wage accrual, payment or
account change. It does not admit payment, balance recovery, generic owner
lifecycle binding, or a unified cross-domain settlement receipt.

- `.harness/verification/infra-economy-wage-terminal-lifecycle-report.json`

### `infra-owner-only-obligation-commit-spine`

Backend-only INF-2Q proof that `ObligationSettlementCoordinator` only plans
validated owner batches and cannot receive a callback or append world truth.
Independent selectors prove planner and direct-call zero writes, raw-store
callback rejection, each existing Construction, Survival, Ecology and two
Economy owner commit rows, duplicate idempotency, revision conflict, scoped
privacy and full/checkpoint-tail replay. It does not admit caller-open policy
registration, arbitrary cross-domain settlement, a second scheduler/store or a
new truth owner.

- `.harness/verification/infra-owner-only-obligation-commit-spine-report.json`

### `infra-state-lifecycle-adapter-matrix`

Backend-only INF-1W proof for the immutable semantic adapter admission matrix.
Its separate selectors prove the existing four Survival and one Construction
apply rows, unsupported-operation rejection before append, both owner action
paths, duplicate/revision/privacy fences, and full/checkpoint-tail replay.
The matrix has no callback or append path. Ecology and Economy remain excluded
because no semantic proposal adapter has been admitted for either owner.

- `.harness/verification/infra-state-lifecycle-adapter-matrix-report.json`

### `infra-semantic-ecology-frost-adapter`

Backend-only INF-1X proof for one closed semantic frost proposal mapped to the
existing Ecology crop-state owner. Separate selectors prove strict input,
owner append, revision/snapshot/idempotency, source-privacy and forged-region
relation zero writes, and Ecology checkpoint-tail replay. It does not admit generic Ecology effects,
caller-selected streams, or a semantic append path.

- `.harness/verification/infra-semantic-ecology-frost-adapter-report.json`

### `infra-ecology-semantic-adapter-matrix-admission`

Backend-only INF-1Y proof that the immutable semantic adapter matrix admits
only the already-existing `effect:frost -> state:frosted@1` Ecology entry for
`apply`. Separate selectors prove the matrix/operation fence, matrix-gated
zero-write entry rejection, strict input, owner append, stale revision,
snapshot, exact/changed duplicate, source privacy/relation, and checkpoint-tail
replay. It does not make the generic state command sufficient for Ecology's
hazard/crop/region source contract.

- `.harness/verification/infra-ecology-semantic-adapter-matrix-admission-report.json`

### `infra-economy-account-settlement-spine`

Backend-only INF-2H proof for the existing `EconomyAuthorityService` account
ledger owner. Independent selectors prove the owner-built
`GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch`
path, authority-scoped redacted outbox, append-derived authority receipt,
duplicate and changed-duplicate behavior, stale-revision and insufficient-funds
zero writes, owner/authority privacy, receipt scope rejection, and full versus
checkpoint-tail replay. It covers only the existing single-stream account
opening, same-currency transfer, and budget reservation events; it does not
admit generic payment, open policy registration, or cross-domain settlement.

- `.harness/verification/infra-economy-account-settlement-spine-report.json`

### `infra-commerce-delivery-payment`

Backend-only INF-2AA proof for one exact `EconomyAuthorityService` payment and
compensation row. Seven independent selectors prove the single append-derived
payment receipt, source/account/currency/privacy/revision zero writes,
commitment-bound reservation and source-head zero writes, idempotency, exact
compensation, insufficient-funds rejection, and authority-only full versus
checkpoint-tail replay. It does not prove generic payment, compensation,
policy registration, or cross-domain settlement.

- `.harness/verification/infra-commerce-delivery-payment-report.json`

### `infra-append-derived-settlement-receipt`

Backend-only INF-2S proof that committed and rejected `SettlementReceipt`
instances derive solely from one append result. Independent selectors cover the
shared factory, Economy/Commerce authority-only reader scopes, the read-only
obligation reader, and owner-only append/replay. It does not authorize a
coordinator or generic business settlement writer.

- `.harness/verification/infra-append-derived-settlement-receipt-report.json`

### `infra-economy-scheduled-transfer-obligation`

### `infra-ecology-drought-process`

Backend-only INF-3K proof for one caller-driven drought process on an existing
Ecology region stream. Independent checks prove one owner batch, authority/
privacy/revision zero writes, exact duplicate and checkpoint-tail replay. It
does not authorize a hazard consumer, scheduler, or cross-domain writer.

- `.harness/verification/infra-ecology-drought-process-report.json`

Backend-only INF-2J proof for one fixed Economy account-transfer obligation.
Each selector independently proves the event-derived open/due/settled,
cancelled, or expired lifecycle; exact and changed idempotency; duplicate
source, revision, insufficient-funds, and forged-input zero writes;
authority-only receipt/outbox privacy; and full versus checkpoint-tail replay.
It admits only `policy:economy_scheduled_account_transfer@1` on
`gameplay:economy`; it does not admit caller policy registration, generic
payment, reservation release, retry/compensation, or cross-domain settlement.

- `.harness/verification/infra-economy-scheduled-transfer-obligation-report.json`

### `infra-continuation-gate`

Backend-only continuation preflight for the active INF sequence. It runs seven
independent assertions for the admitted ecology owner, canonical stream,
record kinds, event family, canonical write path, and the INF-3Y empty enabled
consumer-edge stop fence. It also records the required predecessor reports and
the exact missing consumer contract. This profile is declarative: it cannot
write events and does not authorize a hazard edge.

Output:

- `.harness/verification/infra-continuation-gate-report.json`

### `infra-hazard-propagation`

Backend-only INF-3Y proof for exactly one registered edge,
`ecology-hazard:frost-to-construction-finish:v1`. The ecology owner only emits
a project-visible canonical hazard/crop proposal. The existing construction
owner verifies the exact source vector and writes its existing due-finish
fragment through one append batch. Sixteen independent assertions cover success,
unknown/disabled edge, source/revision/privacy/direct-input zero writes,
forged-authority/admission rejection including a real-class forged admission
and a module-API admission-issuer fence,
event-derived retired-source rejection,
exact crop pinning, idempotency, scoped projection and checkpoint-tail replay. No other consumer,
fanout, retry, compensation or delayed canonical-hazard row is admitted.

Output:

- `.harness/verification/infra-hazard-propagation-report.json`

### `infra-civilization-capability-read`

Backend-only INF-4Y-A proof for the sole `CivilizationCapabilityAuthority`
owner admission. It independently verifies the canonical stream and outbox,
authority/revision/duplicate zero-write behavior, jurisdiction and effective
tick gates, authority/actor/public/creator scopes, event-derived correction and
revocation, and full/checkpoint-tail replay equivalence. It does not bind a
semantic or population consumer and does not admit civilization progression or
P6/P7 work.

- `.harness/verification/infra-civilization-capability-read-report.json`

### `infra-population-world-mode`

Backend-only INF-4R proof that a planner consumes only the typed frozen
`SocialFactAuthority.view_for` result. It separately proves recipient/time/
digest/source-vector pinning, stale and scope zero-write behavior, deterministic
planning, unsupported schedule/capability rejection, legacy generic-merge
zero-write, and social-source full/checkpoint-tail replay. It does not admit
household, organization, civilization, or full
population simulation behavior.

- `.harness/verification/infra-population-world-mode-report.json`

### `infra-household-org-source-projection`

Backend-only INF-4X proof that household membership is sourced by the existing
`SocialFactAuthority` and organization membership/role/shift/work-order
schedule rows by the existing `OrganizationAuthority`. It independently proves
canonical owner writes, recipient privacy, immutable source-input provenance,
effective-window filtering, forged provenance/digest zero-write, stale revision
zero-write, duplicate planning, and full/checkpoint-tail replay.
The planner remains proposal-only; kinship, care, organization policy,
unmapped civilization consumer bindings, INF-4Z full scope, and P6/P7 remain
blocked. The separately verified `supply` capability edge is documented by
`infra-civilization-capability-supply-consumer`.

- `.harness/verification/infra-household-org-source-projection-report.json`

### `infra-population-world-mode-complete`

Backend-only INF-4Z bounded proof for the admitted population world-mode rows.
It independently asserts immutable world-plan base/tail/budget pinning, caller-
selected `game` / `simulation` / `preview` cadence-budget labels, preview
production zero-write fencing, existing-owner `supply` and `inspection`
fragment/receipt paths, a separate generic inspection scoped-outbox privacy and
full/checkpoint-tail replay assertion, unsupported `work` zero-write, retired legacy
`PopulationBatchPlan` free-form merge zero-write, duplicate idempotency
replay, revision conflict zero-write, privacy-scope zero-write, activation-lock
pending zero-write, production full/checkpoint-tail replay, fixed-base branch
request digest pinning, fixed-base branch replay, and tail-boundary zero-write.

It does not admit a population truth store, generic `work` consumer mapping,
branch promotion, unmapped civilization consumer bindings, or P6/P7 work.

### `infra-population-branch-preview`

Backend-only INF-4Z branch evidence for isolated preview inputs. It separately
asserts shuffled candidate determinism, fixed-base digest zero-write,
calibration-digest zero-write, unknown-profile zero-write, dataset-scope
zero-write, metadata-buffer replay and production isolation. It intentionally
covers legacy caller metadata only; authoritative reference-data license
admission is proved separately by `infra-reference-data-license-admission`.
It does not prove replayable branch event/projection evolution, real branch
scenario progression, promotion, or full group simulation.

- `.harness/verification/infra-population-branch-preview-report.json`

### `infra-reference-data-license-admission`

Backend-only INF-4Z-A proof for the sole reference-data owner contract:
`authority:reference_data` writes registered/corrected/revoked dataset records
to `gameplay:reference_data:{dataset_ref}` through the existing event-store
spine. It independently asserts authoritative branch admission, revocation,
forged-digest, owner, revision and privacy zero-write paths, changed duplicate
handling, and full/checkpoint-tail replay. `BranchPreviewAuthority` receives a
frozen authority-scoped view only; external ingestion, branch promotion,
population truth, generic work, P6 and P7 remain excluded.

- `.harness/verification/infra-reference-data-license-admission-report.json`

### `infra-civilization-capability-supply-consumer`

Backend-only INF-4Y proof for the one user-approved capability-gated
eligibility edge: authority-scoped active `CivilizationCapabilityView` to an
existing `OrganizationAuthority` supply fragment. It independently asserts
owner receipt, event redaction, stale/forged/not-effective/unauthorized source
zero-write, candidate mapping, policy pin, revocation, organization revision,
idempotency, changed duplicate zero-write, independent capability lifecycle and
stream revisions, and full/checkpoint-tail replay. Inspection, work, semantic,
and every unlisted consumer remain rejected; no civilization progression or
P6/P7 work is admitted.

- `.harness/verification/infra-civilization-capability-supply-consumer-report.json`

### `infra-civilization-capability-inspection-consumer`

Backend-only INF-4Y proof for the second user-approved capability-gated
eligibility edge: authority-scoped active `CivilizationCapabilityView` to the
existing `GovernmentAuthority` commercial-inspection fragment. Its independent
assertions cover Government owner receipt, actor-scoped outbox projection, opaque capability provenance,
jurisdiction mapping, stale/forged/scope/policy/target-revision/privacy
zero-write, duplicate/changed-duplicate behavior and full/checkpoint-tail
replay. Government's existing target jurisdiction remains inspection data;
capability source lineage is not emitted. Supply is separately proven; work,
semantic and unlisted consumers remain rejected, with no civilization
progression, P6 or P7 work.

- `.harness/verification/infra-civilization-capability-inspection-consumer-report.json`

### `infra-production-completed-evidence-source`

Backend-only INF-4Z source admission for the narrow Production-owned
`production-completed` evidence row. It independently asserts committed worker
contribution linkage, a finished run source requirement, canonical
`GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch`
owner path, actor event scope, redacted outbox, empty/untrusted/mismatched/stale
zero-write, duplicate/changed-duplicate behavior, and full/checkpoint-tail
scoped-view digest/vector replay. It does not admit a PopulationPlanner work
consumer, wage accrual, payroll, or non-production work evidence.

- `.harness/verification/infra-production-completed-evidence-source-report.json`

### `infra-production-evidence-wage-consumer`

Backend-only INF-4Z proof for the one Production completed-evidence to Economy
wage-accrual consumer. It independently asserts worker-scoped frozen source
admission, Economy owner envelope/SettlementPlan write, source event/vector/
digest and wage-policy pins, event/outbox redaction, forged/stale/privacy/wage
revision zero-write, duplicate/changed-duplicate behavior, and
full/checkpoint-tail replay. It does not admit generic work, non-production
evidence, payroll payment, compensation, civilization consumers, or P6/P7.

- `.harness/verification/infra-production-evidence-wage-consumer-report.json`

### `infra-organization-economy-commerce-commitment`

Backend-only INF-2I proof for one fixed Organization/Economy commerce
commitment. It independently asserts the existing owner fragments and one
append batch, append-derived authority receipt, exact and changed idempotency,
Organization and Economy revision zero-writes, missing budget reservation,
public/outbox privacy, full/checkpoint-tail replay, and receipt scope. It does
not admit generic settlement, payment, policy registration, a scheduler, group
simulation, or branch promotion.

- `.harness/verification/infra-organization-economy-commerce-commitment-report.json`

- `.harness/verification/infra-population-world-mode-complete-report.json`

### `infra-exact-lifecycle-owner-contract-catalog`

Backend-only INF-2Y proof that the governed catalog contains exact existing
Survival, Construction maintenance, Ecology frost/drought, and Economy wage
lifecycle rows instead of the synthetic lifecycle placeholder. Its five
independent checks cover exact row metadata, scope rejection, separate
Survival and Construction pre-append zero-write gates, and existing
checkpoint-tail replay. It does not prove caller-open registration, a generic
lifecycle dispatcher, scheduler, or cross-domain settlement.

### `infra-economy-tax-obligation`

Backend-only INF-2Z proof for one fixed Economy owner-local tax obligation.
Its independent checks cover committed-source pinning, exact and changed
idempotency, forged-source and stale-revision zero-write, terminal settlement
without account mutation, cancellation/expiry, authority-only outbox privacy,
and full/checkpoint-tail lifecycle replay. It does not admit payment truth,
account debit/credit, caller-open policy registration, compensation, or
arbitrary cross-domain settlement.

- `.harness/verification/infra-economy-tax-obligation-report.json`

### `infra-economy-government-tax-payment`

Backend-only INF-2AB proof for the approved bounded Treasury collector
identity and Economy-owned government tax-payment capability. Its independent
selectors prove committed tax-due jurisdiction/currency pins, explicit
Economy payer-binding/account-opened pins, collector identity privacy and
replay, the one atomic payment vector, the exact compensation/reopen vector,
authority-only receipt/outbox behavior, full/checkpoint-tail replay, exact and
changed idempotency, and capability/collector/revision zero-write rejection.
It does not admit a generic Treasury, arbitrary payment, transfer, or
settlement authority.

- `.harness/verification/infra-economy-government-tax-payment-report.json`

### `infra-package-declared-negotiated-exchange`

Backend-only INF-2AC proof for the approved immutable-package negotiated
exchange row. Its independent selectors separately prove the admitted
inventory, ownership, and completed-service success modes; fixed price,
source, capability, and inactive-package zero-write rejection; authority-only
receipt and projection scopes; exact duplicate replay and changed-duplicate
zero-write; and full versus checkpoint-tail replay equivalence. It does not
admit generic payment, transfer, treasury, market pricing, compensation,
router, registry, coordinator, or a new truth owner.

- `.harness/verification/infra-package-declared-negotiated-exchange-report.json`

### `infra-reusable-state-transition-plan`

Backend-only INF-1C1 proof for the pure reusable `StateTransitionPlan`.
Independent checks cover add/replace/refresh/reject, scheduled expiry,
dispel, transform, proposal-only zero-write shape, and reuse across existing
Survival, Construction and Ecology definitions. It does not prove generic
state registration, owner routing, event append, or lifecycle settlement.

- `.harness/verification/infra-reusable-state-transition-plan-report.json`

### `infra-ecology-consumer-admission-contract`

Backend-only INF-C4 proof for a finite, read-only weather-front consumer
admission check reused by existing Construction and Organization target owners.
Its independent checks cover two-owner contract reuse, forged owner/stream/
scope/source zero-write, target revision zero-write, existing owner duplicate
idempotency, privacy denial, and full/checkpoint-tail replay. It does not
issue admissions, select owners, construct fragments, append events, or
register generic consumers.

- `.harness/verification/infra-ecology-consumer-admission-contract-report.json`

### `infra-weather-front-survival-dehydration`

Backend-only INF-3Q proof for one fixed project-visible
`weather:drought -> Survival dehydrated` target edge. Independent selectors
prove the one Survival append receipt, missing/wrong-source zero-write,
assignment/privacy and source/target revision fences, exact and changed
idempotency, project-scoped redacted outbox, full/checkpoint-tail replay,
`drought_process_advanced` rejection, and no compensation or fanout vector.
It does not authorize an Ecology-to-Survival router, generic consumer registry,
new runtime, retry, compensation, or any other target edge.

- `.harness/verification/infra-weather-front-survival-dehydration-report.json`

## Evidence Rules

- Static checks prove only static wiring.
- Runtime claims require `phase0`, `phase1-slice`, or `mainline-unified-runtime`, depending on the scope being claimed.
- L1 subsystem integration claims may use `l1-world-fact-runtime`; this is a runtime-verification profile, not a product runtime.
- Backend-only live Siming model-provider architecture claims require explicit `siming-backend-chain`.
- Godot claims require scene execution or Godot MCP/editor inspection.
- Generated evidence should stay under `.harness/verification/`.
- Each Harness report and run manifest records both `run_id` and `suite_id`. For durable
  evidence, match an archived report and manifest on both identifiers; the mutable latest
  files are insufficient when concurrent runs can overwrite them.
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
### `infra-construction-facility-repair`

This independent INF-1AE profile proves one bounded Construction facility
repair and its explicit latest-repair compensation on the existing facility
stream. Seven selectors cover successful owner append and receipt, exact and
changed duplicate behavior, revision/privacy/amount zero-write rejection,
compensation, and full/checkpoint-tail projector replay. It does not admit
generic Construction actions, transform, payment, or material semantics.

### `infra-construction-bakery-reinforcement`

Backend-only INF-1AF proof for one fixed committed project-visible
`facility_acquired(facility_kind=bakery) -> bakery_reinforced` transition
inside the existing Construction owner. Eight independent selectors prove the
one append-derived receipt, source/revision zero-write rejection, owner-fixed
privacy and redacted outbox, exact/changed idempotency, durable acquisition
evidence after a repair, full/checkpoint-tail replay, and the terminal
no-compensation/no-fanout boundary. It does not admit a generic facility
transform, payment, material, policy registry, or second owner/runtime.

- `.harness/verification/infra-construction-bakery-reinforcement-report.json`

### `infra-branch-work-wage-owner-admission`

Backend-only INF-4T proof for one approved branch-request-to-Economy wage
vertical. Five independent selectors prove that a creator-debug branch
candidate is only a request: the existing Production completed-evidence view
is reread and pinned before the existing Economy owner appends one
actor-scoped `gameplay.economy.wage_accrued` event. The profile covers branch
snapshot/base/tail/replay pins, zero-write missing or forged source, worker and
privacy/revision fences, exact/changed idempotency, the single Economy receipt,
independent branch and Economy replay, and the no-combined-receipt,
no-payroll/no-compensation boundary. It does not admit a branch truth owner,
generic promotion, router, registry, payroll, payment, compensation, or any
other branch target.

- `.harness/verification/infra-branch-work-wage-owner-admission-report.json`
