# Siming-Led Population Simulation Implementation Plan（司命主导群体模拟实现计划）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a game-start population simulation governed by Siming that produces validated character simulation seeds, injects them into the same `CharacterRecord`, and activates high-fidelity character cognition when structured player interaction requires it.

**Architecture:** Keep `SimingRuntime.tick(inputs)` as the only Siming decision and dispatch path. Add one internal `PopulationSimulationCapability` that consumes an immutable cadence/read-set, invokes the pure `PopulationPlanner`, classifies outcomes, submits the existing `schedule_gated_supply` owner capability when admitted, and requests Character Core continuity settlement. Character activation changes cognition fidelity for the same actor; it never transfers world authority or gives Siming/Planner direct memory write access.

**Tech Stack:** Python 3, Pydantic v2 contracts, existing `GameplayEventStore`/`SettlementPlan`/outbox/replay spine, existing Character Agent L1-L4 runtime and memory stores, pytest, verification Harness JSON profiles.

**Spec:** `docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-29-siming-led-population-simulation-design.md`

## Global Constraints

- `SimingRuntime.tick(inputs)` remains the only Siming decision and dispatch path.
- Population simulation is a Siming-owned capability domain; `PopulationPlanner` is calculation-only and has no independent principal, owner selection authority, or append authority.
- The game-start cadence comes from existing world-mode/activation/schedule projections; do not create a second clock, scheduler, runtime, event store, bus, or generic writer.
- Objective world facts are committed only by the statically admitted domain Owner through `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`.
- `CharacterSimulationSeed` is a structured, revisioned continuity input, never raw prompt text, `siming_output`, or a five-pool memory record.
- Only Character Core may admit `CharacterContinuityCommand`, append `SeedDelta`, update actor continuity state, materialize five-pool memory, or advance actor continuity cursors.
- Player interaction may trigger prewarm/activation policy but cannot directly select a world owner, stream, event family, memory pool, or actor truth.
- Unknown, stale, private, branch-only, duplicate, catalog-mismatched, or exposure-invalid inputs produce an auditable zero-write/requeue result.
- New behavior types require a source-controlled catalog revision and become eligible in the next population batch, never in the tick that proposes them.
- Use ASCII in new code and comments unless an existing file already requires another character set.
- Every implementation task ends with focused pytest, `git diff --check`, and a Chinese commit message.

---

## Task 0: Baseline and Plan Registration

**Files:**
- Modify: `docs/superpowers/plans/world-character-siming-authority-mainline/README.md`
- Test: no runtime test; baseline commands below

**Interfaces:**
- Consumes: approved spec and existing P3A-P3D implementation evidence.
- Produces: an indexed plan path and a clean baseline report for the executor.

- [ ] **Step 1: Record the current baseline**

Run:

```powershell
python -m pytest -q backend/tests/test_population_continuity.py backend/tests/test_siming_event_pipeline.py backend/tests/test_siming_agent_loop_runtime.py backend/tests/test_character_agent_runtime_memory_integration.py
python scripts/verification/harness.py --profile phase3-population-continuity
git diff --check
```

Expected: focused tests and the existing `phase3-population-continuity` profile pass; any pre-existing worktree changes remain untouched.

- [ ] **Step 2: Register the new plan in the plan tree**

Add this entry after the existing population continuity entry in `docs/superpowers/plans/world-character-siming-authority-mainline/README.md`:

```markdown
12. [2026-08-29-siming-led-population-simulation-implementation-plan.md](2026-08-29-siming-led-population-simulation-implementation-plan.md) - Siming-governed game-start population cadence, seed continuity, and player activation handoff
```

- [ ] **Step 3: Verify documentation formatting**

Run:

```powershell
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 4: Commit the plan registration**

```powershell
git add docs/superpowers/plans/world-character-siming-authority-mainline/README.md
git commit -m "登记司命主导群体模拟实现计划"
```

## Task 1: Cadence, Read-Set, Seed, and Receipt Contracts

**Files:**
- Create: `backend/app/population_continuity/siming_contracts.py`
- Create: `backend/app/character_agent/models/simulation_seed.py`
- Modify: `backend/app/models/siming_event.py`
- Modify: `backend/app/population_continuity/__init__.py`
- Test: `backend/tests/test_siming_population_contracts.py`

**Interfaces:**
- Consumes: existing `ContinuityModel`, `AuthorityEvent`, `SimingInput`, `WorldModeProfile`, and `BatchIntentCandidate`.
- Produces:
  - `PopulationCadenceInput.from_authority_event(event) -> PopulationCadenceInput`
  - `PopulationProjection(ref, scope, revision_vector, payload)`
  - `PopulationReadSet.from_inputs(cadence, projections) -> PopulationReadSet`
  - `PopulationOwnerReceipt`
  - `PopulationCycleResult`
  - `CharacterSimulationSeedCandidate`
  - `CharacterMemoryCandidate`
  - `CharacterContinuityCommand`
  - `CharacterContinuityReceipt`
  - `CharacterMemoryMaterializationReceipt`

- [ ] **Step 1: Write failing contract tests**

Add these tests to `backend/tests/test_siming_population_contracts.py`:

```python
def test_population_cadence_rejects_missing_source_pin() -> None:
    with pytest.raises(ValueError, match="cadence_source_pin_incomplete"):
        PopulationCadenceInput(
            cadence_id="cadence:1",
            world_ref="world:bakery",
            world_mode_ref="mode:bakery",
            world_mode_revision="mode:v1",
            cadence_source_ref="",
            cadence_source_revision="",
            window_start=100,
            window_end=200,
            base_checkpoint_ref="checkpoint:1",
            base_checkpoint_digest="sha256:base",
            base_revision_vector={"world:bakery": 1},
            source_revision_vector={"world:bakery": 1},
            policy_revision="policy:population:v1",
            selector_revision="selector:population:v1",
            ruleset_revision="rules:population:v1",
            deterministic_seed="seed:1",
            catch_up_limit=1,
            budget=2,
            report_scope="organization:summary",
        )


def test_population_read_set_digest_is_order_stable() -> None:
    first = PopulationReadSet.from_inputs(cadence(), [projection("a"), projection("b")])
    second = PopulationReadSet.from_inputs(cadence(), [projection("b"), projection("a")])
    assert first.read_set_digest == second.read_set_digest


def test_seed_candidate_is_actor_scoped_and_not_a_memory_record() -> None:
    seed = CharacterSimulationSeedCandidate(
        seed_id="seed:char_a:1",
        actor_ref="character:char_a",
        world_ref="world:bakery",
        from_tick=100,
        to_tick=101,
        source_event_refs=("evt:frost:101",),
        source_owner_receipt_refs=("receipt:frost:101",),
        state_deltas={"need_tension": {"physiological_pressure": 0.12}},
        memory_candidates=(),
        drift_candidates=(),
        activation_hints={"salience": 0.8},
        presentation_seed={"task": "replenish_family_food"},
        visibility_scope="actor:self",
        privacy_disposition="scoped",
        source_revision_vector={"world:bakery": 101},
        ruleset_revision="rules:population:v1",
        selector_revision="selector:population:v1",
        deterministic_seed="seed:char_a:1",
        idempotency_key="seed:char_a:1",
    )
    assert seed.actor_ref == "character:char_a"
    assert seed.materialization_status == "pending"
    assert seed.memory_candidates == ()


def test_continuity_command_requires_owner_receipt_for_world_effect() -> None:
    with pytest.raises(ValueError, match="owner_settlement_required"):
        CharacterContinuityCommand(
            command_id="continuity:char_a:1",
            actor_ref="character:char_a",
            source_owner_receipt_refs=(),
            expected_character_revision=0,
            source_revision_vector={"world:bakery": 1},
            state_delta={"need_tension": {"physiological_pressure": 0.12}},
            memory_candidate_refs=(),
            exposure_evidence=(),
            policy_revision="policy:character-continuity:v1",
            idempotency_key="continuity:char_a:1",
            world_effect_required=True,
        )
```

The test helpers must construct fully pinned `PopulationCadenceInput` and `PopulationProjection` objects; do not use unvalidated dictionaries.

Define `cadence(**updates) -> PopulationCadenceInput`, `projection(ref, **payload) -> PopulationProjection`, and `cadence_event(**payload) -> AuthorityEvent` in the same test module. `cadence` starts from the exact bakery defaults used by the assertions (`world:bakery`, mode revision `mode:v1`, source revision `1`, window `100..101`, budget `2`, report scope `organization:summary`) and applies explicit updates. `projection` sets scope `organization:summary` and source revision `{"world:bakery": 1}`. `cadence_event` places the serialized cadence under `payload["population_cadence"]` and sets `event_type="population_cadence_event"`.

- [ ] **Step 2: Run the new tests and verify they fail**

```powershell
python -m pytest -q backend/tests/test_siming_population_contracts.py
```

Expected: FAIL because the new contract classes and `population_cadence_input` input literal do not yet exist.

- [ ] **Step 3: Implement the closed contracts**

Implement `PopulationCadenceInput`, `PopulationProjection`, `PopulationReadSet`, `PopulationBatchReport`, and `PopulationCycleResult` with `ConfigDict(extra="forbid", frozen=True)`. `PopulationReadSet.from_inputs` sorts projections by `ref`, computes a stable SHA-256 digest from canonical JSON, and preserves each projection revision vector. `PopulationCadenceInput.from_authority_event` rejects missing, revoked, stale, or scope-incompatible payload pins before returning a model.

Implement `CharacterSimulationSeedCandidate`, `CharacterContinuityCommand`, and `CharacterContinuityReceipt` in `backend/app/character_agent/models/simulation_seed.py`. `CharacterContinuityCommand` rejects `world_effect_required=True` without at least one owner receipt; all models reject empty actor refs and duplicate idempotency keys. Add `population_cadence_input` to `SimingInputType`.

The contract fields used by later tasks are fixed here: `PopulationBatchReport` contains `batch_ref`, `selected_cohort_refs`, `presentation_seeds`, `activation_candidates`, `owner_bound_intents`, `rejected_candidates`, `budget_used`, `budget_remaining`, `unprocessed_cohort_refs`, `read_set_digest`, and `result_digest`; `PopulationOwnerReceipt` contains `receipt_ref`, `owner_ref`, `event_family`, `committed`, `revision_vector`, and `zero_write`; `PopulationCycleResult` contains `status` (`accepted|owner_settlement_required|requeue|rejected`), `batch_ref`, `report`, `seed_candidates`, `owner_receipts`, `continuity_receipts`, `audits`, `reason`, and `production_append_count`; `CharacterMemoryCandidate` contains `candidate_id`, `actor_ref`, `candidate_kind`, `source_event_refs`, `event_valid_at`, `knowledge_available_at`, `exposure_basis`, `summary`, `confidence`, `salience`, `visibility_scope`, `privacy_disposition`, `materialization_policy`, `dedup_key`, and `source_revision_vector`; `CharacterSimulationSeedCandidate` contains `owner_effect_status`, `materialization_status`, and a tuple of `CharacterMemoryCandidate`; `CharacterMemoryMaterializationReceipt` contains `candidate_id`, `actor_ref`, `status`, `selected_pool`, `memory_cursor`, and `refusal_reason`.

- [ ] **Step 4: Run the focused tests**

```powershell
python -m pytest -q backend/tests/test_siming_population_contracts.py
```

Expected: PASS.

- [ ] **Step 5: Commit the contract seam**

```powershell
git add backend/app/population_continuity/siming_contracts.py backend/app/character_agent/models/simulation_seed.py backend/app/models/siming_event.py backend/app/population_continuity/__init__.py backend/tests/test_siming_population_contracts.py
git commit -m "增加群体模拟节奏与角色种子契约"
```

## Task 2: Pure Population Planning and Seed Derivation

**Files:**
- Create: `backend/app/population_continuity/seed_planner.py`
- Modify: `backend/app/population_continuity/batch.py`
- Modify: `backend/app/population_continuity/__init__.py`
- Test: `backend/tests/test_siming_population_planner.py`

**Interfaces:**
- Consumes: `PopulationReadSet`, existing `PopulationPlanner`, `BatchIntentCandidate`, `WorldModeProfile`, and authorized actor/organization projections.
- Produces:
  - `PopulationPlanner.plan_population_cycle(read_set: PopulationReadSet) -> PopulationBatchReport`
  - `CharacterSeedPlanner.derive(read_set: PopulationReadSet, accepted_owner_receipts: Sequence[str]) -> Sequence[CharacterSimulationSeedCandidate]`
  - deterministic `PopulationBatchReport` with candidate classification and budget accounting.

- [ ] **Step 1: Write failing planner tests**

Add these tests to `backend/tests/test_siming_population_planner.py`:

```python
def test_population_cycle_is_deterministic_when_projection_order_changes() -> None:
    planner = PopulationPlanner()
    first = planner.plan_population_cycle(read_set_with_projection_order("a", "b"))
    second = planner.plan_population_cycle(read_set_with_projection_order("b", "a"))
    assert first.model_dump() == second.model_dump()


def test_seed_derivation_requires_owner_receipt_for_objective_change() -> None:
    seeds = CharacterSeedPlanner().derive(read_set_with_supply_candidate(), ())
    assert seeds[0].state_deltas
    assert seeds[0].owner_effect_status == "owner_settlement_required"
    assert seeds[0].materialization_status == "pending"


def test_seed_derivation_records_exposure_without_granting_global_knowledge() -> None:
    seeds = CharacterSeedPlanner().derive(read_set_with_public_frost(), ("receipt:frost:101",))
    candidate = seeds[0].memory_candidates[0]
    assert candidate.visibility_scope == "actor:self"
    assert candidate.exposure_basis in {"affected_directly", "public_propagation"}
    assert candidate.actor_ref == "character:char_a"


def test_unknown_behavior_is_report_only_and_not_owner_bound() -> None:
    report = PopulationPlanner().plan_population_cycle(read_set_with_candidate_kind("new_story_action"))
    assert report.rejected_candidates[0].reason == "capability_not_admitted"
    assert report.owner_bound_intents == ()


def test_routine_b0_behavior_never_requests_an_llm_activation() -> None:
    report = PopulationPlanner().plan_population_cycle(read_set_with_candidate_kind("routine_work"))
    assert report.activation_candidates == ()
    assert report.presentation_seeds


def test_high_value_b2_behavior_is_an_activation_candidate_with_budget_reason() -> None:
    report = PopulationPlanner().plan_population_cycle(read_set_with_candidate_kind("relationship_negotiation"))
    assert report.activation_candidates
    assert report.activation_candidates[0].reason == "high_value_b2_requires_activation"
```

- [ ] **Step 2: Run the planner tests and verify failure**

```powershell
python -m pytest -q backend/tests/test_siming_population_planner.py
```

Expected: FAIL because `plan_population_cycle`, `CharacterSeedPlanner`, and the report contract are not implemented.

The test module must define `read_set_with_projection_order(*refs)`, `read_set_with_supply_candidate()`, `read_set_with_public_frost()`, and `read_set_with_candidate_kind(kind)`, each returning `PopulationReadSet.from_inputs(cadence(), projections)`. They differ only in sorted projection order, registered `schedule_gated_supply`, public frost exposure, or the supplied closed action kind.

- [ ] **Step 3: Implement planner-only behavior**

Extend `PopulationPlanner` with a pure `plan_population_cycle` method that validates cadence/read-set pins, orders cohorts by the existing continuity policy and deterministic actor id, calls the existing `plan`/`plan_schedule_gated_supply` logic for the exact registered row, classifies every outcome as `presentation_seed`, `activation_candidate`, or `owner_bound_intent`, and returns selected cohort ids, budget used, unprocessed cohort ids, candidate ids, and rejection reasons.

Encode the behavior tiers in the closed planner rules: B0 baseline behavior uses deterministic rules and emits `presentation_seed`; B1 local reaction may use bounded rules or a small model and emits a seed or activation candidate; B2 relationship negotiation and B3 high-value events emit activation candidates carrying `activation_reason`, budget, scope, source revision, and an explicit fallback of `no-op` or `requeue`. The planner never runs a per-actor full LLM loop.

Implement `CharacterSeedPlanner` in a separate file. It may derive `state_deltas`, `activation_hints`, `presentation_seed`, and exposure-qualified `memory_candidates`, but it must never call `GameplayEventStore.append_batch()`, `ProfileActivationAuthority`, a domain Owner, or a Character Core write method. A seed whose objective effect lacks an owner receipt must carry `owner_effect_status="owner_settlement_required"` and remain pending. Preserve source revision vector, ruleset revision, selector revision, deterministic seed, and report scope on every seed.

- [ ] **Step 4: Run focused and predecessor tests**

```powershell
python -m pytest -q backend/tests/test_siming_population_planner.py backend/tests/test_population_continuity.py
git diff --check
```

Expected: PASS with no whitespace errors.

- [ ] **Step 5: Commit planner derivation**

```powershell
git add backend/app/population_continuity/seed_planner.py backend/app/population_continuity/batch.py backend/app/population_continuity/__init__.py backend/tests/test_siming_population_planner.py
git commit -m "增加群体批量计划与角色种子派生"
```

## Task 3: Siming Population Capability and Tick Integration

**Files:**
- Create: `backend/app/services/siming_population_capability.py`
- Create: `backend/app/population_continuity/owner_adapters.py`
- Modify: `backend/app/services/siming_runtime.py`
- Modify: `backend/app/services/siming_event_consumer.py`
- Modify: `backend/app/services/siming_event_pipeline.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_siming_population_capability.py`
- Test: `backend/tests/test_siming_heavenly_runtime_tick.py`

**Interfaces:**
- Consumes: `PopulationCadenceInput`, `PopulationReadSet`, `PopulationPlanner`, `CharacterSeedPlanner`, existing Organization owner adapter, and a `CharacterContinuityPort`.
- Produces:
  - `PopulationSimulationCapability.run_cycle(cadence_input: PopulationCadenceInput, read_set: PopulationReadSet) -> PopulationCycleResult`
  - `SimingRuntime(population_capability=capability)`
  - `SimingRuntime(population_read_set_builder=builder, population_capability=capability)`
  - `SimingEventConsumer.handle_event` support for `population_cadence_event -> SimingInput(input_type="population_cadence_input")`.

- [ ] **Step 1: Write failing capability tests**

```python
def test_siming_population_cycle_returns_seed_and_does_not_write_without_owner_adapter() -> None:
    capability = PopulationSimulationCapability(planner=PopulationPlanner(), seed_planner=CharacterSeedPlanner())
    result = capability.run_cycle(cadence_input(), read_set())
    assert result.status == "owner_settlement_required"
    assert result.seed_candidates
    assert result.production_append_count == 0


def test_siming_population_cycle_uses_only_registered_schedule_supply_owner() -> None:
    result = capability_with_bakery_owner().run_cycle(cadence_input(), read_set_with_supply_candidate())
    assert result.owner_receipts[0].owner_ref == "actor_gameplay.organization_domain"
    assert result.owner_receipts[0].event_family == "gameplay.organization.commerce_commitment_accepted"


def test_siming_population_cycle_requeues_stale_read_set_without_append() -> None:
    result = capability_with_bakery_owner().run_cycle(stale_cadence_input(), stale_read_set())
    assert result.status == "requeue"
    assert result.reason == "stale_read_set"
    assert result.production_append_count == 0


def test_siming_tick_routes_population_cadence_through_one_decision_path() -> None:
    recorder = RecordingPopulationCapability()
    runtime = SimingRuntime(population_capability=recorder)
    result = runtime.tick([SimingInput(input_type="population_cadence_input", source_event=cadence_event())])
    assert result.read_model is not None
    assert recorder.calls == 1
```

- [ ] **Step 2: Run the tests and verify failure**

Run `python -m pytest -q backend/tests/test_siming_population_capability.py backend/tests/test_siming_heavenly_runtime_tick.py`.

Expected: FAIL because the capability and tick branch do not exist.

- [ ] **Step 3: Implement the internal capability**

Implement `PopulationSimulationCapability` with injected adapters:

```python
class PopulationOwnerExecutor(Protocol):
    def submit(self, intent: BatchIntentCandidate, *, read_set: PopulationReadSet) -> PopulationOwnerReceipt: pass

class CharacterContinuityPort(Protocol):
    def apply_command(self, command: CharacterContinuityCommand) -> CharacterContinuityReceipt: pass
```

Define the read-set builder seam as `Callable[[AuthorityEvent, PopulationCadenceInput], PopulationReadSet]` and provide a default builder that reads only existing scoped world-mode, organization, household, social, and public-event projections. Create `ScheduleGatedSupplyOwnerExecutor` in `backend/app/population_continuity/owner_adapters.py`; its `submit` method delegates to the existing `ContinuityMergeAuthority.merge_released_schedule_gated_supply` and `OrganizationAuthority` fragment path and returns `PopulationOwnerReceipt` with the exact committed event family `gameplay.organization.commerce_commitment_accepted`.

The capability must reject missing/stale cadence or read-set pins before planner execution, invoke `PopulationPlanner.plan_population_cycle` exactly once, send only the registered `schedule_gated_supply` intent to the existing Organization owner adapter, pass owner receipts into `CharacterSeedPlanner.derive`, invoke `CharacterContinuityPort.apply_command` only for a valid actor-scoped command, return report/seed/receipt/audit/append-count/status fields, and never accept caller-provided stream/event family values. A proposed new behavior is report-only during the current cycle and cannot be submitted until a later catalog revision is pinned.

Add `population_cadence_event` to `SimingEventConsumer.ALLOWED_EVENT_TYPES` and map it to `SimingInput(input_type="population_cadence_input")`. In `SimingRuntime.tick`, handle this input before ordinary event processing by parsing `PopulationCadenceInput.from_authority_event`, building the read-set through an injected scoped projection reader, calling the capability, appending its outputs/audits to `SimingTickResult`, and continuing the same behavior-turn/read-model path. Do not add a second loop or background thread.

Wire the capability in `build_runtime_state`/`SimingEventPipeline` using the existing store and Organization owner code. Keep `StubGroupSimulationBridge` as read-model fallback; it is not the production population executor.

Define `read_set()`, `read_set_with_supply_candidate()`, `stale_read_set()`, `cadence_input()`, and `stale_cadence_input()` in `backend/tests/test_siming_population_capability.py` using the Task 1 contracts. Define `RecordingPopulationCapability` with an integer `calls` field and a `run_cycle(cadence_input, read_set) -> PopulationCycleResult` method that increments `calls` and returns a valid empty cycle result. `capability_with_bakery_owner()` must adapt the existing `OrganizationAuthority`/`ContinuityMergeAuthority` schedule-gated row; the default constructor must leave its owner executor absent so the first test proves zero append.

- [ ] **Step 4: Run focused tests and existing Siming tests**

Run `python -m pytest -q backend/tests/test_siming_population_capability.py backend/tests/test_siming_heavenly_runtime_tick.py backend/tests/test_siming_event_pipeline.py backend/tests/test_siming_agent_loop_runtime.py` and then run `git diff --check`.

Expected: PASS.

- [ ] **Step 5: Commit the Siming integration**

```powershell
git add backend/app/services/siming_population_capability.py backend/app/services/siming_runtime.py backend/app/services/siming_event_consumer.py backend/app/services/siming_event_pipeline.py backend/app/main.py backend/tests/test_siming_population_capability.py backend/tests/test_siming_heavenly_runtime_tick.py
git commit -m "接入司命主导群体模拟决策路径"
```

## Task 4: Character Core Seed Settlement and Parsed Ingress

**Files:**
- Create: `backend/app/character_agent/services/character_continuity.py`
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/app/character_agent/storage/graph_continuity_store.py`
- Modify: `backend/app/character_agent/storage/session_store.py`
- Modify: `backend/app/character_agent/models/private_world_snapshot.py`
- Test: `backend/tests/test_character_agent_seed_continuity.py`
- Test: `backend/tests/test_character_graph_continuity_store.py`

**Interfaces:**
- Consumes: `CharacterSimulationSeedCandidate`, `CharacterContinuityCommand`, `CharacterContinuityReceipt`, existing actor profile registry, dynamic state store, goal store, memory store, session timeline, and graph continuity snapshot.
- Produces:
  - `CharacterContinuityService.apply_command(command: CharacterContinuityCommand) -> CharacterContinuityReceipt`
  - `CharacterAgentRuntime.apply_character_continuity_command(command) -> CharacterContinuityReceipt`
  - `CharacterAgentRuntime.ingest_seed_projection(seed) -> list[CharacterGoalCommand]`
  - actor-local `seed_projection` fields in the parsed private runtime context.

- [ ] **Step 1: Write failing Character Core tests**

```python
def test_seed_command_updates_state_but_defers_memory_materialization() -> None:
    runtime = CharacterAgentRuntime()
    receipt = runtime.apply_character_continuity_command(command_for_char_a())
    assert receipt.status == "committed"
    assert runtime.get_need_tension_state_record("char_a").physiological_pressure > 0
    assert runtime.get_pending_seed_candidates("char_a")
    assert runtime.get_memory_bundle("char_a")["event_memories"] == []


def test_seed_projection_is_parsed_into_actor_local_context_not_raw_prompt_text() -> None:
    runtime = CharacterAgentRuntime()
    runtime.apply_character_continuity_command(command_with_presentation_seed())
    projection = runtime.get_seed_projection("char_a")
    assert projection["presentation_seed"]["task"] == "replenish_family_food"
    assert "raw_prompt" not in projection


def test_seed_command_rejects_stale_actor_revision_without_partial_write() -> None:
    runtime = CharacterAgentRuntime()
    runtime.apply_character_continuity_command(command_for_char_a())
    before = runtime.get_dynamic_state_record("char_a").model_dump()
    rejected = runtime.apply_character_continuity_command(command_for_char_a(expected_character_revision=0, command_id="continuity:stale"))
    assert rejected.status == "requeued"
    assert rejected.refusal_reason == "character_revision_conflict"
    assert runtime.get_dynamic_state_record("char_a").model_dump() == before


def test_memory_materialization_requires_exposure_and_is_idempotent() -> None:
    runtime = CharacterAgentRuntime()
    command = command_with_memory_candidate(exposure_basis="not_observed")
    receipt = runtime.apply_character_continuity_command(command)
    assert receipt.status == "committed"
    materialized = runtime.materialize_pending_seed_memories("char_a", producer_ts=101)
    assert materialized[0].status == "rejected"
    assert materialized[0].refusal_reason == "memory_materialization_denied"
    replay = runtime.materialize_pending_seed_memories("char_a", producer_ts=101)
    assert replay[0].status == "idempotent_replay"


def test_seed_and_memory_cursor_advance_separately() -> None:
    runtime = CharacterAgentRuntime()
    receipt = runtime.apply_character_continuity_command(command_with_memory_candidate(exposure_basis="affected_directly"))
    assert receipt.state_cursor == 101
    assert receipt.memory_cursor == 0
    materialized = runtime.materialize_pending_seed_memories("char_a", producer_ts=101)
    assert materialized[0].status == "committed"
    assert materialized[0].memory_cursor == 101


def test_seed_correction_appends_supersession_without_deleting_subjective_memory() -> None:
    runtime = CharacterAgentRuntime()
    runtime.apply_character_continuity_command(command_with_memory_candidate(exposure_basis="affected_directly"))
    runtime.materialize_pending_seed_memories("char_a", producer_ts=101)
    correction = runtime.apply_character_continuity_command(correction_for_char_a())
    assert correction.status == "committed"
    assert runtime.get_memory_bundle("char_a")["event_memories"]
    assert runtime.get_seed_projection("char_a")["supersedes"] == "seed:char_a:101"
```

- [ ] **Step 2: Run tests and verify failure**

Run `python -m pytest -q backend/tests/test_character_agent_seed_continuity.py`.

Expected: FAIL because the continuity service, seed ledger accessors, and materialization methods do not exist.

Define `command_for_char_a(**updates)`, `command_with_presentation_seed()`, `command_with_memory_candidate(exposure_basis)`, and `correction_for_char_a()` in the test module. The default command must use `character:char_a`, `expected_character_revision=0`, `source_owner_receipt_refs=("receipt:frost:101",)`, `source_revision_vector={"world:bakery": 101}`, `state_delta={"need_tension": {"physiological_pressure": 0.12}}`, and `idempotency_key="continuity:char_a:101"`. The stale builder changes only expected revision and command id. The memory builder changes only candidate exposure basis and candidate id. The correction builder supersedes `seed:char_a:101` and never deletes the prior memory candidate.

- [ ] **Step 3: Implement Character Core-owned settlement**

Create `CharacterContinuityService` as a deep module that uses the existing runtime stores and session/graph snapshot path. `CharacterAgentRuntime` owns one instance and its public `apply_character_continuity_command` delegates to that instance. The service must verify actor identity, expected character revision, source owner receipts, source revision vector, visibility and exposure evidence; merge only closed field families; append a `character_simulation_seed_event` to the existing actor session timeline; update dynamic state and goal stores atomically; retain memory candidates as pending; return a `CharacterContinuityReceipt`; and return the original receipt for duplicate `idempotency_key`.

Implement `materialize_pending_seed_memories(actor_id, producer_ts)` as a Character Core method. Re-run exposure, temporal, privacy, branch, deduplication and revision checks. Append only eligible candidates to the existing `CharacterAgentMemoryStore`/router; advance `memory_cursor` only after append and receipt commit.

Add `get_pending_seed_candidates(actor_id)` and `get_seed_projection(actor_id)` read helpers. Add `ingest_seed_projection(seed)` to parse state/presentation/activation fields into the actor's structured snapshot and existing scheduling/wake-up state. Do not call the LLM with the seed object directly; existing L1/L2/L3/L4 builders consume the parsed snapshot, memory bundle and goal state.

Persist pending seed ledger and cursors through the existing session timeline and complete graph continuity snapshot. Do not create a second seed database.

- [ ] **Step 4: Run focused and memory/continuity regression tests**

Run `python -m pytest -q backend/tests/test_character_agent_seed_continuity.py backend/tests/test_character_agent_runtime_memory_integration.py backend/tests/test_character_graph_continuity_store.py` and then `git diff --check`.

Expected: PASS.

- [ ] **Step 5: Commit Character Core settlement**

```powershell
git add backend/app/character_agent/services/character_continuity.py backend/app/character_agent/runtime/runtime_loop.py backend/app/character_agent/storage/graph_continuity_store.py backend/app/character_agent/storage/session_store.py backend/app/character_agent/models/private_world_snapshot.py backend/tests/test_character_agent_seed_continuity.py backend/tests/test_character_graph_continuity_store.py
git commit -m "实现角色模拟种子连续性结算"
```

## Task 5: Player-Triggered Agent Activation Handoff

**Files:**
- Create: `backend/app/population_continuity/activation_policy.py`
- Modify: `backend/app/population_continuity/models.py`
- Modify: `backend/app/services/session_input_router.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Test: `backend/tests/test_population_activation_policy.py`
- Test: `backend/tests/test_character_agent_activation_handoff.py`

**Interfaces:**
- Consumes: structured `DialogueSubmit`, `FocusTargetChange`, `InteractIntent`, actor positions, pending seed/activation hints, `RuntimePopulationPolicy`, and `ProfileActivationAuthority`.
- Produces:
  - `ActivationPolicy.evaluate(input) -> ActivationDecision`
  - `CharacterAgentRuntime.activate_actor(actor_id, decision, producer_ts) -> ActivationReceipt`
  - structured debug/audit records for `prewarm`, `activation_candidate`, `active`, and `requeue`.

`ActivationDecision` is a closed model with `actor_id`, `state` (`dormant|prewarm|activation_candidate|active|requeue`), `reason`, `requires_activation_lock`, `load_private_memory`, and `policy_revision`. Reuse the existing `ActivationReceipt` model for the lock/result receipt; do not add a second activation authority.

- [ ] **Step 1: Write failing activation tests**

```python
def test_player_proximity_enters_prewarm_without_loading_private_memory() -> None:
    decision = ActivationPolicy().evaluate(
        actor_id="char_a", distance_m=8.0, focused=False, interaction_type="none", pending_seed=True, budget=2
    )
    assert decision.state == "prewarm"
    assert decision.load_private_memory is False


def test_focused_dialogue_enters_active_with_activation_lock() -> None:
    decision = ActivationPolicy().evaluate(
        actor_id="char_a", distance_m=2.0, focused=True, interaction_type="dialogue", pending_seed=True, budget=2
    )
    assert decision.state == "active"
    assert decision.requires_activation_lock is True
    assert decision.load_private_memory is True


def test_activation_preserves_same_character_identity() -> None:
    runtime = CharacterAgentRuntime()
    before = runtime.character_identity_digest("char_a")
    receipt = runtime.activate_actor("char_a", active_dialogue_decision(), producer_ts=101)
    assert receipt.committed
    assert runtime.character_identity_digest("char_a") == before


def test_activation_lock_conflict_requeues_without_duplicate_runtime_state() -> None:
    runtime = CharacterAgentRuntime()
    runtime.activate_actor("char_a", active_dialogue_decision(), producer_ts=101)
    second = runtime.activate_actor("char_a", active_dialogue_decision(), producer_ts=102)
    assert second.status == "requeued"
    assert second.stop_reason == "activation_lock_conflict"
```

- [ ] **Step 2: Run tests and verify failure**

Run `python -m pytest -q backend/tests/test_population_activation_policy.py backend/tests/test_character_agent_activation_handoff.py`.

Expected: FAIL because the activation policy and runtime handoff methods do not exist.

Define `active_dialogue_decision()` in the activation test module as a fully populated `ActivationDecision` for `char_a`, state `active`, lock required, private-memory load enabled, reason `player_dialogue`, and policy revision `policy:activation:v1`.

- [ ] **Step 3: Implement activation policy and route integration**

Implement a pure `ActivationPolicy.evaluate` with these decisions:

```text
dialogue/conflict/consequential interaction + lock        -> active
focused player input + supported actor + budget            -> activation_candidate
distance <= prewarm_distance or pending activation hint -> prewarm
unsupported actor/stale revision/lock conflict            -> requeue
```

The policy must never return a world Owner, stream, event family, memory pool, or raw prompt. It only returns state, reason, lock requirement, private-memory load flag, and actor id.

Implement `CharacterAgentRuntime.activate_actor` by reusing `ProfileActivationAuthority.lock`/release semantics and the seed continuity snapshot. It must materialize only eligible pending candidates after the lock is held, then call the existing L1/L2/L3/L4 path for the active actor. It must not create a second actor or switch `control_mode` as a substitute for activation identity.

In `main.py`, invoke activation policy before handling `DialogueSubmit`, `FocusTargetChange`, and actor-targeted `InteractIntent`. The player message remains a structured intent. Godot receives only the existing ack, `character_agent_execution`, `world_result`, and observatory projections.

- [ ] **Step 4: Run activation and input regression tests**

Run `python -m pytest -q backend/tests/test_population_activation_policy.py backend/tests/test_character_agent_activation_handoff.py backend/tests/test_character_agent_control_modes.py backend/tests/test_siming_character_dispatch_adapter.py` and then `git diff --check`.

Expected: PASS.

- [ ] **Step 5: Commit activation handoff**

```powershell
git add backend/app/population_continuity/activation_policy.py backend/app/population_continuity/models.py backend/app/services/session_input_router.py backend/app/main.py backend/app/character_agent/runtime/runtime_loop.py backend/tests/test_population_activation_policy.py backend/tests/test_character_agent_activation_handoff.py
git commit -m "增加玩家触发的角色智能体激活交接"
```

## Task 6: End-to-End Bakery Vertical, Harness, Replay, and Documentation Evidence

**Files:**
- Create: `backend/tests/test_siming_led_population_seed_continuity.py`
- Create: `scripts/verification/verify_siming_led_population_seed_continuity.py`
- Create: `.harness/profiles/siming-led-population-seed-continuity.json`
- Modify: `backend/app/population_continuity/vertical.py`
- Modify: `docs/8月分析/司命与群体世界补充设计/03-群体模拟与角色分级连续性.md`
- Modify: `docs/8月分析/司命与群体世界补充设计/13-群体模拟生产纵切与推进闭环设计.md`
- Modify: `docs/8月分析/12-实现收口与证据映射.md`
- Modify: `docs/harness.md`
- Test: `backend/tests/test_siming_led_population_seed_continuity.py`

**Interfaces:**
- Consumes: all previous task seams, `BakeryDistrictPopulationFixture`, existing Organization authority, Character Core continuity service, activation lock, replay projector, and Harness conventions.
- Produces:
  - `siming-led-population-seed-continuity` Harness profile
  - `.harness/verification/siming-led-population-seed-continuity-report.json`
  - one reproducible planner -> Siming -> Owner -> Character Core -> activation proof.

- [ ] **Step 1: Write the failing end-to-end test**

```python
def test_game_start_to_player_activation_closes_the_seed_vertical() -> None:
    fixture = SimingLedPopulationFixture.create()
    result = fixture.run()
    assert result["cadence"]["status"] == "accepted"
    assert result["population"]["seed_count"] == 1
    assert result["owner"]["owner_ref"] == "actor_gameplay.organization_domain"
    assert result["character"]["continuity_status"] == "committed"
    assert result["activation"]["status"] == "active"
    assert result["activation"]["same_character_identity"] is True
    assert result["replay"]["full_equals_checkpoint_tail"] is True
    assert result["rejections"]["stale_read_set_zero_write"] is True
    assert result["rejections"]["private_memory_without_exposure_zero_write"] is True
```

- [ ] **Step 2: Run the end-to-end test and verify failure**

Run `python -m pytest -q backend/tests/test_siming_led_population_seed_continuity.py`.

Expected: FAIL because the fixture, verifier, and Harness profile do not exist.

- [ ] **Step 3: Implement the bakery vertical fixture**

Build the fixture around existing `BakeryDistrictPopulationFixture`, not a new store:

1. create a committed world-mode and cadence projection at game start;
2. publish one `population_cadence_event` to the existing AuthorityEventBus;
3. let `SimingEventPipeline` call `SimingRuntime.tick()` and the internal capability;
4. use the existing Organization owner settlement for `schedule_gated_supply`;
5. apply the returned `CharacterContinuityCommand` through Character Core;
6. assert pending seed state and separate cursors before activation;
7. submit a structured player focus/dialogue input for the same actor;
8. assert activation lock, parsed seed projection, local character intent, and unchanged identity digest;
9. replay the event/continuity projection from full history and checkpoint plus tail;
10. run stale revision, private exposure, duplicate seed, and unknown behavior cases and assert zero production append.

The fixture must expose stable result keys used by the test above and include source/revision/seed/result digests in the report.

Define `SimingLedPopulationFixture.create() -> SimingLedPopulationFixture` in `backend/app/population_continuity/vertical.py`; it must construct the existing bakery scenario, event bus, `PopulationSimulationCapability`, Organization owner adapter, Character Core adapter, and activation policy from the prior tasks. It must not create another event store or runtime host.

- [ ] **Step 4: Add the independent Harness verifier and profile**

Create `scripts/verification/verify_siming_led_population_seed_continuity.py` with the conventions of `verify_phase3d_bakery_district_population.py`: run focused pytest, run the fixture, check predecessor reports, and write one JSON report with `overall_passed`, `predecessors`, `harness_checks`, `seed_projection`, `activation`, `replay_hash`, and `zero_write` fields.

Create `.harness/profiles/siming-led-population-seed-continuity.json`:

```json
{
  "schema_version": 1,
  "name": "siming-led-population-seed-continuity",
  "order": 118,
  "include_in_profile_order": false,
  "include_in_all": false,
  "script": "scripts/verification/verify_siming_led_population_seed_continuity.py",
  "requires_godot": false,
  "max_attempts": 1,
  "result_artifact": ".harness/verification/siming-led-population-seed-continuity-report.json",
  "description": "Siming-governed game-start population cadence to CharacterSimulationSeed and player activation handoff"
}
```

Keep `include_in_all=false` until the profile is independently green and documentation status is updated from proposed to implemented bounded. The profile itself must remain runnable directly by name.

- [ ] **Step 5: Update evidence and scope documentation**

Update the three August documents with only proven facts:

- `03-群体模拟与角色分级连续性.md`: record game-start cadence, seed-centered control, and player-triggered same-identity activation as `implemented bounded` only if the Harness report is green.
- `13-群体模拟生产纵切与推进闭环设计.md`: link the new report and state that the vertical proves one owner-mediated seed handoff, not complete population/civilization simulation.
- `12-实现收口与证据映射.md`: add the profile/report and retain the statement that complete population simulation remains incomplete.
- `docs/harness.md`: document the direct profile name, its report artifact, and the fact that it is excluded from aggregate profiles until its evidence is green.

Do not claim large-scale capacity, complete civilization evolution, or LLM-per-actor background simulation.

- [ ] **Step 6: Run the complete verification set**

```powershell
python -m pytest -q
python scripts/verification/verify_siming_led_population_seed_continuity.py
python scripts/verification/harness.py --profile siming-led-population-seed-continuity
python scripts/verification/harness.py --profile phase3-population-continuity
python scripts/verification/harness.py --profile change-lifecycle
python scripts/verification/harness.py --profile all
git diff --check
```

Expected: all focused and predecessor profiles pass; the new report has `overall_passed=true`, replay equality, and zero-write rejection evidence. If the full profile fails, preserve the focused failure report and do not change `include_in_all` to hide it.

- [ ] **Step 7: Commit the verified vertical**

```powershell
git add backend/tests/test_siming_led_population_seed_continuity.py scripts/verification/verify_siming_led_population_seed_continuity.py .harness/profiles/siming-led-population-seed-continuity.json docs/8月分析/司命与群体世界补充设计/03-群体模拟与角色分级连续性.md docs/8月分析/司命与群体世界补充设计/13-群体模拟生产纵切与推进闭环设计.md docs/8月分析/12-实现收口与证据映射.md
git commit -m "验证司命主导群体种子接管纵切"
```

## Execution Order and Review Checkpoints

Execute Tasks 0-6 in order. Each task is independently reviewable at its commit. Do not begin the next task while the current focused tests or `git diff --check` fail. The first implementation checkpoint is after Task 3: it must show a real `population_cadence_event` entering `SimingRuntime.tick()` without a second runtime. The second checkpoint is after Task 4: it must show Character Core accepting a seed command while keeping memory materialization pending. The final checkpoint is Task 6's independent Harness report.

## Deferred Scope

This plan does not implement a general population truth owner, arbitrary behavior registration, full civilization evolution, global social knowledge, a new event bus/store/clock/scheduler, or a per-actor full LLM loop. New behaviors remain proposal-only until their source-controlled capability/catalog revision and owner contract are separately approved.
