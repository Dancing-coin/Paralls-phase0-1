from __future__ import annotations

from app.gameplay.ecology_runtime import (
    CropRecord,
    EcologyHazardAuthority,
    EcologyWeatherFrontPathPropagationPolicy,
    EnvironmentalState,
    EnvironmentRegion,
    HazardRecord,
    ResourceNode,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.shared_contracts import GameplayCommandEnvelope


PATH = ("region:path:a", "region:path:b", "region:path:c", "region:path:d")


def _bundle(*, region_ref: str, neighbors: tuple[str, ...], weather_ref: str):
    return (
        EnvironmentRegion(region_ref=region_ref, climate_profile_ref="climate:temperate", biome_tags=("biome:field",), jurisdiction_ref=f"jurisdiction:{region_ref}", neighbor_region_refs=neighbors, revision=0),
        EnvironmentalState(region_ref=region_ref, temperature_centi_c=175, moisture_basis_points=4_000, weather_ref=weather_ref, revision=0),
        ResourceNode(node_ref=f"resource:{region_ref}:water", region_ref=region_ref, substance_ref="substance:water", quantity=90, regeneration_per_tick=2, revision=0),
        CropRecord(crop_ref=f"crop:{region_ref}:wheat", region_ref=region_ref, plot_ref=f"plot:{region_ref}:1", health=100, growth_basis_points=5_000, revision=0, owner_ref="authority:crop"),
        HazardRecord(hazard_ref=f"hazard:{region_ref}:frost", region_ref=region_ref, effect_ref="effect:frost", severity_basis_points=5_000, due_tick=3, duration_ticks=1, semantic_revision="semantic:1", rule_revision="rule:1", policy_revision="policy:1", idempotency_key=f"ecology:{region_ref}:initial"),
    )


def _authority() -> tuple[GameplayEventStore, EcologyHazardAuthority]:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    neighbors = {
        "region:path:a": ("region:path:b",),
        "region:path:b": ("region:path:a", "region:path:c"),
        "region:path:c": ("region:path:b", "region:path:d"),
        "region:path:d": ("region:path:c",),
    }
    for index, region_ref in enumerate(PATH):
        region, environment, resource, crop, hazard = _bundle(
            region_ref=region_ref,
            neighbors=neighbors[region_ref],
            weather_ref="weather:rain" if index == 0 else "weather:clear",
        )
        stream_id = authority.ecology_stream_id(region_ref=region_ref)
        result = authority.record_region_bundle(
            envelope=GameplayCommandEnvelope(
                command_id=f"command:ecology:{region_ref}", command_type="gameplay.ecology.region_bundle.record", command_version=1,
                principal_ref="authority:ecology", idempotency_key=f"ecology:{region_ref}:initial", expected_revisions={stream_id: 0},
                causation_id=f"cause:{region_ref}", correlation_id=f"corr:{region_ref}", source_ref="authority:ecology", submitted_at="2026-08-15T00:00:00Z", payload={"visibility_scope": "project"},
            ),
            region=region, environment=environment, resource=resource, crop=crop, hazard=hazard,
        )
        assert result.committed
    return store, authority


def _envelope(authority: EcologyHazardAuthority, store: GameplayEventStore, *, key: str = "ecology:path:one", revisions: dict[str, int] | None = None, visibility_scope: str = "project", region_path: tuple[str, ...] = PATH) -> GameplayCommandEnvelope:
    expected = {authority.ecology_stream_id(region_ref=region_ref): store.get_stream_head(authority.ecology_stream_id(region_ref=region_ref)) for region_ref in region_path}
    return GameplayCommandEnvelope(
        command_id=f"command:{key}", command_type="gameplay.ecology.weather_front.propagate_path", command_version=1,
        principal_ref="authority:ecology", idempotency_key=key, expected_revisions=expected if revisions is None else revisions,
        causation_id=f"cause:{key}", correlation_id=f"corr:{key}", source_ref="authority:ecology", submitted_at="2026-08-15T00:00:00Z", payload={"visibility_scope": visibility_scope, "tick": 5},
    )


def _propagate(authority: EcologyHazardAuthority, store: GameplayEventStore, **kwargs: object):
    return authority.propagate_weather_front_path(
        envelope=_envelope(authority, store, **kwargs),
        policy=EcologyWeatherFrontPathPropagationPolicy(),
        region_path=PATH,
    )


def test_weather_front_path_commits_three_hops_on_existing_ecology_streams_in_one_batch() -> None:
    store, authority = _authority()
    before = len(store.read_events())

    result = _propagate(authority, store)

    assert result.committed
    assert len(store.read_events()) == before + 6
    projection = authority.regional_projection(scope="public")
    assert {region: projection["environments"][region]["weather_ref"] for region in PATH[1:]} == {region: "weather:rain" for region in PATH[1:]}
    assert set(projection["frontiers"]) == set(PATH[:-1])


def test_weather_front_path_replays_exact_duplicate_without_second_write() -> None:
    store, authority = _authority()
    command = _envelope(authority, store)
    first = authority.propagate_weather_front_path(
        envelope=command,
        policy=EcologyWeatherFrontPathPropagationPolicy(),
        region_path=PATH,
    )
    duplicate = authority.propagate_weather_front_path(
        envelope=command,
        policy=EcologyWeatherFrontPathPropagationPolicy(),
        region_path=PATH,
    )

    assert first.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == 26


def test_weather_front_path_rejects_changed_duplicate_without_writes() -> None:
    store, authority = _authority()
    assert _propagate(authority, store).committed
    before = store.read_events()

    changed = authority.propagate_weather_front_path(
        envelope=_envelope(authority, store),
        policy=EcologyWeatherFrontPathPropagationPolicy(),
        region_path=PATH[:3],
    )

    assert not changed.committed
    assert changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert store.read_events() == before


def test_weather_front_path_rejects_stale_revision_without_writes() -> None:
    store, authority = _authority()
    stale = _envelope(authority, store, key="ecology:path:stale")
    stale_revisions = {**stale.expected_revisions, authority.ecology_stream_id(region_ref=PATH[2]): 4}
    before = store.read_events()

    result = _propagate(authority, store, key="ecology:path:stale", revisions=stale_revisions)

    assert result.failure is not None and result.failure.error_code == "revision_conflict"
    assert store.read_events() == before


def test_weather_front_path_rejects_repeated_region_without_writes() -> None:
    store, authority = _authority()
    before = store.read_events()

    result = authority.propagate_weather_front_path(
        envelope=_envelope(authority, store, key="ecology:path:loop"),
        policy=EcologyWeatherFrontPathPropagationPolicy(),
        region_path=(PATH[0], PATH[1], PATH[0]),
    )

    assert result.failure is not None and result.failure.error_code == "ecology_front_path_invalid"
    assert store.read_events() == before


def test_weather_front_path_rejects_nonadjacent_hop_without_writes() -> None:
    store, authority = _authority()
    before = store.read_events()

    result = authority.propagate_weather_front_path(
        envelope=_envelope(authority, store, key="ecology:path:nonadjacent", region_path=(PATH[0], PATH[2])),
        policy=EcologyWeatherFrontPathPropagationPolicy(),
        region_path=(PATH[0], PATH[2]),
    )

    assert result.failure is not None and result.failure.error_code == "ecology_front_adjacency_denied"
    assert store.read_events() == before


def test_weather_front_path_rejects_nonproject_scope_without_writes() -> None:
    store, authority = _authority()
    before = store.read_events()

    result = _propagate(authority, store, key="ecology:path:private", visibility_scope="authority_only")

    assert result.failure is not None and result.failure.error_code == "ecology_front_privacy_scope_denied"
    assert store.read_events() == before


def test_weather_front_path_replays_full_and_checkpoint_tail_projection() -> None:
    store, authority = _authority()
    assert _propagate(authority, store).committed

    assert authority.regional_replay().projection_hash == authority.regional_replay(checkpoint_at=12).projection_hash
