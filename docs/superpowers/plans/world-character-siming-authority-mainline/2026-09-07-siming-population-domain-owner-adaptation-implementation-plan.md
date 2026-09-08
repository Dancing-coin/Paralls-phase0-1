# Siming Population Domain-Owner Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将最新 `Dancing-coin` 领域 Owner（领域事实写入者）能力按批准的行为逐项接入司命群体模拟，使领域投影能够成为司命候选、经权衡后进入既有 Owner/Character Core 路径，并保留零写入、隐私、幂等和回放边界。

**Architecture:** 复用现有 `SimingRuntime.tick(...)`、`PopulationReadSet`、`PopulationDecisionPlanner`、`PopulationSimulationCapability`、`GameplayEventStore` 和领域 Owner。新增的只是“已提交领域投影到群体候选”和“群体 intent 到既有 Owner 的窄适配器”，不新增 truth owner（真相 Owner）、event bus（事件总线）、event store（事件存储）、clock（时钟）或 scheduler（调度器）。实施顺序为 Production/Organization → Inventory → Social population signal → Tax 只读压力候选；每个纵切单独拥有 capability、adapter、receipt、replay/privacy Harness。

**Tech Stack:** Python 3.13, Pydantic contracts, existing `GameplayEventStore`, existing domain authorities, pytest, Harness verification profiles.

**Spec:**
- `docs/superpowers/specs/world-character-siming-authority-mainline/2026-09-01-siming-generalized-population-decision-surface-design.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-29-siming-led-population-simulation-design.md`
- `docs/8月分析/司命与群体世界补充设计/07-群体世界本体与状态模型.md`
- `docs/8月分析/司命与群体世界补充设计/08-时间空间与推进内核.md`
- `docs/8月分析/司命与群体世界补充设计/13-群体模拟生产纵切与推进闭环设计.md`

## Global Constraints

- `SimingRuntime.tick(...)` remains the only Siming decision/dispatch path.
- Population candidates are derived from committed, scope-filtered projections; a candidate is never a world fact.
- Objective candidates must resolve to a source-controlled capability and a named existing Owner; callers cannot provide a stream, event family or replacement Owner.
- Owner receipt is required before an objective result becomes Character Core continuity input.
- Actor-private projections, private Social facts and authority-only Tax amounts never enter a global population read set.
- Existing three-actor cohort and Bakery supply fixtures remain regression fixtures.
- Do not add a generic population truth owner, generic writer/router, second event bus/store, clock, scheduler or per-actor background LLM loop.
- Every new vertical must have stale, duplicate, changed-duplicate, Owner rejection, privacy and full/checkpoint-tail replay evidence.

---

### Task 1: Baseline and Capability-Adapter Matrix

**Files:**
- Create: `docs/superpowers/specs/world-character-siming-authority-mainline/2026-09-07-siming-population-domain-owner-adaptation-design.md`
- Create: `backend/tests/test_siming_population_domain_owner_matrix.py`
- Modify: `docs/harness.md`

**Interfaces:**
- Consumes: existing `GovernedAuthorityContractCatalog`, `OwnerOperationDescriptor`, `PopulationCapabilityDescriptor`, `PopulationProjection`, and the latest `Dancing-coin` Owner methods.
- Produces: an explicit matrix of candidate behavior, source projection, capability id, Owner contract, adapter, event family, visibility, and replay reader. This matrix is the admission list for later tasks.

- [ ] **Step 1: Write the failing matrix test**

Assert that the matrix distinguishes the following states:

```python
assert matrix["production_work_contribution"].status == "executable_next"
assert matrix["inventory_output_custody"].status == "planned"
assert matrix["social_population_signal"].status == "planned"
assert matrix["tax_pressure"].status == "report_only"
assert matrix["stormnight_action_window"].status == "not_population_behavior"
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python -m pytest -q backend/tests/test_siming_population_domain_owner_matrix.py`

Expected: FAIL because the adaptation matrix does not exist.

- [ ] **Step 3: Define the matrix in the design document**

Record these initial rows:

| Population behavior | Source | Existing Owner | Initial status |
|---|---|---|---|
| `organization_production_work_contribution` | committed Production evidence + Organization schedule projection | `OrganizationAuthority.accept_production_work_contribution` | first executable vertical |
| `inventory_output_custody` | certified Production output projection | `InventoryAuthorityService.settle_production_output_custody` | second executable vertical |
| `social_population_signal` | public population signal projection | `SocialFactAuthority.record_admitted_population_signal_materialization_proposal` | third executable vertical |
| `tax_pressure` | authority-derived Tax obligation summary with amount redacted | Economy/Tax Owner | report-only first |
| `stormnight_action_window` | realtime action-window evidence | `InvestigationConflictAuthority` | excluded from population cadence |

- [ ] **Step 4: Add Harness documentation for the matrix gate**

Document that a domain contract may exist without being a population capability. The profile must report the distinction explicitly.

- [ ] **Step 5: Run checks and commit**

Run: `python -m pytest -q backend/tests/test_siming_population_domain_owner_matrix.py; python scripts/verification/check_docs.py; git diff --check`

Commit: `git commit -m "建立司命群体领域 Owner 适配矩阵"`

### Task 2: Production/Organization Projection Source and Owner Adapter

**Files:**
- Create: `backend/app/population_continuity/domain_projection_sources.py`
- Modify: `backend/app/population_continuity/decision_surface.py`
- Modify: `backend/app/population_continuity/owner_adapters.py`
- Modify: `backend/app/services/siming_population_capability.py`
- Test: `backend/tests/test_siming_population_production_owner_vertical.py`

**Interfaces:**
- Consumes: committed Production evidence and Organization schedule projections; `OrganizationAuthority.accept_production_work_contribution(...)`; `PopulationReadSet`.
- Produces: `PopulationProjection` with behavior `organization_production_work_contribution`, capability `population:organization-production-work-contribution:v1`, and `OrganizationProductionWorkContributionOwnerExecutor.submit(...) -> PopulationOwnerReceipt`.

- [ ] **Step 1: Write the failing projection and adapter tests**

Cover:

```python
def test_committed_production_evidence_becomes_scoped_population_candidate():
    read_set = production_read_set_with_committed_evidence()
    projections = production_work_population_projections(
        committed_events=read_set.committed_events,
        organization_projection=read_set.organization_projection,
        scope="organization:summary",
    )
    assert projections[0].payload["candidate_kind"] == "organization_production_work_contribution"
    assert projections[0].revision_vector["gameplay:organization:org:bakery"] == 2

def test_selected_production_candidate_reaches_organization_owner():
    result = production_population_fixture().run_default_cycle()
    assert result.status == "accepted"
    assert result.owner_receipts[0].event_family == "gameplay.organization.production_work_contribution_accepted"

def test_missing_or_stale_production_evidence_is_zero_write():
    result = production_population_fixture(stale_source=True).run_default_cycle()
    assert result.status == "requeue"
    assert result.production_append_count == 0

def test_duplicate_production_owner_intent_replays_receipt_without_append():
    fixture = production_population_fixture()
    first = fixture.run_default_cycle()
    replay = fixture.run_default_cycle()
    assert first.owner_receipts[0].committed
    assert replay.owner_receipts[0].idempotency_status == "duplicate_replayed"
    assert fixture.organization_stream_head() == first.owner_receipts[0].revision_vector["gameplay:organization:org:bakery"]

def test_owner_rejection_stops_character_continuity_command():
    result = production_population_fixture(owner_rejects=True).run_default_cycle()
    assert result.status == "requeue"
    assert result.continuity_receipts == ()
```

The test fixture must use a real `GameplayEventStore` and the existing `OrganizationAuthority`, not a second writer.

- [ ] **Step 2: Run the tests and verify failure**

Run: `python -m pytest -q backend/tests/test_siming_population_production_owner_vertical.py`

Expected: FAIL because the population behavior, source projection, and adapter are not registered.

- [ ] **Step 3: Implement the projection source**

Add a pure function:

```python
def production_work_population_projections(
    *, committed_events: tuple[AuthorityEvent, ...],
    organization_projection: Mapping[str, object],
    scope: str,
) -> tuple[PopulationProjection, ...]:
    """Return only committed, scope-admitted production candidates."""
```

It may emit a candidate only when the source evidence is committed, the Organization schedule/source revision is present, the projection is public or organization-scoped, and all source refs/revisions are pinned. It must not call an Owner or append.

- [ ] **Step 4: Implement the narrow Owner adapter**

Add `OrganizationProductionWorkContributionOwnerExecutor` to `owner_adapters.py`. It must derive the target stream, event family, expected revisions, privacy and idempotency from the fixed adapter/Owner contract. It must reject caller-provided stream/event-family overrides and return `PopulationOwnerReceipt` from the existing append result.

- [ ] **Step 5: Register only this capability**

Add the descriptor to `PopulationCapabilityCatalog.default(...)`, route the adapter through `owner_executors`, and preserve `ScheduleGatedSupplyOwnerExecutor` compatibility. Do not register every catalog contract.

- [ ] **Step 6: Run the focused vertical**

Run: `python -m pytest -q backend/tests/test_siming_population_production_owner_vertical.py backend/tests/test_siming_population_decision_routing.py backend/tests/test_siming_population_replanning.py; git diff --check`

- [ ] **Step 7: Commit**

Commit: `git commit -m "接入司命生产工作 Owner 纵切"`

### Task 3: Production Receipt Projection and Replanning

**Files:**
- Modify: `backend/app/population_continuity/domain_projection_sources.py`
- Modify: `backend/app/services/siming_population_capability.py`
- Modify: `backend/app/services/siming_runtime.py`
- Test: `backend/tests/test_siming_population_production_replanning.py`
- Modify: `scripts/verification/verify_siming_generalized_population_decision.py`

**Interfaces:**
- Consumes: `PopulationOwnerReceipt`, resulting Organization projection, and existing `replan_from_receipts(...)`.
- Produces: a second cadence whose read set contains only committed Owner output and a new expected revision; rejected or stale receipt produces requeue without dependent Character Core writes.

- [ ] **Step 1: Write the failing receipt-flow tests**

```python
def test_production_receipt_is_the_only_source_for_next_population_read_set():
    fixture = production_population_fixture()
    first = fixture.run_default_cycle()
    next_read_set = fixture.read_set_after_receipt(first.owner_receipts[0])
    assert next_read_set.base_revision_vector == first.owner_receipts[0].revision_vector

def test_owner_rejection_does_not_create_next_projection():
    fixture = production_population_fixture(owner_rejects=True)
    result = fixture.run_default_cycle()
    assert result.reason == "owner_rejected"
    assert fixture.next_population_projection() is None

def test_replan_preserves_actor_revision_and_idempotency():
    fixture = production_population_fixture()
    first = fixture.run_default_cycle()
    second = fixture.replan_from_receipt(first.owner_receipts[0])
    assert second.seed_candidates[0].idempotency_key != first.seed_candidates[0].idempotency_key
    assert fixture.character_revision("character:char_a") == 2

def test_full_and_checkpoint_tail_production_replay_match():
    fixture = production_population_fixture()
    fixture.run_default_cycle()
    full, tail = fixture.replay_projection_hashes()
    assert full == tail
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest -q backend/tests/test_siming_population_production_replanning.py`

Expected: FAIL until the new production projection is consumed by the next cycle.

- [ ] **Step 3: Implement explicit projection-to-replan handoff**

Use the existing synchronous replan seam. Do not add a background loop. The next cycle must be invoked only from a committed cadence event or explicit fixture call carrying the new source vector.

- [ ] **Step 4: Verify and commit**

Run: `python -m pytest -q backend/tests/test_siming_population_production_replanning.py backend/tests/test_siming_led_population_seed_continuity.py; git diff --check`

Commit: `git commit -m "接通生产 Owner 回执群体重规划"`

### Task 4: Inventory Custody Population Vertical

**Files:**
- Create: `backend/app/population_continuity/inventory_owner_adapter.py`
- Modify: `backend/app/population_continuity/domain_projection_sources.py`
- Modify: `backend/app/population_continuity/decision_surface.py`
- Test: `backend/tests/test_siming_population_inventory_vertical.py`

**Interfaces:**
- Consumes: certified Production output projection and existing `InventoryAuthorityService.settle_production_output_custody(...)`.
- Produces: `inventory_output_custody` candidate and a receipt-backed Inventory Owner path.

- [ ] **Step 1: Write failing tests**

Cover certified source admission, holder/container mapping, stale source, changed duplicate, private custody rejection, and receipt-before-seed.

- [ ] **Step 2: Run the focused test and verify failure**

Run: `python -m pytest -q backend/tests/test_siming_population_inventory_vertical.py`

Expected: FAIL because no Population capability maps to the Inventory adapter.

- [ ] **Step 3: Implement the minimum adapter**

Reuse the existing family binding and Inventory method. The population intent may carry source refs and revision pins only; holder, container, quantity and target stream remain Owner-derived or binding-derived.

- [ ] **Step 4: Verify and commit**

Run: `python -m pytest -q backend/tests/test_siming_population_inventory_vertical.py backend/tests/test_production_output_custody_family.py; git diff --check`

Commit: `git commit -m "接入司命库存保管 Owner 纵切"`

### Task 5: Public Social Population Signal Vertical

**Files:**
- Create: `backend/app/population_continuity/social_owner_adapter.py`
- Modify: `backend/app/population_continuity/domain_projection_sources.py`
- Modify: `backend/app/population_continuity/decision_surface.py`
- Test: `backend/tests/test_siming_population_social_signal_vertical.py`

**Interfaces:**
- Consumes: public, revision-pinned population signal input and `SocialFactAuthority.record_admitted_population_signal_materialization_proposal(...)`.
- Produces: a public `social_population_signal` candidate and receipt; no private relationship projection enters the global read set.

- [ ] **Step 1: Write failing tests**

```python
def test_public_signal_can_be_selected_and_settled_by_social_owner():
    result = social_population_fixture().run_default_cycle()
    assert result.status == "accepted"
    assert result.owner_receipts[0].owner_ref == "authority:p5:social"

def test_private_relationship_projection_is_rejected_before_planning():
    result = social_population_fixture(private_projection=True).run_default_cycle()
    assert result.status == "requeue"
    assert result.production_append_count == 0

def test_social_owner_receipt_is_replayable_without_duplicate_write():
    fixture = social_population_fixture()
    first = fixture.run_default_cycle()
    replay = fixture.run_default_cycle()
    assert first.owner_receipts[0].committed
    assert replay.owner_receipts[0].idempotency_status == "duplicate_replayed"
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest -q backend/tests/test_siming_population_social_signal_vertical.py`

Expected: FAIL because the population capability and adapter are absent.

- [ ] **Step 3: Implement the adapter and projection source**

Use only the public population-signal contract. Do not expose `social-private-projection`, actor memory, or relationship private facts to Siming population selection.

- [ ] **Step 4: Verify and commit**

Run: `python -m pytest -q backend/tests/test_siming_population_social_signal_vertical.py backend/tests/test_organization_government_social_family_success_matrix.py; git diff --check`

Commit: `git commit -m "接入司命公开社会信号 Owner 纵切"`

### Task 6: Tax Pressure Read-Only Candidate

**Files:**
- Modify: `backend/app/population_continuity/domain_projection_sources.py`
- Modify: `backend/app/population_continuity/decision_surface.py`
- Test: `backend/tests/test_siming_population_tax_pressure.py`

**Interfaces:**
- Consumes: authority-derived Tax obligation lifecycle projection with amount/evidence redaction.
- Produces: `tax_pressure` as `presentation_seed`, `activation_candidate`, or `defer`; no population-driven account debit/payment.

- [ ] **Step 1: Write failing tests**

```python
def test_tax_obligation_projection_becomes_redacted_pressure_candidate():
    projections = tax_pressure_projections(tax_obligation_projection())
    assert projections[0].payload["candidate_kind"] == "tax_pressure"
    assert "amount_minor" not in projections[0].payload

def test_tax_amount_and_authority_only_evidence_never_enter_population_read_set():
    read_set = tax_population_read_set()
    assert all("amount_minor" not in projection.payload for projection in read_set.projections)
    assert all(projection.scope != "authority_only" for projection in read_set.projections)

def test_tax_pressure_cannot_produce_owner_bound_intent():
    result = tax_population_fixture().run_default_cycle()
    assert all("owner_bound_intent" not in candidate.allowed_outputs for candidate in result.decision.selected_candidates)
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest -q backend/tests/test_siming_population_tax_pressure.py`

Expected: FAIL because the projection classifier does not recognize tax pressure.

- [ ] **Step 3: Implement report-only classification**

Add a descriptor with no `owner_bound_intent`. Preserve the Tax Owner as the only writer of tax obligations and payments. A future payment vertical must be a separate approved plan with payer/account/currency/source evidence.

- [ ] **Step 4: Verify and commit**

Run: `python -m pytest -q backend/tests/test_siming_population_tax_pressure.py backend/tests/test_infra_economy_tax_obligation.py; git diff --check`

Commit: `git commit -m "增加司命税务压力只读候选"`

### Task 7: Runtime Wiring and Generalized Population Harness

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/population_continuity/__init__.py`
- Create: `scripts/verification/verify_siming_population_domain_owner_adaptation.py`
- Create: `.harness/profiles/siming-population-domain-owner-adaptation.json`
- Modify: `docs/harness.md`
- Modify: `docs/8月分析/司命与群体世界补充设计/03-群体模拟与角色分级连续性.md`
- Modify: `docs/8月分析/司命与群体世界补充设计/13-群体模拟生产纵切与推进闭环设计.md`

**Interfaces:**
- Consumes: Tasks 2–6 adapters and descriptors.
- Produces: one production runtime wiring path and an independent Harness proving that multiple domain candidates can be selected, deferred, settled, replayed, or rejected through `SimingRuntime.tick(...)`.

- [ ] **Step 1: Write the failing integration test**

Assert that runtime construction passes `owner_executors` for only the admitted adapters and that an unsupported descriptor requeues with zero write.

- [ ] **Step 2: Run it and verify failure**

Run: `python -m pytest -q backend/tests/test_siming_population_domain_owner_runtime.py`

Expected: FAIL because `main.py` currently wires only the legacy supply Owner.

- [ ] **Step 3: Wire the admitted adapters**

Construct adapters from the existing shared `GameplayEventStore` and authorities. Keep `owner_executor` for Bakery compatibility and pass the explicit `owner_executors` mapping for new population capabilities.

- [ ] **Step 4: Add the Harness verifier**

The verifier must assert:

```text
multiple domain candidates remain valid;
selection changes with policy/budget;
only admitted capability ids reach Owners;
private/authority-only projections are redacted or rejected;
Owner receipts precede Character Core seeds;
replay and checkpoint-tail digests match;
Stormnight action windows remain outside population cadence;
```

- [ ] **Step 5: Run the complete verification set**

Run:

```powershell
python -m pytest -q
python scripts/verification/harness.py --profile siming-population-domain-owner-adaptation
python scripts/verification/harness.py --profile siming-generalized-population-decision
python scripts/verification/harness.py --profile siming-led-population-seed-continuity
python scripts/verification/harness.py --profile siming-governed-three-actor-cohort-continuity-v1
python scripts/verification/check_docs.py
git diff --check
```

- [ ] **Step 6: Commit the integrated vertical**

Commit: `git commit -m "完成司命群体领域 Owner 适配闭环"`

## Execution Order and Review Checkpoints

1. Task 1 is the admission checkpoint: no domain capability is added without a row in the matrix.
2. Task 2 is the first new executable vertical: Production/Organization must pass before Inventory or Social work starts.
3. Task 3 proves receipt-driven projection and replan, not a background loop.
4. Tasks 4 and 5 are independent domain slices and may be stopped if their source or privacy contract is insufficient.
5. Task 6 is intentionally report-only until a separate exact Tax payment/settlement contract is approved.
6. Task 7 is the only point where the new adapters enter the default runtime wiring.

## Explicit Non-Goals

- No automatic discovery or registration of every existing Owner contract.
- No direct use of Stormnight realtime action windows as population behavior.
- No population-driven inventory quantity invention, relationship invention, tax payment or account debit.
- No global Social private-memory projection.
- No new event bus, event store, clock, scheduler, population truth owner or generic writer.
- No per-actor background LLM population loop.
- No claim that completing these slices equals complete civilization simulation.
