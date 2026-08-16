from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.survival_runtime import SurvivalAuthority
from test_infra_weather_front_survival_cold import PROFILE_REF, _command, _seed


def _heat_command(
    store: GameplayEventStore,
    weather_event_id: str,
    assignment_event_id: str,
    *,
    key: str = "weather-survival:heat",
    survival_revision: int = 0,
    ecology_revision: int | None = None,
    population_revision: int | None = None,
    visibility_scope: str = "project",
):
    return _command(
        store,
        weather_event_id,
        assignment_event_id,
        key=key,
        survival_revision=survival_revision,
        ecology_revision=ecology_revision,
        population_revision=population_revision,
        visibility_scope=visibility_scope,
    ).model_copy(
        update={"command_type": "gameplay.survival.apply_weather_front_heat"}
    )


def test_weather_front_heat_survival_owner_commits_existing_state_events() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:heat")

    result = SurvivalAuthority(store=store).apply_weather_front_heat_exposure(
        command=_heat_command(store, weather_event_id, assignment_event_id)
    )

    assert result.committed
    assert [event.event_type for event in store.read_stream(f"gameplay:survival:{PROFILE_REF}")] == [
        "gameplay.survival.state_applied",
        "gameplay.survival.obligation_opened",
    ]
    state = store.read_stream(f"gameplay:survival:{PROFILE_REF}")[0].payload["state"]
    assert state["state_ref"] == "state:overheated"
    assert state["effect_ref"] == "effect:heat_exposure"
    assert store.read_stream(f"gameplay:survival:{PROFILE_REF}")[1].payload["due_tick"] == 5


def test_weather_front_heat_rejects_wrong_weather_without_write() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:frost")
    before = tuple(store.read_events())

    result = SurvivalAuthority(store=store).apply_weather_front_heat_exposure(
        command=_heat_command(store, weather_event_id, assignment_event_id, key="weather-survival:frost")
    )

    assert result.failure is not None
    assert tuple(store.read_events()) == before


def test_weather_front_heat_rejects_forged_source_without_write() -> None:
    store, _, assignment_event_id = _seed(source_weather_ref="weather:heat")
    before = tuple(store.read_events())

    result = SurvivalAuthority(store=store).apply_weather_front_heat_exposure(
        command=_heat_command(store, "event:missing", assignment_event_id, key="weather-survival:missing")
    )

    assert result.failure is not None
    assert tuple(store.read_events()) == before


def test_weather_front_heat_rejects_nonproject_scope_without_write() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:heat")
    before = tuple(store.read_events())

    result = SurvivalAuthority(store=store).apply_weather_front_heat_exposure(
        command=_heat_command(
            store,
            weather_event_id,
            assignment_event_id,
            key="weather-survival:private",
            visibility_scope="authority_only",
        )
    )

    assert result.failure is not None
    assert tuple(store.read_events()) == before


def test_weather_front_heat_rejects_stale_ecology_revision_without_write() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:heat")
    before = tuple(store.read_events())

    stale_source = SurvivalAuthority(store=store).apply_weather_front_heat_exposure(
        command=_heat_command(
            store,
            weather_event_id,
            assignment_event_id,
            key="weather-survival:stale-source",
            ecology_revision=5,
        )
    )

    assert stale_source.failure is not None
    assert tuple(store.read_events()) == before


def test_weather_front_heat_rejects_stale_population_revision_without_write() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:heat")
    before = tuple(store.read_events())

    stale_population = SurvivalAuthority(store=store).apply_weather_front_heat_exposure(
        command=_heat_command(
            store,
            weather_event_id,
            assignment_event_id,
            key="weather-survival:stale-population",
            population_revision=1,
        )
    )

    assert stale_population.failure is not None
    assert tuple(store.read_events()) == before


def test_weather_front_heat_rejects_stale_survival_revision_without_write() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:heat")
    before = tuple(store.read_events())

    result = SurvivalAuthority(store=store).apply_weather_front_heat_exposure(
        command=_heat_command(
            store,
            weather_event_id,
            assignment_event_id,
            key="weather-survival:stale-survival",
            survival_revision=1,
        )
    )

    assert result.failure is not None
    assert tuple(store.read_events()) == before


def test_weather_front_heat_duplicate_is_idempotent() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:heat")
    authority = SurvivalAuthority(store=store)
    command = _heat_command(store, weather_event_id, assignment_event_id)
    assert authority.apply_weather_front_heat_exposure(command=command).committed
    before = tuple(store.read_events())

    duplicate = authority.apply_weather_front_heat_exposure(command=command)

    assert duplicate.idempotency_status == "duplicate_replayed"
    assert tuple(store.read_events()) == before


def test_weather_front_heat_rejects_changed_duplicate_without_write() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:heat")
    authority = SurvivalAuthority(store=store)
    command = _heat_command(store, weather_event_id, assignment_event_id)
    assert authority.apply_weather_front_heat_exposure(command=command).committed
    before = tuple(store.read_events())
    changed = command.model_copy(
        update={
            "payload": {
                **command.payload,
                "region_assignment_event_id": "event:forged",
            }
        }
    )

    result = authority.apply_weather_front_heat_exposure(command=changed)

    assert result.failure is not None
    assert tuple(store.read_events()) == before


def test_weather_front_heat_outbox_and_replay_are_project_scoped() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:heat")
    result = SurvivalAuthority(store=store).apply_weather_front_heat_exposure(
        command=_heat_command(store, weather_event_id, assignment_event_id, key="weather-survival:replay")
    )
    assert result.committed
    outbox = store.list_outbox()[-1]
    assert outbox.audience == "project"
    assert "weather_event_id" not in outbox.payload_projection
    assert "region_assignment_event_id" not in outbox.payload_projection

    events = store.read_events()
    replay = GameplayProjectionReplay(projector_id="infra-weather-front-survival-overheated", projector_version="1")
    checkpoint = replay.create_checkpoint(events[:-2])
    assert replay.full_replay(events).projection_hash == replay.checkpoint_plus_tail_replay(
        checkpoint, events[-2:]
    ).projection_hash


def test_weather_front_heat_rejects_private_ecology_source_without_write() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:heat")
    weather_event = store.get_event(weather_event_id)
    private_batch = build_atomic_event_batch(
        command_id="command:weather-survival:heat-private-source",
        principal_ref="authority:ecology",
        stream_id=weather_event.stream_id,
        expected_revision=store.get_stream_head(weather_event.stream_id),
        event_specs=[
            ("gameplay.ecology.weather_front.propagated", dict(weather_event.payload)),
        ],
        idempotency_key="weather-survival:heat-private-source",
        causation_id="cause:weather-survival:heat-private-source",
        correlation_id="corr:weather-survival",
    )
    private_batch = private_batch.model_copy(
        update={"events": [private_batch.events[0].model_copy(update={"visibility_policy": "authority_only"})]},
        deep=True,
    )
    private_result = store.append_batch(private_batch)
    assert private_result.committed
    before = tuple(store.read_events())

    result = SurvivalAuthority(store=store).apply_weather_front_heat_exposure(
        command=_heat_command(
            store,
            private_result.committed_event_ids[0],
            assignment_event_id,
            key="weather-survival:heat-private",
        )
    )

    assert result.failure is not None
    assert tuple(store.read_events()) == before
