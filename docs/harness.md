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
python scripts/verification/harness.py --profile character-model-live
python scripts/verification/harness.py --profile llm-integration-closure
python scripts/verification/harness.py --profile l1-world-fact-runtime
python scripts/verification/harness.py --profile mainline-unified-runtime
python scripts/verification/harness.py --profile model-provider-readiness
python scripts/verification/harness.py --profile godot-sampling-production-grade-providers
python scripts/verification/harness.py --profile embodied-skeletal-debug-replay
python scripts/verification/harness.py --profile vla-provider-backend
python scripts/verification/harness.py --profile non-runtime-production-pipeline
python scripts/verification/harness.py --profile perception-input-alignment
python scripts/verification/harness.py --profile embodied-interaction-contracts
python scripts/verification/harness.py --profile embodied-affordance-registry
python scripts/verification/harness.py --profile embodied-bridge-attestation
python scripts/verification/harness.py --profile embodied-action-controller
python scripts/verification/harness.py --profile embodied-authority-settlement
python scripts/verification/harness.py --profile embodied-interaction-replay
python scripts/verification/harness.py --profile embodied-interaction-foundation-all
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

For explicit VLA route comparison, run:

```powershell
python scripts/verification/benchmark_vla_advisory_routes.py --allow-live-call --samples 3
```

It replays the fresh Godot capture through each route and archives only redacted
per-attempt reports. Fewer than 20 samples are explicitly insufficient for
latency-percentile or semantic-quality claims.

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

Output:

- `.harness/verification/embodied-affordance-registry-report.json`
- `.harness/verification/embodied-affordance-registry-report.md`
- `.harness/verification/embodied-affordance-registry-trace.json`
- `.harness/verification/embodied-affordance-registry-godot-runtime.json`

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

### `embodied-interaction-foundation-all`

Dependency-ordered aggregate for embodied-interaction product foundation Phase 0 through Phase 5.

It runs:

- `embodied-interaction-contracts`
- `embodied-affordance-registry`
- `embodied-bridge-attestation`
- `embodied-action-controller`
- `embodied-authority-settlement`
- `embodied-interaction-replay`

Phase 6 remains blocked by design until the Gameplay Foundation event store and atomic event-batch writer are implemented and verified.

Output:

- `.harness/verification/embodied-interaction-foundation-all-report.json`
- `.harness/verification/embodied-interaction-foundation-all-report.md`

### `all`

Runs `docs`, `boundaries`, `drift`, `backend-contract`, `godot-project`, `character-agent-execution`, `release-gate`, `harness-lifecycle`, `change-lifecycle`, `harness-reference`, `harness-evolution`, `phase0`, `phase1-slice`, `l1-world-fact-runtime`, `mainline-unified-runtime`, `model-provider-readiness`, `godot-sampling-production-grade-providers`, `embodied-skeletal-debug-replay`, `vla-provider-backend`, `actor-scene-knowledge-lifecycle`, `siming-global-situation-layer`, `interaction-orchestration-service`, `esm-physical-channel-world-actuation`, `non-runtime-production-pipeline`, `perception-input-alignment`, `embodied-interaction-contracts`, `embodied-affordance-registry`, `embodied-bridge-attestation`, `embodied-action-controller`, `embodied-authority-settlement`, `embodied-interaction-replay`, and `embodied-interaction-foundation-all` in order. It stops on the first failed profile.

`siming-backend-chain` is excluded from `all` because it requires live model-provider credentials.
`character-model-live` and `llm-integration-closure` are also excluded from `all`; they require fresh live provider artifacts and an explicit closure run ID.

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

## Evidence Rules

- Static checks prove only static wiring.
- Runtime claims require `phase0`, `phase1-slice`, or `mainline-unified-runtime`, depending on the scope being claimed.
- L1 subsystem integration claims may use `l1-world-fact-runtime`; this is a runtime-verification profile, not a product runtime.
- Backend-only live Siming model-provider architecture claims require explicit `siming-backend-chain`.
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
