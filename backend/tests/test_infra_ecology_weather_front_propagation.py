from __future__ import annotations

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
from app.gameplay.shared_contracts import GameplayCommandEnvelope


def _bundle(*, region_ref: str, neighbors: tuple[str, ...], weather_ref: str) -> tuple[EnvironmentRegion, EnvironmentalState, ResourceNode, CropRecord, HazardRecord]:
    return (
        EnvironmentRegion(
            region_ref=region_ref,
            climate_profile_ref="climate:temperate",
            biome_tags=("biome:field",),
            jurisdiction_ref=f"jurisdiction:{region_ref}",
            neighbor_region_refs=neighbors,
            revision=0,
        ),
        EnvironmentalState(region_ref=region_ref, temperature_centi_c=175, moisture_basis_points=4_000, weather_ref=weather_ref, revision=0),
        ResourceNode(node_ref=f"resource:{region_ref}:water", region_ref=region_ref, substance_ref="substance:water", quantity=90, regeneration_per_tick=2, revision=0),
        CropRecord(crop_ref=f"crop:{region_ref}:wheat", region_ref=region_ref, plot_ref=f"plot:{region_ref}:1", health=100, growth_basis_points=5_000, revision=0, owner_ref="authority:crop"),
        HazardRecord(hazard_ref=f"hazard:{region_ref}:frost", region_ref=region_ref, effect_ref="effect:frost", severity_basis_points=5_000, due_tick=3, duration_ticks=1, semantic_revision="semantic:1", rule_revision="rule:1", policy_revision="policy:1", idempotency_key=f"ecology:{region_ref}:initial"),
    )


def _record_regions(store: GameplayEventStore) -> EcologyHazardAuthority:
    authority = EcologyHazardAuthority(store=store)
    for region_ref, neighbors, weather_ref in (
        ("region:front:source", ("region:front:target",), "weather:rain"),
        ("region:front:target", ("region:front:source",), "weather:clear"),
        ("region:front:isolated", (), "weather:clear"),
    ):
        region, environment, resource, crop, hazard = _bundle(region_ref=region_ref, neighbors=neighbors, weather_ref=weather_ref)
        stream_id = authority.ecology_stream_id(region_ref=region_ref)
        result = authority.record_region_bundle(
            envelope=GameplayCommandEnvelope(
                command_id=f"command:ecology:{region_ref}", command_type="gameplay.ecology.region_bundle.record", command_version=1,
                principal_ref="authority:ecology", idempotency_key=f"ecology:{region_ref}:initial", expected_revisions={stream_id: 0},
                causation_id=f"cause:{region_ref}", correlation_id=f"corr:{region_ref}", source_ref="authority:ecology",
                submitted_at="2026-08-14T00:00:00Z", payload={"visibility_scope": "project"},
            ),
            region=region, environment=environment, resource=resource, crop=crop, hazard=hazard,
        )
        assert result.committed is True
    return authority


def _front_envelope(authority: EcologyHazardAuthority, store: GameplayEventStore, *, key: str = "ecology:front:one", source_revision: int | None = None, target_revision: int | None = None, target_region_ref: str = "region:front:target", visibility_scope: str = "project") -> GameplayCommandEnvelope:
    source_stream = authority.ecology_stream_id(region_ref="region:front:source")
    target_stream = authority.ecology_stream_id(region_ref=target_region_ref)
    return GameplayCommandEnvelope(
        command_id=f"command:{key}", command_type="gameplay.ecology.weather_front.propagate", command_version=1,
        principal_ref="authority:ecology", idempotency_key=key,
        expected_revisions={
            source_stream: store.get_stream_head(source_stream) if source_revision is None else source_revision,
            target_stream: store.get_stream_head(target_stream) if target_revision is None else target_revision,
        },
        causation_id=f"cause:{key}", correlation_id=f"corr:{key}", source_ref="authority:ecology",
        submitted_at="2026-08-14T00:00:00Z", payload={"visibility_scope": visibility_scope, "tick": 4},
    )


def test_weather_front_propagates_one_project_visible_neighbor_step_in_one_existing_append_batch() -> None:
    store = GameplayEventStore()
    authority = _record_regions(store)
    before = len(store.read_events())

    result = authority.propagate_weather_front(
        envelope=_front_envelope(authority, store),
        policy=EcologyWeatherFrontPropagationPolicy(),
        source_region_ref="region:front:source",
        target_region_ref="region:front:target",
    )

    assert result.committed is True
    assert len(store.read_events()) == before + 2
    assert [event.event_type for event in store.read_events()[-2:]] == [
        "gameplay.ecology.weather_front.propagated",
        "gameplay.ecology.environment.recorded",
    ]
    projection = authority.regional_projection(scope="public")
    assert projection["environments"]["region:front:target"]["weather_ref"] == "weather:rain"
    assert projection["frontiers"]["region:front:source"]["target_region_ref"] == "region:front:target"


def test_weather_front_rejects_stale_revision_without_writes() -> None:
    store = GameplayEventStore()
    authority = _record_regions(store)
    before = len(store.read_events())

    stale = authority.propagate_weather_front(
        envelope=_front_envelope(authority, store, key="ecology:front:stale", source_revision=4),
        policy=EcologyWeatherFrontPropagationPolicy(), source_region_ref="region:front:source", target_region_ref="region:front:target",
    )
    assert stale.failure is not None and stale.failure.error_code == "revision_conflict"
    assert len(store.read_events()) == before


def test_weather_front_rejects_asymmetric_neighbor_without_writes() -> None:
    store = GameplayEventStore()
    authority = _record_regions(store)
    before = len(store.read_events())

    asymmetric = authority.propagate_weather_front(
        envelope=_front_envelope(authority, store, key="ecology:front:asymmetric", target_region_ref="region:front:isolated"),
        policy=EcologyWeatherFrontPropagationPolicy(), source_region_ref="region:front:source", target_region_ref="region:front:isolated",
    )

    assert asymmetric.failure is not None and asymmetric.failure.error_code == "ecology_front_adjacency_denied"
    assert len(store.read_events()) == before


def test_weather_front_is_idempotent() -> None:
    store = GameplayEventStore()
    authority = _record_regions(store)
    command = _front_envelope(authority, store)
    first = authority.propagate_weather_front(envelope=command, policy=EcologyWeatherFrontPropagationPolicy(), source_region_ref="region:front:source", target_region_ref="region:front:target")
    duplicate = authority.propagate_weather_front(envelope=command, policy=EcologyWeatherFrontPropagationPolicy(), source_region_ref="region:front:source", target_region_ref="region:front:target")

    assert first.committed is True
    assert duplicate.idempotency_status == "duplicate_replayed"


def test_weather_front_rejects_nonproject_scope_without_writes() -> None:
    store = GameplayEventStore()
    authority = _record_regions(store)
    before = len(store.read_events())
    private = authority.propagate_weather_front(envelope=_front_envelope(authority, store, key="ecology:front:private", visibility_scope="authority_only"), policy=EcologyWeatherFrontPropagationPolicy(), source_region_ref="region:front:source", target_region_ref="region:front:target")

    assert private.failure is not None and private.failure.error_code == "ecology_front_privacy_scope_denied"
    assert len(store.read_events()) == before


def test_weather_front_outbox_is_project_scoped() -> None:
    store = GameplayEventStore()
    authority = _record_regions(store)
    assert authority.propagate_weather_front(envelope=_front_envelope(authority, store), policy=EcologyWeatherFrontPropagationPolicy(), source_region_ref="region:front:source", target_region_ref="region:front:target").committed

    assert store.list_outbox()[-1].audience == "project"


def test_weather_front_checkpoint_tail_replay_matches_full_replay() -> None:
    store = GameplayEventStore()
    authority = _record_regions(store)
    assert authority.propagate_weather_front(envelope=_front_envelope(authority, store), policy=EcologyWeatherFrontPropagationPolicy(), source_region_ref="region:front:source", target_region_ref="region:front:target").committed

    assert authority.regional_replay().projection_hash == authority.regional_replay(checkpoint_at=6).projection_hash
