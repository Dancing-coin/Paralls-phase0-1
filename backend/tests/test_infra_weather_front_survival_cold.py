from __future__ import annotations

from pathlib import Path

from app.character_agent.profile.registry import CharacterProfileRegistry
from app.gameplay.ecology_runtime import (
    CropRecord,
    EcologyHazardAuthority,
    EcologyWeatherFrontPropagationPolicy,
    EnvironmentalState,
    EnvironmentRegion,
    HazardRecord,
    ResourceNode,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import build_atomic_event_batch
from app.gameplay.shared_contracts import GameplayCommandEnvelope
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.models import ActivationProposal
from app.gameplay.survival_runtime import SurvivalAuthority


PROFILE_DIR = Path(__file__).resolve().parents[2] / "assets" / "characters" / "profiles"
WORLD_REF = "world:weather-survival"
PROFILE_REF = "character:char_a"
SOURCE_REGION = "region:weather-survival:source"
TARGET_REGION = "region:weather-survival:target"


def _record_bundle(
    ecology: EcologyHazardAuthority, *, region_ref: str, neighbors: tuple[str, ...], weather_ref: str
) -> str:
    result = ecology.record_region_bundle(
        envelope=GameplayCommandEnvelope(
            command_id=f"command:weather-survival:region:{region_ref}",
            command_type="gameplay.ecology.region_bundle.record",
            command_version=1,
            principal_ref="authority:ecology",
            idempotency_key=f"weather-survival:region:{region_ref}",
            expected_revisions={ecology.ecology_stream_id(region_ref=region_ref): 0},
            causation_id=f"cause:weather-survival:region:{region_ref}",
            correlation_id="corr:weather-survival",
            source_ref="authority:ecology",
            submitted_at="2026-08-16T00:00:00Z",
            payload={"visibility_scope": "project"},
        ),
        region=EnvironmentRegion(
            region_ref=region_ref,
            climate_profile_ref="climate:temperate",
            biome_tags=("biome:field",),
            jurisdiction_ref=f"jurisdiction:{region_ref}",
            neighbor_region_refs=neighbors,
            revision=0,
        ),
        environment=EnvironmentalState(
            region_ref=region_ref,
            temperature_centi_c=-50,
            moisture_basis_points=4_000,
            weather_ref=weather_ref,
            revision=0,
        ),
        resource=ResourceNode(
            node_ref=f"resource:{region_ref}:water",
            region_ref=region_ref,
            substance_ref="substance:water",
            quantity=90,
            regeneration_per_tick=2,
            revision=0,
        ),
        crop=CropRecord(
            crop_ref=f"crop:{region_ref}:wheat",
            region_ref=region_ref,
            plot_ref=f"plot:{region_ref}:1",
            health=100,
            growth_basis_points=5_000,
            revision=0,
            owner_ref="authority:crop",
        ),
        hazard=HazardRecord(
            hazard_ref=f"hazard:{region_ref}:frost",
            region_ref=region_ref,
            effect_ref="effect:frost",
            severity_basis_points=5_000,
            due_tick=3,
            duration_ticks=1,
            semantic_revision="semantic:1",
            rule_revision="rule:1",
            policy_revision="policy:1",
            idempotency_key=f"weather-survival:hazard:{region_ref}",
        ),
    )
    assert result.committed
    return result.committed_event_ids[0]


def _seed(
    *, source_weather_ref: str = "weather:frost", assigned_region_ref: str = TARGET_REGION
) -> tuple[GameplayEventStore, str, str]:
    store = GameplayEventStore()
    ecology = EcologyHazardAuthority(store=store)
    source_region_event_id = _record_bundle(
        ecology,
        region_ref=SOURCE_REGION,
        neighbors=(TARGET_REGION,),
        weather_ref=source_weather_ref,
    )
    target_region_event_id = _record_bundle(
        ecology,
        region_ref=TARGET_REGION,
        neighbors=(SOURCE_REGION,),
        weather_ref="weather:clear",
    )
    activation = ProfileActivationAuthority(
        registry=CharacterProfileRegistry.from_directory(PROFILE_DIR), store=store
    )
    assert activation.commit(
        ActivationProposal(
            proposal_id="proposal:weather-survival:activate",
            profile_ref=PROFILE_REF,
            world_ref=WORLD_REF,
            package_revision="package:weather-survival:1",
            policy_revision="policy:weather-survival:1",
            activation_reason="fixture",
            scope_grant=("project",),
            cadence_class="daily",
            expected_revisions={f"population:{WORLD_REF}": 0},
            idempotency_key="weather-survival:activate",
            correlation_id="corr:weather-survival",
            source_ref="world_runtime.activation_authority",
        )
    ).committed
    assert activation.assign_profile_region(
        command=GameplayCommandEnvelope(
            command_id="command:weather-survival:assign",
            command_type="population.activation.assign_region",
            command_version=1,
            principal_ref="world_runtime.activation_authority",
            actor_ref=PROFILE_REF,
            project_ref="project:weather-survival",
            idempotency_key="weather-survival:assign",
            expected_revisions={f"population:{WORLD_REF}": 1},
                read_set_revisions={ecology.ecology_stream_id(region_ref=assigned_region_ref): 5},
            causation_id="cause:weather-survival:assign",
            correlation_id="corr:weather-survival",
            source_ref="world_runtime.activation_authority",
            submitted_at="2026-08-16T00:00:00Z",
                payload={"region_ref": assigned_region_ref, "visibility_scope": "project"},
        ),
        world_ref=WORLD_REF,
        profile_ref=PROFILE_REF,
        region_ref=assigned_region_ref,
        region_evidence_event_id=(
            source_region_event_id
            if assigned_region_ref == SOURCE_REGION
            else target_region_event_id
        ),
    ).committed
    source_stream = ecology.ecology_stream_id(region_ref=SOURCE_REGION)
    target_stream = ecology.ecology_stream_id(region_ref=TARGET_REGION)
    assert ecology.propagate_weather_front(
        envelope=GameplayCommandEnvelope(
            command_id="command:weather-survival:front",
            command_type="gameplay.ecology.weather_front.propagate",
            command_version=1,
            principal_ref="authority:ecology",
            idempotency_key="weather-survival:front",
            expected_revisions={
                source_stream: store.get_stream_head(source_stream),
                target_stream: store.get_stream_head(target_stream),
            },
            causation_id="cause:weather-survival:front",
            correlation_id="corr:weather-survival",
            source_ref="authority:ecology",
            submitted_at="2026-08-16T00:00:00Z",
            payload={"visibility_scope": "project", "tick": 4},
        ),
        policy=EcologyWeatherFrontPropagationPolicy(),
        source_region_ref=SOURCE_REGION,
        target_region_ref=TARGET_REGION,
    ).committed
    weather_event = next(
        event
        for event in store.read_stream(source_stream)
        if event.event_type == "gameplay.ecology.weather_front.propagated"
    )
    region_assignment_event = store.read_stream(f"population:{WORLD_REF}")[-1]
    return store, weather_event.event_id, region_assignment_event.event_id


def _command(
    store: GameplayEventStore,
    weather_event_id: str,
    region_assignment_event_id: str,
    *,
    key: str = "weather-survival:cold",
    survival_revision: int = 0,
    ecology_revision: int | None = None,
    population_revision: int | None = None,
    visibility_scope: str = "project",
) -> GameplayCommandEnvelope:
    try:
        ecology_stream = store.get_event(weather_event_id).stream_id
    except KeyError:
        ecology_stream = f"gameplay:ecology:{SOURCE_REGION}"
    return GameplayCommandEnvelope(
        command_id=f"command:{key}",
        command_type="gameplay.survival.apply_weather_front_cold",
        command_version=1,
        principal_ref="actor_gameplay.survival_domain",
        actor_ref=PROFILE_REF,
        project_ref="project:weather-survival",
        idempotency_key=key,
        expected_revisions={f"gameplay:survival:{PROFILE_REF}": survival_revision},
        read_set_revisions={
            ecology_stream: store.get_stream_head(ecology_stream)
            if ecology_revision is None
            else ecology_revision,
            f"population:{WORLD_REF}": store.get_stream_head(f"population:{WORLD_REF}")
            if population_revision is None
            else population_revision,
        },
        causation_id=weather_event_id,
        correlation_id="corr:weather-survival",
        source_ref="authority:ecology",
        submitted_at="2026-08-16T00:00:00Z",
        payload={
            "world_ref": WORLD_REF,
            "weather_event_id": weather_event_id,
            "region_assignment_event_id": region_assignment_event_id,
            "visibility_scope": visibility_scope,
        },
    )


def test_weather_front_cold_survival_owner_commits_existing_state_events() -> None:
    store, weather_event_id, assignment_event_id = _seed()

    result = SurvivalAuthority(store=store).apply_weather_front_cold_exposure(
        command=_command(store, weather_event_id, assignment_event_id)
    )

    assert result.committed
    assert [event.event_type for event in store.read_stream(f"gameplay:survival:{PROFILE_REF}")] == [
        "gameplay.survival.state_applied",
        "gameplay.survival.obligation_opened",
    ]


def test_weather_front_cold_rejects_forged_source_without_write() -> None:
    store, weather_event_id, assignment_event_id = _seed()
    before = len(store.read_events())

    result = SurvivalAuthority(store=store).apply_weather_front_cold_exposure(
        command=_command(store, "event:missing", assignment_event_id)
    )

    assert result.failure is not None
    assert len(store.read_events()) == before


def test_weather_front_cold_rejects_nonproject_scope_without_write() -> None:
    store, weather_event_id, assignment_event_id = _seed()
    before = len(store.read_events())

    result = SurvivalAuthority(store=store).apply_weather_front_cold_exposure(
        command=_command(store, weather_event_id, assignment_event_id, visibility_scope="authority_only")
    )

    assert result.failure is not None
    assert len(store.read_events()) == before


def test_weather_front_cold_rejects_nonfrost_weather_without_write() -> None:
    store, weather_event_id, assignment_event_id = _seed(source_weather_ref="weather:rain")
    before = len(store.read_events())

    result = SurvivalAuthority(store=store).apply_weather_front_cold_exposure(
        command=_command(store, weather_event_id, assignment_event_id, key="weather-survival:rain")
    )

    assert result.failure is not None
    assert len(store.read_events()) == before


def test_weather_front_cold_rejects_region_mismatched_assignment_without_write() -> None:
    store, weather_event_id, assignment_event_id = _seed(assigned_region_ref=SOURCE_REGION)
    before = len(store.read_events())

    result = SurvivalAuthority(store=store).apply_weather_front_cold_exposure(
        command=_command(store, weather_event_id, assignment_event_id, key="weather-survival:mismatched-region")
    )

    assert result.failure is not None
    assert len(store.read_events()) == before


def test_weather_front_cold_duplicate_is_idempotent() -> None:
    store, weather_event_id, assignment_event_id = _seed()
    authority = SurvivalAuthority(store=store)
    command = _command(store, weather_event_id, assignment_event_id)
    assert authority.apply_weather_front_cold_exposure(command=command).committed
    before = len(store.read_events())

    duplicate = authority.apply_weather_front_cold_exposure(command=command)

    assert duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == before


def test_weather_front_cold_rejects_stale_survival_revision_without_write() -> None:
    store, weather_event_id, assignment_event_id = _seed()
    authority = SurvivalAuthority(store=store)
    assert authority.apply_weather_front_cold_exposure(
        command=_command(store, weather_event_id, assignment_event_id)
    ).committed
    before = len(store.read_events())

    stale = authority.apply_weather_front_cold_exposure(
        command=_command(store, weather_event_id, assignment_event_id, key="weather-survival:stale-target")
    )

    assert stale.failure is not None
    assert len(store.read_events()) == before


def test_weather_front_cold_rejects_stale_ecology_revision_without_write() -> None:
    store, weather_event_id, assignment_event_id = _seed()
    before = len(store.read_events())

    stale = SurvivalAuthority(store=store).apply_weather_front_cold_exposure(
        command=_command(store, weather_event_id, assignment_event_id, key="weather-survival:stale-source", ecology_revision=5)
    )

    assert stale.failure is not None
    assert len(store.read_events()) == before


def test_weather_front_cold_rejects_stale_population_revision_without_write() -> None:
    store, weather_event_id, assignment_event_id = _seed()
    before = len(store.read_events())

    stale = SurvivalAuthority(store=store).apply_weather_front_cold_exposure(
        command=_command(store, weather_event_id, assignment_event_id, key="weather-survival:stale-population", population_revision=1)
    )

    assert stale.failure is not None
    assert len(store.read_events()) == before


def test_weather_front_cold_rejects_changed_duplicate_without_write() -> None:
    store, weather_event_id, assignment_event_id = _seed()
    authority = SurvivalAuthority(store=store)
    assert authority.apply_weather_front_cold_exposure(
        command=_command(store, weather_event_id, assignment_event_id)
    ).committed
    before = len(store.read_events())
    changed = _command(store, weather_event_id, assignment_event_id).model_copy(
        update={"payload": {"world_ref": WORLD_REF, "weather_event_id": weather_event_id, "region_assignment_event_id": "event:forged", "visibility_scope": "project"}}
    )

    result = authority.apply_weather_front_cold_exposure(command=changed)

    assert result.failure is not None
    assert len(store.read_events()) == before


def test_weather_front_cold_outbox_is_project_scoped_and_redacted() -> None:
    store, weather_event_id, assignment_event_id = _seed()
    assert SurvivalAuthority(store=store).apply_weather_front_cold_exposure(
        command=_command(store, weather_event_id, assignment_event_id, key="weather-survival:outbox")
    ).committed

    outbox = store.list_outbox()[-1]

    assert outbox.audience == "project"
    assert "weather_event_id" not in outbox.payload_projection
    assert "region_assignment_event_id" not in outbox.payload_projection


def test_weather_front_cold_full_and_checkpoint_tail_replay_match() -> None:
    store, weather_event_id, assignment_event_id = _seed()
    assert SurvivalAuthority(store=store).apply_weather_front_cold_exposure(
        command=_command(store, weather_event_id, assignment_event_id, key="weather-survival:replay")
    ).committed
    events = store.read_events()
    replay = GameplayProjectionReplay(
        projector_id="infra-weather-front-survival-cold", projector_version="1"
    )
    checkpoint = replay.create_checkpoint(events[:-2])

    assert replay.full_replay(events).projection_hash == replay.checkpoint_plus_tail_replay(
        checkpoint, events[-2:]
    ).projection_hash


def test_weather_front_cold_rejects_private_ecology_source_without_write() -> None:
    store, weather_event_id, assignment_event_id = _seed()
    weather_event = store.get_event(weather_event_id)
    private_batch = build_atomic_event_batch(
        command_id="command:weather-survival:private-source",
        principal_ref="authority:ecology",
        stream_id=weather_event.stream_id,
        expected_revision=store.get_stream_head(weather_event.stream_id),
        event_specs=[
            (
                "gameplay.ecology.weather_front.propagated",
                {
                    **weather_event.payload,
                    "weather_ref": "weather:frost",
                },
            )
        ],
        idempotency_key="weather-survival:private-source",
        causation_id="cause:weather-survival:private-source",
        correlation_id="corr:weather-survival",
    )
    private_batch = private_batch.model_copy(
        update={
            "events": [
                private_batch.events[0].model_copy(
                    update={"visibility_policy": "authority_only"}
                )
            ]
        },
        deep=True,
    )
    private_result = store.append_batch(private_batch)
    assert private_result.committed
    before = len(store.read_events())

    result = SurvivalAuthority(store=store).apply_weather_front_cold_exposure(
        command=_command(
            store,
            private_result.committed_event_ids[0],
            assignment_event_id,
            key="weather-survival:private",
        )
    )

    assert result.failure is not None
    assert len(store.read_events()) == before
