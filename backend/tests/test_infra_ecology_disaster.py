from __future__ import annotations

from app.gameplay.ecology_runtime import (
    CropRecord,
    EcologyHazardAuthority,
    EnvironmentalState,
    EnvironmentRegion,
    HazardRecord,
    ResourceNode,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.semantic_effects import ResistanceProfile


def _hazard() -> HazardRecord:
    return HazardRecord(
        hazard_ref="hazard:frost:1", region_ref="region:valley", effect_ref="effect:frost", severity_basis_points=5000,
        due_tick=12, duration_ticks=1, causal_parent_refs=("event:weather:1",), semantic_revision="semantic:1", rule_revision="rule:1", policy_revision="policy:1",
        idempotency_key="hazard:frost:1", privacy_scope="project",
    )


def test_ecology_records_are_versioned_and_owner_scoped() -> None:
    region = EnvironmentRegion(region_ref="region:valley", climate_profile_ref="climate:temperate", biome_tags=("biome:field",), jurisdiction_ref="jurisdiction:1", revision=1)
    state = EnvironmentalState(region_ref=region.region_ref, temperature_centi_c=200, moisture_basis_points=5000, weather_ref="weather:clear", revision=1)
    resource = ResourceNode(node_ref="resource:water:1", region_ref=region.region_ref, substance_ref="substance:water", quantity=100, regeneration_per_tick=2, revision=1)
    crop = CropRecord(crop_ref="crop:wheat:1", region_ref=region.region_ref, health=100, growth_basis_points=5000, revision=1, owner_ref="authority:crop")
    assert state.region_ref == resource.region_ref == crop.region_ref
    assert _hazard().causal_parent_refs == ("event:weather:1",)


def test_hazard_settles_frost_through_semantic_authority_and_existing_store() -> None:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    result = authority.settle_frost(
        hazard=_hazard(),
        crop=CropRecord(crop_ref="crop:wheat:1", region_ref="region:valley", health=100, growth_basis_points=5000, revision=0, owner_ref="authority:crop"),
        resistance=ResistanceProfile(effect_ref="effect:frost", source_ref="crop:wheat:1", modifier_basis_points=2500, revision=1),
    )
    assert result.committed is True
    assert len(store.read_events()) == 1
    assert store.read_events()[0].payload["effective_magnitude"] == 37
    assert store.read_events()[0].payload["causal_parent_refs"] == ["event:weather:1"]
    assert len(store.list_outbox()) == 1


def test_hazard_duplicate_revision_and_scope_failures_do_not_write() -> None:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    crop = CropRecord(crop_ref="crop:wheat:1", region_ref="region:valley", health=100, growth_basis_points=5000, revision=1, owner_ref="authority:crop")
    stale = authority.settle_frost(hazard=_hazard(), crop=crop, resistance=ResistanceProfile(effect_ref="effect:frost", source_ref="crop:wheat:1", modifier_basis_points=0, revision=1))
    assert stale.committed is False and stale.error_code == "revision_conflict"
    assert store.read_events() == []


def test_hazard_duplicate_replays_and_chain_budget_rejection_is_zero_write() -> None:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    crop = CropRecord(crop_ref="crop:wheat:1", region_ref="region:valley", health=100, growth_basis_points=5000, revision=0, owner_ref="authority:crop")
    first = authority.settle_frost(hazard=_hazard(), crop=crop, resistance=ResistanceProfile(effect_ref="effect:frost", source_ref="crop:wheat:1", modifier_basis_points=0, revision=1))
    duplicate = authority.settle_frost(hazard=_hazard(), crop=crop, resistance=ResistanceProfile(effect_ref="effect:frost", source_ref="crop:wheat:1", modifier_basis_points=0, revision=1))
    assert first.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert len(store.read_events()) == 1
    rejected = authority.settle_frost(hazard=_hazard().model_copy(update={"hazard_ref": "hazard:budget", "idempotency_key": "hazard:budget", "chain_depth": 1}), crop=crop.model_copy(update={"revision": 1}), resistance=ResistanceProfile(effect_ref="effect:frost", source_ref="crop:wheat:1", modifier_basis_points=0, revision=1))
    assert rejected.error_code == "hazard_chain_budget_exhausted"
    assert len(store.read_events()) == 1
    private = authority.settle_frost(hazard=_hazard().model_copy(update={"privacy_scope": "private_evidence", "idempotency_key": "hazard:private"}), crop=crop.model_copy(update={"revision": 0}), resistance=ResistanceProfile(effect_ref="effect:frost", source_ref="crop:wheat:1", modifier_basis_points=0, revision=1))
    assert private.committed is False and private.error_code == "hazard_privacy_scope_denied"
    assert len(store.read_events()) == 1


def test_hazard_projection_is_redacted_and_replay_equivalent() -> None:
    store = GameplayEventStore()
    authority = EcologyHazardAuthority(store=store)
    authority.settle_frost(hazard=_hazard(), crop=CropRecord(crop_ref="crop:wheat:1", region_ref="region:valley", health=100, growth_basis_points=5000, revision=0, owner_ref="authority:crop"), resistance=ResistanceProfile(effect_ref="effect:frost", source_ref="crop:wheat:1", modifier_basis_points=0, revision=1))
    assert authority.project(scope="public")["evidence_refs"] == ()
    assert authority.project(scope="authority")["evidence_refs"]
    assert authority.replay().projection_hash == authority.replay(checkpoint_at=1).projection_hash
