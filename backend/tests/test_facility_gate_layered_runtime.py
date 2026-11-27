import hashlib
import hmac
import json
from decimal import Decimal

import pytest
from starlette.testclient import TestClient

from app import main
from app.gameplay.event_schema_registry import create_stormnight_event_schema_registry
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.facility_integrity_runtime import FacilityIntegrityAuthority
from app.gameplay.impact_gate_obligation import rebuild_impact_gate_obligations
from app.gameplay.place_event_schema import PLACE_ASSESSMENT_CONFIRMED_EVENT
from app.gameplay.facility_gate_layered_runtime import (
    FACILITY_PRINCIPAL,
    FacilityGateLayeredAuthority,
)
from app.gameplay.m6_5_siege_runtime import (
    DEFAULT_MORALE_DEFINITIONS,
    M6_5_RESOLVER_HANDLERS,
    build_m6_5_siege_runtime,
)
from app.gameplay.l5_pipeline import Pipeline
from app.gameplay.pool_runtime import PoolDefinition, PoolThreshold
from app.gameplay.siege_physical_input_runtime import (
    GateImpactReceiptV2,
    PresenceAssessmentReceiptV2,
    SiegePhysicalInputAuthority,
)


AUTHORITY = "ue:stormnight-physics"
SECRET = "fixture-key"
GATE = "gate-03"
LAYERS = ("durability", "latch-durability", "integrity")


def _pool(layer: str, initial: str) -> PoolDefinition:
    thresholds = (
        (PoolThreshold("breach", Decimal("40"), Decimal("45")),)
        if layer == "integrity"
        else ()
    )
    return PoolDefinition(
        fact_type=FacilityGateLayeredAuthority.fact_type_for(GATE, layer),
        lower=Decimal("0"),
        upper=Decimal("100"),
        initial=Decimal(initial),
        thresholds=thresholds,
    )


def _receipt(
    receipt_id: str,
    revisions: dict[str, int] | None = None,
    *,
    impact_kind_ref: str = "impact_kind:battering-ram@1",
):
    unsigned = GateImpactReceiptV2(
        authority_ref=AUTHORITY,
        receipt_id=receipt_id,
        gate_ref=GATE,
        impact_kind_ref=impact_kind_ref,
        physics_tick=501,
        target_incarnation_ref="gate-03:incarnation-2",
        contact_source_digest="sha256:" + "a" * 64,
        expected_layer_revisions=revisions or {
            FacilityGateLayeredAuthority.fact_type_for(GATE, layer): 1
            for layer in LAYERS
        },
        signature="0" * 64,
    )
    return unsigned.model_copy(update={
        "signature": hmac.new(
            SECRET.encode(), unsigned.canonical_bytes(), hashlib.sha256
        ).hexdigest(),
    })


def _authorities(
    initials: tuple[str, str, str] = ("100", "100", "100"),
    *,
    magnitude: str = "20",
):
    store = GameplayEventStore(
        event_schema_registry=create_stormnight_event_schema_registry()
    )
    inputs = SiegePhysicalInputAuthority(
        store=store,
        authority_secrets={AUTHORITY: SECRET},
    )
    definitions = {
        FacilityGateLayeredAuthority.fact_type_for(GATE, layer): _pool(layer, initial)
        for layer, initial in zip(LAYERS, initials, strict=True)
    }
    authority = FacilityGateLayeredAuthority(
        store=store,
        definitions={GATE: definitions},
        impact_magnitudes={
            GATE: {"impact_kind:battering-ram@1": Decimal(magnitude)}
        },
    )
    authority.initialize(
        gate_ref=GATE,
        command_prefix="facility:init:gate-03",
        causation_id="siege:setup",
        correlation_id="siege:east",
    )
    return store, inputs, authority


def test_layered_impact_applies_to_first_available_durability_layer():
    store, inputs, authority = _authorities(("100", "75", "100"))
    receipt = _receipt("impact:layered-1")
    assert inputs.record_gate_impact_v2(receipt).committed

    result = authority.apply_signed_impact(
        input_authority=inputs,
        authority_ref=AUTHORITY,
        receipt_id=receipt.receipt_id,
    )

    assert result.committed
    assert store.read_stream("fact:facility:gate-03:durability")[-1].payload["next"] == "80"
    assert len(store.read_stream("fact:facility:gate-03:latch-durability")) == 1
    assert len(store.read_stream("fact:facility:gate-03:integrity")) == 1
    assert store.read_stream("fact:facility:gate-03:latch") == []
    obligation, = rebuild_impact_gate_obligations(store)
    assert obligation.status == "open"
    assert obligation.pipeline_ref == "impact_gate"
    assert obligation.completed_steps == ("impact", "facility")
    assert obligation.pending_steps == ("presence_input", "passability")
    assert obligation.pending_reason == "unknown"
    assert obligation.owner_refs == ("Presence",)
    assert obligation.recovery_action == "reconcile"
    assert obligation.deadline_world_tick is None
    assert obligation.step_receipts[0] == ("impact", (
        store.read_events(event_type="gameplay.facility.gate_impact_input_received@2")[0].event_id,
    ))
    assert obligation.step_receipts[1] == ("facility", tuple(
        event.event_id for event in store.read_events()
        if event.causation_id == obligation.step_receipts[0][1][0]
        and event.event_type == "gameplay.pool.adjusted"
    ))


def test_impact_gate_rebuild_pins_the_shared_input_revision_vector(tmp_path):
    database_path = tmp_path / "impact-gate-input-vector.db"
    store = DurableGameplayEventStore(
        database_path,
        event_schema_registry=create_stormnight_event_schema_registry(),
    )
    _, _, facility = _authorities_for_store(store)
    runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions=DEFAULT_MORALE_DEFINITIONS,
        physical_authority_secrets={AUTHORITY: SECRET},
        layered_facility=facility,
    )

    evidence, impact_result, _ = runtime.record_gate_impact_v2(
        _receipt("impact:shared-input-vector")
    )
    assert impact_result.committed
    impact = store.get_event(evidence.committed_event_ids[0])
    obligation, = runtime.impact_gate_obligations()

    assert dict(obligation.input_revision_vector) == {
        **{
            FacilityGateLayeredAuthority.fact_type_for(GATE, layer): 1
            for layer in LAYERS
        },
        runtime.presence.stream_id(GATE): 0,
    }

    assessment = PresenceAssessmentReceiptV2.model_validate(
        _presence_input(store, impact, "presence:shared-input-vector")
    )
    _, assessment_result = runtime.record_presence_assessment(assessment)
    assert assessment_result.committed, assessment_result.failure
    store.close()
    reopened = DurableGameplayEventStore(
        database_path,
        event_schema_registry=create_stormnight_event_schema_registry(),
    )
    try:
        rebuilt, = rebuild_impact_gate_obligations(reopened)
        assert rebuilt.input_revision_vector == obligation.input_revision_vector
    finally:
        reopened.close()


def test_impact_pipeline_binds_the_durable_input_snapshot(monkeypatch):
    store, _, facility = _authorities()
    runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions=DEFAULT_MORALE_DEFINITIONS,
        physical_authority_secrets={AUTHORITY: SECRET},
        layered_facility=facility,
    )
    observed = []
    original_bind_inputs = Pipeline.bind_inputs

    def observe_binding(pipeline, *, scopes, revision_vectors):
        observed.append((
            bool(store.read_events(event_type="gameplay.facility.gate_impact_input_received@2")),
            dict(revision_vectors[0]),
        ))
        return original_bind_inputs(
            pipeline, scopes=scopes, revision_vectors=revision_vectors,
        )

    monkeypatch.setattr(Pipeline, "bind_inputs", observe_binding)
    evidence, impact_result, _ = runtime.record_gate_impact_v2(
        _receipt("impact:pipeline-input-snapshot")
    )

    assert evidence.committed and impact_result.committed
    obligation, = runtime.impact_gate_obligations()
    revision_vector = dict(obligation.input_revision_vector)
    impact = store.get_event(evidence.committed_event_ids[0])
    assessment = PresenceAssessmentReceiptV2.model_validate(
        _presence_input(store, impact, "presence:pipeline-input-snapshot")
    )
    _, place_result = runtime.record_presence_assessment(assessment)

    assert place_result.committed
    assert observed == [(True, revision_vector), (True, revision_vector)]


def test_presence_owner_rejects_pipeline_plan_that_disagrees_with_signed_input(monkeypatch):
    def conflicting_presence_plan(inputs, _params):
        return {
            "state": "blocked",
            "source_event_ids": inputs["source_event_ids"],
        }

    monkeypatch.setitem(
        M6_5_RESOLVER_HANDLERS,
        "presence_assessment@1",
        conflicting_presence_plan,
    )
    store, _, facility = _authorities(magnitude="270")
    runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions=DEFAULT_MORALE_DEFINITIONS,
        physical_authority_secrets={AUTHORITY: SECRET},
        layered_facility=facility,
    )
    evidence, impact_result, _ = runtime.record_gate_impact_v2(
        _receipt("impact:pipeline-presence-plan")
    )
    assert evidence.committed and impact_result.committed
    impact = store.get_event(evidence.committed_event_ids[0])
    assessment = PresenceAssessmentReceiptV2.model_validate(
        _presence_input(store, impact, "presence:resolver-disagreement")
    )
    place_before = store.read_stream("place:gate-03:passability")

    signed_input, place_result = runtime.record_presence_assessment(assessment)

    assert signed_input.committed
    assert place_result.failure.error_code == "place_assessment_resolver_output_invalid"
    assert store.read_stream("place:gate-03:passability") == place_before


def test_facility_owner_rejects_pipeline_plan_without_writing_pool_facts():
    store, inputs, authority = _authorities()
    receipt = _receipt("impact:resolver-plan-disagreement")
    assert inputs.record_gate_impact_v2(receipt).committed
    before = {
        stream: store.read_stream(stream)
        for stream in (
            *(FacilityGateLayeredAuthority.fact_type_for(GATE, layer) for layer in LAYERS),
            FacilityGateLayeredAuthority.latch_fact_type_for(GATE),
        )
    }

    def conflicting_plan(*, fact_type, **_inputs):
        return {
            "fact_type": fact_type,
            "applied": "19",
            "next_value": "81",
            "remaining_damage": "1",
        }

    result = authority.apply_signed_impact(
        input_authority=inputs,
        authority_ref=AUTHORITY,
        receipt_id=receipt.receipt_id,
        resolver=conflicting_plan,
    )

    assert result.failure.error_code == "facility_gate_resolver_output_invalid"
    assert {
        stream: store.read_stream(stream)
        for stream in before
    } == before


def test_layered_initialization_reuses_existing_integrity_stream():
    store = GameplayEventStore()
    definition = _pool("integrity", "100")
    legacy = FacilityIntegrityAuthority(
        store=store, definitions={GATE: definition}, impact_profiles={},
    )
    assert legacy.initialize(
        gate_ref=GATE,
        command_id="legacy:initialize",
        idempotency_key="legacy:initialize",
        causation_id="siege:setup",
        correlation_id="siege:east",
    ).committed
    before = store.read_stream(definition.fact_type)

    _authorities_for_store(store)

    assert store.read_stream(definition.fact_type) == before
    for layer in ("durability", "latch-durability"):
        assert len(store.read_stream(FacilityGateLayeredAuthority.fact_type_for(GATE, layer))) == 1


def test_layered_impact_carries_residual_damage_and_updates_latch_machine():
    store, inputs, authority = _authorities(("10", "5", "100"))
    receipt = _receipt("impact:layered-residual")
    assert inputs.record_gate_impact_v2(receipt).committed

    result = authority.apply_signed_impact(
        input_authority=inputs,
        authority_ref=AUTHORITY,
        receipt_id=receipt.receipt_id,
    )

    assert result.committed
    assert store.read_stream("fact:facility:gate-03:durability")[-1].payload["next"] == "0"
    assert store.read_stream("fact:facility:gate-03:latch-durability")[-1].payload["next"] == "0"
    assert store.read_stream("fact:facility:gate-03:integrity")[-1].payload["next"] == "95"
    latch_events = store.read_stream("fact:facility:gate-03:latch")
    assert latch_events[-1].payload["to"] == "broken"
    for event in store.read_stream("fact:facility:gate-03:latch"):
        assert store.transaction_owns_event(
            transaction_id=event.transaction_id,
            event_id=event.event_id,
            principal_ref=FACILITY_PRINCIPAL,
        )


def test_layered_impact_exact_retry_replays_after_pool_revisions_advance():
    store, inputs, authority = _authorities()
    receipt = _receipt("impact:layered-retry")
    assert inputs.record_gate_impact_v2(receipt).committed

    first = authority.apply_signed_impact(
        input_authority=inputs,
        authority_ref=AUTHORITY,
        receipt_id=receipt.receipt_id,
    )
    retry = authority.apply_signed_impact(
        input_authority=inputs,
        authority_ref=AUTHORITY,
        receipt_id=receipt.receipt_id,
    )

    assert first.committed
    assert retry.idempotency_status == "duplicate_replayed"
    assert store.read_stream("fact:facility:gate-03:durability")[-1].payload["next"] == "80"


def test_layered_impact_rejects_incomplete_replay_receipt_without_writing():
    store, inputs, authority = _authorities(magnitude="270")
    receipt = _receipt("impact:layered-corrupt-replay")
    assert inputs.record_gate_impact_v2(receipt).committed
    first = authority.apply_signed_impact(
        input_authority=inputs,
        authority_ref=AUTHORITY,
        receipt_id=receipt.receipt_id,
    )
    assert first.committed and len(first.committed_event_ids) > 1
    key = (FACILITY_PRINCIPAL, first.command_id)
    store._idempotency_results[key] = first.model_copy(
        update={"committed_event_ids": first.committed_event_ids[:-1]}, deep=True
    )
    before = store.export_snapshot()

    replay = authority.apply_signed_impact(
        input_authority=inputs,
        authority_ref=AUTHORITY,
        receipt_id=receipt.receipt_id,
    )

    assert not replay.committed
    assert replay.failure.error_code == "facility_replay_event_count_mismatch"
    assert store.export_snapshot() == before


def test_stale_layer_vector_rejects_without_writing_facility_facts():
    store, inputs, authority = _authorities()
    receipt = _receipt(
        "impact:layered-stale",
        revisions={
            FacilityGateLayeredAuthority.fact_type_for(GATE, layer): 0
            for layer in LAYERS
        },
    )
    assert inputs.record_gate_impact_v2(receipt).committed

    result = authority.apply_signed_impact(
        input_authority=inputs,
        authority_ref=AUTHORITY,
        receipt_id=receipt.receipt_id,
    )

    assert not result.committed
    assert result.failure.error_code == "facility_impact_revision_conflict"
    assert all(
        len(store.read_stream(FacilityGateLayeredAuthority.fact_type_for(GATE, layer))) == 1
        for layer in LAYERS
    )


def test_second_impact_with_stale_vector_does_not_apply_again():
    store, inputs, authority = _authorities()
    first_receipt = _receipt("impact:layered-concurrent-1")
    second_receipt = _receipt("impact:layered-concurrent-2")
    assert inputs.record_gate_impact_v2(first_receipt).committed
    assert inputs.record_gate_impact_v2(second_receipt).committed

    first = authority.apply_signed_impact(
        input_authority=inputs,
        authority_ref=AUTHORITY,
        receipt_id=first_receipt.receipt_id,
    )
    second = authority.apply_signed_impact(
        input_authority=inputs,
        authority_ref=AUTHORITY,
        receipt_id=second_receipt.receipt_id,
    )

    assert first.committed
    assert second.failure.error_code == "facility_impact_revision_conflict"
    assert len(store.read_stream("fact:facility:gate-03:durability")) == 2
    assert store.read_stream("fact:facility:gate-03:durability")[-1].payload["next"] == "80"


def test_unknown_impact_kind_rejects_without_writing_facility_facts():
    store, inputs, authority = _authorities()
    receipt = _receipt(
        "impact:layered-unknown-kind",
        impact_kind_ref="impact_kind:unknown@1",
    )
    assert inputs.record_gate_impact_v2(receipt).committed

    result = authority.apply_signed_impact(
        input_authority=inputs,
        authority_ref=AUTHORITY,
        receipt_id=receipt.receipt_id,
    )

    assert result.failure.error_code == "facility_impact_profile_unknown"
    assert all(
        len(store.read_stream(FacilityGateLayeredAuthority.fact_type_for(GATE, layer))) == 1
        for layer in LAYERS
    )


def test_breach_does_not_write_place_facts():
    store, inputs, authority = _authorities(magnitude="270")
    receipt = _receipt("impact:layered-breach")
    assert inputs.record_gate_impact_v2(receipt).committed

    result = authority.apply_signed_impact(
        input_authority=inputs,
        authority_ref=AUTHORITY,
        receipt_id=receipt.receipt_id,
    )

    assert result.committed
    integrity_events = store.read_stream("fact:facility:gate-03:integrity")
    integrity_adjustment = next(
        event for event in integrity_events
        if event.event_type == "gameplay.pool.adjusted"
    )
    assert integrity_adjustment.payload["next"] == "30"
    assert any(
        event.event_type == "gameplay.pool.threshold_crossed"
        and event.payload["threshold_ref"] == "breach"
        and event.payload["direction"] == "enter"
        for event in integrity_events
    )
    assert store.read_stream("place:gate-03:passability") == []


def test_committed_gate_breach_dispatches_presence_and_keeps_unknown_unwritten():
    store, inputs, authority = _authorities(magnitude="270")
    runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions=DEFAULT_MORALE_DEFINITIONS,
        physical_authority_secrets={AUTHORITY: SECRET},
        layered_facility=authority,
    )
    receipt = _receipt("impact:layered-l5-breach")

    evidence, facility_result, dispatch_results = runtime.record_gate_impact_v2(receipt)

    assert evidence.committed
    assert facility_result.committed
    assert len(dispatch_results) == 1
    assert dispatch_results[0].failure.error_code == "place_assessment_unknown"
    assert store.read_stream("place:gate-03:passability") == []


def _presence_input(store, impact, receipt_id, **overrides):
    body = {
        "authority_ref": AUTHORITY,
        "receipt_id": receipt_id,
        "gate_ref": GATE,
        "impact_event_id": impact.event_id,
        "target_incarnation_ref": impact.payload["receipt"]["target_incarnation_ref"],
        "physics_tick": 502,
        "assessment_ref": "assessment:gate-clearance@1",
        "state": "passable",
        "expected_layer_revisions": {
            stream: store.get_stream_head(stream)
            for stream in impact.payload["receipt"]["expected_layer_revisions"]
        },
        "expected_place_revision": store.get_stream_head("place:gate-03:passability"),
        **overrides,
    }
    data = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return {**body, "signature": hmac.new(SECRET.encode(), data, hashlib.sha256).hexdigest()}


@pytest.mark.parametrize("magnitude", ["20", "270"])
def test_signed_impact_presence_gateway_settles_without_requiring_breach(monkeypatch, magnitude):
    store, _, facility = _authorities(magnitude=magnitude)
    runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions=DEFAULT_MORALE_DEFINITIONS,
        physical_authority_secrets={AUTHORITY: SECRET},
        layered_facility=facility,
    )
    evidence, result, _ = runtime.record_gate_impact_v2(_receipt("impact:presence-v2"))
    assert result.committed
    impact = store.get_event(evidence.committed_event_ids[0])
    assert runtime.impact_gate_obligations()[0].status == "open"
    assert runtime.presence.state(GATE) == "unknown"
    monkeypatch.setattr(main, "m6_5_siege_runtime", runtime)
    monkeypatch.setattr(main, "runtime_execution", None)
    client = TestClient(main.component_app)
    body = _presence_input(store, impact, "presence:v2")

    response = client.post("/api/v2/siege/presence-assessment-input", json=body)

    assert response.status_code == 200
    data = response.json()
    assert data["evidence"]["committed"] and data["place"]["committed"]
    assert runtime.presence.state(GATE) == "passable"
    place_event = store.get_event(data["place"]["committed_event_ids"][0])
    assert place_event.payload["read_stream_revisions"][impact.stream_id] == impact.stream_revision
    obligation, = runtime.impact_gate_obligations()
    assert obligation.status == "settled"
    assert obligation.pipeline_ref == "impact_gate"
    assert obligation.completed_steps == ("impact", "facility", "presence_input", "passability")
    assert obligation.pending_steps == ()
    assert obligation.pending_reason is None
    assert obligation.owner_refs == ()
    assert obligation.recovery_action is None
    assert obligation.deadline_world_tick is None
    assert dict(obligation.step_receipts)["presence_input"] == tuple(
        data["evidence"]["committed_event_ids"]
    )
    assert dict(obligation.step_receipts)["passability"] == tuple(
        data["place"]["committed_event_ids"]
    )
    facility_events = [
        store.get_event(event_id)
        for event_id in dict(obligation.step_receipts)["facility"]
    ]
    has_breach = any(
        event.event_type == "gameplay.pool.threshold_crossed"
        and event.payload.get("threshold_ref") == "breach"
        and event.payload.get("direction") == "enter"
        for event in facility_events
    )
    assert has_breach is (magnitude == "270")
    replay = client.post("/api/v2/siege/presence-assessment-input", json=body).json()
    assert replay["evidence"]["idempotency_status"] == "duplicate_replayed"
    assert replay["place"]["idempotency_status"] == "duplicate_replayed"


def test_presence_assessment_uses_signed_revisions_and_confirms_unchanged_state():
    store, _, facility = _authorities()
    runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions=DEFAULT_MORALE_DEFINITIONS,
        physical_authority_secrets={AUTHORITY: SECRET},
        layered_facility=facility,
    )
    place_stream = runtime.presence.stream_id(GATE)
    evidence, result, _ = runtime.record_gate_impact_v2(_receipt("impact:presence-first"))
    assert result.committed
    first = store.get_event(evidence.committed_event_ids[0])
    stale = _presence_input(store, first, "presence:stale")
    next_revisions = {
        stream: store.get_stream_head(stream)
        for stream in first.payload["receipt"]["expected_layer_revisions"]
    }
    evidence, result, _ = runtime.record_gate_impact_v2(_receipt("impact:presence-second", next_revisions))
    assert result.committed
    second = store.get_event(evidence.committed_event_ids[0])

    rejected, place = runtime.record_presence_assessment(PresenceAssessmentReceiptV2.model_validate(stale))
    assert rejected.failure.error_code == "siege_presence_evidence_invalid"
    assert place is None
    wrong_target = _presence_input(store, first, "presence:wrong-target", target_incarnation_ref="gate-03:other")
    rejected, place = runtime.record_presence_assessment(PresenceAssessmentReceiptV2.model_validate(wrong_target))
    assert rejected.failure.error_code == "siege_presence_evidence_invalid"
    assert place is None
    assert store.read_stream(place_stream) == []

    # A fresh evaluation can still settle an earlier outstanding impact.
    first_assessment = PresenceAssessmentReceiptV2.model_validate(_presence_input(store, first, "presence:first"))
    pending = PresenceAssessmentReceiptV2.model_validate(_presence_input(store, second, "presence:old-place"))
    assert runtime.record_presence_assessment(first_assessment)[1].committed
    evidence, rejected_place = runtime.record_presence_assessment(pending)
    assert evidence.committed
    assert rejected_place.failure.error_code == "place_assessment_source_stale"
    assert [entry.status for entry in runtime.impact_gate_obligations()] == ["settled", "open"]

    second_assessment = PresenceAssessmentReceiptV2.model_validate(_presence_input(store, second, "presence:fresh"))
    _, confirmation = runtime.record_presence_assessment(second_assessment)

    assert confirmation.committed
    event = store.get_event(confirmation.committed_event_ids[0])
    assert event.event_type == PLACE_ASSESSMENT_CONFIRMED_EVENT
    assert event.visibility_policy == "authority_only"
    assert store.get_stream_head(place_stream) == 1
    assert [entry.status for entry in runtime.impact_gate_obligations()] == ["settled", "settled"]


@pytest.mark.parametrize("unchanged", [False, True])
def test_presence_rejects_corrupt_replay_receipt_without_writing(unchanged):
    store, _, facility = _authorities()
    runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions=DEFAULT_MORALE_DEFINITIONS,
        physical_authority_secrets={AUTHORITY: SECRET},
        layered_facility=facility,
    )
    evidence, damage, _ = runtime.record_gate_impact_v2(_receipt("impact:presence-corrupt-1"))
    assert damage.committed
    impact = store.get_event(evidence.committed_event_ids[0])
    assessment = PresenceAssessmentReceiptV2.model_validate(
        _presence_input(store, impact, "presence:corrupt-1")
    )
    if unchanged:
        _, changed = runtime.record_presence_assessment(assessment)
        assert changed.committed
        revisions = {
            stream: store.get_stream_head(stream)
            for stream in impact.payload["receipt"]["expected_layer_revisions"]
        }
        evidence, damage, _ = runtime.record_gate_impact_v2(
            _receipt("impact:presence-corrupt-2", revisions)
        )
        assert damage.committed
        impact = store.get_event(evidence.committed_event_ids[0])
        assessment = PresenceAssessmentReceiptV2.model_validate(
            _presence_input(store, impact, "presence:corrupt-2")
        )
    _, first = runtime.record_presence_assessment(assessment)
    assert first.committed
    key = ("population.presence_authority", first.command_id)
    store._idempotency_results[key] = first.model_copy(
        update={"committed_event_ids": []}, deep=True
    )
    before = store.export_snapshot()

    _, replay = runtime.record_presence_assessment(assessment)

    assert not replay.committed
    assert replay.failure.error_code == "presence_replay_event_count_mismatch"
    assert store.export_snapshot() == before


def test_impact_presence_recovery_settles_durable_assessment_without_double_damage(tmp_path):
    database_path = tmp_path / "impact-presence.db"
    store = DurableGameplayEventStore(database_path, event_schema_registry=create_stormnight_event_schema_registry())
    _, inputs, facility = _authorities_for_store(store)
    runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions=DEFAULT_MORALE_DEFINITIONS,
        physical_authority_secrets={AUTHORITY: SECRET},
        layered_facility=facility,
    )
    evidence, damage, _ = runtime.record_gate_impact_v2(_receipt("impact:restart-assessment"))
    assert damage.committed
    impact = store.get_event(evidence.committed_event_ids[0])
    assessment = PresenceAssessmentReceiptV2.model_validate(_presence_input(store, impact, "presence:restart"))
    assert inputs.record_presence_assessment(assessment).committed
    assert runtime.impact_gate_obligations()[0].status == "open"
    store.close()

    reopened = DurableGameplayEventStore(database_path, event_schema_registry=create_stormnight_event_schema_registry())
    try:
        _, _, recovered_facility = _authorities_for_store(reopened)
        restored = build_m6_5_siege_runtime(
            store=reopened,
            morale_definitions=DEFAULT_MORALE_DEFINITIONS,
            physical_authority_secrets={AUTHORITY: SECRET},
            layered_facility=recovered_facility,
        )
        recovered = restored.recover_physical_input_obligations()
        assert recovered[0][1].idempotency_status == "duplicate_replayed"
        assert recovered[1][1].committed
        assert restored.impact_gate_obligations()[0].status == "settled"
        assert restored.presence.state(GATE) == "passable"
        assert all(
            result.idempotency_status == "duplicate_replayed"
            for _, result in restored.recover_physical_input_obligations()
        )
        assert reopened.get_stream_head(facility.fact_type_for(GATE, "durability")) == 2
        assert reopened.get_stream_head(restored.presence.stream_id(GATE)) == 1
    finally:
        reopened.close()


def test_layered_impact_recovers_after_durable_store_restart(tmp_path):
    database_path = tmp_path / "layered-siege.db"
    store = DurableGameplayEventStore(
        database_path,
        event_schema_registry=create_stormnight_event_schema_registry(),
    )
    store, inputs, authority = _authorities_for_store(store)
    receipt = _receipt("impact:layered-durable-recovery")
    assert inputs.record_gate_impact_v2(receipt).committed
    store.close()

    reopened_store = DurableGameplayEventStore(
        database_path,
        event_schema_registry=create_stormnight_event_schema_registry(),
    )
    _, _, recovered_authority = _authorities_for_store(reopened_store)
    runtime = build_m6_5_siege_runtime(
        store=reopened_store,
        morale_definitions=DEFAULT_MORALE_DEFINITIONS,
        physical_authority_secrets={AUTHORITY: SECRET},
        layered_facility=recovered_authority,
    )

    first_recovery = runtime.recover_physical_input_obligations()
    second_recovery = runtime.recover_physical_input_obligations()

    assert first_recovery[0][1].committed
    assert second_recovery[0][1].idempotency_status == "duplicate_replayed"
    assert reopened_store.read_stream("fact:facility:gate-03:durability")[-1].payload["next"] == "80"
    assert len(reopened_store.read_stream("fact:facility:gate-03:durability")) == 2
    assert len(reopened_store.read_stream("fact:facility:gate-03:latch-durability")) == 1
    assert len(reopened_store.read_stream("fact:facility:gate-03:integrity")) == 1
    reopened_store.close()


def _authorities_for_store(store):
    inputs = SiegePhysicalInputAuthority(
        store=store,
        authority_secrets={AUTHORITY: SECRET},
    )
    definitions = {
        FacilityGateLayeredAuthority.fact_type_for(GATE, layer): _pool(layer, "100")
        for layer in LAYERS
    }
    authority = FacilityGateLayeredAuthority(
        store=store,
        definitions={GATE: definitions},
        impact_magnitudes={GATE: {"impact_kind:battering-ram@1": Decimal("20")}},
    )
    assert all(result.committed for result in authority.initialize(
        gate_ref=GATE,
        command_prefix="facility:init:gate-03",
        causation_id="siege:setup",
        correlation_id="siege:east",
    ))
    return store, inputs, authority
