import hashlib
import hmac
from decimal import Decimal

from app.gameplay.event_schema_registry import create_stormnight_event_schema_registry
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.facility_integrity_runtime import FacilityIntegrityAuthority
from app.gameplay.impact_gate_obligation import rebuild_impact_gate_obligations
from app.gameplay.facility_gate_layered_runtime import (
    FACILITY_PRINCIPAL,
    FacilityGateLayeredAuthority,
)
from app.gameplay.m6_5_siege_runtime import (
    DEFAULT_MORALE_DEFINITIONS,
    build_m6_5_siege_runtime,
)
from app.gameplay.pool_runtime import PoolDefinition, PoolThreshold
from app.gameplay.siege_physical_input_runtime import (
    GateImpactReceiptV2,
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
    assert obligation.step_receipts[0] == ("impact", (
        store.read_events(event_type="gameplay.facility.gate_impact_input_received@2")[0].event_id,
    ))
    assert obligation.step_receipts[1] == ("facility", tuple(
        event.event_id for event in store.read_events()
        if event.causation_id == obligation.step_receipts[0][1][0]
        and event.event_type == "gameplay.pool.adjusted"
    ))


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
