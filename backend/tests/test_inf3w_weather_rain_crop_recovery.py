from __future__ import annotations

import pytest

from app.gameplay.ecology_runtime import EcologyDroughtProcessPolicy, EcologyHazardAuthority
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from test_infra_weather_front_survival_cold import _seed, SOURCE_REGION, TARGET_REGION


def _request(store, weather_event_id: str, crop_ref: str, *, key: str | None = None, revision: int = 1):
    stream = f"gameplay:ecology:{TARGET_REGION}"
    return GameplayCommandEnvelope(
        command_id="inf3w:recover",
        command_type="gameplay.ecology.recover_rain_crop_health",
        command_version=1,
        principal_ref="authority:ecology",
        idempotency_key=key or f"ecology:weather-rain-crop-recovery:{weather_event_id}:{crop_ref}:{revision}:v1",
        expected_revisions={stream: store.get_stream_head(stream)},
        read_set_revisions={stream: store.get_stream_head(stream)},
        causation_id=weather_event_id,
        correlation_id="corr:inf3w",
        source_ref=weather_event_id,
        submitted_at="2026-08-28T13:00:00Z",
        payload={"visibility_scope": "project", "weather_event_id": weather_event_id, "target_region_ref": TARGET_REGION},
    )


def _damage_crop(store) -> None:
    authority = EcologyHazardAuthority(store=store)
    stream = f"gameplay:ecology:{TARGET_REGION}"
    result = authority.advance_drought_process(
        envelope=GameplayCommandEnvelope(
            command_id="inf3w:damage",
            command_type="gameplay.ecology.drought_process.advance",
            command_version=1,
            principal_ref="authority:ecology",
            idempotency_key="inf3w:damage",
            expected_revisions={stream: store.get_stream_head(stream)},
            causation_id="cause:inf3w:damage",
            correlation_id="corr:inf3w",
            source_ref="authority:ecology",
            submitted_at="2026-08-28T13:00:00Z",
            payload={"visibility_scope": "project", "tick": 1},
        ),
        policy=EcologyDroughtProcessPolicy(),
        region_ref=TARGET_REGION,
    )
    assert result.committed


def test_inf3w_rain_recovers_one_unique_damaged_crop() -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:rain")
    _damage_crop(store)
    crop_ref = f"crop:{TARGET_REGION}:wheat"
    result = EcologyHazardAuthority(store=store).recover_rain_crop_health(
        envelope=_request(store, weather_event_id, crop_ref)
    )
    assert result.committed, result.failure
    event = store.read_stream(f"gameplay:ecology:{TARGET_REGION}")[-1]
    assert event.event_type == "gameplay.ecology.crop.recorded"
    assert event.payload["row_ref"] == "ecology:weather-rain-crop-recovery@1"
    assert event.payload["recovery_delta"] == 5
    assert event.payload["record"]["health"] == 100


def test_inf3w_wrong_weather_or_missing_crop_is_zero_write() -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:drought")
    before = store.export_snapshot()
    denied = EcologyHazardAuthority(store=store).recover_rain_crop_health(
        envelope=_request(store, weather_event_id, f"crop:{TARGET_REGION}:wheat")
    )
    assert not denied.committed
    assert store.export_snapshot() == before


def test_inf3w_duplicate_changed_duplicate_and_replay_are_bounded() -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:rain")
    _damage_crop(store)
    authority = EcologyHazardAuthority(store=store)
    request = _request(store, weather_event_id, f"crop:{TARGET_REGION}:wheat")
    first = authority.recover_rain_crop_health(envelope=request)
    assert first.committed
    before = store.export_snapshot()
    duplicate = authority.recover_rain_crop_health(envelope=request)
    changed = authority.recover_rain_crop_health(envelope=request.model_copy(update={"correlation_id": "corr:changed"}))
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed
    assert store.export_snapshot() == before
    full = authority.regional_replay()
    tail = authority.regional_replay(checkpoint_at=first.committed_event_ids and 1)
    assert full == tail


def test_inf3w_successful_replay_accepts_the_committed_predicate_partition() -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:rain")
    _damage_crop(store)
    authority = EcologyHazardAuthority(store=store)
    result = authority.recover_rain_crop_health(
        envelope=_request(store, weather_event_id, f"crop:{TARGET_REGION}:wheat")
    )
    assert result.committed
    assert authority.regional_projection(scope="authority")["crops"]


def test_inf3w_invalid_privacy_scope_is_zero_write() -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:rain")
    _damage_crop(store)
    request = _request(store, weather_event_id, f"crop:{TARGET_REGION}:wheat").model_copy(
        update={"payload": {"visibility_scope": "authority_only", "weather_event_id": weather_event_id, "target_region_ref": TARGET_REGION}},
        deep=True,
    )
    before = store.export_snapshot()
    result = EcologyHazardAuthority(store=store).recover_rain_crop_health(envelope=request)
    assert not result.committed
    assert store.export_snapshot() == before


def test_inf3w_malformed_privacy_scope_is_zero_write() -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:rain")
    _damage_crop(store)
    request = _request(store, weather_event_id, f"crop:{TARGET_REGION}:wheat").model_copy(
        update={"payload": {"visibility_scope": "private_evidence", "weather_event_id": weather_event_id, "target_region_ref": TARGET_REGION}},
        deep=True,
    )
    before = store.export_snapshot()
    result = EcologyHazardAuthority(store=store).recover_rain_crop_health(envelope=request)
    assert not result.committed
    assert result.failure and result.failure.error_code == "rain_crop_recovery_privacy_denied"
    assert store.export_snapshot() == before


def test_inf3w_caller_source_ref_mismatch_is_zero_write() -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:rain")
    _damage_crop(store)
    request = _request(store, weather_event_id, f"crop:{TARGET_REGION}:wheat").model_copy(
        update={"source_ref": "authority:ecology"},
        deep=True,
    )
    before = store.export_snapshot()
    result = EcologyHazardAuthority(store=store).recover_rain_crop_health(envelope=request)
    assert not result.committed
    assert result.failure and result.failure.error_code == "rain_crop_recovery_reference_invalid"
    assert store.export_snapshot() == before


def test_inf3w_causation_mismatch_is_zero_write() -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:rain")
    _damage_crop(store)
    request = _request(store, weather_event_id, f"crop:{TARGET_REGION}:wheat").model_copy(
        update={"causation_id": "cause:forged"},
        deep=True,
    )
    before = store.export_snapshot()
    result = EcologyHazardAuthority(store=store).recover_rain_crop_health(envelope=request)
    assert not result.committed
    assert result.failure and result.failure.error_code == "rain_crop_recovery_reference_invalid"
    assert store.export_snapshot() == before


def test_inf3w_changed_binding_under_existing_key_is_zero_write() -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:rain")
    _damage_crop(store)
    authority = EcologyHazardAuthority(store=store)
    request = _request(store, weather_event_id, f"crop:{TARGET_REGION}:wheat")
    first = authority.recover_rain_crop_health(envelope=request)
    assert first.committed
    before = store.export_snapshot()
    changed = authority.recover_rain_crop_health(
        envelope=request.model_copy(
            update={"payload": {**request.payload, "target_region_ref": SOURCE_REGION}},
            deep=True,
        )
    )
    assert not changed.committed
    assert store.export_snapshot() == before


def test_inf3w_catalog_pins_only_the_exact_ecology_recovery_operation() -> None:
    contract = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:ecology-weather-rain-crop-recovery@1",
        contract_kind="ecology_consumer",
    )
    assert contract.owner_ref == "authority:ecology"
    assert contract.stream_patterns == ("gameplay:ecology:{region_ref}",)
    assert contract.event_types == ("gameplay.ecology.crop.recorded",)
    assert contract.projection_scope == "project"


def test_inf3w_regional_replay_rejects_forged_weather_provenance() -> None:
    store, weather_event_id, _ = _seed(source_weather_ref="weather:rain")
    _damage_crop(store)
    authority = EcologyHazardAuthority(store=store)
    result = authority.recover_rain_crop_health(
        envelope=_request(store, weather_event_id, f"crop:{TARGET_REGION}:wheat")
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
    with pytest.raises(ValueError, match="rain_crop_recovery_replay_provenance_invalid"):
        authority.regional_projection(scope="authority")
    with pytest.raises(ValueError, match="rain_crop_recovery_replay_provenance_invalid"):
        authority.regional_replay()
    with pytest.raises(ValueError, match="rain_crop_recovery_replay_provenance_invalid"):
        authority.regional_replay(checkpoint_at=1)
