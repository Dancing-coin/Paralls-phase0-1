from __future__ import annotations

from dataclasses import replace

import pytest

from app.gameplay.ecology_runtime import (
    CropRecord,
    EcologyHazardAuthority,
    EcologyWeatherFrontPropagationPolicy,
    EnvironmentRegion,
    EnvironmentalState,
    HazardRecord,
    ResourceNode,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, GovernedAuthorityContractError
from app.gameplay.organization_government_runtime import GovernmentAuthority, GovernmentDroughtAdvisoryIntentV1
from app.gameplay.shared_contracts import GameplayCommandEnvelope


SOURCE_REGION = "region:drought-advisory:source"
TARGET_REGION = "region:drought-advisory:target"
JURISDICTION = "jurisdiction:drought-advisory:target"
GOVERNMENT_STREAM = f"gameplay:government:advisory:{JURISDICTION}"


def _snapshot(store: GameplayEventStore) -> dict[str, object]:
    exported = store.export_snapshot()
    return {key: exported[key] for key in ("events", "outbox", "idempotency")}


def _record_bundle(authority: EcologyHazardAuthority, *, region_ref: str, neighbors: tuple[str, ...], weather_ref: str) -> None:
    stream_id = authority.ecology_stream_id(region_ref=region_ref)
    result = authority.record_region_bundle(
        envelope=GameplayCommandEnvelope(
            command_id=f"command:{region_ref}:bundle",
            command_type="gameplay.ecology.region_bundle.record",
            command_version=1,
            principal_ref="authority:ecology",
            idempotency_key=f"ecology:{region_ref}:bundle",
            expected_revisions={stream_id: 0},
            causation_id=f"cause:{region_ref}:bundle",
            correlation_id=f"corr:{region_ref}:bundle",
            source_ref="authority:ecology",
            submitted_at="2026-08-26T00:00:00Z",
            payload={"visibility_scope": "project"},
        ),
        region=EnvironmentRegion(
            region_ref=region_ref,
            climate_profile_ref="climate:temperate",
            biome_tags=("biome:field",),
            jurisdiction_ref=JURISDICTION if region_ref == TARGET_REGION else "jurisdiction:drought-advisory:source",
            neighbor_region_refs=neighbors,
            revision=0,
        ),
        environment=EnvironmentalState(
            region_ref=region_ref,
            temperature_centi_c=180,
            moisture_basis_points=2_000,
            weather_ref=weather_ref,
            revision=0,
        ),
        resource=ResourceNode(
            node_ref=f"resource:{region_ref}:water",
            region_ref=region_ref,
            substance_ref="substance:water",
            quantity=80,
            regeneration_per_tick=1,
            revision=0,
        ),
        crop=CropRecord(
            crop_ref=f"crop:{region_ref}:grain",
            region_ref=region_ref,
            plot_ref=f"plot:{region_ref}",
            health=85,
            growth_basis_points=4_000,
            revision=0,
            owner_ref="authority:crop",
        ),
        hazard=HazardRecord(
            hazard_ref=f"hazard:{region_ref}:drought",
            region_ref=region_ref,
            effect_ref="effect:drought",
            severity_basis_points=6_000,
            due_tick=4,
            duration_ticks=2,
            semantic_revision="semantic:1",
            rule_revision="rule:1",
            policy_revision="policy:1",
            idempotency_key=f"hazard:{region_ref}:drought",
        ),
    )
    assert result.committed, result.failure


def _setup(*, source_weather_ref: str = "weather:drought") -> tuple[GameplayEventStore, EcologyHazardAuthority, GovernmentAuthority, str]:
    store = GameplayEventStore()
    ecology = EcologyHazardAuthority(store=store)
    _record_bundle(ecology, region_ref=SOURCE_REGION, neighbors=(TARGET_REGION,), weather_ref=source_weather_ref)
    _record_bundle(ecology, region_ref=TARGET_REGION, neighbors=(SOURCE_REGION,), weather_ref="weather:clear")
    source_stream = ecology.ecology_stream_id(region_ref=SOURCE_REGION)
    target_stream = ecology.ecology_stream_id(region_ref=TARGET_REGION)
    propagation = ecology.propagate_weather_front(
        envelope=GameplayCommandEnvelope(
            command_id="command:drought-advisory:propagate",
            command_type="gameplay.ecology.weather_front.propagate",
            command_version=1,
            principal_ref="authority:ecology",
            idempotency_key="drought-advisory:propagate",
            expected_revisions={source_stream: store.get_stream_head(source_stream), target_stream: store.get_stream_head(target_stream)},
            causation_id="cause:drought-advisory:propagate",
            correlation_id="corr:drought-advisory:propagate",
            source_ref="authority:ecology",
            submitted_at="2026-08-26T00:00:00Z",
            payload={"visibility_scope": "project", "tick": 7},
        ),
        policy=EcologyWeatherFrontPropagationPolicy(),
        source_region_ref=SOURCE_REGION,
        target_region_ref=TARGET_REGION,
    )
    assert propagation.committed, propagation.failure
    weather_event_id = next(
        event_id
        for event_id in propagation.committed_event_ids
        if store.get_event(event_id).event_type == "gameplay.ecology.weather_front.propagated"
    )
    return store, ecology, GovernmentAuthority(store=store), weather_event_id


def _intent(store: GameplayEventStore, weather_event_id: str, **updates: object) -> GovernmentDroughtAdvisoryIntentV1:
    weather = store.get_event(weather_event_id)
    values: dict[str, object] = {
        "weather_event_id": weather_event_id,
        "expected_ecology_revision": weather.stream_revision,
        "expected_region_revision": int(weather.payload["target_region_revision"]),
        "expected_government_revision": store.get_stream_head(GOVERNMENT_STREAM),
        "command_id": "command:government:drought-advisory:1",
        "idempotency_key": "pending",
        "causation_id": weather_event_id,
        "correlation_id": "corr:government:drought-advisory:1",
        "submitted_at": "2026-08-26T00:00:00Z",
    }
    values.update(updates)
    values["idempotency_key"] = (
        f"government:drought-advisory:{values['weather_event_id']}:{values['expected_ecology_revision']}:"
        f"{TARGET_REGION}:{values['expected_region_revision']}:{JURISDICTION}:"
        f"{values['expected_government_revision']}:descriptor:government-drought-advisory@1"
    )
    return GovernmentDroughtAdvisoryIntentV1.model_validate(values)


def test_drought_weather_front_issues_one_fixed_government_advisory_and_receipt() -> None:
    store, _ecology, government, weather_event_id = _setup()

    result = government.issue_drought_advisory(_intent(store, weather_event_id))

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.government.drought_advisory_issued"
    assert event.stream_id == GOVERNMENT_STREAM
    assert event.visibility_policy == "project"
    assert event.payload["jurisdiction_ref"] == JURISDICTION
    assert event.payload["target_region_ref"] == TARGET_REGION
    assert event.payload["weather_event_id"] == weather_event_id
    assert event.payload["weather_ref"] == "weather:drought"
    view = government.drought_advisory_view_for(jurisdiction_ref=JURISDICTION)
    assert view.advisory_refs == (event.payload["advisory_ref"],)
    assert view.advisory_source_vectors[event.payload["advisory_ref"]] == {
        event.payload["ecology_stream_id"]: event.payload["ecology_event_revision"],
        GOVERNMENT_STREAM: 1,
    }
    assert tuple(government.drought_advisory_receipt_for(result=result, scope="project").committed_event_ids) == tuple(result.committed_event_ids)


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("wrong_weather", "government_drought_advisory_source_invalid"),
        ("private", "government_drought_advisory_source_private"),
        ("stale_ecology", "government_drought_advisory_source_revision_conflict"),
        ("stale_region", "government_drought_advisory_region_revision_conflict"),
        ("stale_government", "revision_conflict"),
    ],
)
def test_drought_advisory_source_privacy_and_revision_fences_are_zero_write(mutation: str, error: str) -> None:
    store, ecology, government, weather_event_id = _setup()
    updates: dict[str, object] = {}
    if mutation == "wrong_weather":
        event = store.get_event(weather_event_id)
        store._events_by_id[weather_event_id] = event.model_copy(update={"payload": {**event.payload, "weather_ref": "weather:rain"}}, deep=True)
    elif mutation == "private":
        event = store.get_event(weather_event_id)
        store._events_by_id[weather_event_id] = event.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
    elif mutation == "stale_ecology":
        source_stream = ecology.ecology_stream_id(region_ref=SOURCE_REGION)
        target_stream = ecology.ecology_stream_id(region_ref=TARGET_REGION)
        assert ecology.propagate_weather_front(
            envelope=GameplayCommandEnvelope(
                command_id="command:drought-advisory:advance",
                command_type="gameplay.ecology.weather_front.propagate",
                command_version=1,
                principal_ref="authority:ecology",
                idempotency_key="drought-advisory:advance",
                expected_revisions={source_stream: store.get_stream_head(source_stream), target_stream: store.get_stream_head(target_stream)},
                causation_id="cause:drought-advisory:advance",
                correlation_id="corr:drought-advisory:advance",
                source_ref="authority:ecology",
                submitted_at="2026-08-26T00:01:00Z",
                payload={"visibility_scope": "project", "tick": 8},
            ),
            policy=EcologyWeatherFrontPropagationPolicy(),
            source_region_ref=SOURCE_REGION,
            target_region_ref=TARGET_REGION,
        ).committed
    elif mutation == "stale_region":
        updates["expected_region_revision"] = 1
    else:
        updates["expected_government_revision"] = 1
    before = _snapshot(store)

    result = government.issue_drought_advisory(_intent(store, weather_event_id, **updates))

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == error
    assert _snapshot(store) == before


def test_drought_advisory_catalog_mismatch_is_zero_write(monkeypatch) -> None:
    store, _ecology, government, weather_event_id = _setup()
    before = _snapshot(store)

    def reject_contract(**_kwargs: object) -> None:
        raise GovernedAuthorityContractError("governed_authority_contract_event_mismatch")

    monkeypatch.setattr(GovernedAuthorityContractCatalog, "require_operation", reject_contract)
    result = government.issue_drought_advisory(_intent(store, weather_event_id))

    assert not result.committed
    assert result.failure is not None and result.failure.error_code == "governed_authority_contract_event_mismatch"
    assert _snapshot(store) == before


def test_drought_advisory_duplicate_receipt_and_checkpoint_tail_replay_are_fixed() -> None:
    store, _ecology, government, weather_event_id = _setup()
    intent = _intent(store, weather_event_id)
    first = government.issue_drought_advisory(intent)
    assert first.committed
    before = _snapshot(store)

    duplicate = government.issue_drought_advisory(intent)
    changed = government.issue_drought_advisory(
        _intent(
            store,
            weather_event_id,
            expected_government_revision=intent.expected_government_revision,
            correlation_id="corr:government:drought-advisory:changed",
        )
    )
    full = government.drought_advisory_view_for(jurisdiction_ref=JURISDICTION)
    tail = government.drought_advisory_view_for(jurisdiction_ref=JURISDICTION, checkpoint_at=0)

    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert not changed.committed and changed.failure is not None
    assert changed.failure.error_code == "idempotency_key_reused"
    assert full == tail
    assert _snapshot(store) == before
    assert not hasattr(government, "revoke_drought_advisory")
    assert not hasattr(government, "enforce_drought_advisory")


def test_drought_advisory_exact_duplicate_replays_after_ecology_source_advances() -> None:
    store, ecology, government, weather_event_id = _setup()
    intent = _intent(store, weather_event_id)
    assert government.issue_drought_advisory(intent).committed
    source_stream = ecology.ecology_stream_id(region_ref=SOURCE_REGION)
    target_stream = ecology.ecology_stream_id(region_ref=TARGET_REGION)
    assert ecology.propagate_weather_front(
        envelope=GameplayCommandEnvelope(
            command_id="command:drought-advisory:post-commit-advance",
            command_type="gameplay.ecology.weather_front.propagate",
            command_version=1,
            principal_ref="authority:ecology",
            idempotency_key="drought-advisory:post-commit-advance",
            expected_revisions={source_stream: store.get_stream_head(source_stream), target_stream: store.get_stream_head(target_stream)},
            causation_id="cause:drought-advisory:post-commit-advance",
            correlation_id="corr:drought-advisory:post-commit-advance",
            source_ref="authority:ecology",
            submitted_at="2026-08-26T00:02:00Z",
            payload={"visibility_scope": "project", "tick": 9},
        ),
        policy=EcologyWeatherFrontPropagationPolicy(),
        source_region_ref=SOURCE_REGION,
        target_region_ref=TARGET_REGION,
    ).committed
    before = _snapshot(store)

    duplicate = government.issue_drought_advisory(intent)

    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert _snapshot(store) == before
