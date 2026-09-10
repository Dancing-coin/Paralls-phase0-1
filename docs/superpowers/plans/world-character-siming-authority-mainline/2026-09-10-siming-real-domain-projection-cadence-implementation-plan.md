# Siming Real Domain Projection Cadence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make committed Production, Inventory, public Social, and redacted Tax facts enter an already-authorized population cadence as real `PopulationProjection` inputs, so Siming selects actual world consequences instead of only the hard-coded Bakery supply candidate.

**Architecture:** Keep the cadence authorization and the candidate source separate. An existing world-mode/schedule-authorized `PopulationCadenceInput` decides that a batch may run; a new read-only assembler reads only committed, scoped, revision-pinned `GameplayEventStore` facts and adds typed projections to that batch. `SimingRuntime.tick(...)` remains the only decision/dispatch path; domain Owners and Character Core keep all writes.

**Tech Stack:** Python 3.13, Pydantic, `GameplayEventStore`, `AuthorityEvent`, `PopulationCadenceInput`, `PopulationProjection`, existing Owner authorities, pytest, Harness.

**Spec:**
- `docs/superpowers/specs/world-character-siming-authority-mainline/2026-09-01-siming-generalized-population-decision-surface-design.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-29-siming-led-population-simulation-design.md`
- `docs/8月分析/司命与群体世界补充设计/08-时间空间与推进内核.md`
- `docs/8月分析/司命与群体世界补充设计/13-群体模拟生产纵切与推进闭环设计.md`

## Global Constraints

- `SimingRuntime.tick(...)` is the only Siming decision and dispatch path.
- A cadence is authorized only by an existing committed world-mode, activation, or schedule projection. This plan adds no wall-clock, scheduler, background loop, or locally invented cadence.
- Projection assembly is read-only: it may not append to `GameplayEventStore`, invoke an Owner, call Character Core, alter a package registry, or allocate an identity.
- A candidate names one source-controlled capability and one existing Owner. Candidate payloads never select streams, event families, owner refs, account refs, container refs, quantity, or package bindings.
- Only `project`, `public`, and `organization:summary` data may enter a global population read set. Actor-private Social data and Tax amount/account/evidence data remain excluded.
- Owner receipts are required before objective Character Core seeds. A projection cannot self-declare a settled receipt.
- Default package activation remains the exact six-manifest set in `production_package_registry.py`; do not broaden it by directory scanning.
- Existing Bakery supply, three-actor fixture, Production/Organization, Inventory, public Social, and Tax-pressure regression tests remain green.

---

### Task 1: Read-Only Store Projection Assembler

**Files:**
- Create: `backend/app/population_continuity/store_projection_assembler.py`
- Modify: `backend/app/population_continuity/domain_projection_sources.py`
- Test: `backend/tests/test_siming_population_store_projection_assembler.py`

**Interfaces:**
- Consumes: `GameplayEventStore`, `PopulationCadenceInput`, and one existing scoped Organization schedule projection.
- Produces: `assemble_committed_population_projections(store, cadence, organization_projection) -> tuple[PopulationProjection, ...]`.
- Uses: `production_work_population_projections`, `inventory_output_custody_population_projections`, `social_population_signal_population_projections`, and `tax_pressure_population_projections` without changing their Owner boundaries.

- [ ] **Step 1: Write failing source-event tests**

```python
def test_assembler_emits_production_candidate_only_from_committed_evidence() -> None:
    store, cadence, organization_projection = committed_production_fixture()
    projections = assemble_committed_population_projections(
        store=store,
        cadence=cadence,
        organization_projection=organization_projection,
    )
    assert [item.payload["candidate_kind"] for item in projections] == [
        "organization_production_work_contribution"
    ]


def test_assembler_rejects_private_evidence_and_stale_schedule_vector() -> None:
    store, cadence, private_projection = private_or_stale_production_fixture()
    assert assemble_committed_population_projections(
        store=store,
        cadence=cadence,
        organization_projection=private_projection,
    ) == ()
```

- [ ] **Step 2: Verify the tests fail before implementation**

Run: `python -m pytest -q backend/tests/test_siming_population_store_projection_assembler.py`

Expected: FAIL because `assemble_committed_population_projections` does not exist.

- [ ] **Step 3: Implement the assembler**

```python
def assemble_committed_population_projections(
    *,
    store: GameplayEventStore,
    cadence: PopulationCadenceInput,
    organization_projection: Mapping[str, object],
) -> tuple[PopulationProjection, ...]:
    """Read committed facts pinned by the cadence; never append or settle."""
```

Implementation rules:

```text
1. Read events only from store.read_events().
2. Convert only the fields required by each existing source function.
3. Require every emitted projection revision vector to equal the source stream head and be compatible with cadence.base_revision_vector.
4. Sort projections by ref before returning.
5. Drop malformed, private, stale, cross-scope, duplicate-ref, or non-committed rows.
6. Do not call an Owner or Character Core method.
```

- [ ] **Step 4: Add Inventory, Social, and Tax source tests**

```python
def test_assembler_emits_inventory_only_from_project_visible_certification() -> None:
    store, cadence, organization_projection = certified_output_fixture()
    projections = assemble_committed_population_projections(
        store=store, cadence=cadence, organization_projection=organization_projection
    )
    assert "inventory_output_custody" in {
        item.payload["candidate_kind"] for item in projections
    }


def test_assembler_emits_public_social_but_not_private_relationships() -> None:
    store, cadence, organization_projection = public_and_private_social_fixture()
    projections = assemble_committed_population_projections(
        store=store, cadence=cadence, organization_projection=organization_projection
    )
    assert all(item.scope != "actor:self" for item in projections)
    assert "social_population_signal" in {
        item.payload["candidate_kind"] for item in projections
    }


def test_assembler_redacts_tax_before_creating_pressure_candidate() -> None:
    store, cadence, organization_projection = tax_due_fixture()
    projections = assemble_committed_population_projections(
        store=store, cadence=cadence, organization_projection=organization_projection
    )
    tax = next(item for item in projections if item.payload["candidate_kind"] == "tax_pressure")
    assert "amount_minor" not in tax.payload
    assert "payer_account_id" not in tax.payload
```

- [ ] **Step 5: Verify and commit**

Run:

```powershell
python -m pytest -q backend/tests/test_siming_population_store_projection_assembler.py backend/tests/test_siming_population_production_owner_vertical.py backend/tests/test_siming_population_inventory_vertical.py backend/tests/test_siming_population_social_signal_vertical.py backend/tests/test_siming_population_tax_pressure.py
git diff --check
```

Commit: `git commit -m "汇编已提交领域群体投影"`

### Task 2: Authorized Cadence Publication Seam

**Files:**
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_siming_population_authorized_cadence_publication.py`
- Modify: `backend/tests/test_siming_population_production_boundaries.py`

**Interfaces:**
- Consumes: an existing `PopulationCadenceInput`, existing room/scene/zone routing coordinates, scoped Organization projection, and `assemble_committed_population_projections(...)`.
- Produces: one `AuthorityEvent(event_type="population_cadence_event")` whose `population_projections` are the frozen union of legacy supply and assembled domain projections.

- [ ] **Step 1: Write failing publication tests**

```python
def test_authorized_cadence_publisher_uses_given_cadence_without_minting_time() -> None:
    store, cadence, organization_projection = committed_production_fixture()
    event = publish_authorized_population_cadence(
        cadence=cadence,
        store=store,
        organization_projection=organization_projection,
        room_id="room:bakery",
        scene_id="scene:bakery",
        zone_id="zone:bakery",
        causation_id="event:mode:1",
        correlation_id="population:bakery:W1",
    )
    assert event.payload["population_cadence"] == cadence.model_dump(mode="json")
    assert event.payload["population_projections"]


def test_cadence_publisher_rejects_source_revision_not_in_authorized_vector() -> None:
    store, cadence, organization_projection = committed_production_fixture()
    stale = cadence.model_copy(update={"base_revision_vector": {"gameplay:organization:org:bakery": 0}})
    assert publish_authorized_population_cadence(
        cadence=stale,
        store=store,
        organization_projection=organization_projection,
        room_id="room:bakery",
        scene_id="scene:bakery",
        zone_id="zone:bakery",
        causation_id="event:mode:1",
        correlation_id="population:bakery:W1",
    ) is None
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest -q backend/tests/test_siming_population_authorized_cadence_publication.py`

Expected: FAIL because the publisher does not exist.

- [ ] **Step 3: Extract the publisher from the game-start function**

```python
def publish_authorized_population_cadence(
    *,
    cadence: PopulationCadenceInput,
    store: GameplayEventStore,
    organization_projection: Mapping[str, object],
    room_id: str,
    scene_id: str,
    zone_id: str,
    causation_id: str,
    correlation_id: str,
    legacy_projections: tuple[PopulationProjection, ...] = (),
) -> AuthorityEvent | None:
    """Publish one already-authorized cadence; it never creates cadence time."""
```

Rules:

```text
- Validate cadence source ref/revision against the store before publication.
- Assemble committed domain projections through Task 1.
- Accept legacy projections only if their refs are unique, scope-admitted, and their vectors are contained in cadence.base_revision_vector.
- Publish through the existing authority_event_bus only after the entire payload validates.
- Return None with no bus event when the cadence or any projection pin is invalid.
- Keep _publish_population_cadence_at_game_start() as one caller that constructs its already-authorized game-start cadence and legacy supply projection, then delegates here.
```

- [ ] **Step 4: Verify no scheduler expansion**

```python
def test_game_start_remains_one_explicit_authorized_cadence() -> None:
    import app.main as main
    main.reset_runtime_state()
    events = main.authority_event_bus.list_events(event_type="population_cadence_event")
    assert len(events) == 1
    assert events[0].payload["population_cadence"]["cadence_id"].endswith("game-start:v3")
```

- [ ] **Step 5: Verify and commit**

Run:

```powershell
python -m pytest -q backend/tests/test_siming_population_authorized_cadence_publication.py backend/tests/test_siming_population_production_boundaries.py backend/tests/test_siming_population_domain_owner_runtime.py
git diff --check
```

Commit: `git commit -m "发布授权领域群体节拍"`

### Task 3: Production Evidence to Real Siming Cycle

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/siming_runtime.py`
- Modify: `backend/app/services/siming_population_capability.py`
- Modify: `backend/app/population_continuity/domain_projection_sources.py`
- Modify: `backend/app/gameplay/organization_government_runtime.py`
- Modify: `backend/tests/test_siming_population_authorized_cadence_publication.py`
- Modify: `backend/tests/test_siming_population_production_replanning.py`
- Modify: `scripts/verification/verify_siming_population_domain_owner_adaptation.py`

**Interfaces:**
- Consumes: committed `gameplay.construction_production.work_completion_evidence_recorded`, Organization schedule projection, and an explicit authorized cadence from Task 2.
- Produces: `organization_production_work_contribution` selection, one Organization receipt, Character Core seed, and a receipt-pinned next batch input.

- [ ] **Step 1: Write failing end-to-end test**

```python
def test_committed_work_evidence_runs_through_real_authorized_cadence() -> None:
    fixture = production_runtime_fixture()
    event = fixture.publish_authorized_cadence_after_completed_work()
    cycle = fixture.population_cycle_audit_for(event.event_id)
    assert cycle["status"] == "accepted"
    assert cycle["owner_event_family"] == "gameplay.organization.production_work_contribution_accepted"
    assert cycle["owner_receipt_count"] == 1
    assert cycle["continuity_receipt_count"] == 1


def test_production_owner_rejection_publishes_no_follow_up_cadence() -> None:
    fixture = production_runtime_fixture(stale_organization_revision=True)
    assert fixture.publish_authorized_cadence_after_completed_work() is None
    assert fixture.population_cadence_event_count() == 0
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest -q backend/tests/test_siming_population_authorized_cadence_publication.py -k real_authorized_cadence`

Expected: FAIL until Task 2 output is consumed by the real Siming event pipeline.

- [ ] **Step 3: Wire the real fixture through the existing bus/pipeline**

Do not invoke `PopulationSimulationCapability` directly in this test. Commit the Production evidence through the existing Construction Owner, publish Task 2's authorized cadence through the existing `authority_event_bus`, and read the `SimingAuditWriter` record. The event must reach `SimingRuntime.tick(...)` through `SimingEventPipeline`.

- [ ] **Step 4: Add receipt-driven next-batch assertion**

```python
def test_production_receipt_is_the_only_next_batch_source() -> None:
    fixture = production_runtime_fixture()
    first = fixture.publish_authorized_cadence_after_completed_work()
    receipt = fixture.owner_receipt_for(first.event_id)
    second = fixture.publish_receipt_authorized_cadence(receipt)
    assert fixture.read_set_for(second.event_id).cadence.base_revision_vector == receipt.revision_vector
    assert fixture.owner_write_count() == 1
```

- [ ] **Step 5: Verify and commit**

Run:

```powershell
python -m pytest -q backend/tests/test_siming_population_authorized_cadence_publication.py backend/tests/test_siming_population_production_replanning.py backend/tests/test_siming_led_population_seed_continuity.py
python scripts/verification/harness.py --profile siming-population-domain-owner-adaptation
git diff --check
```

Commit: `git commit -m "接通真实生产群体节拍纵切"`

### Task 4: Inventory and Public Social Source Activation

**Files:**
- Modify: `backend/tests/test_siming_population_authorized_cadence_publication.py`
- Modify: `backend/tests/test_siming_population_inventory_vertical.py`
- Modify: `backend/tests/test_siming_population_social_signal_vertical.py`
- Modify: `backend/app/population_continuity/batch.py` (required read-set pin seam: accept non-empty source-vector subsets)
- Modify: `backend/app/population_continuity/store_projection_assembler.py` (public sources retain public projection scope under organization cadences)
- Modify: `backend/app/services/siming_population_capability.py` (admit inventory Owner actor refs without character-core seeding)
- Modify: `scripts/verification/verify_siming_population_domain_owner_adaptation.py`

**Interfaces:**
- Consumes: committed `production_output_certified@1` and committed public `population_signal_recorded@1` facts.
- Produces: authorized cadence projections that select the already runtime-admitted Inventory/Social adapters.

- [ ] **Step 1: Write failing Inventory cadence test**

```python
def test_certified_output_enters_authorized_cadence_and_uses_inventory_owner() -> None:
    fixture = inventory_runtime_fixture_with_registered_output_container()
    event = fixture.publish_authorized_cadence_after_certification()
    cycle = fixture.population_cycle_audit_for(event.event_id)
    assert cycle["owner_event_family"] == "gameplay.inventory.production_output_received@1"
    assert fixture.inventory_owner_receipt_count() == 1
```

- [ ] **Step 2: Write failing Social cadence test**

```python
def test_public_population_signal_enters_authorized_cadence_and_uses_social_owner() -> None:
    fixture = social_runtime_fixture_with_public_signal()
    event = fixture.publish_authorized_cadence_after_public_signal()
    cycle = fixture.population_cycle_audit_for(event.event_id)
    assert cycle["owner_event_family"] == "gameplay.social.population_signal_recorded@1"
    assert fixture.social_owner_receipt_count() == 1


def test_private_social_signal_never_publishes_population_cadence_candidate() -> None:
    fixture = social_runtime_fixture_with_private_signal()
    assert fixture.publish_authorized_cadence_after_public_signal() is None
```

- [ ] **Step 3: Verify failures**

Run:

```powershell
python -m pytest -q backend/tests/test_siming_population_authorized_cadence_publication.py -k "inventory or social"
```

Expected: FAIL until fixtures establish the real certified-output container and public signal source facts.

- [ ] **Step 4: Implement only source preconditions in the fixture/bootstrap**

```text
- Create the Inventory output container through the existing Inventory Owner before a certified output is consumed.
- Produce the Social signal through the existing public Social Owner and exact active package binding.
- Do not fabricate holder, container, quantity, participant, stream, event family, or receipt in the population projection.
```

- [ ] **Step 5: Verify and commit**

Run:

```powershell
python -m pytest -q backend/tests/test_siming_population_authorized_cadence_publication.py backend/tests/test_siming_population_inventory_vertical.py backend/tests/test_siming_population_social_signal_vertical.py
python scripts/verification/harness.py --profile siming-population-domain-owner-adaptation
git diff --check
```

Commit: `git commit -m "接通库存与公开社会群体节拍"`

### Task 5: Tax Pressure and Evidence Harness

**Files:**
- Modify: `backend/tests/test_siming_population_authorized_cadence_publication.py`
- Modify: `backend/app/gameplay/economy_runtime.py` (read-only redacted Tax pressure projection helper)
- Modify: `backend/app/population_continuity/store_projection_assembler.py` (consume only explicit redacted Tax metadata)
- Modify: `backend/app/main.py` (strip Tax metadata before cadence event publication)
- Modify: `backend/app/services/siming_runtime.py` (always record read-set and decision digests in cycle audit)
- Modify: `scripts/verification/verify_siming_population_domain_owner_adaptation.py`
- Modify: `docs/harness.md`
- Modify: `docs/8月分析/司命与群体世界补充设计/03-群体模拟与角色分级连续性.md`
- Modify: `docs/8月分析/司命与群体世界补充设计/13-群体模拟生产纵切与推进闭环设计.md`

**Interfaces:**
- Consumes: a committed Economy Tax obligation projection with authority-only fields redacted before population assembly.
- Produces: a `tax_pressure` presentation/activation/defer candidate and no Owner intent.

- [ ] **Step 1: Write failing Tax cadence test**

```python
def test_tax_due_enters_authorized_cadence_as_report_only_pressure() -> None:
    fixture = tax_runtime_fixture()
    event = fixture.publish_authorized_cadence_after_tax_due()
    read_set = fixture.read_set_for(event.event_id)
    tax = next(item for item in read_set.projections if item.payload["candidate_kind"] == "tax_pressure")
    assert "amount_minor" not in tax.payload
    assert fixture.owner_write_count() == 0
```

- [ ] **Step 2: Verify failure**

Run: `python -m pytest -q backend/tests/test_siming_population_authorized_cadence_publication.py -k tax`

Expected: FAIL until the assembler receives a valid committed Tax obligation source.

- [ ] **Step 3: Add Tax trace invariants to the Harness**

The verifier must assert one audit chain for each admitted source:

```text
committed source event
→ authorized cadence event
→ read-set digest
→ Siming decision digest
→ Owner receipt or report-only disposition
→ Character Core receipt when and only when an objective Owner receipt exists
```

It must additionally assert Tax has no `owner_bound_intent`, no account reference, no amount, and no payment event.

- [ ] **Step 4: Run the complete verification set**

```powershell
python -m pytest -q
python scripts/verification/harness.py --profile phase3a-profile-activation
python scripts/verification/harness.py --profile phase3b-world-mode-continuity
python scripts/verification/harness.py --profile phase3c-batch-intent-merge
python scripts/verification/harness.py --profile phase3d-bakery-district-population
python scripts/verification/harness.py --profile phase3-population-continuity
python scripts/verification/harness.py --profile siming-led-population-seed-continuity
python scripts/verification/harness.py --profile siming-governed-three-actor-cohort-continuity-v1
python scripts/verification/harness.py --profile siming-generalized-population-decision
python scripts/verification/harness.py --profile siming-population-domain-owner-adaptation
python scripts/verification/check_docs.py
git diff --check
```

- [ ] **Step 5: Commit**

Commit: `git commit -m "验证真实领域群体投影节拍闭环"`

## Review Checkpoints

1. After Task 1, inspect that no assembler calls `append_batch`, an Owner, Character Core, or a package activation method.
2. After Task 2, inspect that cadence input is always caller/Owner supplied; the publisher validates but never creates a time window.
3. After Task 3, require one real Production source event through `authority_event_bus -> SimingEventPipeline -> SimingRuntime.tick`.
4. After Task 4, require actual Inventory container and public Social signal preconditions, not test-only payload fields.
5. After Task 5, require complete source-to-audit trace and no Tax write path.

## Explicit Non-Goals

- No autonomous cadence scheduler, wall-clock timer, retry loop, or catch-up worker.
- No generic event-store scanner that auto-enables arbitrary Owner contracts.
- No direct population write to inventory, social facts, tax obligations, accounts, or Character Core.
- No private Social, private memory, authority-only Tax evidence, or payer account data in a global read set.
- No Stormnight action-window cadence input.
- No claim of a general population/NPC/social truth Owner or full civilization simulation.
