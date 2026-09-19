"""真实 Organization 事实形成 B1 来源；不让 fixture 直接声明角色层级或完成。"""
from __future__ import annotations

import pytest

from app.gameplay.econ1_economy_runtime import OperatingWindow
from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.population_continuity.organization_due_source import OrganizationWindowDueSource
from app.population_continuity.owner_adapters import OrganizationOperatingWindowDueOwnerExecutor
from app.population_continuity.roster import PopulationRoster
from app.population_continuity.decision_surface import PopulationDecisionPolicy
from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationReadSet
from app.services.siming_population_capability import PopulationSimulationCapability


NOW = "2026-09-17T00:00:00+00:00"


def schedule(authority, suffix, actor="worker", *, organization="org:one", window=None, scope="organization:summary", until=None):
    result = authority.record_schedule(command_id=f"schedule:{suffix}", organization_ref=organization,
        recipient_ref=f"character:{actor}", membership_ref=f"membership:{suffix}", assignment_ref=f"assignment:{suffix}",
        role="worker", shift_ref=f"shift:{suffix}", operating_window_ref=window or f"window:{suffix}",
        work_order_ref=f"work:{suffix}", effective_from="2026-09-01T00:00:00Z", effective_to=until,
        visibility_scope=scope)
    assert result.committed, result.failure
    return result


def window(authority, suffix, *, organization="org:one", scope="project", due=5):
    result = authority.open_operating_window(command_id=f"open:{suffix}", idempotency_key=f"open:{suffix}",
        causation_id=f"cause:{suffix}", correlation_id=f"corr:{suffix}", visibility_scope=scope,
        window=OperatingWindow(window_ref=f"window:{suffix}", organization_ref=organization,
            opens_at_tick=1, closes_at_tick=due, policy_revision="window:v1", source_revision="schedule:v1"))
    assert result.committed, result.failure
    result = authority.close_operating_window(command_id=f"close:{suffix}", idempotency_key=f"close:{suffix}",
        causation_id=f"cause:{suffix}", correlation_id=f"corr:{suffix}", organization_ref=organization,
        window_ref=f"window:{suffix}", expected_stream_revision=1, visibility_scope=scope)
    assert result.committed, result.failure
    return result


def source(store, actors=("worker",)):
    return OrganizationWindowDueSource(store=store, world_ref="world:test", roster=PopulationRoster(actor_ids=actors))


def read(projector, end=5, scope="organization:summary"):
    return projector.read(window_end=end, observed_at=NOW, scope=scope)


def cycle(store, projections, ordinal):
    vector = {key: revision for projection in projections for key, revision in projection.revision_vector.items()}
    cadence = PopulationCadenceInput(cadence_id=f"cadence:{ordinal}", world_ref="world:test", world_mode_ref="mode:test",
        world_mode_revision="mode:v1", cadence_source_ref="world:test", cadence_source_revision=ordinal,
        window_start=ordinal - 1, window_end=ordinal, base_checkpoint_ref="checkpoint:test",
        base_checkpoint_digest="sha256:test", base_revision_vector={"world:test": ordinal, **vector},
        policy_revision="policy:population:v1", selector_revision="selector:v1", ruleset_revision="rules:v1",
        deterministic_seed="seed:test", catch_up_limit=2, budget=100, report_scope="organization:summary")
    capability = PopulationSimulationCapability(owner_executors={
        "population:organization-window-due:v1": OrganizationOperatingWindowDueOwnerExecutor(authority=OrganizationAuthority(store=store))})
    return capability.run_decision_cycle(cadence, PopulationReadSet.from_inputs(cadence, projections),
        PopulationDecisionPolicy(policy_revision=cadence.policy_revision, default_fidelity_tier="B1", budget=100, max_candidates=100),
        capability.default_capabilities(cadence))


def test_real_schedule_join_is_due_scoped_detached_and_pinned(tmp_path, monkeypatch):
    store = DurableGameplayEventStore(tmp_path / "gameplay.sqlite3")
    owner = OrganizationAuthority(store=store)
    scheduled, closed = schedule(owner, "one"), window(owner, "one")
    projector = source(store)
    assert read(projector, end=4).projections == ()
    assert read(projector, scope="public").projections == ()
    before = store.get_last_global_sequence()
    rows = read(projector).projections
    assert store.get_last_global_sequence() == before
    assert len(rows) == 1
    row = rows[0]
    assert row.scope == "organization:summary"
    assert row.payload["actor_ref"] == "character:worker"
    assert row.payload["due_tick"] == 5
    assert row.payload["schedule_event_id"] == scheduled.committed_event_ids[-1]
    assert row.payload["closed_event_id"] == closed.committed_event_ids[0]
    assert row.revision_vector == {"gameplay:organization:org:one": 4, "gameplay:organization:window:window:one": 2}
    assert not {"membership_ref", "role", "opens_at_tick", "effective_from"}.intersection(row.payload)
    monkeypatch.setattr(store, "save_projection_checkpoint", lambda *args: pytest.fail("来源未变不重复写checkpoint"))
    row.payload["actor_ref"] = "character:forged"
    assert read(projector).projections[0].payload["actor_ref"] == "character:worker"
    assert read(projector, end=20).projections[0].ref == row.ref


@pytest.mark.parametrize("defect", ["no_schedule", "private_window", "private_schedule", "public_schedule", "wrong_org", "unknown_actor", "expired", "ambiguous"])
def test_unproven_or_unauthorized_binding_never_becomes_b1(tmp_path, defect):
    store = DurableGameplayEventStore(tmp_path / "gameplay.sqlite3")
    owner = OrganizationAuthority(store=store)
    if defect != "no_schedule":
        schedule(owner, "one", actor="unknown" if defect == "unknown_actor" else "worker",
            organization="org:other" if defect == "wrong_org" else "org:one",
            scope={"private_schedule": "authority_only", "public_schedule": "public"}.get(defect, "organization:summary"),
            until="2026-09-16T00:00:00Z" if defect == "expired" else None)
    if defect == "ambiguous":
        schedule(owner, "two", actor="second", window="window:one")
    window(owner, "one", scope="authority_only" if defect == "private_window" else "project")
    result = read(source(store, ("worker", "second")))
    assert result.projections == ()


@pytest.mark.parametrize('invalid', ['expired', 'wrong_org'])
def test_invalid_extra_binding_does_not_starve_valid_window_after_reopen(tmp_path, invalid):
    path = tmp_path / 'gameplay.sqlite3'
    store = DurableGameplayEventStore(path)
    owner = OrganizationAuthority(store=store)
    schedule(owner, 'one')
    window(owner, 'one')
    projector = source(store, ('worker', 'second'))
    original = read(projector).projections
    assert len(original) == 1
    schedule(owner, 'two', actor='second', window='window:one',
        organization='org:other' if invalid == 'wrong_org' else 'org:one',
        until='2026-09-16T00:00:00Z' if invalid == 'expired' else None)
    current = read(projector)
    assert [row.ref for row in current.projections] == [original[0].ref]
    assert current.projections[0].payload['actor_ref'] == 'character:worker'
    assert ('window:one', 'window_binding_ambiguous') not in current.diagnostics
    reopened = DurableGameplayEventStore(path)
    recovered = read(source(reopened, ('worker', 'second')))
    assert recovered.projections == current.projections


def test_budget_and_owner_commit_preserve_deferred_across_sqlite_restart(tmp_path, monkeypatch):
    path = tmp_path / "gameplay.sqlite3"
    store = DurableGameplayEventStore(path)
    owner = OrganizationAuthority(store=store)
    actors = tuple(f"worker_{i:02}" for i in range(40))
    for index, actor in enumerate(actors):
        organization = "org:one" if index % 2 else "org:two"
        schedule(owner, actor, actor=actor, organization=organization)
        window(owner, actor, organization=organization)
    projector = source(store, actors)
    original = read(projector).projections
    assert len(original) == 40
    first = cycle(store, original, 5)
    assert first.status == "accepted"
    assert len(first.owner_receipts) == 32
    assert all(receipt.committed for receipt in first.owner_receipts)
    assert len(first.decision.deferred_candidates) == 8
    deferred_refs = {ref for candidate in first.decision.deferred_candidates for ref in candidate.source_projection_refs}
    checkpoint = store.get_projection_checkpoint(projector.checkpoint_id)
    cursor = checkpoint.last_global_sequence
    # Owner已提交，派生checkpoint尚未更新时重开；只读原tail，不能重扫历史。
    reopened = DurableGameplayEventStore(path)
    original_read = reopened.read_events
    def bounded(**kwargs):
        assert kwargs.get("global_sequence_after", 0) >= cursor
        assert 1 <= kwargs["limit"] <= 256
        return original_read(**kwargs)
    monkeypatch.setattr(reopened, "read_events", bounded)
    pending = read(source(reopened, actors), end=6).projections
    assert {row.ref for row in pending} == deferred_refs
    assert all(row.payload["due_tick"] == 5 for row in pending)
    second = cycle(reopened, pending, 6)
    assert second.status == "accepted" and len(second.owner_receipts) == 8
    assert read(source(reopened, actors), end=7).projections == ()


def test_current_scope_replacement_removes_old_authorization(tmp_path):
    store = DurableGameplayEventStore(tmp_path / "gameplay.sqlite3")
    owner = OrganizationAuthority(store=store)
    schedule(owner, "one")
    window(owner, "one")
    projector = source(store)
    assert len(read(projector).projections) == 1
    assert owner.record_schedule(command_id="schedule:revoked", organization_ref="org:one", recipient_ref="character:worker",
        membership_ref="membership:one", assignment_ref="assignment:one", role="worker", shift_ref="shift:one",
        operating_window_ref="window:one", work_order_ref="work:one", effective_from="2026-09-01T00:00:00Z",
        effective_to=None, visibility_scope="authority_only").committed
    assert read(projector).projections == ()


def test_late_binding_reads_closed_head_without_retaining_unrelated_windows(tmp_path):
    store = DurableGameplayEventStore(tmp_path / "gameplay.sqlite3")
    owner = OrganizationAuthority(store=store)
    window(owner, "early")
    window(owner, "unrelated")
    projector = source(store)
    assert read(projector).projections == ()
    assert store.get_projection_checkpoint(projector.checkpoint_id).state["source_events"] == []
    schedule(owner, "early")
    assert len(read(projector).projections) == 1
    events = store.get_projection_checkpoint(projector.checkpoint_id).state["source_events"]
    assert len(events) == 2


def test_same_actor_separate_obligations_survive_later_org_schedule(tmp_path):
    store = DurableGameplayEventStore(tmp_path / "gameplay.sqlite3")
    owner = OrganizationAuthority(store=store)
    for suffix in ("one", "two"):
        schedule(owner, suffix)
        window(owner, suffix)
    projector = source(store)
    before = read(projector).projections
    assert len(before) == 2 and len({row.ref for row in before}) == 2
    schedule(owner, "future")
    after = read(projector).projections
    assert {row.ref for row in after} == {row.ref for row in before}
    assert all(row.revision_vector["gameplay:organization:org:one"] == 12 for row in after)


def test_checkpoint_cannot_forge_actor_by_rehashing_derived_state(tmp_path):
    from app.population_continuity.store_projection_assembler import _checkpoint_digest
    store = DurableGameplayEventStore(tmp_path / "gameplay.sqlite3")
    owner = OrganizationAuthority(store=store)
    schedule(owner, "one")
    window(owner, "one")
    projector = source(store, ("worker", "second"))
    read(projector)
    checkpoint = store.get_projection_checkpoint(projector.checkpoint_id)
    event = next(event for event in checkpoint.state["source_events"] if event["event_type"].endswith("work_order_recorded"))
    event["payload"]["recipient_ref"] = "character:second"
    checkpoint.projection_hash = _checkpoint_digest(checkpoint)
    store.save_projection_checkpoint(checkpoint)
    with pytest.raises(ValueError, match="source_event"):
        read(source(store, ("worker", "second")))
