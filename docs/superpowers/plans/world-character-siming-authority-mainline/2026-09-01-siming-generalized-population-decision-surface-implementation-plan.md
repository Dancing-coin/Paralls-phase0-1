# Siming Generalized Population Decision Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the production population simulator's actor-specific decision path with a generic Siming-governed candidate selection surface while retaining the existing three-actor vertical as a regression fixture.

**Architecture:** Add a typed, pure decision surface that converts scoped projections into multiple bounded candidates. Keep selection and tradeoffs in `SimingRuntime.tick(...)`/`PopulationSimulationCapability`; keep world truth in existing Owner contracts and actor continuity in Character Core. The existing `plan_three_actor_cohort` remains fixture-only and delegates through the generic surface where possible.

**Tech Stack:** Python 3.13, Pydantic contracts, existing `GameplayEventStore`, `GovernedAuthorityContractCatalog`, Character Core, pytest, replay projector, Harness JSON profiles.

**Spec:** `docs/superpowers/specs/world-character-siming-authority-mainline/2026-09-01-siming-generalized-population-decision-surface-design.md`

## Global Constraints

- `SimingRuntime.tick(...)` is the only Siming decision and dispatch path.
- `PopulationPlanner` remains pure: no event store, Owner invocation, Character Core write, clock, scheduler or memory write.
- Objective candidates must map to an existing source-controlled capability and named domain Owner; callers cannot choose streams or event families.
- Owner receipts precede objective Character Core commands; Character Core alone writes actor continuity, SeedDelta, memory materialization and revisions.
- Runtime capability registration stays closed and source-controlled; no dynamic unreviewed behavior registry.
- Branch, private, cross-actor, stale, malformed, duplicate-mismatch and budget-exhausted inputs are auditable zero-write outcomes.
- The implementation must not claim complete population, social, economic, civilization or multi-region simulation.
- Existing `siming-governed-three-actor-cohort-continuity-v1` remains a fixture/direct profile and is not converted into the generic contract.

---

### Task 1: Generic candidate, decision and capability contracts

**Files:**
- Create: `backend/app/population_continuity/decision_surface.py`
- Modify: `backend/app/population_continuity/siming_contracts.py`
- Modify: `backend/app/population_continuity/__init__.py`
- Test: `backend/tests/test_siming_population_decision_contracts.py`

**Interfaces:**
- `PopulationDecisionCandidate(ContinuityModel)` with `candidate_ref`, `actor_ref`, `cohort_ref`, `behavior_kind`, `fidelity_tier`, `source_projection_refs`, `source_revision_vector`, `evidence_refs`, `estimated_cost`, `objective_risk`, `player_proximity`, `narrative_obligation_pressure`, `unresolved_owner_consequence`, `propagation_pressure`, `starvation_credit`, `allowed_outputs`, `policy_revision`, `selector_revision`, `ruleset_revision`, and `idempotency_key`.
- `fidelity_tier` is `Literal["B0", "B1", "B2", "B3"]`; `objective_risk` is `Literal["none", "low", "medium", "high"]`; numeric signals are finite floats in `[0, 1]`; `estimated_cost` is an integer `>= 0`.
- `PopulationDecision(ContinuityModel)` with `selected_candidates`, `deferred_candidates`, `rejected_candidates`, `unprocessed_refs`, `budget_used`, `budget_remaining`, `fidelity_counts`, `decision_reason_codes`, `read_set_digest`, and `result_digest`.
- `PopulationCapabilityDescriptor(ContinuityModel)` with `capability_id`, `accepted_behavior_kinds`, `required_scopes`, `required_source_domains`, `target_owner`, `allowed_output_kinds`, `capability_revision`, `policy_revision`, and `enabled`.
- `PopulationDecisionCandidate.allowed_outputs` is a closed tuple of `Literal["presentation_seed", "activation_candidate", "owner_bound_intent", "character_core_command", "defer"]`.
- Extend `PopulationCycleResult` with optional `decision: PopulationDecision | None` so generic decisions travel through the existing result contract without changing legacy callers.

- [ ] **Step 1: Write failing contract tests**

```python
def test_candidate_preserves_bounded_decision_fields() -> None:
    candidate = PopulationDecisionCandidate(
        candidate_ref="candidate:char_a:supply:W0",
        actor_ref="character:char_a",
        cohort_ref="cohort:bakery:W0",
        behavior_kind="schedule_gated_supply",
        fidelity_tier="B2",
        source_projection_refs=("projection:char_a:W0",),
        source_revision_vector={"world:bakery": 1},
        evidence_refs=("event:frost:1",),
        estimated_cost=1,
        objective_risk="low",
        player_proximity=0.2,
        narrative_obligation_pressure=0.0,
        unresolved_owner_consequence=1.0,
        propagation_pressure=0.0,
        starvation_credit=0.0,
        allowed_outputs=("owner_bound_intent", "character_core_command"),
        policy_revision="mode:v1",
        selector_revision="selector:cohort-bakery:v1",
        ruleset_revision="rules:cohort-bakery:v1",
        idempotency_key="candidate:char_a:supply:W0",
    )
    assert candidate.fidelity_tier == "B2"

def test_unknown_output_kind_is_rejected() -> None:
    with pytest.raises(ValidationError):
        PopulationDecisionCandidate.model_validate({**candidate_payload(), "allowed_outputs": ("free_form_write",)})

def test_decision_budget_and_digests_are_explicit() -> None:
    decision = PopulationDecision(
        selected_candidates=(), deferred_candidates=(), rejected_candidates=(),
        unprocessed_refs=("bucket:far",), budget_used=0, budget_remaining=3,
        fidelity_counts={}, decision_reason_codes=("budget_reserved_for_player",),
        read_set_digest="sha256:read", result_digest="sha256:result",
    )
    assert decision.budget_remaining == 3

```

- [ ] **Step 2: Run tests and verify RED**

Run `python -m pytest -q backend/tests/test_siming_population_decision_contracts.py`.

Expected: FAIL because the generic contracts do not exist.

- [ ] **Step 3: Implement the minimum immutable contracts**

Use the existing `ContinuityModel`, `Literal`, and Pydantic field constraints. Do not add persistence, registration mutation or runtime behavior.

- [ ] **Step 4: Run focused and regression tests**

Run `python -m pytest -q backend/tests/test_siming_population_decision_contracts.py backend/tests/test_siming_population_cohort_contracts.py backend/tests/test_siming_population_capability.py` and `git diff --check`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/population_continuity/decision_surface.py backend/app/population_continuity/siming_contracts.py backend/app/population_continuity/__init__.py backend/tests/test_siming_population_decision_contracts.py
git commit -m "增加司命群体决策契约"
```

### Task 2: Pure generic candidate evaluation and tradeoff scoring

**Files:**
- Modify: `backend/app/population_continuity/decision_surface.py`
- Modify: `backend/app/population_continuity/batch.py`
- Test: `backend/tests/test_siming_population_decision_planner.py`

**Interfaces:**
- `PopulationDecisionPolicy` immutable value object with `policy_revision`, `default_fidelity_tier`, `budget`, `max_candidates`, `player_proximity_weight`, `owner_consequence_weight`, `propagation_weight`, `narrative_obligation_weight`, and `starvation_weight`.
- `PopulationDecisionPlanner.evaluate(read_set: PopulationReadSet, capabilities: tuple[PopulationCapabilityDescriptor, ...], policy: PopulationDecisionPolicy) -> tuple[PopulationDecisionCandidate, ...]`.
- `PopulationDecisionPlanner.select(candidates: tuple[PopulationDecisionCandidate, ...], policy: PopulationDecisionPolicy) -> PopulationDecision`.
- `PopulationPlanner.plan_three_actor_cohort(...)` remains a fixture adapter and must not become the generic evaluator.

- [ ] **Step 1: Write failing planner tests**

```python
def test_evaluate_emits_multiple_registered_candidates_without_writes() -> None:
    candidates = PopulationDecisionPlanner().evaluate(
        competing_read_set(), registered_capabilities(), decision_policy(budget=3)
    )
    assert {item.behavior_kind for item in candidates} == {
        "schedule_gated_supply", "routine_work", "relationship_negotiation"
    }
    assert all(item.allowed_outputs for item in candidates)

def test_select_spends_budget_on_highest_weighted_candidates_and_defers_the_rest() -> None:
    candidates = competing_candidates()
    decision = PopulationDecisionPlanner().select(candidates, decision_policy(budget=2))
    assert decision.budget_used == 2
    assert len(decision.selected_candidates) == 2
    assert len(decision.deferred_candidates) == len(candidates) - 2
    assert decision.decision_reason_codes

def test_policy_weight_changes_selection_without_changing_authority_outputs() -> None:
    owner_first = PopulationDecisionPlanner().select(
        competing_candidates(), decision_policy(owner_consequence_weight=10, budget=1)
    )
    player_first = PopulationDecisionPlanner().select(
        competing_candidates(), decision_policy(player_proximity_weight=10, budget=1)
    )
    assert owner_first.selected_candidates[0].allowed_outputs == player_first.selected_candidates[0].allowed_outputs
    assert owner_first.selected_candidates[0].candidate_ref != player_first.selected_candidates[0].candidate_ref

def test_unknown_capability_and_private_projection_are_rejected_without_writes() -> None:
    candidates = PopulationDecisionPlanner().evaluate(
        malformed_read_set(), registered_capabilities(), decision_policy(budget=3)
    )
    assert candidates == ()
```

- [ ] **Step 2: Run tests and verify RED**

Run `python -m pytest -q backend/tests/test_siming_population_decision_planner.py`.

Expected: FAIL because the evaluator and policy do not exist.

- [ ] **Step 3: Implement pure evaluation and deterministic selection**

Normalize only typed projection fields. Score candidates from pinned numeric inputs using a deterministic weighted sum and stable tie-break `(candidate_ref, source_projection_refs)`. Reject unknown behavior/capability, forbidden scope, cross-actor evidence, missing source vectors, and malformed cost before selection. The evaluator must not call `GovernedAuthorityContractCatalog`, Owner implementations, Character Core or event stores; capability descriptors are passed in as immutable input.

- [ ] **Step 4: Verify planner purity and fixture compatibility**

Run `python -m pytest -q backend/tests/test_siming_population_decision_contracts.py backend/tests/test_siming_population_decision_planner.py backend/tests/test_siming_population_cohort_planner.py backend/tests/test_siming_population_planner.py` and `git diff --check`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/population_continuity/decision_surface.py backend/app/population_continuity/batch.py backend/tests/test_siming_population_decision_planner.py
git commit -m "实现司命群体候选权衡"
```

### Task 3: Siming decision routing and capability admission

**Files:**
- Modify: `backend/app/services/siming_population_capability.py`
- Modify: `backend/app/services/siming_runtime.py`
- Modify: `backend/app/population_continuity/decision_surface.py`
- Test: `backend/tests/test_siming_population_decision_routing.py`

**Interfaces:**
- `PopulationSimulationCapability.run_decision_cycle(cadence_input, read_set, policy, capabilities) -> PopulationCycleResult`.
- `SimingRuntime.tick(...)` calls `run_decision_cycle` for generic decision inputs; the existing cohort fixture remains available through its fixture path.
- Admission must map selected candidates to existing Owner/Core adapters only after selection. No caller-provided stream/event-family/Owner override is accepted.

- [ ] **Step 1: Write failing routing tests**

```python
def test_siming_can_select_owner_seed_activation_or_defer_in_one_cycle() -> None:
    result, owner, continuity = run_competing_cycle()
    assert result.status == "accepted"
    assert owner.calls == ["character:char_a"]
    assert {item.actor_ref for item in continuity.commands} <= {
        "character:char_a", "character:char_b"
    }
    assert result.decision is not None
    assert result.decision.deferred_candidates

def test_player_proximity_policy_can_choose_char_c_activation_without_core_command() -> None:
    result, owner, continuity = run_competing_cycle(player_proximity_weight=10)
    assert result.report.activation_candidates == ("projection:char_c:W0",)
    assert all(command.actor_ref != "character:char_c" for command in continuity.commands)

def test_owner_mapping_cannot_be_overridden_by_candidate_payload() -> None:
    result, owner, continuity = run_competing_cycle(candidate_owner_override="owner:forged")
    assert result.status == "requeue"
    assert result.production_append_count == 0
    assert owner.calls == []
    assert continuity.commands == []

def test_budget_and_fidelity_change_selection_but_not_write_authority() -> None:
    low = run_competing_cycle(budget=1)[0]
    high = run_competing_cycle(budget=3)[0]
    assert low.report.owner_intent_count <= high.report.owner_intent_count
    assert low.report.owner_intent_count <= 1
    assert all(receipt.owner_ref == "organization:bakery" for receipt in high.owner_receipts)
```

- [ ] **Step 2: Run tests and verify RED**

Run `python -m pytest -q backend/tests/test_siming_population_decision_routing.py`.

Expected: FAIL because generic decision routing is absent.

- [ ] **Step 3: Route selected candidates through existing adapters**

Validate cadence/read-set/policy/selector/ruleset pins before planner evaluation. Convert only selected candidates with an admitted descriptor into existing `PopulationOwnerBoundIntent`, presentation seed, activation candidate, or Character Core command. Preserve receipt-before-Core and stop dependent writes after rejection/requeue. Keep the single `tick(...)` path and bounded audit fields.

- [ ] **Step 4: Run routing regressions**

Run `python -m pytest -q backend/tests/test_siming_population_decision_routing.py backend/tests/test_siming_population_cohort_capability.py backend/tests/test_siming_population_capability.py backend/tests/test_siming_population_production_boundaries.py backend/tests/test_siming_character_dispatch_adapter.py` and `git diff --check`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/siming_population_capability.py backend/app/services/siming_runtime.py backend/app/population_continuity/decision_surface.py backend/tests/test_siming_population_decision_routing.py
git commit -m "接入司命通用群体决策路由"
```

### Task 4: Receipt-driven replanning and continuity integration

**Files:**
- Modify: `backend/app/services/siming_population_capability.py`
- Modify: `backend/app/population_continuity/vertical.py`
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Test: `backend/tests/test_siming_population_replanning.py`

**Interfaces:**
- `PopulationSimulationCapability.replan_from_receipts(previous_decision, receipts, next_read_set, policy, capabilities) -> PopulationCycleResult`.
- `ThreeActorCohortContinuityFixture` remains a regression fixture but adds one competing-candidate scenario proving it is data-fed rather than core actor branching.

- [ ] **Step 1: Write failing replanning tests**

```python
def test_owner_receipt_changes_next_cycle_source_and_expected_revision() -> None:
    fixture = GenericDecisionFixture.create()
    first = fixture.run_cycle(window="W0", budget=2)
    second = fixture.replan_from_cycle(first, window="W1", budget=2)
    assert first.status == "accepted"
    assert second.status == "accepted"
    assert second.report.read_set_digest != first.report.read_set_digest
    assert fixture.owner_source_revision("organization:bakery") > 0

def test_owner_rejection_requeues_dependents_without_partial_character_write() -> None:
    result = GenericDecisionFixture.create(owner_rejects=True).run_cycle(window="W0", budget=3)
    assert result.status == "requeue"
    assert result.production_append_count == 0
    assert result.continuity_receipts == ()

def test_noop_and_defer_are_valid_decisions() -> None:
    result = GenericDecisionFixture.create(empty_evidence=True).run_cycle(window="W0", budget=3)
    assert result.status == "accepted"
    assert result.report.selected_count == 0
    assert result.report.decision_reason_codes

def test_replanning_never_creates_a_second_actor_identity() -> None:
    fixture = GenericDecisionFixture.create()
    fixture.run_cycle(window="W0", budget=3)
    before = fixture.character.actor_record_refs()
    fixture.replan_from_cycle(fixture.last_result, window="W1", budget=3)
    assert fixture.character.actor_record_refs() == before
```

- [ ] **Step 2: Run tests and verify RED**

Run `python -m pytest -q backend/tests/test_siming_population_replanning.py`.

Expected: FAIL because receipt-driven generic replanning is absent.

- [ ] **Step 3: Implement replan and continuity handoff**

Use only committed Owner/Character Core receipts to build the next read-set. Preserve per-actor monotonic revisions, idempotency keys and dependency failure propagation. Do not introduce a new record store or background loop. Keep activation synchronous and player-triggered.

- [ ] **Step 4: Run continuity and replay regressions**

Run `python -m pytest -q backend/tests/test_siming_population_replanning.py backend/tests/test_siming_governed_three_actor_cohort_continuity.py backend/tests/test_siming_population_cohort_activation.py backend/tests/test_character_agent_activation_handoff.py` and `git diff --check`.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/siming_population_capability.py backend/app/population_continuity/vertical.py backend/app/character_agent/runtime/runtime_loop.py backend/tests/test_siming_population_replanning.py
git commit -m "实现司命回执驱动重规划"
```

### Task 5: Invariant Harness, scenario matrix and documentation

**Files:**
- Create: `backend/tests/test_siming_generalized_population_decision.py`
- Create: `scripts/verification/verify_siming_generalized_population_decision.py`
- Create: `.harness/profiles/siming-generalized-population-decision.json`
- Modify: `docs/harness.md`
- Modify: `docs/8月分析/司命与群体世界补充设计/03-群体模拟与角色分级连续性.md`
- Modify: `docs/8月分析/司命与群体世界补充设计/05-性能回放观测与渐进交付.md`
- Modify: `docs/8月分析/司命与群体世界补充设计/09-行为分层与信息传播.md`
- Modify: `docs/8月分析/司命与群体世界补充设计/10-校准性能与故障恢复.md`
- Modify: `docs/8月分析/司命与群体世界补充设计/13-群体模拟生产纵切与推进闭环设计.md`

**Interfaces:**
- `GeneralizedPopulationDecisionFixture.create()`.
- `run_scenario(name: Literal["competing_candidates", "budget_exhaustion", "stale_receipt", "owner_rejection", "player_proximity", "propagation_pressure", "noop_defer"]) -> dict[str, object]`.
- Harness profile `siming-generalized-population-decision` uses `include_in_profile_order=false`, `include_in_all=false`, `requires_godot=false`, and writes `.harness/verification/siming-generalized-population-decision-report.json`.

- [ ] **Step 1: Write failing invariant tests**

```python
def test_multiple_valid_selections_are_accepted_without_authority_bypass() -> None:
    fixture = GeneralizedPopulationDecisionFixture.create()
    owner_first = fixture.run_scenario("propagation_pressure")
    player_first = fixture.run_scenario("player_proximity")
    assert owner_first["status"] == "accepted"
    assert player_first["status"] == "accepted"
    assert owner_first["selected"] != player_first["selected"]
    assert owner_first["owner_refs"] == ["organization:bakery"]
    assert player_first["owner_refs"] in ([], ["organization:bakery"])

def test_all_adversarial_scenarios_are_zero_write() -> None:
    fixture = GeneralizedPopulationDecisionFixture.create()
    for name in ("stale_receipt", "owner_rejection", "budget_exhaustion"):
        result = fixture.run_scenario(name)
        assert result["zero_write"] is True

def test_fixed_input_replays_identically_and_fixture_is_not_generic_contract() -> None:
    fixture = GeneralizedPopulationDecisionFixture.create()
    first = fixture.run_scenario("competing_candidates")
    replay = fixture.replay_scenario("competing_candidates")
    assert first["decision_digest"] == replay["decision_digest"]
    assert first["uses_actor_specific_fixture"] is False
```

- [ ] **Step 2: Run tests and verify RED**

Run `python -m pytest -q backend/tests/test_siming_generalized_population_decision.py`.

Expected: FAIL because the generic fixture/verifier/profile do not exist.

- [ ] **Step 3: Implement scenario fixture and invariant verifier**

The verifier must assert authority, scope, revision, receipt, replay, budget and identity invariants while allowing multiple valid selected sets. It must not assert that every scenario chooses a particular actor or behavior.

- [ ] **Step 4: Add direct Harness profile and update docs**

Use this exact manifest:

```json
{
  "schema_version": 1,
  "name": "siming-generalized-population-decision",
  "order": 120,
  "include_in_profile_order": false,
  "include_in_all": false,
  "script": "scripts/verification/verify_siming_generalized_population_decision.py",
  "requires_godot": false,
  "max_attempts": 1,
  "result_artifact": ".harness/verification/siming-generalized-population-decision-report.json",
  "description": "Invariant and scenario proof for generalized Siming population candidate selection"
}
```

Document the distinction between the generic decision surface and the existing three-actor fixture. Keep complete population/social/economic/civilization/multi-region simulation explicitly incomplete.

- [ ] **Step 5: Run focused Harness and docs checks**

Run `python -m pytest -q backend/tests/test_siming_generalized_population_decision.py backend/tests/test_siming_population_decision_contracts.py backend/tests/test_siming_population_decision_planner.py backend/tests/test_siming_population_decision_routing.py backend/tests/test_siming_population_replanning.py`, `python scripts/verification/verify_siming_generalized_population_decision.py`, `python scripts/verification/harness.py --profile siming-generalized-population-decision`, `python scripts/verification/check_docs.py`, and `git diff --check`.

- [ ] **Step 6: Commit**

```powershell
git add backend/tests/test_siming_generalized_population_decision.py scripts/verification/verify_siming_generalized_population_decision.py .harness/profiles/siming-generalized-population-decision.json docs/harness.md docs/8月分析/司命与群体世界补充设计/03-群体模拟与角色分级连续性.md docs/8月分析/司命与群体世界补充设计/05-性能回放观测与渐进交付.md docs/8月分析/司命与群体世界补充设计/09-行为分层与信息传播.md docs/8月分析/司命与群体世界补充设计/10-校准性能与故障恢复.md docs/8月分析/司命与群体世界补充设计/13-群体模拟生产纵切与推进闭环设计.md
git commit -m "验证司命通用群体决策面"
```

## Plan Self-Review

- Spec coverage: generic candidate/decision contracts, pure evaluation, Siming tradeoff selection, static capability admission, Owner/Core routing, receipt-driven replanning, player activation, replay, zero-write handling, invariant Harness and explicit non-goals are covered by Tasks 1–5.
- Fixture boundary: the existing three-actor W0/W1 profile remains a regression fixture; no task removes it or treats it as the generic population contract.
- Authority boundary: no task introduces a second runtime, event bus, event store, clock, scheduler, population roster store or background LLM loop.
- Harness boundary: Task 5 explicitly allows multiple valid selected sets and tests invariants rather than a single golden path.
- Placeholder scan: no `TBD`, `TODO`, “appropriate handling”, or unspecified behavior remains in the task steps.
- Type consistency: Task 1 defines candidate/decision/descriptor types; Task 2 consumes them; Task 3 consumes selection results; Task 4 consumes receipts and emits next-cycle results; Task 5 consumes all bounded results and scenario names.
