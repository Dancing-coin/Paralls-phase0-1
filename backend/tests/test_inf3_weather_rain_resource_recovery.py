from __future__ import annotations

import pytest

from app.gameplay.ecology_runtime import EcologyHazardAuthority, ResourceNode
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from test_infra_weather_front_survival_cold import (
    SOURCE_REGION,
    TARGET_REGION,
    _seed,
)


ROW_REF = "ecology:weather-rain-water-resource-recovery@1"
POLICY_REF = "policy:ecology-weather-rain-water-resource-recovery@1"
PREDICATE_REF = "predicate:ecology-weather-front-rain-and-water-resource@1"
DESCRIPTOR_REF = "descriptor:ecology-weather-rain-water-resource-recovery@1"
CATALOG_REF = "inf:ecology-weather-rain-water-resource-recovery@1"
RESOURCE_REF = f"resource:{TARGET_REGION}:water"


def _request(
    store,
    weather_event_id: str,
    *,
    key: str | None = None,
    target_region_ref: str = TARGET_REGION,
    visibility_scope: str = "project",
    resource_revision: int = 0,
) -> GameplayCommandEnvelope:
    stream = f"gameplay:ecology:{target_region_ref}"
    return GameplayCommandEnvelope(
        command_id="inf3:recover-water",
        command_type="gameplay.ecology.recover_rain_water_resource",
        command_version=1,
        principal_ref="authority:ecology",
        idempotency_key=key
        or f"ecology:weather-rain-water-resource-recovery:{weather_event_id}:{RESOURCE_REF}:{resource_revision}:v1",
        expected_revisions={stream: store.get_stream_head(stream)},
        read_set_revisions={stream: store.get_stream_head(stream)},
        causation_id=weather_event_id,
        correlation_id="corr:inf3-water",
        source_ref=weather_event_id,
        submitted_at="2026-08-28T13:00:00Z",
        payload={
            "visibility_scope": visibility_scope,
            "weather_event_id": weather_event_id,
            "target_region_ref": target_region_ref,
        },
    )


def _record_resource(store, *, quantity: int, revision: int = 1) -> None:
    authority = EcologyHazardAuthority(store=store)
    stream = authority.ecology_stream_id(region_ref=TARGET_REGION)
    result = authority.record_resource(
        envelope=GameplayCommandEnvelope(
            command_id=f"inf3:resource:{revision}",
            command_type="gameplay.ecology.resource.record",
            command_version=1,
            principal_ref="authority:ecology",
            idempotency_key=f"inf3:resource:{revision}",
            expected_revisions={stream: store.get_stream_head(stream)},
            causation_id=f"cause:inf3:resource:{revision}",
            correlation_id="corr:inf3-water",
            source_ref="authority:ecology",
            submitted_at="2026-08-28T13:00:00Z",
            payload={"visibility_scope": "project"},
        ),
        resource=ResourceNode(
            node_ref=RESOURCE_REF,
            region_ref=TARGET_REGION,
            substance_ref="substance:water",
            quantity=quantity,
            regeneration_per_tick=2,
            revision=revision,
        ),
    )
    assert result.committed


def test_inf3_weather_rain_recovers_one_owner_derived_water_resource_and_caps_at_100() -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:rain")
    _record_resource(store, quantity=95)

    result = EcologyHazardAuthority(store=store).recover_rain_water_resource(
        envelope=_request(store, weather_event_id, resource_revision=1)
    )

    assert result.committed, result.failure
    assert result.committed_event_ids
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.ecology.resource.recorded"
    assert event.payload["record"]["node_ref"] == RESOURCE_REF
    assert event.payload["record"]["region_ref"] == TARGET_REGION
    assert event.payload["record"]["substance_ref"] == "substance:water"
    assert event.payload["record"]["quantity"] == 100
    assert event.payload["recovery_delta"] == 10
    assert event.payload["row_ref"] == ROW_REF
    assert event.payload["policy_revision"] == POLICY_REF
    assert event.payload["predicate_ref"] == PREDICATE_REF
    assert event.payload["descriptor_ref"] == DESCRIPTOR_REF
    assert event.payload["descriptor_revision"] == DESCRIPTOR_REF
    assert event.payload["catalog_ref"] == CATALOG_REF
    assert event.visibility_policy == "project"
    assert store.list_outbox()[-1].topic == "ecology.weather_rain_water_resource_recovery.scoped_projection"
    assert store.list_outbox()[-1].audience == "project"


def test_inf3_weather_rain_recovers_exactly_10_water_units_when_below_cap() -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:rain")
    _record_resource(store, quantity=0)

    result = EcologyHazardAuthority(store=store).recover_rain_water_resource(
        envelope=_request(store, weather_event_id, resource_revision=1)
    )

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.payload["record"]["quantity"] == 10
    assert event.payload["recovery_delta"] == 10


def test_inf3_weather_rain_resource_recovery_rejects_no_eligible_resource_without_writes() -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:rain")
    _record_resource(store, quantity=100)
    before = store.export_snapshot()
    denied = EcologyHazardAuthority(store=store).recover_rain_water_resource(
        envelope=_request(store, weather_event_id, resource_revision=1)
    )
    assert not denied.committed
    assert denied.failure and denied.failure.error_code.endswith("resource_missing")
    assert store.export_snapshot() == before


def test_inf3_weather_rain_resource_recovery_rejects_multiple_eligible_resources_without_writes() -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:rain")
    authority = EcologyHazardAuthority(store=store)
    stream = authority.ecology_stream_id(region_ref=TARGET_REGION)
    result = authority.record_resource(
        envelope=GameplayCommandEnvelope(
            command_id="inf3:second-resource",
            command_type="gameplay.ecology.resource.record",
            command_version=1,
            principal_ref="authority:ecology",
            idempotency_key="inf3:second-resource",
            expected_revisions={stream: store.get_stream_head(stream)},
            causation_id="cause:inf3:second-resource",
            correlation_id="corr:inf3-water",
            source_ref="authority:ecology",
            submitted_at="2026-08-28T13:00:00Z",
            payload={"visibility_scope": "project"},
        ),
        resource=ResourceNode(
            node_ref=f"resource:{TARGET_REGION}:water-2",
            region_ref=TARGET_REGION,
            substance_ref="substance:water",
            quantity=10,
            regeneration_per_tick=2,
            revision=0,
        ),
    )
    assert result.committed
    before = store.export_snapshot()
    denied = authority.recover_rain_water_resource(
        envelope=_request(store, weather_event_id)
    )
    assert not denied.committed
    assert denied.failure and denied.failure.error_code.endswith("resource_ambiguous")
    assert store.export_snapshot() == before


@pytest.mark.parametrize(
    ("source_weather_ref", "visibility_scope"),
    [("weather:drought", "project"), ("weather:rain", "authority_only"), ("weather:rain", "private_evidence")],
)
def test_inf3_weather_rain_resource_recovery_rejects_stale_private_or_wrong_weather_without_writes(
    source_weather_ref: str, visibility_scope: str
) -> None:
    store, weather_event_id, _ = _seed(source_weather_ref=source_weather_ref)
    before = store.export_snapshot()
    denied = EcologyHazardAuthority(store=store).recover_rain_water_resource(
        envelope=_request(store, weather_event_id, visibility_scope=visibility_scope)
    )
    assert not denied.committed
    assert store.export_snapshot() == before


def test_inf3_weather_rain_resource_recovery_rejects_stale_weather_source_without_writes() -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:rain")
    authority = EcologyHazardAuthority(store=store)
    source_stream = authority.ecology_stream_id(region_ref=SOURCE_REGION)
    assert authority.record_resource(
        envelope=GameplayCommandEnvelope(
            command_id="inf3:stale-source",
            command_type="gameplay.ecology.resource.record",
            command_version=1,
            principal_ref="authority:ecology",
            idempotency_key="inf3:stale-source",
            expected_revisions={source_stream: store.get_stream_head(source_stream)},
            causation_id="cause:inf3:stale-source",
            correlation_id="corr:inf3-water",
            source_ref="authority:ecology",
            submitted_at="2026-08-28T13:00:00Z",
            payload={"visibility_scope": "project"},
        ),
        resource=ResourceNode(
            node_ref=f"resource:{SOURCE_REGION}:water-2",
            region_ref=SOURCE_REGION,
            substance_ref="substance:water",
            quantity=1,
            regeneration_per_tick=1,
            revision=0,
        ),
    ).committed
    before = store.export_snapshot()
    denied = authority.recover_rain_water_resource(
        envelope=_request(store, weather_event_id)
    )
    assert not denied.committed
    assert denied.failure and denied.failure.error_code.endswith("source_revision_conflict")
    assert store.export_snapshot() == before


def test_inf3_weather_rain_resource_recovery_rejects_private_resource_without_writes() -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:rain")
    authority = EcologyHazardAuthority(store=store)
    stream = authority.ecology_stream_id(region_ref=TARGET_REGION)
    projection = authority.regional_projection(scope="authority")
    resource = next(value for value in projection["resources"].values() if value["region_ref"] == TARGET_REGION)
    private = ResourceNode.model_validate(
        {key: value for key, value in resource.items() if key not in {"causal_parent_refs"}}
    ).model_copy(update={"quantity": 80, "revision": int(resource["revision"]) + 1})
    assert authority.record_resource(
        envelope=GameplayCommandEnvelope(
            command_id="inf3:private-resource",
            command_type="gameplay.ecology.resource.record",
            command_version=1,
            principal_ref="authority:ecology",
            idempotency_key="inf3:private-resource",
            expected_revisions={stream: store.get_stream_head(stream)},
            causation_id="cause:inf3:private-resource",
            correlation_id="corr:inf3-water",
            source_ref="authority:ecology",
            submitted_at="2026-08-28T13:00:00Z",
            payload={"visibility_scope": "authority_only"},
        ),
        resource=private,
    ).committed
    before = store.export_snapshot()

    denied = authority.recover_rain_water_resource(
        envelope=_request(store, weather_event_id, resource_revision=private.revision)
    )

    assert not denied.committed
    assert denied.failure and denied.failure.error_code == "rain_water_resource_private"
    assert store.export_snapshot() == before


def test_inf3_weather_rain_resource_recovery_rejects_duplicate_and_changed_idempotency_binding_without_writes() -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:rain")
    authority = EcologyHazardAuthority(store=store)
    request = _request(store, weather_event_id)
    first = authority.recover_rain_water_resource(envelope=request)
    assert first.committed
    before = store.export_snapshot()
    duplicate = authority.recover_rain_water_resource(envelope=request)
    changed = authority.recover_rain_water_resource(
        envelope=request.model_copy(update={"correlation_id": "corr:changed"})
    )
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed
    assert store.export_snapshot() == before


def test_inf3_weather_rain_resource_recovery_rejects_wrong_idempotency_key_without_writes() -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:rain")
    before = store.export_snapshot()
    denied = EcologyHazardAuthority(store=store).recover_rain_water_resource(
        envelope=_request(store, weather_event_id, key="ecology:wrong-key")
    )
    assert not denied.committed
    assert denied.failure and denied.failure.error_code.endswith("idempotency_key_invalid")
    assert store.export_snapshot() == before


def test_inf3_weather_rain_resource_recovery_rejects_forged_replay_provenance() -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:rain")
    authority = EcologyHazardAuthority(store=store)
    result = authority.recover_rain_water_resource(
        envelope=_request(store, weather_event_id)
    )
    assert result.committed
    recovery = store.get_event(result.committed_event_ids[0])
    forged = recovery.model_copy(
        update={"payload": {**recovery.payload, "weather_event_id": "event:forged"}},
        deep=True,
    )
    store._events_by_id[recovery.event_id] = forged
    store._events = [
        forged if event.event_id == recovery.event_id else event
        for event in store._events
    ]
    with pytest.raises(ValueError, match="rain_water_resource_recovery_replay_provenance_invalid"):
        authority.regional_replay()
    with pytest.raises(ValueError, match="rain_water_resource_recovery_replay_provenance_invalid"):
        authority.regional_replay(checkpoint_at=1)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("descriptor_revision", "descriptor:forged@1"),
        ("terminal", "reversible"),
    ),
)
def test_inf3_weather_rain_resource_recovery_replay_rejects_forged_contract_pins(
    field: str, value: str
) -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:rain")
    authority = EcologyHazardAuthority(store=store)
    result = authority.recover_rain_water_resource(
        envelope=_request(store, weather_event_id)
    )
    assert result.committed
    recovery = store.get_event(result.committed_event_ids[0])
    forged = recovery.model_copy(
        update={"payload": {**recovery.payload, field: value}}, deep=True
    )
    store._events_by_id[recovery.event_id] = forged
    store._events = [
        forged if event.event_id == recovery.event_id else event
        for event in store._events
    ]

    with pytest.raises(ValueError, match="rain_water_resource_recovery_replay_provenance_invalid"):
        authority.regional_replay()


def test_inf3_weather_rain_resource_recovery_full_and_checkpoint_tail_replay_are_equal() -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:rain")
    authority = EcologyHazardAuthority(store=store)
    result = authority.recover_rain_water_resource(
        envelope=_request(store, weather_event_id)
    )
    assert result.committed
    assert authority.regional_replay().projection_hash == authority.regional_replay(
        checkpoint_at=1
    ).projection_hash


def test_inf3_weather_rain_resource_recovery_replay_rejects_private_source_resource() -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:rain")
    authority = EcologyHazardAuthority(store=store)
    result = authority.recover_rain_water_resource(
        envelope=_request(store, weather_event_id)
    )
    assert result.committed
    recovery = store.get_event(result.committed_event_ids[0])
    source_resource = next(
        event
        for event in store.read_stream(f"gameplay:ecology:{TARGET_REGION}")
        if event.event_type == "gameplay.ecology.resource.recorded"
        and event.payload.get("record_ref") == RESOURCE_REF
        and event.event_id != recovery.event_id
    )
    private_source = source_resource.model_copy(
        update={"visibility_policy": "authority_only"}, deep=True
    )
    store._events_by_id[source_resource.event_id] = private_source
    store._events = [
        private_source if event.event_id == source_resource.event_id else event
        for event in store._events
    ]

    with pytest.raises(ValueError, match="rain_water_resource_recovery_replay_provenance_invalid"):
        authority.regional_replay()


def test_inf3_catalog_pins_only_the_exact_weather_rain_water_resource_recovery_operation() -> None:
    contract = GovernedAuthorityContractCatalog.require(
        contract_ref=CATALOG_REF,
        contract_kind="ecology_consumer",
    )
    assert contract.owner_ref == "authority:ecology"
    assert contract.stream_patterns == ("gameplay:ecology:{region_ref}",)
    assert contract.event_types == ("gameplay.ecology.resource.recorded",)
    assert contract.projection_scope == "project"
