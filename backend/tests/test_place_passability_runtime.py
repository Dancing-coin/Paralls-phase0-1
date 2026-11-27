from decimal import Decimal

from app.gameplay.event_schema_registry import create_stormnight_event_schema_registry
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.facility_integrity_runtime import FacilityIntegrityAuthority
from app.gameplay.pool_runtime import PoolDefinition, PoolThreshold
from app.gameplay.place_passability_runtime import (
    PlacePassabilityAssessment,
    PlacePassabilityAuthority,
)
from app.gameplay.settlement_plan import build_atomic_event_batch


GATE = "gate-03"
INTEGRITY = "fact:facility:gate-03:integrity"
PLACE_STREAM = "place:gate-03:passability"


def _store():
    return GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())


def _integrity_authority(store):
    return FacilityIntegrityAuthority(store=store, definitions={
        GATE: PoolDefinition(
            fact_type=INTEGRITY,
            lower=Decimal("0"),
            upper=Decimal("100"),
            initial=Decimal("100"),
            thresholds=(PoolThreshold("breach", Decimal("40"), Decimal("45")),),
        ),
    })


def _breach(store):
    authority = _integrity_authority(store)
    assert authority.initialize(
        gate_ref=GATE, command_id="gate:init", idempotency_key="gate:init",
        causation_id="cause:init", correlation_id="corr:gate",
    ).committed
    result = authority.apply_delta(
        gate_ref=GATE, delta=Decimal("-61"), reason_code="damage",
        command_id="gate:damage", idempotency_key="gate:damage", expected_revision=1,
        causation_id="impact:gate", correlation_id="corr:gate",
    )
    return store.get_event(result.committed_event_ids[-1])


def _presence_evidence(store):
    result = store.append_batch(build_atomic_event_batch(
        command_id="presence:gate-evidence",
        principal_ref="population.presence_authority",
        stream_id="presence:gate-03:clearance",
        expected_revision=0,
        event_specs=(("population.presence.spawned", {
            "world_ref": "gate-03",
            "gate_ref": GATE,
            "clearance": "open",
        }),),
        idempotency_key="presence:gate-evidence",
        causation_id="presence:assessment-input",
        correlation_id="corr:gate",
    ))
    assert result.committed
    return store.get_event(result.committed_event_ids[0])


def _authority(store, assessment, *, evidence_event_principals=None):
    return PlacePassabilityAuthority(
        store=store,
        resolver=lambda _gate_ref, _breach: assessment,
        evidence_event_principals=evidence_event_principals,
    )


def test_breach_does_not_write_passability_until_presence_commits_its_decision():
    store = _store()
    breach = _breach(store)
    presence_input = _presence_evidence(store)
    assert store.read_stream(PLACE_STREAM) == []
    decision = PlacePassabilityAssessment(
        state="passable",
        assessment_ref="resolver:gate-clearance@1",
        read_stream_revisions={
            INTEGRITY: store.get_stream_head(INTEGRITY),
            presence_input.stream_id: presence_input.stream_revision,
        },
        source_event_ids=(breach.event_id, presence_input.event_id),
    )
    authority = PlacePassabilityAuthority(
        store=store,
        resolver=lambda _gate_ref, _breach: decision,
        evidence_event_principals={
            "population.presence.spawned": "population.presence_authority",
        },
    )

    result = authority.commit_assessment(
        gate_ref=GATE,
        breach_event_id=breach.event_id,
        expected_revision=0,
    )

    assert result.committed
    assert authority.state(GATE) == "passable"
    event = store.read_stream(PLACE_STREAM)[0]
    assert event.visibility_policy == "project"
    assert store.transaction_owns_event(
        transaction_id=event.transaction_id,
        event_id=event.event_id,
        principal_ref="population.presence_authority",
    )
    assert event.payload["source_event_ids"] == [breach.event_id, presence_input.event_id]

    later_impact = _integrity_authority(store).apply_delta(
        gate_ref=GATE, delta=Decimal("-1"), reason_code="damage",
        command_id="gate:later-impact", idempotency_key="gate:later-impact", expected_revision=3,
        causation_id="impact:gate:later", correlation_id="corr:gate",
    )
    retry = authority.commit_assessment(
        gate_ref=GATE,
        breach_event_id=breach.event_id,
        expected_revision=0,
    )
    assert later_impact.committed
    assert retry.committed and retry.idempotency_status == "duplicate_replayed"
    assert retry.committed_event_ids == result.committed_event_ids
    restored = GameplayEventStore.from_snapshot(store.export_snapshot())
    assert PlacePassabilityAuthority(store=restored).state(GATE) == "passable"


def test_legacy_presence_retry_rejects_incomplete_receipt_without_writing():
    store = _store()
    breach = _breach(store)
    presence_input = _presence_evidence(store)
    decision = PlacePassabilityAssessment(
        state="passable",
        assessment_ref="resolver:gate-clearance@1",
        read_stream_revisions={
            INTEGRITY: store.get_stream_head(INTEGRITY),
            presence_input.stream_id: presence_input.stream_revision,
        },
        source_event_ids=(breach.event_id, presence_input.event_id),
    )
    authority = PlacePassabilityAuthority(
        store=store,
        resolver=lambda _gate_ref, _breach: decision,
        evidence_event_principals={
            "population.presence.spawned": "population.presence_authority",
        },
    )
    first = authority.commit_assessment(
        gate_ref=GATE,
        breach_event_id=breach.event_id,
        expected_revision=0,
    )
    assert first.committed
    store._idempotency_results[("population.presence_authority", first.command_id)] = (
        first.model_copy(update={"committed_event_ids": []}, deep=True)
    )
    before = store.export_snapshot()

    replay = authority.commit_assessment(
        gate_ref=GATE,
        breach_event_id=breach.event_id,
        expected_revision=0,
    )

    assert not replay.committed
    assert replay.failure.error_code == "presence_replay_event_count_mismatch"
    assert store.export_snapshot() == before


def test_missing_presence_assessment_returns_unknown_without_writing():
    store = _store()
    breach = _breach(store)
    authority = _authority(store, None)
    before = store.export_snapshot()

    result = authority.commit_assessment(
        gate_ref=GATE,
        breach_event_id=breach.event_id,
        expected_revision=0,
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "place_assessment_unknown"
    assert store.export_snapshot() == before


def test_breach_without_independent_presence_evidence_returns_unknown():
    store = _store()
    breach = _breach(store)
    decision = PlacePassabilityAssessment(
        state="passable",
        assessment_ref="resolver:gate-clearance@1",
        read_stream_revisions={INTEGRITY: store.get_stream_head(INTEGRITY)},
        source_event_ids=(breach.event_id,),
    )
    authority = _authority(store, decision)
    before = store.export_snapshot()

    result = authority.commit_assessment(
        gate_ref=GATE,
        breach_event_id=breach.event_id,
        expected_revision=0,
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "place_assessment_unknown"
    assert store.export_snapshot() == before


def test_presence_assessment_rejects_stale_integrity_revision_without_writing():
    store = _store()
    breach = _breach(store)
    presence_input = _presence_evidence(store)
    decision = PlacePassabilityAssessment(
        state="blocked",
        assessment_ref="resolver:gate-clearance@1",
        read_stream_revisions={
            INTEGRITY: breach.stream_revision,
            presence_input.stream_id: presence_input.stream_revision,
        },
        source_event_ids=(breach.event_id, presence_input.event_id),
    )
    authority = _authority(
        store,
        decision,
        evidence_event_principals={
            "population.presence.spawned": "population.presence_authority",
        },
    )
    _integrity_authority(store).apply_delta(
        gate_ref=GATE, delta=Decimal("-1"), reason_code="damage",
        command_id="gate:later-impact", idempotency_key="gate:later-impact", expected_revision=3,
        causation_id="impact:gate:later", correlation_id="corr:gate",
    )
    before = store.export_snapshot()

    result = authority.commit_assessment(
        gate_ref=GATE,
        breach_event_id=breach.event_id,
        expected_revision=0,
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "place_assessment_source_stale"
    assert store.export_snapshot() == before


def test_place_passability_event_is_registered_in_factory_and_graph_registry():
    from app.gameplay.event_schema_registry import gameplay_schema_event_types
    from app.models.fact_type import FACT_TYPE_REGISTRY

    registry = create_stormnight_event_schema_registry()
    event_type = "gameplay.presence.place_passability_changed"
    assert registry.get(event_type, 1) is not None
    assert event_type in set(gameplay_schema_event_types())
    assert FACT_TYPE_REGISTRY.domain_for(FACT_TYPE_REGISTRY.from_event_type(event_type)) == "presence"


def test_place_passability_rejects_unowned_breach_source_without_writing():
    store = _store()
    source = store.append_batch(build_atomic_event_batch(
        command_id="untrusted:breach",
        principal_ref="actor:untrusted",
        stream_id=INTEGRITY,
        expected_revision=0,
        event_specs=(("gameplay.pool.threshold_crossed", {
            "fact_type": INTEGRITY,
            "threshold_ref": "breach",
            "direction": "enter",
            "value": "39",
        }),),
        idempotency_key="untrusted:breach",
        causation_id="untrusted:impact",
        correlation_id="corr:gate",
    ))
    source_event = store.get_event(source.committed_event_ids[0])
    decision = PlacePassabilityAssessment(
        state="passable",
        assessment_ref="resolver:gate-clearance@1",
        read_stream_revisions={INTEGRITY: 1},
        source_event_ids=(source_event.event_id,),
    )
    authority = _authority(store, decision)
    before = store.export_snapshot()

    result = authority.commit_assessment(
        gate_ref=GATE,
        breach_event_id=source_event.event_id,
        expected_revision=0,
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "place_breach_source_invalid"
    assert store.export_snapshot() == before
