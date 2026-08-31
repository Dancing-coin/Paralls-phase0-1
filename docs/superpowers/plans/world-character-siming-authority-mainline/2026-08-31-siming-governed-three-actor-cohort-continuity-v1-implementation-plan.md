# Siming-Governed Three-Actor Cohort Continuity V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing one-actor bakery proof into a deterministic three-actor, two-cadence cohort flow governed by `SimingRuntime.tick(...)`, with one Owner-mediated world effect and two non-world-writing actor continuity outcomes.

**Architecture:** Reuse the existing `PopulationReadSet`, `PopulationPlanner`, `PopulationSimulationCapability`, `OrganizationAuthority`, `CharacterAgentRuntime`, `ActivationPolicy`, `AuthorityEventBus`, and replay/Harness surfaces. Add only the narrow cohort disposition and report fields needed to distinguish `char_a` owner-bound supply, `char_b` presentation-only routine work, and `char_c` activation-only social pressure. Keep all objective writes behind existing Owner contracts and all actor continuity writes behind Character Core.

**Tech Stack:** Python 3.13, Pydantic contracts, existing gameplay event store and authority event bus, pytest, replay projector, Harness JSON profiles.

**Spec:** `docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-31-siming-governed-three-actor-cohort-continuity-v1-design.md`

## Global Constraints

- `SimingRuntime.tick(...)` remains the only Siming decision and dispatch path.
- `PopulationPlanner` is an internal pure calculator; it cannot append events, invoke an Owner, or write Character Core state/memory.
- The existing Organization Owner is the only V1 objective-world writer, and only `schedule_gated_supply` for `character:char_a` is admitted.
- `char_b` may receive only a presentation-only `routine_work` seed with empty state deltas and no memory candidate.
- `char_c` receives only an `activation_candidate`; cohort simulation must not issue a Character Core command or implicit LLM turn for it.
- Owner receipt is required before an objective seed reaches Character Core.
- Character Core is the only owner allowed to admit `CharacterContinuityCommand`, append SeedDelta, update actor continuity state, materialize five-pool memory, or advance actor revision.
- Branch, private, cross-actor, stale, unknown, duplicate-mismatch, owner-rejected, budget-exhausted, and malformed inputs must produce auditable zero production write.
- No second runtime, event bus, event store, truth owner, clock, scheduler, generic writer, dynamic behavior registry, population roster store, global social graph, or per-actor background LLM loop.
- Full replay and checkpoint-plus-tail replay must agree for gameplay/Owner projections, all three actor continuity projections, cohort reports, receipts, and cycle status.
- The implementation must not claim complete population, social, economic, civilization, or multi-region simulation.

## Task 1: Closed cohort contracts and deterministic disposition

**Files:**
- Modify: `backend/app/population_continuity/models.py`
- Modify: `backend/app/population_continuity/siming_contracts.py`
- Test: `backend/tests/test_siming_population_cohort_contracts.py`

**Interfaces:**
- Add `CohortDisposition = Literal["char_a_supply", "char_b_routine_work", "char_c_social_activation"]`.
- Add `PopulationCohortMember(ContinuityModel)` with `actor_ref`, `disposition`, `cost`, and `source_projection_ref`.
- Add `PopulationCohortReport(ContinuityModel)` with `cohort_ref`, `window`, `member_refs`, `selected_refs`, `unprocessed_refs`, `budget`, `selector_revision`, and `ruleset_revision`.
- Extend `PopulationBatchReport` with optional `cohort_ref`, `cohort_member_refs`, `unprocessed_cohort_refs` and bounded classification counts without changing existing callers.

- [ ] **Step 1: Write the failing tests**

```python
def test_cohort_member_accepts_only_the_three_closed_dispositions() -> None:
    member = PopulationCohortMember(
        actor_ref="character:char_a",
        disposition="char_a_supply",
        cost=1,
        source_projection_ref="projection:char_a:w0",
    )
    assert member.disposition == "char_a_supply"


def test_unknown_cohort_disposition_is_rejected_by_schema() -> None:
    with pytest.raises(ValidationError):
        PopulationCohortMember(
            actor_ref="character:char_a",
            disposition="free_form_social",
            cost=1,
            source_projection_ref="projection:char_a:w0",
        )


def test_cohort_report_preserves_fixed_actor_order_and_budget() -> None:
    report = PopulationCohortReport(
        cohort_ref="cohort:bakery:W0",
        window="W0",
        member_refs=("character:char_a", "character:char_b", "character:char_c"),
        selected_refs=("character:char_a", "character:char_b", "character:char_c"),
        unprocessed_refs=(),
        budget=3,
        selector_revision="selector:cohort-bakery:v1",
        ruleset_revision="rules:cohort-bakery:v1",
    )
    assert report.member_refs == ("character:char_a", "character:char_b", "character:char_c")
    assert report.budget == 3
```

- [ ] **Step 2: Run tests and verify RED**

Run `python -m pytest -q backend/tests/test_siming_population_cohort_contracts.py`.

Expected: FAIL because the cohort models and report fields do not exist.

- [ ] **Step 3: Implement the minimal closed models**

Use Pydantic `Literal`/`Field` validation and `extra="forbid"` through the existing `ContinuityModel`. Do not create a registry or persistence layer. Export the models from `backend/app/population_continuity/__init__.py` only if existing package exports require it.

- [ ] **Step 4: Run the tests and regression checks**

Run the cohort contract test and `python -m pytest -q backend/tests/test_siming_population_planner.py backend/tests/test_siming_population_capability.py`.

Expected: PASS with existing planner/capability behavior unchanged.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/population_continuity/models.py backend/app/population_continuity/siming_contracts.py backend/tests/test_siming_population_cohort_contracts.py
git commit -m "增加三角色群体分组契约"
```

## Task 2: Pure planner cohort selection and classification

**Files:**
- Modify: `backend/app/population_continuity/batch.py`
- Modify: `backend/app/population_continuity/seed_planner.py`
- Test: `backend/tests/test_siming_population_cohort_planner.py`

**Interfaces:**
- Add `PopulationPlanner.plan_three_actor_cohort(read_set: PopulationReadSet) -> PopulationBatchReport`.
- Keep the fixed order `(character:char_a, character:char_b, character:char_c)` and cost `1` for each disposition.
- `char_a_supply` produces the existing `PopulationOwnerBoundIntent` only.
- `char_b_routine_work` produces a presentation seed with no objective effect.
- `char_c_social_activation` produces `PopulationActivationCandidate` only.
- Extend `CharacterSeedPlanner.derive(...)` so `routine_work` can produce a seed with empty `state_deltas` and no memory candidates, while `relationship_negotiation` remains activation-only in this cohort path.

- [ ] **Step 1: Write failing planner tests**

```python
def test_three_actor_cohort_classifies_supply_routine_and_social_without_writes() -> None:
    report = PopulationPlanner().plan_three_actor_cohort(cohort_read_set("W0", budget=3))
    assert report.cohort_member_refs == (
        "character:char_a",
        "character:char_b",
        "character:char_c",
    )
    assert len(report.owner_bound_intents) == 1
    assert report.owner_bound_intents[0].actor_ref == "character:char_a"
    assert report.presentation_seeds["character:char_b"]["behavior_kind"] == "routine_work"
    assert report.activation_candidates == ("projection:char_c:w0",)


def test_budget_two_reports_char_c_unprocessed_without_upgrading_char_b() -> None:
    report = PopulationPlanner().plan_three_actor_cohort(cohort_read_set("W0", budget=2))
    assert report.selected_cohort_refs == (
        "projection:char_a:w0",
        "projection:char_b:w0",
    )
    assert report.unprocessed_cohort_refs == ("projection:char_c:w0",)
    assert report.owner_bound_intents[0].intent_kind == "supply"


def test_routine_work_seed_has_no_memory_candidate_or_objective_effect() -> None:
    seeds = CharacterSeedPlanner().derive(cohort_read_set("W0", budget=3), accepted_owner_receipts=())
    routine = next(seed for seed in seeds if seed.actor_ref == "character:char_b")
    assert routine.memory_candidates == ()
    assert routine.state_deltas == {}
    assert routine.owner_effect_status == "not_required"


def test_relationship_negotiation_stays_activation_only() -> None:
    seeds = CharacterSeedPlanner().derive(cohort_read_set("W0", budget=3), accepted_owner_receipts=())
    social = next(seed for seed in seeds if seed.actor_ref == "character:char_c")
    assert social.owner_effect_status == "not_required"
    assert social.memory_candidates == ()
```

The test module must define `cohort_read_set(window, budget)` with three typed `PopulationProjection` values and exact source revision vectors. The `char_a` projection includes the existing frozen `schedule_gated_supply_source_context`; `char_b` and `char_c` contain only public/organization summary fields.

- [ ] **Step 2: Run tests and verify RED**

Run `python -m pytest -q backend/tests/test_siming_population_cohort_planner.py`.

Expected: FAIL because `plan_three_actor_cohort` and the new disposition handling do not exist.

- [ ] **Step 3: Implement pure classification**

Reuse `PopulationPlanner.plan_population_cycle` helpers where possible. The method must not import `GameplayEventStore`, `OrganizationAuthority`, `CharacterAgentRuntime`, or activation authority. Unknown behavior remains rejected; no fallback behavior is invented.

- [ ] **Step 4: Run planner regressions**

Run:

```powershell
python -m pytest -q backend/tests/test_siming_population_cohort_contracts.py backend/tests/test_siming_population_cohort_planner.py backend/tests/test_siming_population_planner.py
git diff --check
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/population_continuity/batch.py backend/app/population_continuity/seed_planner.py backend/tests/test_siming_population_cohort_planner.py
git commit -m "实现司命三角色群体分组计算"
```

## Task 3: Siming capability across W0/W1 and Owner/Character Core routing

**Files:**
- Modify: `backend/app/services/siming_population_capability.py`
- Modify: `backend/app/services/siming_runtime.py`
- Test: `backend/tests/test_siming_population_cohort_capability.py`

**Interfaces:**
- Add `PopulationSimulationCapability.run_cohort_cycle(cadence_input, read_set) -> PopulationCycleResult`.
- Keep `run_cycle(...)` backward-compatible by delegating only when the read-set identifies a V1 cohort.
- Add a bounded cycle summary audit containing cohort/window/classification/Owner/continuity counts.
- Resolve all planned actor revisions before Owner submission; use per-actor monotonic revisions for multiple seeds.
- Send Character Core commands only for `char_a` settled supply and `char_b` presentation seed; never for `char_c` activation-only.
- `SimingRuntime.tick(...)` remains the only caller of `run_cohort_cycle`.

- [ ] **Step 1: Write failing capability tests**

```python
def test_w0_routes_only_char_a_to_owner_and_char_a_char_b_to_character_core() -> None:
    result, owner, continuity = run_cohort_cycle("W0")
    assert result.status == "accepted"
    assert [item.profile_ref for item in owner.calls] == ["character:char_a"]
    assert [item.actor_ref for item in continuity.commands] == [
        "character:char_a",
        "character:char_b",
    ]


def test_w1_uses_new_source_revision_and_actor_revision() -> None:
    fixture = CohortCapabilityFixture.create()
    first = fixture.run_window("W0")
    second = fixture.run_window("W1", base_revision_vector=fixture.owner_revision_vector())
    assert first.status == "accepted"
    assert second.status == "accepted"
    assert fixture.continuity.expected_revisions("character:char_a") == [0, 1]
    assert fixture.continuity.expected_revisions("character:char_b") == [0, 1]


def test_missing_owner_receipt_keeps_char_a_seed_pending_without_core_command() -> None:
    result, owner, continuity = run_cohort_cycle("W0", owner_committed=False)
    assert result.status == "owner_settlement_required"
    assert continuity.commands == []
    assert any(seed.owner_effect_status == "owner_settlement_required" for seed in result.seed_candidates)


def test_char_c_is_activation_candidate_only() -> None:
    result, owner, continuity = run_cohort_cycle("W0")
    assert result.report.activation_candidates == ("projection:char_c:W0",)
    assert all(command.actor_ref != "character:char_c" for command in continuity.commands)


def test_w1_duplicate_and_changed_source_are_distinct() -> None:
    fixture = CohortCapabilityFixture.create()
    fixture.run_window("W0")
    duplicate = fixture.run_window("W0")
    changed = fixture.run_window("W1")
    assert duplicate.owner_receipts[0].idempotency_status == "duplicate_replayed"
    assert duplicate.continuity_receipts[0].status == "idempotent_replay"
    assert changed.status == "accepted"
```

- [ ] **Step 2: Run tests and verify RED**

Run `python -m pytest -q backend/tests/test_siming_population_cohort_capability.py`.

Expected: FAIL because the cohort cycle interface, W0/W1 fixture path, and per-window routing do not exist.

- [ ] **Step 3: Implement capability routing**

Perform scope/cadence/read-set validation before planner execution. After planning, resolve every actor revision before invoking the Owner. Only a settled Owner association can produce a `char_a` Character Core command. `char_b` uses a non-objective command with empty memory candidates. `char_c` remains activation-only. Any continuity rejection/requeue changes the cycle status and stops dependent later commands.

In `SimingRuntime.tick(...)`, retain the existing `SimingAuditRecord` path and include the bounded cohort summary. Do not add a population result store or a second read model.

- [ ] **Step 4: Run capability and runtime regressions**

```powershell
python -m pytest -q backend/tests/test_siming_population_cohort_contracts.py backend/tests/test_siming_population_cohort_planner.py backend/tests/test_siming_population_cohort_capability.py backend/tests/test_siming_population_production_boundaries.py backend/tests/test_siming_population_capability.py backend/tests/test_siming_character_dispatch_adapter.py
git diff --check
```

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/siming_population_capability.py backend/app/services/siming_runtime.py backend/tests/test_siming_population_cohort_capability.py
git commit -m "接入司命双节奏群体连续性"
```

## Task 4: Character Core continuity and player activation for three actors

**Files:**
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Modify: `backend/app/character_agent/services/character_continuity.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_siming_population_cohort_activation.py`

**Interfaces:**
- Reuse `CharacterAgentRuntime.apply_character_continuity_command`, `get_continuity_revision`, `activate_actor`, and `ActivationPolicy`.
- Add no new actor identity. `char_a` and `char_b` continue through existing records; `char_c` activation uses the existing record only.
- Verify `char_b` pending seed has no memory candidate and activation does not materialize a five-pool record.
- Verify player focus/dialogue for `char_c` enters `prewarm`/`active` according to existing policy and holds the existing activation lock through the synchronous cognition callback.

- [ ] **Step 1: Write failing activation/continuity tests**

```python
def test_char_b_seed_is_actor_local_and_has_no_pending_memory() -> None:
    fixture = CohortCapabilityFixture.create()
    fixture.run_window("W0")
    assert fixture.character.get_seed_projection("char_b")["presentation_seed"]["behavior_kind"] == "routine_work"
    assert fixture.character.get_pending_seed_candidates("char_b") == []
    assert fixture.character.get_memory_bundle("char_b")["event_memories"] == []


def test_char_c_player_dialogue_activates_same_identity_under_lock() -> None:
    fixture = CohortCapabilityFixture.create()
    fixture.run_window("W0")
    before = fixture.character.character_identity_digest("char_c")
    seen_lock: list[bool] = []
    receipt = fixture.player_dialogue_char_c(
        cognition_callback=lambda: seen_lock.append(fixture.character.activation_lock_is_active("char_c"))
    )
    assert receipt.status == "active"
    assert seen_lock == [True]
    assert fixture.character.character_identity_digest("char_c") == before


def test_char_c_without_player_input_never_gets_continuity_command() -> None:
    fixture = CohortCapabilityFixture.create()
    result = fixture.run_window("W0")
    assert result.report.activation_candidates == ("projection:char_c:W0",)
    assert fixture.continuity.commands_for("character:char_c") == []
```

- [ ] **Step 2: Run tests and verify RED**

Run `python -m pytest -q backend/tests/test_siming_population_cohort_activation.py`.

Expected: FAIL because the three-actor fixture and `char_b`/`char_c` assertions do not exist.

- [ ] **Step 3: Implement only missing Character Core seams**

Use the existing continuity command path. Do not add a second memory store or a new activation authority. Keep `char_b`'s seed empty of memory candidates; keep `char_c` out of continuity admission until a structured player input reaches the existing production input handler.

- [ ] **Step 4: Run activation regressions**

```powershell
python -m pytest -q backend/tests/test_siming_population_cohort_activation.py backend/tests/test_population_activation_policy.py backend/tests/test_character_agent_activation_handoff.py backend/tests/test_character_agent_control_modes.py
git diff --check
```

- [ ] **Step 5: Commit**

```powershell
git add backend/app/character_agent/runtime/runtime_loop.py backend/app/character_agent/services/character_continuity.py backend/app/main.py backend/tests/test_siming_population_cohort_activation.py
git commit -m "接入三角色连续性与玩家激活"
```

## Task 5: Two-window production fixture, replay, Harness and documentation

**Files:**
- Modify: `backend/app/population_continuity/vertical.py`
- Create: `backend/tests/test_siming_governed_three_actor_cohort_continuity.py`
- Create: `scripts/verification/verify_siming_governed_three_actor_cohort_continuity.py`
- Create: `.harness/profiles/siming-governed-three-actor-cohort-continuity-v1.json`
- Modify: `docs/harness.md`
- Modify: `docs/8月分析/司命与群体世界补充设计/03-群体模拟与角色分级连续性.md`
- Modify: `docs/8月分析/司命与群体世界补充设计/13-群体模拟生产纵切与推进闭环设计.md`
- Modify: `docs/8月分析/12-实现收口与证据映射.md`

**Interfaces:**
- Add `ThreeActorCohortContinuityFixture.create() -> ThreeActorCohortContinuityFixture`.
- Add `run_window("W0" | "W1") -> PopulationCycleResult` and `run() -> dict[str, object]`.
- Add direct Harness profile `siming-governed-three-actor-cohort-continuity-v1` with `include_in_all=false` until independently green.

- [ ] **Step 1: Write failing end-to-end test**

```python
def test_two_window_three_actor_cohort_closes_under_siming_governance() -> None:
    result = ThreeActorCohortContinuityFixture.create().run()
    assert result["w0"]["status"] == "accepted"
    assert result["w1"]["status"] == "accepted"
    assert result["w0"]["selected"] == ["character:char_a", "character:char_b", "character:char_c"]
    assert result["w1"]["selected"] == ["character:char_a", "character:char_b", "character:char_c"]
    assert result["owner"]["actor_ref"] == "character:char_a"
    assert result["owner"]["event_family"] == "gameplay.organization.commerce_commitment_accepted"
    assert result["character"]["seeded_actors"] == ["character:char_a", "character:char_b"]
    assert result["character"]["activation_only_actors"] == ["character:char_c"]
    assert result["replay"]["full_equals_checkpoint_tail"] is True
    assert result["rejections"]["private_zero_write"] is True
    assert result["rejections"]["branch_zero_write"] is True
    assert result["rejections"]["duplicate_mismatch_zero_write"] is True
    assert result["rejections"]["budget_unprocessed_zero_write"] is True
```

- [ ] **Step 2: Run test and verify RED**

Run `python -m pytest -q backend/tests/test_siming_governed_three_actor_cohort_continuity.py`.

Expected: FAIL because the fixture, verifier and profile do not exist.

- [ ] **Step 3: Implement the fixture and verifier**

Build on `BakeryDistrictPopulationFixture`; do not create a new event store or runtime. Publish W0 and W1 through the existing authority bus. Capture per-window read-set/result digests, selected/unprocessed cohort refs, Owner receipts, Character Core receipts, activation candidate state, and per-actor continuity snapshots. Replay both gameplay/Owner history and all three actor continuity snapshots through independent full-history and checkpoint-tail paths.

Add zero-write cases for:

```text
branch/private/nested scope -> no planner/Owner/Core write
budget=2 -> char_c unprocessed, no upgrade to Owner intent
duplicate W0 -> Owner duplicate_replayed + Character idempotent_replay
changed duplicate payload/source -> idempotency_key_reused + no settled seed
missing Owner receipt -> char_a remains owner_settlement_required, no Core command
```

- [ ] **Step 4: Add direct Harness profile**

Use this exact manifest:

```json
{
  "schema_version": 1,
  "name": "siming-governed-three-actor-cohort-continuity-v1",
  "order": 119,
  "include_in_profile_order": false,
  "include_in_all": false,
  "script": "scripts/verification/verify_siming_governed_three_actor_cohort_continuity.py",
  "requires_godot": false,
  "max_attempts": 1,
  "result_artifact": ".harness/verification/siming-governed-three-actor-cohort-continuity-v1-report.json",
  "description": "Siming-governed three-actor two-cadence cohort continuity with one existing Organization Owner row"
}
```

The verifier must check predecessor reports, focused pytest, single bus/tick identity, Owner event family, seeded actors, activation-only actor, replay equality, and every zero-write case. It must write `overall_passed`, `predecessors`, `harness_checks`, `w0`, `w1`, `owner`, `character`, `activation`, `replay`, and `zero_write` fields.

- [ ] **Step 5: Update documentation with proven facts only**

Record that the three-actor/two-window cohort vertical is implemented bounded only after its direct profile is green. Keep complete population, social, economic, civilization and multi-region simulation explicitly incomplete. Keep the new profile excluded from aggregate `all`.

- [ ] **Step 6: Run complete verification**

```powershell
python -m pytest -q
python scripts/verification/verify_siming_governed_three_actor_cohort_continuity.py
python scripts/verification/harness.py --profile siming-governed-three-actor-cohort-continuity-v1
python scripts/verification/harness.py --profile siming-led-population-seed-continuity
python scripts/verification/harness.py --profile phase3-population-continuity
python scripts/verification/harness.py --profile change-lifecycle
git diff --check
```

Do not add the profile to `all` in this plan. If an aggregate profile fails for an unrelated existing environment issue, preserve the report and describe the caveat instead of hiding the failure.

- [ ] **Step 7: Commit the vertical**

```powershell
git add backend/app/population_continuity/vertical.py backend/tests/test_siming_governed_three_actor_cohort_continuity.py scripts/verification/verify_siming_governed_three_actor_cohort_continuity.py .harness/profiles/siming-governed-three-actor-cohort-continuity-v1.json docs/harness.md docs/8月分析/司命与群体世界补充设计/03-群体模拟与角色分级连续性.md docs/8月分析/司命与群体世界补充设计/13-群体模拟生产纵切与推进闭环设计.md docs/8月分析/12-实现收口与证据映射.md
git commit -m "验证司命监管三角色双节奏群体连续性"
```

## Plan Self-Review

- Spec coverage: ownership, fixed three-actor cohort, W0/W1 cadence, pure planner classification, Owner gate, Character Core continuity, player activation, privacy/replay/idempotency/zero-write, direct Harness evidence, and non-goals are each covered by Tasks 1–5.
- Placeholder scan: no `TBD`, `TODO`, or unspecified “appropriate handling” steps remain; test builders and exact field values are named in the task where they are used.
- Type consistency: Task 1 defines the cohort models; Task 2 consumes them; Task 3 consumes the planner report and emits `PopulationCycleResult`; Task 4 reuses the existing Character Core/Activation interfaces; Task 5 exposes the final fixture and Harness contract.
- Scope ruling: `char_b` and `char_c` deliberately do not gain new world Owner contracts in V1. This keeps implementation inside the approved documents and leaves future behavior rows to separate source-controlled capability/Owner plans.
