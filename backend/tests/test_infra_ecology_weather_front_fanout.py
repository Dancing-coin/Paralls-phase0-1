from __future__ import annotations

from app.gameplay.ecology_runtime import CropRecord, EcologyHazardAuthority, EcologyWeatherFrontFanoutPolicy, EnvironmentalState, EnvironmentRegion, HazardRecord, ResourceNode
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.shared_contracts import GameplayCommandEnvelope


ROOT = "region:fanout:root"
TARGETS = ("region:fanout:a", "region:fanout:b", "region:fanout:c")


def _authority() -> tuple[GameplayEventStore, EcologyHazardAuthority]:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    for region_ref in (ROOT, *TARGETS):
        neighbors = TARGETS if region_ref == ROOT else (ROOT,)
        region = EnvironmentRegion(region_ref=region_ref, climate_profile_ref="climate:temperate", biome_tags=("biome:field",), jurisdiction_ref=f"jurisdiction:{region_ref}", neighbor_region_refs=neighbors, revision=0)
        environment = EnvironmentalState(region_ref=region_ref, temperature_centi_c=175, moisture_basis_points=4_000, weather_ref="weather:rain" if region_ref == ROOT else "weather:clear", revision=0)
        resource = ResourceNode(node_ref=f"resource:{region_ref}:water", region_ref=region_ref, substance_ref="substance:water", quantity=90, regeneration_per_tick=2, revision=0)
        crop = CropRecord(crop_ref=f"crop:{region_ref}:wheat", region_ref=region_ref, plot_ref=f"plot:{region_ref}:1", health=100, growth_basis_points=5_000, revision=0, owner_ref="authority:crop")
        hazard = HazardRecord(hazard_ref=f"hazard:{region_ref}:frost", region_ref=region_ref, effect_ref="effect:frost", severity_basis_points=5_000, due_tick=3, duration_ticks=1, semantic_revision="semantic:1", rule_revision="rule:1", policy_revision="policy:1", idempotency_key=f"ecology:{region_ref}:initial")
        stream = authority.ecology_stream_id(region_ref=region_ref)
        assert authority.record_region_bundle(envelope=GameplayCommandEnvelope(command_id=f"command:{region_ref}", command_type="gameplay.ecology.region_bundle.record", command_version=1, principal_ref="authority:ecology", idempotency_key=f"ecology:{region_ref}:initial", expected_revisions={stream: 0}, causation_id=f"cause:{region_ref}", correlation_id=f"corr:{region_ref}", source_ref="authority:ecology", submitted_at="2026-08-15T00:00:00Z", payload={"visibility_scope": "project"}), region=region, environment=environment, resource=resource, crop=crop, hazard=hazard).committed
    return store, authority


def _command(authority: EcologyHazardAuthority, store: GameplayEventStore, *, key: str = "ecology:fanout:one", target_refs: tuple[str, ...] = TARGETS, visibility_scope: str = "project", revisions: dict[str, int] | None = None) -> GameplayCommandEnvelope:
    refs = (ROOT, *target_refs)
    expected = {authority.ecology_stream_id(region_ref=ref): store.get_stream_head(authority.ecology_stream_id(region_ref=ref)) for ref in refs}
    return GameplayCommandEnvelope(command_id=f"command:{key}", command_type="gameplay.ecology.weather_front.fanout", command_version=1, principal_ref="authority:ecology", idempotency_key=key, expected_revisions=expected if revisions is None else revisions, causation_id=f"cause:{key}", correlation_id=f"corr:{key}", source_ref="authority:ecology", submitted_at="2026-08-15T00:00:00Z", payload={"visibility_scope": visibility_scope, "tick": 6})


def _fanout(authority: EcologyHazardAuthority, store: GameplayEventStore, **kwargs: object):
    targets = kwargs.pop("target_refs", TARGETS)
    return authority.fanout_weather_front(envelope=_command(authority, store, target_refs=targets, **kwargs), policy=EcologyWeatherFrontFanoutPolicy(), root_region_ref=ROOT, target_region_refs=targets)


def test_weather_front_fanout_commits_three_targets_and_preserves_all_project_edges() -> None:
    store, authority = _authority()
    before = len(store.read_events())
    result = _fanout(authority, store)
    projection = authority.regional_projection(scope="public")
    assert result.committed and len(store.read_events()) == before + 6
    assert {ref: projection["environments"][ref]["weather_ref"] for ref in TARGETS} == {ref: "weather:rain" for ref in TARGETS}
    assert {edge["target_region_ref"] for edge in projection["frontier_edges"] if edge["source_region_ref"] == ROOT} == set(TARGETS)


def test_weather_front_fanout_replays_exact_duplicate_without_write() -> None:
    store, authority = _authority(); command = _command(authority, store)
    first = authority.fanout_weather_front(envelope=command, policy=EcologyWeatherFrontFanoutPolicy(), root_region_ref=ROOT, target_region_refs=TARGETS)
    duplicate = authority.fanout_weather_front(envelope=command, policy=EcologyWeatherFrontFanoutPolicy(), root_region_ref=ROOT, target_region_refs=TARGETS)
    assert first.committed and duplicate.idempotency_status == "duplicate_replayed"


def test_weather_front_fanout_rejects_changed_duplicate_without_writes() -> None:
    store, authority = _authority(); assert _fanout(authority, store).committed; before = store.read_events()
    changed = _fanout(authority, store, target_refs=TARGETS[:2])
    assert changed.failure is not None and changed.failure.error_code == "idempotency_key_reused" and store.read_events() == before


def test_weather_front_fanout_rejects_stale_revision_without_writes() -> None:
    store, authority = _authority(); command = _command(authority, store, key="ecology:fanout:stale"); before = store.read_events()
    stale = _fanout(authority, store, key="ecology:fanout:stale", revisions={**command.expected_revisions, authority.ecology_stream_id(region_ref=TARGETS[0]): 4})
    assert stale.failure is not None and stale.failure.error_code == "revision_conflict" and store.read_events() == before


def test_weather_front_fanout_rejects_duplicate_target_without_writes() -> None:
    store, authority = _authority(); before = store.read_events()
    rejected = _fanout(authority, store, key="ecology:fanout:duplicate-target", target_refs=(TARGETS[0], TARGETS[0]))
    assert rejected.failure is not None and rejected.failure.error_code == "ecology_front_fanout_invalid" and store.read_events() == before


def test_weather_front_fanout_rejects_nonproject_scope_without_writes() -> None:
    store, authority = _authority(); before = store.read_events()
    rejected = _fanout(authority, store, key="ecology:fanout:private", visibility_scope="authority_only")
    assert rejected.failure is not None and rejected.failure.error_code == "ecology_front_privacy_scope_denied" and store.read_events() == before


def test_weather_front_fanout_replays_full_and_checkpoint_tail_projection() -> None:
    store, authority = _authority(); assert _fanout(authority, store).committed
    assert authority.regional_replay().projection_hash == authority.regional_replay(checkpoint_at=12).projection_hash
