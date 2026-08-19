from __future__ import annotations

from app.gameplay.ecology_runtime import EcologyDroughtProcessPolicy, EcologyHazardAuthority
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.gameplay.survival_runtime import SurvivalAuthority
from test_infra_weather_front_survival_cold import (
    PROFILE_REF,
    SOURCE_REGION,
    TARGET_REGION,
    WORLD_REF,
    _command,
    _seed,
)


def _drought_command(
    store: GameplayEventStore,
    weather_event_id: str,
    region_assignment_event_id: str,
    *,
    key: str | None = None,
    survival_revision: int = 0,
    ecology_revision: int | None = None,
    population_revision: int | None = None,
    visibility_scope: str = "project",
) -> GameplayCommandEnvelope:
    idempotency_key = key or f"weather-front-dehydration:{weather_event_id}:{PROFILE_REF}:v1"
    return _command(
        store,
        weather_event_id,
        region_assignment_event_id,
        key=idempotency_key,
        survival_revision=survival_revision,
        ecology_revision=ecology_revision,
        population_revision=population_revision,
        visibility_scope=visibility_scope,
    ).model_copy(
        update={"command_type": "gameplay.survival.apply_weather_front_dehydration"}
    )


def test_weather_front_drought_survival_owner_commits_dehydration_state_and_receipt() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:drought")
    before = tuple(store.read_events())

    result = SurvivalAuthority(store=store).apply_weather_front_dehydration_exposure(
        command=_drought_command(store, weather_event_id, assignment_event_id)
    )

    survival_events = store.read_stream(f"gameplay:survival:{PROFILE_REF}")
    assert result.committed
    assert result.transaction_id
    assert len(result.committed_event_ids) == 2
    assert tuple(store.read_events()[: len(before)]) == before
    assert [event.event_type for event in survival_events] == [
        "gameplay.survival.state_applied",
        "gameplay.survival.obligation_opened",
    ]
    assert survival_events[0].payload["state"]["state_ref"] == "state:dehydrated"
    assert survival_events[0].payload["state"]["effect_ref"] == "effect:dehydration_exposure"
    assert survival_events[0].payload["source_evidence_refs"] == [weather_event_id, assignment_event_id]
    assert all(event.event_id in result.committed_event_ids for event in survival_events)


def test_weather_front_drought_rejects_missing_or_wrong_source_without_write() -> None:
    store, _, assignment_event_id = _seed(source_weather_ref="weather:drought")
    before = tuple(store.read_events())

    missing = SurvivalAuthority(store=store).apply_weather_front_dehydration_exposure(
        command=_drought_command(store, "event:missing", assignment_event_id)
    )

    assert missing.failure is not None
    assert tuple(store.read_events()) == before

    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:rain")
    before = tuple(store.read_events())
    wrong_weather = SurvivalAuthority(store=store).apply_weather_front_dehydration_exposure(
        command=_drought_command(store, weather_event_id, assignment_event_id)
    )

    assert wrong_weather.failure is not None
    assert tuple(store.read_events()) == before


def test_weather_front_drought_rejects_assignment_mismatch_and_nonproject_scope_without_write() -> None:
    store, weather_event_id, assignment_event_id = _seed(
        source_weather_ref="weather:drought", assigned_region_ref=SOURCE_REGION
    )
    before = tuple(store.read_events())

    mismatch = SurvivalAuthority(store=store).apply_weather_front_dehydration_exposure(
        command=_drought_command(store, weather_event_id, assignment_event_id)
    )

    assert mismatch.failure is not None
    assert tuple(store.read_events()) == before

    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:drought")
    before = tuple(store.read_events())
    private = SurvivalAuthority(store=store).apply_weather_front_dehydration_exposure(
        command=_drought_command(
            store, weather_event_id, assignment_event_id, visibility_scope="authority_only"
        )
    )

    assert private.failure is not None
    assert tuple(store.read_events()) == before


def test_weather_front_drought_rejects_stale_ecology_population_and_survival_revisions_without_write() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:drought")
    before = tuple(store.read_events())
    authority = SurvivalAuthority(store=store)

    stale_ecology = authority.apply_weather_front_dehydration_exposure(
        command=_drought_command(store, weather_event_id, assignment_event_id, ecology_revision=5)
    )
    stale_population = authority.apply_weather_front_dehydration_exposure(
        command=_drought_command(
            store,
            weather_event_id,
            assignment_event_id,
            key=f"weather-front-dehydration:{weather_event_id}:{PROFILE_REF}:population:v1",
            population_revision=1,
        )
    )
    stale_survival = authority.apply_weather_front_dehydration_exposure(
        command=_drought_command(
            store,
            weather_event_id,
            assignment_event_id,
            key=f"weather-front-dehydration:{weather_event_id}:{PROFILE_REF}:survival:v1",
            survival_revision=1,
        )
    )

    assert all(result.failure is not None for result in (stale_ecology, stale_population, stale_survival))
    assert tuple(store.read_events()) == before


def test_weather_front_drought_exact_and_changed_duplicate_have_fixed_idempotency_boundary() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:drought")
    authority = SurvivalAuthority(store=store)
    command = _drought_command(store, weather_event_id, assignment_event_id)
    first = authority.apply_weather_front_dehydration_exposure(command=command)
    before = tuple(store.read_events())

    duplicate = authority.apply_weather_front_dehydration_exposure(command=command)
    changed = authority.apply_weather_front_dehydration_exposure(
        command=command.model_copy(
            update={
                "payload": {
                    **command.payload,
                    "region_assignment_event_id": "event:forged",
                }
            }
        )
    )

    assert first.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert changed.failure is not None
    assert tuple(store.read_events()) == before


def test_weather_front_drought_outbox_is_project_scoped_and_redacted() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:drought")

    assert SurvivalAuthority(store=store).apply_weather_front_dehydration_exposure(
        command=_drought_command(store, weather_event_id, assignment_event_id)
    ).committed

    outbox = store.list_outbox()[-1]
    assert outbox.audience == "project"
    assert "weather_event_id" not in outbox.payload_projection
    assert "region_assignment_event_id" not in outbox.payload_projection


def test_weather_front_drought_full_and_checkpoint_tail_replay_match() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:drought")
    assert SurvivalAuthority(store=store).apply_weather_front_dehydration_exposure(
        command=_drought_command(store, weather_event_id, assignment_event_id)
    ).committed
    events = store.read_events()
    replay = GameplayProjectionReplay(
        projector_id="infra-weather-front-survival-dehydration", projector_version="1"
    )
    checkpoint = replay.create_checkpoint(events[:-2])

    assert replay.full_replay(events).projection_hash == replay.checkpoint_plus_tail_replay(
        checkpoint, events[-2:]
    ).projection_hash


def test_drought_process_advanced_is_not_a_weather_front_source_and_writes_nothing() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:drought")
    ecology = EcologyHazardAuthority(store=store)
    stream_id = ecology.ecology_stream_id(region_ref=SOURCE_REGION)
    drought_process = ecology.advance_drought_process(
        envelope=GameplayCommandEnvelope(
            command_id="command:weather-survival:drought-process",
            command_type="gameplay.ecology.drought_process.advance",
            command_version=1,
            principal_ref="authority:ecology",
            idempotency_key="weather-survival:drought-process",
            expected_revisions={stream_id: store.get_stream_head(stream_id)},
            causation_id=weather_event_id,
            correlation_id="corr:weather-survival",
            source_ref="authority:ecology",
            submitted_at="2026-08-17T00:00:00Z",
            payload={"visibility_scope": "project", "tick": 3},
        ),
        policy=EcologyDroughtProcessPolicy(),
        region_ref=SOURCE_REGION,
    )
    assert drought_process.committed
    before = tuple(store.read_events())

    result = SurvivalAuthority(store=store).apply_weather_front_dehydration_exposure(
        command=_drought_command(
            store,
            drought_process.committed_event_ids[-1],
            assignment_event_id,
            key=f"weather-front-dehydration:{drought_process.committed_event_ids[-1]}:{PROFILE_REF}:v1",
            ecology_revision=store.get_stream_head(stream_id),
        )
    )

    assert result.failure is not None
    assert tuple(store.read_events()) == before


def test_weather_front_drought_has_no_compensation_or_fanout_event_vector() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:drought")
    result = SurvivalAuthority(store=store).apply_weather_front_dehydration_exposure(
        command=_drought_command(store, weather_event_id, assignment_event_id)
    )

    assert result.committed
    assert [event.event_type for event in store.read_stream(f"gameplay:survival:{PROFILE_REF}")] == [
        "gameplay.survival.state_applied",
        "gameplay.survival.obligation_opened",
    ]
    assert not hasattr(SurvivalAuthority, "compensate_weather_front_dehydration_exposure")
    assert TARGET_REGION not in {event.stream_id for event in store.read_events() if event.event_id in result.committed_event_ids}
