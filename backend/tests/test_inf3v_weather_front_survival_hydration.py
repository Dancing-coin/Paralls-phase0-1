from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.survival_runtime import SurvivalAuthority
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from test_infra_weather_front_survival_cold import (
    PROFILE_REF,
    SOURCE_REGION,
    TARGET_REGION,
    WORLD_REF,
    _command,
    _seed,
)


def _rain_command(store: GameplayEventStore, weather_event_id: str, assignment_event_id: str, *, key: str | None = None) -> GameplayCommandEnvelope:
    return _command(
        store,
        weather_event_id,
        assignment_event_id,
        key=key or f"weather-front-hydration:{weather_event_id}:{PROFILE_REF}:v1",
    ).model_copy(update={"command_type": "gameplay.survival.apply_weather_front_hydration"})


def test_inf3v_rain_weather_front_commits_hydrated_state_and_expiry() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:rain")
    result = SurvivalAuthority(store=store).apply_weather_front_rain_hydration(
        command=_rain_command(store, weather_event_id, assignment_event_id)
    )
    assert result.committed
    events = store.read_stream(f"gameplay:survival:{PROFILE_REF}")
    assert [event.event_type for event in events] == [
        "gameplay.survival.state_applied",
        "gameplay.survival.obligation_opened",
    ]
    assert events[0].payload["state"]["state_ref"] == "state:hydrated"
    assert events[0].payload["state"]["effect_ref"] == "effect:hydration"
    assert events[0].visibility_policy == "project"


def test_inf3v_wrong_weather_and_drought_process_substitute_are_zero_write() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:drought")
    before = store.export_snapshot()
    result = SurvivalAuthority(store=store).apply_weather_front_rain_hydration(
        command=_rain_command(store, weather_event_id, assignment_event_id)
    )
    assert not result.committed
    assert result.failure and result.failure.error_code == "weather_front_hydration_evidence_invalid"
    assert store.export_snapshot() == before


def test_inf3v_exact_duplicate_and_changed_duplicate_are_zero_write() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:rain")
    authority = SurvivalAuthority(store=store)
    command = _rain_command(store, weather_event_id, assignment_event_id)
    first = authority.apply_weather_front_rain_hydration(command=command)
    assert first.committed
    before = store.export_snapshot()
    duplicate = authority.apply_weather_front_rain_hydration(command=command)
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    changed = authority.apply_weather_front_rain_hydration(
        command=command.model_copy(update={"payload": {**command.payload, "region_assignment_event_id": "event:forged"}})
    )
    assert not changed.committed
    assert changed.failure is not None
    assert store.export_snapshot() == before


def test_inf3v_stale_revision_private_scope_and_replay_are_bounded() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:rain")
    authority = SurvivalAuthority(store=store)
    stale = authority.apply_weather_front_rain_hydration(
        command=_rain_command(store, weather_event_id, assignment_event_id, key=f"weather-front-hydration:{weather_event_id}:{PROFILE_REF}:stale:v1").model_copy(
            update={"read_set_revisions": {f"gameplay:ecology:{SOURCE_REGION}": 99, f"population:{WORLD_REF}": 99}}
        )
    )
    private = authority.apply_weather_front_rain_hydration(
        command=_rain_command(store, weather_event_id, assignment_event_id, key=f"weather-front-hydration:{weather_event_id}:{PROFILE_REF}:private:v1").model_copy(
            update={"payload": {**_rain_command(store, weather_event_id, assignment_event_id).payload, "visibility_scope": "authority_only"}}
        )
    )
    assert not stale.committed and not private.committed
    assert authority.apply_weather_front_rain_hydration(command=_rain_command(store, weather_event_id, assignment_event_id)).committed
    full = authority.projector()
    tail = authority.projector(checkpoint_at=1)
    assert full.states == tail.states
    assert full.source_revision_vector == tail.source_revision_vector
