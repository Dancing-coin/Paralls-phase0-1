from __future__ import annotations

from app.gameplay.ecology_runtime import (
    CropRecord,
    EcologyHazardAuthority,
    EcologyWeatherFrontWaveFanoutPolicy,
    EnvironmentalState,
    EnvironmentRegion,
    HazardRecord,
    ResourceNode,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.shared_contracts import GameplayCommandEnvelope


ROOT = "region:wave:root"
WAVE_ONE = ((ROOT, "region:wave:a"), (ROOT, "region:wave:b"))
WAVE_TWO = (
    ("region:wave:a", "region:wave:c"),
    ("region:wave:a", "region:wave:d"),
    ("region:wave:b", "region:wave:e"),
)
WAVES = (WAVE_ONE, WAVE_TWO)


def _authority() -> tuple[GameplayEventStore, EcologyHazardAuthority]:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    neighbors = {
        ROOT: ("region:wave:a", "region:wave:b"),
        "region:wave:a": (ROOT, "region:wave:c", "region:wave:d"),
        "region:wave:b": (ROOT, "region:wave:e"),
        "region:wave:c": ("region:wave:a",),
        "region:wave:d": ("region:wave:a",),
        "region:wave:e": ("region:wave:b",),
    }
    for region_ref, region_neighbors in neighbors.items():
        stream = authority.ecology_stream_id(region_ref=region_ref)
        assert authority.record_region_bundle(
            envelope=GameplayCommandEnvelope(
                command_id=f"command:{region_ref}",
                command_type="gameplay.ecology.region_bundle.record",
                command_version=1,
                principal_ref="authority:ecology",
                idempotency_key=f"ecology:wave:{region_ref}:initial",
                expected_revisions={stream: 0},
                causation_id=f"cause:{region_ref}",
                correlation_id=f"corr:{region_ref}",
                source_ref="authority:ecology",
                submitted_at="2026-08-15T00:00:00Z",
                payload={"visibility_scope": "project"},
            ),
            region=EnvironmentRegion(
                region_ref=region_ref,
                climate_profile_ref="climate:temperate",
                biome_tags=("biome:field",),
                jurisdiction_ref=f"jurisdiction:{region_ref}",
                neighbor_region_refs=region_neighbors,
                revision=0,
            ),
            environment=EnvironmentalState(
                region_ref=region_ref,
                temperature_centi_c=175,
                moisture_basis_points=4_000,
                weather_ref="weather:rain" if region_ref == ROOT else "weather:clear",
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
                idempotency_key=f"ecology:wave:{region_ref}:initial",
            ),
        ).committed
    return store, authority


def _regions(waves: tuple[tuple[tuple[str, str], ...], ...]) -> tuple[str, ...]:
    return tuple(sorted({ROOT, *(region_ref for wave in waves for edge in wave for region_ref in edge)}))


def _command(
    authority: EcologyHazardAuthority,
    store: GameplayEventStore,
    *,
    key: str = "ecology:wave:one",
    waves: tuple[tuple[tuple[str, str], ...], ...] = WAVES,
    visibility_scope: str = "project",
    revisions: dict[str, int] | None = None,
) -> GameplayCommandEnvelope:
    expected = {
        authority.ecology_stream_id(region_ref=region_ref): store.get_stream_head(
            authority.ecology_stream_id(region_ref=region_ref)
        )
        for region_ref in _regions(waves)
    }
    return GameplayCommandEnvelope(
        command_id=f"command:{key}",
        command_type="gameplay.ecology.weather_front.wave_fanout",
        command_version=1,
        principal_ref="authority:ecology",
        idempotency_key=key,
        expected_revisions=expected if revisions is None else revisions,
        causation_id=f"cause:{key}",
        correlation_id=f"corr:{key}",
        source_ref="authority:ecology",
        submitted_at="2026-08-15T00:00:00Z",
        payload={"visibility_scope": visibility_scope, "tick": 7},
    )


def _propagate(
    authority: EcologyHazardAuthority,
    store: GameplayEventStore,
    **kwargs: object,
):
    waves = kwargs.pop("waves", WAVES)
    return authority.fanout_weather_front_waves(
        envelope=_command(authority, store, waves=waves, **kwargs),
        policy=EcologyWeatherFrontWaveFanoutPolicy(),
        root_region_ref=ROOT,
        waves=waves,
    )


def test_weather_front_wave_fanout_commits_two_levels_in_one_ecology_batch() -> None:
    store, authority = _authority()
    before = len(store.read_events())

    result = _propagate(authority, store)

    assert result.committed
    assert len(store.read_events()) == before + 10
    projection = authority.regional_projection(scope="authority")
    targets = {target for wave in WAVES for _source, target in wave}
    assert {target: projection["environments"][target]["weather_ref"] for target in targets} == {
        target: "weather:rain" for target in targets
    }
    assert {
        (edge["source_region_ref"], edge["target_region_ref"])
        for edge in projection["frontier_edges"]
        if edge.get("wave_fanout_digest")
    } == {edge for wave in WAVES for edge in wave}
    wave_two_edge = next(
        event
        for event in store.read_events()
        if event.event_type == "gameplay.ecology.weather_front.propagated"
        and event.payload["source_region_ref"] == "region:wave:a"
        and event.payload["target_region_ref"] == "region:wave:c"
    )
    assert wave_two_edge.payload["source_environment_revision"] == 1
    assert all(event.stream_id.startswith("gameplay:ecology:") for event in store.read_events()[before:])


def test_weather_front_wave_fanout_replays_exact_duplicate_without_second_write() -> None:
    store, authority = _authority()
    command = _command(authority, store)
    first = authority.fanout_weather_front_waves(
        envelope=command,
        policy=EcologyWeatherFrontWaveFanoutPolicy(),
        root_region_ref=ROOT,
        waves=WAVES,
    )
    duplicate = authority.fanout_weather_front_waves(
        envelope=command,
        policy=EcologyWeatherFrontWaveFanoutPolicy(),
        root_region_ref=ROOT,
        waves=WAVES,
    )

    assert first.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == 40


def test_weather_front_wave_fanout_rejects_changed_duplicate_without_write() -> None:
    store, authority = _authority()
    assert _propagate(authority, store).committed
    before = store.read_events()

    changed = _propagate(authority, store, waves=(WAVE_ONE, WAVE_TWO[:2]))

    assert changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert store.read_events() == before


def test_weather_front_wave_fanout_rejects_stale_revision_without_write() -> None:
    store, authority = _authority()
    command = _command(authority, store, key="ecology:wave:stale")
    stale = {**command.expected_revisions, authority.ecology_stream_id(region_ref="region:wave:e"): 4}
    before = store.read_events()

    result = _propagate(authority, store, key="ecology:wave:stale", revisions=stale)

    assert result.failure is not None and result.failure.error_code == "revision_conflict"
    assert store.read_events() == before


def test_weather_front_wave_fanout_rejects_invalid_second_wave_source_without_write() -> None:
    store, authority = _authority()
    before = store.read_events()

    result = _propagate(
        authority,
        store,
        key="ecology:wave:depth",
        waves=(WAVE_ONE, ((ROOT, "region:wave:c"),)),
    )

    assert result.failure is not None and result.failure.error_code == "ecology_front_wave_invalid"
    assert store.read_events() == before


def test_weather_front_wave_fanout_rejects_nonadjacent_edge_without_write() -> None:
    store, authority = _authority()
    before = store.read_events()

    result = _propagate(
        authority,
        store,
        key="ecology:wave:adjacency",
        waves=(WAVE_ONE, (("region:wave:a", "region:wave:e"),)),
    )

    assert result.failure is not None and result.failure.error_code == "ecology_front_adjacency_denied"
    assert store.read_events() == before


def test_weather_front_wave_fanout_rejects_nonproject_scope_without_write() -> None:
    store, authority = _authority()
    before = store.read_events()

    result = _propagate(authority, store, key="ecology:wave:private", visibility_scope="authority_only")

    assert result.failure is not None and result.failure.error_code == "ecology_front_privacy_scope_denied"
    assert store.read_events() == before


def test_weather_front_wave_fanout_outbox_is_project_scoped_and_redacted() -> None:
    store, authority = _authority()

    assert _propagate(authority, store).committed

    outbox = store.list_outbox()[-10:]
    assert {entry.audience for entry in outbox} == {"project"}
    assert all(set(entry.payload_projection) == {"region_ref", "event_type"} for entry in outbox)
    assert all("weather_ref" not in entry.payload_projection for entry in outbox)


def test_weather_front_wave_fanout_replays_full_and_checkpoint_tail_projection() -> None:
    store, authority = _authority()
    assert _propagate(authority, store).committed

    assert authority.regional_replay().projection_hash == authority.regional_replay(checkpoint_at=30).projection_hash
