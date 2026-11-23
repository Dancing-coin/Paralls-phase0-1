from decimal import Decimal
import hashlib
import hmac

from fastapi.testclient import TestClient

from app import main
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.facility_integrity_runtime import FacilityIntegrityAuthority
from app.gameplay.m6_5_siege_runtime import build_m6_5_siege_runtime
from app.gameplay.pool_runtime import PoolDefinition, PoolThreshold
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.siege_physical_input_runtime import GateImpactReceipt


ORGANIZATION = "organization:garrison:east@1"
ROLE = "role:garrison-defender@1"
MORALE_FACT = "fact:unit:garrison-east:morale"
GATE = "gate-03"
INTEGRITY_FACT = "fact:facility:gate-03:integrity"
PLACE_STREAM = "place:gate-03:passability"
PHYSICS_AUTHORITY = "ue:stormnight-physics"
PHYSICS_SECRET = "0123456789abcdef0123456789abcdef"


def _append(store, *, principal, stream_id, event_type, payload, command_id):
    revision = store.get_stream_head(stream_id)
    result = store.append_batch(build_atomic_event_batch(
        command_id=command_id,
        principal_ref=principal,
        stream_id=stream_id,
        expected_revision=revision,
        event_specs=((event_type, payload),),
        idempotency_key=command_id,
        causation_id=f"cause:{command_id}",
        correlation_id="siege:east",
    ))
    assert result.committed
    return store.get_transaction(result.transaction_id)


def _morale_pool():
    return PoolDefinition(
        fact_type=MORALE_FACT,
        lower=Decimal("0"),
        upper=Decimal("100"),
        initial=Decimal("100"),
        aggregation_mode="distribution",
        refold_model_ref="morale_refold@1",
    )


def _facility_pool():
    return PoolDefinition(
        fact_type=INTEGRITY_FACT,
        lower=Decimal("0"),
        upper=Decimal("100"),
        initial=Decimal("100"),
        thresholds=(PoolThreshold("breach", Decimal("40"), Decimal("45")),),
    )


def test_m6_5_production_dispatch_refolds_morale_and_keeps_missing_presence_input_unknown():
    store = GameplayEventStore()
    runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions={(ORGANIZATION, ROLE): _morale_pool()},
        presence_resolver=None,
    )

    members = tuple(f"character:defender-{index}" for index in range(4))
    organization_stream = f"gameplay:organization:{ORGANIZATION}"
    for index, member in enumerate(members):
        _append(
            store,
            principal="actor_gameplay.organization_domain",
            stream_id=organization_stream,
            event_type="gameplay.organization.membership_delegation_recorded@1",
            payload={
                "organization_ref": ORGANIZATION,
                "member_ref": member,
                "role_ref": ROLE,
                "provenance_ref": f"provenance:appointment-{index}@1",
                "source_revision_pin": index,
                "delegation_state": "active",
            },
            command_id=f"garrison:{index}",
        )
        _append(
            store,
            principal="authority:character:life-state:presence-admission",
            stream_id=f"gameplay:character:life:{member}",
            event_type="gameplay.character.life_state_changed",
            payload={"actor_ref": member, "from_state": "unknown", "to_state": "alive"},
            command_id=f"life-alive:{index}",
        )

    death = _append(
        store,
        principal="authority:character:life-state",
        stream_id=f"gameplay:character:life:{members[0]}",
        event_type="gameplay.character.life_state_changed",
        payload={"actor_ref": members[0], "from_state": "alive", "to_state": "dead"},
        command_id="life-death:0",
    )
    first_result = runtime.after_transaction_dispatched(death)
    second_result = runtime.after_transaction_dispatched(death)

    assert runtime.morale.projection(MORALE_FACT).value == Decimal("75")
    morale_events = store.read_stream(MORALE_FACT)
    assert len(morale_events) == 2
    assert second_result[0].idempotency_status == "duplicate_replayed"
    assert first_result[0].committed

    facility = FacilityIntegrityAuthority(store=store, definitions={GATE: _facility_pool()})
    facility.initialize(
        gate_ref=GATE,
        command_id="facility:init",
        idempotency_key="facility:init",
        causation_id="siege:setup",
        correlation_id="siege:east",
    )
    breach = facility.apply_delta(
        gate_ref=GATE,
        delta=Decimal("-61"),
        reason_code="damage",
        command_id="facility:damage",
        idempotency_key="facility:damage",
        expected_revision=1,
        causation_id="impact:gate",
        correlation_id="siege:east",
    )
    breach_transaction = store.get_transaction(breach.transaction_id)

    presence_result = runtime.after_transaction_dispatched(breach_transaction)

    assert presence_result[0].failure.error_code == "place_assessment_unknown"
    assert store.read_stream(PLACE_STREAM) == []


def test_m6_5_production_runtime_routes_signed_gate_input_through_facility_owner():
    store = GameplayEventStore()
    facility = FacilityIntegrityAuthority(
        store=store,
        definitions={GATE: _facility_pool()},
        impact_profiles={
            GATE: {"impact_kind:battering-ram@1": Decimal("-20")},
        },
    )
    assert facility.initialize(
        gate_ref=GATE,
        command_id="facility:init",
        idempotency_key="facility:init",
        causation_id="siege:setup",
        correlation_id="siege:east",
    ).committed
    runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions={(ORGANIZATION, ROLE): _morale_pool()},
        physical_authority_secrets={PHYSICS_AUTHORITY: PHYSICS_SECRET},
        facility=facility,
    )
    unsigned = GateImpactReceipt(
        authority_ref=PHYSICS_AUTHORITY,
        receipt_id="impact:runtime",
        gate_ref=GATE,
        impact_kind_ref="impact_kind:battering-ram@1",
        target_incarnation_ref="gate-03:incarnation-2",
        contact_source_digest="sha256:" + "a" * 64,
        expected_integrity_revision=1,
        physics_tick=510,
        signature="0" * 64,
    )
    receipt = unsigned.model_copy(update={
        "signature": hmac.new(
            PHYSICS_SECRET.encode(), unsigned.canonical_bytes(), hashlib.sha256
        ).hexdigest(),
    })

    evidence, owner_result = runtime.record_gate_impact(receipt)

    assert evidence.committed
    assert owner_result.committed
    integrity_events = store.read_stream(INTEGRITY_FACT)
    assert len(integrity_events) == 2
    assert integrity_events[-1].payload["delta"] == "-20"
    assert integrity_events[-1].causation_id == evidence.committed_event_ids[0]


def test_m6_5_gate_impact_http_gateway_commits_facility_fact(monkeypatch):
    store = GameplayEventStore()
    facility = FacilityIntegrityAuthority(
        store=store,
        definitions={GATE: _facility_pool()},
        impact_profiles={
            GATE: {"impact_kind:battering-ram@1": Decimal("-20")},
        },
    )
    facility.initialize(
        gate_ref=GATE,
        command_id="facility:init",
        idempotency_key="facility:init",
        causation_id="siege:setup",
        correlation_id="siege:east",
    )
    runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions={(ORGANIZATION, ROLE): _morale_pool()},
        physical_authority_secrets={PHYSICS_AUTHORITY: PHYSICS_SECRET},
        facility=facility,
    )
    monkeypatch.setattr(main, "m6_5_siege_runtime", runtime)
    monkeypatch.setattr(main, "runtime_execution", None)
    unsigned = GateImpactReceipt(
        authority_ref=PHYSICS_AUTHORITY,
        receipt_id="impact:http-gateway",
        gate_ref=GATE,
        impact_kind_ref="impact_kind:battering-ram@1",
        target_incarnation_ref="gate-03:incarnation-2",
        contact_source_digest="sha256:" + "b" * 64,
        expected_integrity_revision=1,
        physics_tick=511,
        signature="0" * 64,
    )
    receipt = unsigned.model_copy(update={
        "signature": hmac.new(
            PHYSICS_SECRET.encode(), unsigned.canonical_bytes(), hashlib.sha256
        ).hexdigest(),
    })

    response = TestClient(main.component_app).post(
        "/api/v2/siege/gate-impact-input",
        json=receipt.model_dump(mode="json"),
    )

    assert response.status_code == 200
    assert response.json()["evidence"]["committed"] is True
    assert response.json()["facility"]["committed"] is True
    assert store.read_stream(INTEGRITY_FACT)[-1].payload["delta"] == "-20"
