from decimal import Decimal
import hashlib
import hmac

from fastapi.testclient import TestClient
import pytest

from app import main
from app.config import (
    FacilityGateProfileSettings,
    RulePackDeploymentSettings,
    Settings,
)
from app.gameplay.event_store import DurableGameplayEventStore, GameplayEventStore
from app.gameplay.facility_integrity_runtime import FacilityIntegrityAuthority
from app.gameplay.m6_5_siege_runtime import (
    INFORMATION_PACK,
    M6_5_PACK,
    MORALE_OWNER_DOMAINS,
    build_facility_integrity_authority,
    build_facility_gate_layered_authority,
    build_m6_5_siege_runtime,
)
from app.gameplay.package_migration_runtime import (
    PackageArchive,
    PackageRef,
    load_deployment_package_archive,
)
from app.gameplay.rule_pack_validator import load_pack
from app.gameplay.pool_runtime import PoolDefinition, PoolThreshold
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.siege_physical_input_runtime import (
    GateImpactReceipt,
    GateImpactReceiptV2,
    PresenceAssessmentReceipt,
)


ORGANIZATION = "organization:garrison:east@1"
ROLE = "role:garrison-defender@1"
MORALE_FACT = "fact:unit:garrison-east:morale"
GATE = "gate-03"
INTEGRITY_FACT = "fact:facility:gate-03:integrity"
PLACE_STREAM = "place:gate-03:passability"
PHYSICS_AUTHORITY = "ue:stormnight-physics"
PHYSICS_SECRET = "fixture-key"


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


def _m6_5_archive():
    morale_ref = PackageRef("county_siege_morale_presence", "1.0.0")
    information_ref = PackageRef("county_siege_information", "1.0.0")
    morale_pack = load_pack(
        M6_5_PACK,
        handlers={},
        owner_domains=MORALE_OWNER_DOMAINS,
        command_fact_outputs={
            "morale.refold": {MORALE_FACT},
            "presence.reevaluate": {PLACE_STREAM},
        },
    )
    information_pack = load_pack(
        INFORMATION_PACK,
        handlers={},
        owner_domains={"Information": "information"},
        command_fact_outputs={
            "information.update_knowledge": {"fact:information:knowledge"},
        },
    )
    return PackageArchive(
        (morale_pack, information_pack),
        expected_content_hashes={
            morale_ref: morale_pack.content_hash,
            information_ref: information_pack.content_hash,
        },
    ), {"morale_presence": morale_ref, "information": information_ref}


def test_m6_5_runtime_can_consume_world_pinned_package_archive(monkeypatch):
    archive, refs = _m6_5_archive()
    monkeypatch.setattr(
        "app.gameplay.m6_5_siege_runtime.load_pack",
        lambda *args, **kwargs: pytest.fail("legacy package loader used"),
    )
    runtime = build_m6_5_siege_runtime(
        store=GameplayEventStore(),
        morale_definitions={(ORGANIZATION, ROLE): _morale_pool()},
        package_archive=archive,
        package_refs=refs,
    )

    assert runtime.information is not None


def test_m6_5_runtime_can_bootstrap_from_deployment_manifest():
    morale_hash = load_pack(
        M6_5_PACK,
        handlers={},
        owner_domains=MORALE_OWNER_DOMAINS,
        command_fact_outputs={
            "morale.refold": {MORALE_FACT},
            "presence.reevaluate": {PLACE_STREAM},
        },
    ).content_hash
    information_hash = load_pack(
        INFORMATION_PACK,
        handlers={},
        owner_domains={"Information": "information"},
        command_fact_outputs={
            "information.update_knowledge": {"fact:information:knowledge"},
        },
    ).content_hash
    archive = load_deployment_package_archive(
        {
            "county_siege_morale_presence@1.0.0": "packs/county_siege_morale_presence",
            "county_siege_information@1.0.0": "packs/county_siege_information",
        },
        {
            "county_siege_morale_presence@1.0.0": morale_hash,
            "county_siege_information@1.0.0": information_hash,
        },
        base_directory=M6_5_PACK.parents[1],
        handlers={},
        owner_domains={**MORALE_OWNER_DOMAINS, "Information": "information"},
        command_fact_outputs={
            "morale.refold": {MORALE_FACT},
            "presence.reevaluate": {PLACE_STREAM},
            "information.update_knowledge": {"fact:information:knowledge"},
        },
    )
    runtime = build_m6_5_siege_runtime(
        store=GameplayEventStore(),
        morale_definitions={(ORGANIZATION, ROLE): _morale_pool()},
        package_archive=archive,
        package_refs={
            "morale_presence": PackageRef("county_siege_morale_presence", "1.0.0"),
            "information": PackageRef("county_siege_information", "1.0.0"),
        },
        world_ref="world:siege",
    )

    assert runtime.world_ref == "world:siege"


def test_m6_5_runtime_rejects_incomplete_package_consumer_configuration():
    archive, _ = _m6_5_archive()

    with pytest.raises(ValueError, match="m6_5_package_consumer_configuration_incomplete"):
        build_m6_5_siege_runtime(
            store=GameplayEventStore(),
            morale_definitions={(ORGANIZATION, ROLE): _morale_pool()},
            package_archive=archive,
        )

    with pytest.raises(ValueError, match="m6_5_package_consumer_package_refs_missing"):
        build_m6_5_siege_runtime(
            store=GameplayEventStore(),
            morale_definitions={(ORGANIZATION, ROLE): _morale_pool()},
            package_archive=archive,
            package_refs={},
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


def test_m6_5_recovery_replays_committed_gate_input_without_a_second_obligation_ledger():
    store = GameplayEventStore()
    facility = FacilityIntegrityAuthority(
        store=store,
        definitions={GATE: _facility_pool()},
        impact_profiles={GATE: {"impact_kind:battering-ram@1": Decimal("-20")}},
    )
    facility.initialize(
        gate_ref=GATE,
        command_id="facility:init-recovery",
        idempotency_key="facility:init-recovery",
        causation_id="siege:setup",
        correlation_id="siege:east",
    )
    first_runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions={(ORGANIZATION, ROLE): _morale_pool()},
        physical_authority_secrets={PHYSICS_AUTHORITY: PHYSICS_SECRET},
        facility=facility,
    )
    unsigned = GateImpactReceipt(
        authority_ref=PHYSICS_AUTHORITY,
        receipt_id="impact:recovery",
        gate_ref=GATE,
        impact_kind_ref="impact_kind:battering-ram@1",
        target_incarnation_ref="gate-03:incarnation-2",
        contact_source_digest="sha256:" + "c" * 64,
        expected_integrity_revision=1,
        physics_tick=512,
        signature="0" * 64,
    )
    receipt = unsigned.model_copy(update={
        "signature": hmac.new(
            PHYSICS_SECRET.encode(), unsigned.canonical_bytes(), hashlib.sha256
        ).hexdigest(),
    })
    evidence = first_runtime.physical_inputs.record_gate_impact(receipt)
    assert evidence.committed

    recovered_runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions={(ORGANIZATION, ROLE): _morale_pool()},
        physical_authority_secrets={PHYSICS_AUTHORITY: PHYSICS_SECRET},
        facility=FacilityIntegrityAuthority(
            store=store,
            definitions={GATE: _facility_pool()},
            impact_profiles={GATE: {"impact_kind:battering-ram@1": Decimal("-20")}},
        ),
    )

    first_recovery = recovered_runtime.recover_physical_input_obligations()
    second_recovery = recovered_runtime.recover_physical_input_obligations()

    assert first_recovery[0][1].committed
    assert second_recovery[0][1].idempotency_status == "duplicate_replayed"
    assert len(store.read_stream(INTEGRITY_FACT)) == 2
    assert store.read_stream(INTEGRITY_FACT)[-1].payload["delta"] == "-20"


def test_m6_5_gate_input_recovery_survives_durable_store_restart(tmp_path):
    database_path = tmp_path / "siege.db"
    store = DurableGameplayEventStore(database_path)
    facility = FacilityIntegrityAuthority(
        store=store,
        definitions={GATE: _facility_pool()},
        impact_profiles={GATE: {"impact_kind:battering-ram@1": Decimal("-20")}},
    )
    assert facility.initialize(
        gate_ref=GATE,
        command_id="facility:init-durable-recovery",
        idempotency_key="facility:init-durable-recovery",
        causation_id="siege:setup",
        correlation_id="siege:east",
    ).committed
    first_runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions={(ORGANIZATION, ROLE): _morale_pool()},
        physical_authority_secrets={PHYSICS_AUTHORITY: PHYSICS_SECRET},
        facility=facility,
    )
    unsigned = GateImpactReceipt(
        authority_ref=PHYSICS_AUTHORITY,
        receipt_id="impact:durable-recovery",
        gate_ref=GATE,
        impact_kind_ref="impact_kind:battering-ram@1",
        target_incarnation_ref="gate-03:incarnation-2",
        contact_source_digest="sha256:" + "e" * 64,
        expected_integrity_revision=1,
        physics_tick=515,
        signature="0" * 64,
    )
    receipt = unsigned.model_copy(update={
        "signature": hmac.new(
            PHYSICS_SECRET.encode(), unsigned.canonical_bytes(), hashlib.sha256
        ).hexdigest(),
    })
    evidence = first_runtime.physical_inputs.record_gate_impact(receipt)
    assert evidence.committed
    store.close()

    reopened_store = DurableGameplayEventStore(database_path)
    recovered_runtime = build_m6_5_siege_runtime(
        store=reopened_store,
        morale_definitions={(ORGANIZATION, ROLE): _morale_pool()},
        physical_authority_secrets={PHYSICS_AUTHORITY: PHYSICS_SECRET},
        facility=FacilityIntegrityAuthority(
            store=reopened_store,
            definitions={GATE: _facility_pool()},
            impact_profiles={GATE: {"impact_kind:battering-ram@1": Decimal("-20")}},
        ),
    )

    first_recovery = recovered_runtime.recover_physical_input_obligations()
    second_recovery = recovered_runtime.recover_physical_input_obligations()

    assert first_recovery[0][1].committed
    assert second_recovery[0][1].idempotency_status == "duplicate_replayed"
    integrity_events = reopened_store.read_stream(INTEGRITY_FACT)
    assert len(integrity_events) == 2
    assert integrity_events[-1].payload["delta"] == "-20"
    reopened_store.close()


def test_m6_5_recovery_completes_presence_from_persisted_signed_assessment():
    store = GameplayEventStore()
    facility = FacilityIntegrityAuthority(store=store, definitions={GATE: _facility_pool()})
    facility.initialize(
        gate_ref=GATE,
        command_id="facility:init-presence-recovery",
        idempotency_key="facility:init-presence-recovery",
        causation_id="siege:setup",
        correlation_id="siege:east",
    )
    input_runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions={(ORGANIZATION, ROLE): _morale_pool()},
        physical_authority_secrets={PHYSICS_AUTHORITY: PHYSICS_SECRET},
    )
    impact_unsigned = GateImpactReceipt(
        authority_ref=PHYSICS_AUTHORITY,
        receipt_id="impact:presence-recovery-source",
        gate_ref=GATE,
        impact_kind_ref="impact_kind:battering-ram@1",
        target_incarnation_ref="gate-03:incarnation-2",
        contact_source_digest="sha256:" + "d" * 64,
        expected_integrity_revision=1,
        physics_tick=513,
        signature="0" * 64,
    )
    impact_receipt = impact_unsigned.model_copy(update={
        "signature": hmac.new(
            PHYSICS_SECRET.encode(), impact_unsigned.canonical_bytes(), hashlib.sha256
        ).hexdigest(),
    })
    impact_result = input_runtime.physical_inputs.record_gate_impact(impact_receipt)
    impact_event = store.get_event(impact_result.committed_event_ids[0])
    breach_result = facility.apply_delta(
        gate_ref=GATE,
        delta=Decimal("-61"),
        reason_code="damage",
        command_id="facility:presence-recovery-breach",
        idempotency_key="facility:presence-recovery-breach",
        expected_revision=1,
        causation_id=impact_event.event_id,
        correlation_id="siege:east",
    )
    breach = next(
        store.get_event(event_id)
        for event_id in breach_result.committed_event_ids
        if store.get_event(event_id).event_type == "gameplay.pool.threshold_crossed"
    )
    assessment_unsigned = PresenceAssessmentReceipt(
        authority_ref=PHYSICS_AUTHORITY,
        receipt_id="assessment:presence-recovery",
        gate_ref=GATE,
        breach_event_id=breach.event_id,
        assessment_ref="assessment:trusted-gate-clearance@1",
        state="passable",
        source_event_ids=(breach.event_id, impact_event.event_id),
        source_stream_revisions={
            breach.stream_id: store.get_stream_head(breach.stream_id),
            impact_event.stream_id: store.get_stream_head(impact_event.stream_id),
        },
        physics_tick=514,
        signature="0" * 64,
    )
    assessment_receipt = assessment_unsigned.model_copy(update={
        "signature": hmac.new(
            PHYSICS_SECRET.encode(), assessment_unsigned.canonical_bytes(), hashlib.sha256
        ).hexdigest(),
    })
    evidence = input_runtime.physical_inputs.record_presence_assessment(assessment_receipt)
    assert evidence.committed

    recovered_runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions={(ORGANIZATION, ROLE): _morale_pool()},
        physical_authority_secrets={PHYSICS_AUTHORITY: PHYSICS_SECRET},
    )

    first_recovery = recovered_runtime.recover_physical_input_obligations()
    second_recovery = recovered_runtime.recover_physical_input_obligations()

    assert first_recovery[-1][1].committed
    assert second_recovery[-1][1].idempotency_status == "duplicate_replayed"
    assert len(store.read_stream(PLACE_STREAM)) == 1
    assert store.read_stream(PLACE_STREAM)[0].payload["to_state"] == "passable"


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


def test_m6_5_layered_gate_impact_http_gateway_commits_facility_layers(monkeypatch):
    store = GameplayEventStore()
    profile = FacilityGateProfileSettings.model_validate({
        "gate_ref": GATE,
        "integrity_lower": "0",
        "integrity_upper": "100",
        "integrity_initial": "100",
        "breach_threshold": "40",
        "breach_reset_threshold": "45",
        "impact_deltas": {"impact_kind:battering-ram@1": "-20"},
        "durability_lower": "0",
        "durability_upper": "100",
        "durability_initial": "100",
        "latch_durability_lower": "0",
        "latch_durability_upper": "100",
        "latch_durability_initial": "100",
    })
    layered_facility = build_facility_gate_layered_authority(
        store=store,
        profiles=(profile,),
    )
    assert layered_facility is not None
    assert all(result.committed for result in layered_facility.initialize(
        gate_ref=GATE,
        command_prefix="facility:http-layered-init",
        causation_id="siege:setup",
        correlation_id="siege:east",
    ))
    runtime = build_m6_5_siege_runtime(
        store=store,
        morale_definitions={(ORGANIZATION, ROLE): _morale_pool()},
        physical_authority_secrets={PHYSICS_AUTHORITY: PHYSICS_SECRET},
        layered_facility=layered_facility,
    )
    monkeypatch.setattr(main, "m6_5_siege_runtime", runtime)
    monkeypatch.setattr(main, "runtime_execution", None)
    unsigned = GateImpactReceiptV2(
        authority_ref=PHYSICS_AUTHORITY,
        receipt_id="impact:http-layered-gateway",
        gate_ref=GATE,
        impact_kind_ref="impact_kind:battering-ram@1",
        target_incarnation_ref="gate-03:incarnation-2",
        contact_source_digest="sha256:" + "d" * 64,
        expected_layer_revisions={
            "fact:facility:gate-03:durability": 1,
            "fact:facility:gate-03:latch-durability": 1,
            INTEGRITY_FACT: 1,
        },
        physics_tick=514,
        signature="0" * 64,
    )
    receipt = unsigned.model_copy(update={
        "signature": hmac.new(
            PHYSICS_SECRET.encode(), unsigned.canonical_bytes(), hashlib.sha256
        ).hexdigest(),
    })

    response = TestClient(main.component_app).post(
        "/api/v2/siege/gate-impact-input-v2",
        json=receipt.model_dump(mode="json"),
    )

    assert response.status_code == 200
    assert response.json()["evidence"]["committed"] is True
    assert response.json()["facility"]["committed"] is True
    assert store.read_stream("fact:facility:gate-03:durability")[-1].payload["delta"] == "-20"
    assert len(store.read_stream("fact:facility:gate-03:latch-durability")) == 1
    assert len(store.read_stream(INTEGRITY_FACT)) == 1


def test_m6_5_presence_assessment_http_gateway_commits_place_fact(monkeypatch):
    store = GameplayEventStore()
    facility = FacilityIntegrityAuthority(store=store, definitions={GATE: _facility_pool()})
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
    )
    impact_unsigned = GateImpactReceipt(
        authority_ref=PHYSICS_AUTHORITY,
        receipt_id="impact:presence-source",
        gate_ref=GATE,
        impact_kind_ref="impact_kind:battering-ram@1",
        target_incarnation_ref="gate-03:incarnation-2",
        contact_source_digest="sha256:" + "c" * 64,
        expected_integrity_revision=1,
        physics_tick=512,
        signature="0" * 64,
    )
    impact = impact_unsigned.model_copy(update={
        "signature": hmac.new(
            PHYSICS_SECRET.encode(), impact_unsigned.canonical_bytes(), hashlib.sha256
        ).hexdigest(),
    })
    input_result, owner_result = runtime.record_gate_impact(impact)
    assert input_result.committed and owner_result is None
    impact_event = store.get_event(input_result.committed_event_ids[0])
    breach_result = facility.apply_delta(
        gate_ref=GATE,
        delta=Decimal("-61"),
        reason_code="damage",
        command_id="facility:breach",
        idempotency_key="facility:breach",
        expected_revision=1,
        causation_id=impact_event.event_id,
        correlation_id="siege:east",
    )
    breach = next(
        store.get_event(event_id)
        for event_id in breach_result.committed_event_ids
        if store.get_event(event_id).event_type == "gameplay.pool.threshold_crossed"
    )
    assessment_unsigned = PresenceAssessmentReceipt(
        authority_ref=PHYSICS_AUTHORITY,
        receipt_id="assessment:http-gateway",
        gate_ref=GATE,
        breach_event_id=breach.event_id,
        assessment_ref="assessment:trusted-gate-clearance@1",
        state="passable",
        source_event_ids=(breach.event_id, impact_event.event_id),
        source_stream_revisions={
            breach.stream_id: store.get_stream_head(breach.stream_id),
            impact_event.stream_id: store.get_stream_head(impact_event.stream_id),
        },
        physics_tick=513,
        signature="0" * 64,
    )
    assessment = assessment_unsigned.model_copy(update={
        "signature": hmac.new(
            PHYSICS_SECRET.encode(), assessment_unsigned.canonical_bytes(), hashlib.sha256
        ).hexdigest(),
    })
    monkeypatch.setattr(main, "m6_5_siege_runtime", runtime)
    monkeypatch.setattr(main, "runtime_execution", None)

    response = TestClient(main.component_app).post(
        "/api/v2/siege/presence-assessment-input",
        json=assessment.model_dump(mode="json"),
    )

    assert response.status_code == 200
    assert response.json()["evidence"]["committed"] is True
    assert response.json()["place"]["committed"] is True
    place_fact = store.read_stream(PLACE_STREAM)[0]
    assert place_fact.payload["to_state"] == "passable"
    assert impact_event.event_id in place_fact.payload["source_event_ids"]


def test_configured_gate_content_profile_builds_facility_authority_without_defaults():
    store = GameplayEventStore()
    profile = FacilityGateProfileSettings.model_validate({
        "gate_ref": GATE,
        "integrity_lower": "0",
        "integrity_upper": "100",
        "integrity_initial": "100",
        "breach_threshold": "40",
        "breach_reset_threshold": "45",
        "impact_deltas": {"impact_kind:battering-ram@1": "-20"},
    })

    authority = build_facility_integrity_authority(store=store, profiles=(profile,))

    assert authority is not None
    assert authority.initialize(
        gate_ref=GATE,
        command_id="facility:configured-init",
        idempotency_key="facility:configured-init",
        causation_id="siege:setup",
        correlation_id="siege:east",
    ).committed
    assert store.read_stream(INTEGRITY_FACT)[0].payload["initial"] == "100"


def test_empty_gate_content_configuration_keeps_facility_unconfigured():
    assert build_facility_integrity_authority(
        store=GameplayEventStore(),
        profiles=(),
    ) is None


def test_layered_gate_profile_builds_three_owner_pools_without_demo_defaults():
    store = GameplayEventStore()
    profile = FacilityGateProfileSettings.model_validate({
        "gate_ref": GATE,
        "integrity_lower": "0",
        "integrity_upper": "100",
        "integrity_initial": "100",
        "breach_threshold": "40",
        "breach_reset_threshold": "45",
        "impact_deltas": {"impact_kind:battering-ram@1": "-20"},
        "durability_lower": "0",
        "durability_upper": "100",
        "durability_initial": "100",
        "latch_durability_lower": "0",
        "latch_durability_upper": "100",
        "latch_durability_initial": "100",
    })

    authority = build_facility_gate_layered_authority(store=store, profiles=(profile,))

    assert authority is not None
    initialized = authority.initialize(
        gate_ref=GATE,
        command_prefix="facility:configured-layered-init",
        causation_id="siege:setup",
        correlation_id="siege:east",
    )
    assert len(initialized) == 3
    assert all(result.committed for result in initialized)
    for fact_type in (
        "fact:facility:gate-03:durability",
        "fact:facility:gate-03:latch-durability",
        INTEGRITY_FACT,
    ):
        assert store.read_stream(fact_type)[0].payload["initial"] == "100"


def test_layered_gate_profile_requires_all_durability_layer_values():
    with pytest.raises(ValueError, match="siege_facility_layered_profile_incomplete"):
        FacilityGateProfileSettings.model_validate({
            "gate_ref": GATE,
            "integrity_lower": "0",
            "integrity_upper": "100",
            "integrity_initial": "100",
            "breach_threshold": "40",
            "breach_reset_threshold": "45",
            "impact_deltas": {"impact_kind:battering-ram@1": "-20"},
            "durability_lower": "0",
        })


def test_settings_reject_duplicate_gate_content_profiles():
    profile = FacilityGateProfileSettings.model_validate({
        "gate_ref": GATE,
        "integrity_lower": "0",
        "integrity_upper": "100",
        "integrity_initial": "100",
        "breach_threshold": "40",
        "breach_reset_threshold": "45",
        "impact_deltas": {"impact_kind:battering-ram@1": "-20"},
    })

    with pytest.raises(ValueError, match="siege_facility_gate_profile_duplicate"):
        Settings(siege_facility_gate_profiles=[profile, profile])


def test_rule_pack_deployment_contract_requires_all_manifest_inputs():
    deployment = RulePackDeploymentSettings.model_validate({
        "world_ref": "world:siege",
        "initial_refs": {
            "morale_presence": {
                "pack_id": "county_siege_morale_presence",
                "pack_version": "1.0.0",
            },
            "information": {
                "pack_id": "county_siege_information",
                "pack_version": "1.0.0",
            },
        },
        "archive_directories": {
            "county_siege_morale_presence@1.0.0": "packs/county_siege_morale_presence",
            "county_siege_information@1.0.0": "packs/county_siege_information",
        },
        "trusted_content_hashes": {
            "county_siege_morale_presence@1.0.0": "sha256:morale",
            "county_siege_information@1.0.0": "sha256:information",
        },
    })

    assert deployment.world_ref == "world:siege"


def test_rule_pack_deployment_contract_rejects_partial_manifest():
    with pytest.raises(ValueError, match="rule_pack_archive_manifest_mismatch"):
        RulePackDeploymentSettings.model_validate({
            "world_ref": "world:siege",
            "initial_refs": {
                "morale_presence": {
                    "pack_id": "county_siege_morale_presence",
                    "pack_version": "1.0.0",
                },
            },
            "archive_directories": {"county_siege_morale_presence@1.0.0": "packs/morale"},
            "trusted_content_hashes": {},
        })


def _valid_gate_profile(**updates):
    profile = {
        "gate_ref": GATE,
        "integrity_lower": "0",
        "integrity_upper": "100",
        "integrity_initial": "100",
        "breach_threshold": "40",
        "breach_reset_threshold": "45",
        "impact_deltas": {"impact_kind:battering-ram@1": "-20"},
    }
    profile.update(updates)
    return profile


def test_gate_profile_defaults_to_compatible_v1_contract():
    profile = FacilityGateProfileSettings.model_validate(_valid_gate_profile())

    assert profile.schema_version == 1


def test_gate_profile_accepts_explicit_v1_schema_version():
    profile = FacilityGateProfileSettings.model_validate(
        _valid_gate_profile(schema_version=1)
    )

    assert profile.schema_version == 1


def test_gate_profile_rejects_unsupported_schema_version():
    with pytest.raises(ValueError, match="siege_facility_profile_version_unsupported"):
        FacilityGateProfileSettings.model_validate(
            _valid_gate_profile(schema_version=2)
        )


@pytest.mark.parametrize(
    ("updates", "error_code"),
    [
        ({"gate_ref": ""}, "siege_facility_gate_ref_invalid"),
        ({"gate_ref": " gate-03"}, "siege_facility_gate_ref_invalid"),
        ({"integrity_upper": "0"}, "siege_facility_integrity_bounds_invalid"),
        ({"integrity_initial": "101"}, "siege_facility_integrity_initial_invalid"),
        ({"breach_threshold": "-1"}, "siege_facility_breach_thresholds_invalid"),
        ({"breach_reset_threshold": "39"}, "siege_facility_breach_thresholds_invalid"),
        ({"integrity_lower": "NaN"}, "siege_facility_numeric_value_invalid"),
        ({"integrity_initial": 100.0}, "siege_facility_decimal_string_required"),
        ({"integrity_initial": True}, "siege_facility_decimal_string_required"),
        ({"impact_deltas": {"": "-20"}}, "siege_facility_impact_profile_invalid"),
        ({"impact_deltas": {}}, "siege_facility_impact_profile_invalid"),
        ({"impact_deltas": {"impact_kind:battering-ram@1": "0"}}, "siege_facility_impact_profile_invalid"),
        ({"impact_deltas": {"impact_kind:battering-ram@1": "20"}}, "siege_facility_impact_profile_invalid"),
        ({
            "durability_lower": "0",
            "durability_upper": "0",
            "durability_initial": "0",
            "latch_durability_lower": "0",
            "latch_durability_upper": "100",
            "latch_durability_initial": "100",
        }, "siege_facility_layer_bounds_invalid"),
        ({
            "durability_lower": "0",
            "durability_upper": "100",
            "durability_initial": "101",
            "latch_durability_lower": "0",
            "latch_durability_upper": "100",
            "latch_durability_initial": "100",
        }, "siege_facility_layer_initial_invalid"),
    ],
)
def test_gate_profile_rejects_invalid_v1_contract_values(updates, error_code):
    with pytest.raises(ValueError, match=error_code):
        FacilityGateProfileSettings.model_validate(_valid_gate_profile(**updates))


def test_gate_profile_rejects_unknown_fields():
    with pytest.raises(ValueError) as raised:
        FacilityGateProfileSettings.model_validate(
            _valid_gate_profile(integrity_inital="100")
        )

    assert "integrity_inital" in str(raised.value)
