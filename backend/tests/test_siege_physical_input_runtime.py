import hashlib
import hmac
from decimal import Decimal

from app.gameplay.event_schema_registry import (
    create_stormnight_event_schema_registry,
    gameplay_schema_event_types,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.facility_integrity_runtime import FacilityIntegrityAuthority
from app.gameplay.pool_runtime import PoolDefinition, PoolThreshold
from app.gameplay.siege_physical_input_runtime import (
    GATE_IMPACT_INPUT_EVENT,
    PRESENCE_ASSESSMENT_INPUT_EVENT,
    SIEGE_PHYSICAL_INPUT_PRINCIPAL,
    GateImpactReceipt,
    PresenceAssessmentReceipt,
    SiegePhysicalInputAuthority,
)
from app.world_runtime.replay_participants import _siege_physical_input_participant


AUTHORITY = "ue:stormnight-physics"
SECRET = "test-ue-physics-secret"


def _store():
    return GameplayEventStore(event_schema_registry=create_stormnight_event_schema_registry())


def _signed(receipt):
    signature = hmac.new(
        SECRET.encode(), receipt.canonical_bytes(), hashlib.sha256
    ).hexdigest()
    return receipt.model_copy(update={"signature": signature})


def test_gate_impact_evidence_is_signed_persisted_and_exact_retry_replays():
    store = _store()
    authority = SiegePhysicalInputAuthority(
        store=store,
        authority_secrets={AUTHORITY: SECRET},
        evidence_event_principals={GATE_IMPACT_INPUT_EVENT: SIEGE_PHYSICAL_INPUT_PRINCIPAL},
    )
    receipt = _signed(GateImpactReceipt(
        authority_ref=AUTHORITY,
        receipt_id="impact:ram-17",
        gate_ref="gate-03",
        impact_kind_ref="impact_kind:battering-ram@1",
        physics_tick=481,
        target_incarnation_ref="gate-03:incarnation-2",
        contact_source_digest="sha256:" + "a" * 64,
        signature="0" * 64,
    ))

    first = authority.record_gate_impact(receipt)
    retry = authority.record_gate_impact(receipt)

    assert first.committed
    assert retry.idempotency_status == "duplicate_replayed"
    assert len(store.read_stream("gameplay:combat:gate-impact:impact:ram-17")) == 1
    event = store.get_event(first.committed_event_ids[0])
    assert event.event_type == GATE_IMPACT_INPUT_EVENT
    assert store.transaction_owns_event(
        transaction_id=event.transaction_id,
        event_id=event.event_id,
        principal_ref=SIEGE_PHYSICAL_INPUT_PRINCIPAL,
    )


def test_forged_gate_impact_evidence_is_rejected_without_a_write():
    store = _store()
    authority = SiegePhysicalInputAuthority(
        store=store,
        authority_secrets={AUTHORITY: SECRET},
        evidence_event_principals={GATE_IMPACT_INPUT_EVENT: SIEGE_PHYSICAL_INPUT_PRINCIPAL},
    )
    receipt = GateImpactReceipt(
        authority_ref=AUTHORITY,
        receipt_id="impact:forged",
        gate_ref="gate-03",
        impact_kind_ref="impact_kind:battering-ram@1",
        physics_tick=482,
        target_incarnation_ref="gate-03:incarnation-2",
        contact_source_digest="sha256:" + "b" * 64,
        signature="f" * 64,
    )

    result = authority.record_gate_impact(receipt)

    assert not result.committed
    assert result.failure.error_code == "siege_input_signature_invalid"
    assert store.read_stream("gameplay:combat:gate-impact:impact:forged") == []


def test_presence_assessment_is_a_separate_registered_trusted_input_event():
    store = _store()
    authority = SiegePhysicalInputAuthority(
        store=store,
        authority_secrets={AUTHORITY: SECRET},
        evidence_event_principals={GATE_IMPACT_INPUT_EVENT: SIEGE_PHYSICAL_INPUT_PRINCIPAL},
    )
    impact = _signed(GateImpactReceipt(
        authority_ref=AUTHORITY,
        receipt_id="impact:ram-18",
        gate_ref="gate-03",
        impact_kind_ref="impact_kind:battering-ram@1",
        physics_tick=489,
        target_incarnation_ref="gate-03:incarnation-2",
        contact_source_digest="sha256:" + "c" * 64,
        signature="0" * 64,
    ))
    impact_result = authority.record_gate_impact(impact)
    impact_event = store.get_event(impact_result.committed_event_ids[0])
    facility = FacilityIntegrityAuthority(
        store=store,
        definitions={"gate-03": PoolDefinition(
            fact_type="fact:facility:gate-03:integrity",
            lower=Decimal("0"),
            upper=Decimal("100"),
            initial=Decimal("100"),
            thresholds=(PoolThreshold("breach", Decimal("40"), Decimal("45")),),
        )},
    )
    facility.initialize(
        gate_ref="gate-03",
        command_id="facility:init",
        idempotency_key="facility:init",
        causation_id="siege:setup",
        correlation_id="siege:east",
    )
    damaged = facility.apply_delta(
        gate_ref="gate-03",
        delta=Decimal("-61"),
        reason_code="damage",
        command_id="facility:impact",
        idempotency_key="facility:impact",
        expected_revision=1,
        causation_id=impact_event.event_id,
        correlation_id="siege:east",
    )
    breach_event = next(
        store.get_event(event_id)
        for event_id in damaged.committed_event_ids
        if store.get_event(event_id).event_type == "gameplay.pool.threshold_crossed"
    )
    receipt = _signed(PresenceAssessmentReceipt(
        authority_ref=AUTHORITY,
        receipt_id="assessment:gate-03:breach-8",
        gate_ref="gate-03",
        breach_event_id=breach_event.event_id,
        assessment_ref="assessment:ue-gate-clearance@1",
        state="passable",
        source_event_ids=(breach_event.event_id, impact_event.event_id),
        source_stream_revisions={
            breach_event.stream_id: store.get_stream_head(breach_event.stream_id),
            impact_event.stream_id: store.get_stream_head(impact_event.stream_id),
        },
        physics_tick=490,
        signature="0" * 64,
    ))

    result = authority.record_presence_assessment(receipt)

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == PRESENCE_ASSESSMENT_INPUT_EVENT
    assert event.payload["receipt"]["state"] == "passable"
    assert PRESENCE_ASSESSMENT_INPUT_EVENT in gameplay_schema_event_types()
    assert GATE_IMPACT_INPUT_EVENT in gameplay_schema_event_types()
    registration = create_stormnight_event_schema_registry().get(
        PRESENCE_ASSESSMENT_INPUT_EVENT, 1
    )
    assert registration.event_type == PRESENCE_ASSESSMENT_INPUT_EVENT
    participant = _siege_physical_input_participant(store)
    assert participant["scope"] == "project:siege-physical-inputs"
    assert [item["event_type"] for item in participant["event_refs"]] == [
        GATE_IMPACT_INPUT_EVENT,
        PRESENCE_ASSESSMENT_INPUT_EVENT,
    ]


def test_presence_receipt_rejects_a_breach_without_independent_source_evidence():
    store = _store()
    authority = SiegePhysicalInputAuthority(
        store=store, authority_secrets={AUTHORITY: SECRET}
    )
    receipt = _signed(PresenceAssessmentReceipt(
        authority_ref=AUTHORITY,
        receipt_id="assessment:missing-evidence",
        gate_ref="gate-03",
        breach_event_id="event:integrity-breach-8",
        assessment_ref="assessment:ue-gate-clearance@1",
        state="blocked",
        source_event_ids=("event:integrity-breach-8", "event:assessment-evidence-missing"),
        source_stream_revisions={"fact:facility:gate-03:integrity": 4},
        physics_tick=491,
        signature="0" * 64,
    ))

    result = authority.record_presence_assessment(receipt)

    assert not result.committed
    assert result.failure.error_code == "siege_presence_evidence_invalid"
    assert store.read_stream(
        "gameplay:combat:gate-presence:assessment:missing-evidence"
    ) == []
