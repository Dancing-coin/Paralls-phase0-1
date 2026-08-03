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
python scripts/verification/harness.py --profile embodied-interaction-session
python scripts/verification/harness.py --profile embodied-handoff-authority
python scripts/verification/harness.py --profile embodied-grab-carry-place-authority
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

### `script-evolution-proof`

Static proof that script-evolution rules and their regression coverage remain
present. This profile is part of the normal registry order and should be run
when changing governed script-evolution behavior.

### `siming-heavenly-graph-foundation`

Proof profile for the Siming heavenly-graph foundation and its governed
runtime contracts.

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
cross-version reader/rollback compatibility, privacy views, or Godot delivery.

Output:

- `.harness/verification/gameplay-patch-runtime-report.json`
- `.harness/verification/gameplay-patch-runtime-report.md`
- `.harness/verification/gameplay-patch-runtime-pytest.log`

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
bounded after-commit connection-fanout plumbing, and a local Godot bridge probe
that routes only granted actors and clears state on disconnect.

It does not prove a production identity adapter, a live WebSocket-to-Godot
deployment, reconnect/resync, prediction, persistence, or migration behavior.

Output:

- `.harness/verification/godot-gameplay-mirror-report.json`
- `.harness/verification/godot-gameplay-mirror-report.md`
- `.harness/verification/godot-gameplay-mirror-pytest.log`

### `adventure-basic`

Validates the strict, digest-checked governed `adventure-basic` manifest before
Patch activation plus the backend-only Scenario 1 fixed-offer purchase/equip
composition. This is not evidence of Patch activation, replay comparison,
mirror delivery, Godot result, or the remaining reference scenarios.

Output:

- `.harness/verification/adventure-basic-report.json`
- `.harness/verification/adventure-basic-report.md`
- `.harness/verification/adventure-basic-pytest.log`

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

Runs `docs`, `boundaries`, `drift`, `backend-contract`, `godot-project`, `character-agent-execution`, `release-gate`, `harness-lifecycle`, `change-lifecycle`, `harness-reference`, `harness-evolution`, `phase0`, `siming-backend-chain`, `character-model-live`, `l1-world-fact-runtime`, `llm-integration-closure`, `phase1-slice`, `mainline-unified-runtime`, `model-provider-readiness`, `godot-sampling-production-grade-providers`, `embodied-skeletal-debug-replay`, `tts-voice-profile-adapter`, `vla-provider-backend`, `actor-scene-knowledge-lifecycle`, `siming-global-situation-layer`, `interaction-orchestration-service`, `esm-physical-channel-world-actuation`, `non-runtime-production-pipeline`, `perception-input-alignment`, `embodied-interaction-contracts`, `embodied-affordance-registry`, `embodied-bridge-attestation`, `embodied-action-controller`, `embodied-authority-settlement`, `embodied-interaction-replay`, `gameplay-foundation-contract`, `gameplay-event-replay`, `gameplay-foundation-event-spine`, `gameplay-state-groups`, `embodied-interaction-session`, `gameplay-resource-body`, `embodied-handoff-authority`, `gameplay-effective-stats`, `embodied-grab-carry-place-authority`, `gameplay-status-tags`, `embodied-interaction-foundation-all`, `gameplay-ability-affordance`, `godot-gameplay-mirror`, `gameplay-inventory`, `gameplay-possession-equipment`, `gameplay-ownership-authority`, `gameplay-economy-authority`, `gameplay-patch-runtime`, and `adventure-basic` in profile order. It stops on the first failed profile.

`siming-backend-chain` is excluded from `all` because it requires live model-provider credentials.
`character-model-live` and `llm-integration-closure` are also excluded from `all`; they require fresh live provider artifacts and an explicit closure run ID.
`gameplay-patch-runtime` follows `gameplay-economy-authority` by profile order
and verifies the current Patch Rule IR/lifecycle foundation. `adventure-basic`
follows it and proves its strict digest-valid manifest plus the backend-only
Scenario 1 purchase/equip composition; it does not make Patch activation,
cross-runtime proof, or the remaining adventure scenarios part of the
repository-wide closure.

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
