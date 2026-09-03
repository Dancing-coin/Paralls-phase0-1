from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.gameplay.ecology_platform_content import (
    CellDefinition,
    ConsumerEdgeDefinition,
    CropDefinition,
    EnvironmentPolicy,
    FoodWebEdge,
    HazardDefinition,
    PopulationSignalDefinition,
    RecoveryPolicy,
    RegionDefinition,
    ResourceDefinition,
    SpeciesDefinition,
)


def _region(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "region_ref": "region:north_fen@1",
        "region_schema_ref": "schema:ecology-region@1",
        "environment_policy_ref": "policy:fen-baseline@1",
        "jurisdiction_ref": "jurisdiction:north_fen@1",
        "biome_refs": ["biome:freshwater@1", "biome:temperate@1"],
        "cell_refs": ["cell:north_fen:a1@1", "cell:north_fen:a2@1"],
        "average_temperature_centi_c": 1850,
        "average_moisture_basis_points": 6200,
        "carrying_capacity_units": 180,
    }
    value.update(overrides)
    return value


def _cell(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "cell_ref": "cell:north_fen:a1@1",
        "cell_schema_ref": "schema:ecology-cell@1",
        "region_ref": "region:north_fen@1",
        "terrain_ref": "terrain:wetland@1",
        "adjacency_cell_refs": ["cell:north_fen:a2@1", "cell:north_fen:b1@1"],
        "elevation_centimeters": 240,
        "freshwater_units": 80,
        "fertility_basis_points": 7100,
    }
    value.update(overrides)
    return value


def _environment_policy(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "policy_ref": "policy:fen-baseline@1",
        "climate_band_ref": "climate:temperate-humid@1",
        "renewable_resource_cap_units": 240,
        "hazard_pressure_basis_points": 1800,
        "recovery_window_ticks": 12,
        "drought_trigger_moisture_basis_points": 2500,
    }
    value.update(overrides)
    return value


def _resource(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "resource_ref": "resource:freshwater:north_fen:a1@1",
        "resource_schema_ref": "schema:ecology-resource@1",
        "region_ref": "region:north_fen@1",
        "cell_ref": "cell:north_fen:a1@1",
        "resource_kind": "water",
        "quantity_units": 80,
        "regeneration_units_per_tick": 3,
        "carrying_capacity_units": 120,
        "renewal_policy_ref": "policy:freshwater-renewal@1",
    }
    value.update(overrides)
    return value


def _crop(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "crop_ref": "crop:marsh_rice:north_fen:a1@1",
        "crop_schema_ref": "schema:ecology-crop@1",
        "species_ref": "species:marsh_rice@1",
        "region_ref": "region:north_fen@1",
        "cell_ref": "cell:north_fen:a1@1",
        "water_demand_basis_points": 5400,
        "growth_ticks": 9,
        "yield_units": 16,
        "nutrient_resource_refs": ["resource:freshwater:north_fen:a1@1"],
    }
    value.update(overrides)
    return value


def _species(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "species_ref": "species:fen_heron@1",
        "species_schema_ref": "schema:ecology-species@1",
        "trophic_level": "carnivore",
        "native_region_refs": ["region:north_fen@1"],
        "habitat_cell_refs": ["cell:north_fen:a1@1", "cell:north_fen:a2@1"],
        "reproduction_ticks": 18,
        "base_population_units": 6,
        "stress_tolerance_basis_points": 4300,
    }
    value.update(overrides)
    return value


def _food_web_edge(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "edge_ref": "edge:fen_heron_to_marsh_fish@1",
        "predator_species_ref": "species:fen_heron@1",
        "prey_species_ref": "species:marsh_fish@1",
        "consumption_basis_points": 3800,
        "conversion_basis_points": 1400,
        "priority_rank": 1,
    }
    value.update(overrides)
    return value


def _hazard(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "hazard_ref": "hazard:drought:north_fen@1",
        "hazard_schema_ref": "schema:ecology-hazard@1",
        "region_ref": "region:north_fen@1",
        "hazard_kind": "drought",
        "severity_basis_points": 4200,
        "duration_ticks": 7,
        "impacted_cell_refs": ["cell:north_fen:a1@1", "cell:north_fen:a2@1"],
        "recovery_policy_ref": "policy:drought-recovery@1",
        "trigger_policy_ref": "policy:drought-trigger@1",
    }
    value.update(overrides)
    return value


def _recovery_policy(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "policy_ref": "policy:drought-recovery@1",
        "target_kind": "resource",
        "target_metric": "quantity",
        "recovery_units_per_tick": 3,
        "recovery_cap_basis_points": 8200,
        "activation_threshold_basis_points": 2500,
    }
    value.update(overrides)
    return value


def _consumer_edge(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "edge_ref": "edge:fen_heron_forage@1",
        "consumer_species_ref": "species:fen_heron@1",
        "source_resource_refs": ["resource:freshwater:north_fen:a1@1"],
        "source_crop_refs": ["crop:marsh_rice:north_fen:a1@1"],
        "demand_units_per_tick": 2,
        "priority_rank": 1,
        "policy_ref": "policy:fen-forage@1",
    }
    value.update(overrides)
    return value


def _population_signal(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "signal_ref": "signal:fen_heron:north_fen:population@1",
        "signal_schema_ref": "schema:ecology-population-signal@1",
        "species_ref": "species:fen_heron@1",
        "region_ref": "region:north_fen@1",
        "metric_kind": "population",
        "measurement_window_ticks": 6,
        "quantity_units": 6,
        "normalized_basis_points": 5100,
        "source_revision_ref": "population:north_fen@3",
        "public_digest": "sha256:" + "a" * 64,
    }
    value.update(overrides)
    return value


def test_ecology_platform_content_accepts_canonical_typed_records() -> None:
    region = RegionDefinition.model_validate(_region())
    cell = CellDefinition.model_validate(_cell())
    policy = EnvironmentPolicy.model_validate(_environment_policy())
    resource = ResourceDefinition.model_validate(_resource())
    crop = CropDefinition.model_validate(_crop())
    species = SpeciesDefinition.model_validate(_species())
    edge = FoodWebEdge.model_validate(_food_web_edge())
    hazard = HazardDefinition.model_validate(_hazard())
    recovery = RecoveryPolicy.model_validate(_recovery_policy())
    consumer = ConsumerEdgeDefinition.model_validate(_consumer_edge())
    signal = PopulationSignalDefinition.model_validate(_population_signal())

    assert region.biome_refs == ("biome:freshwater@1", "biome:temperate@1")
    assert cell.adjacency_cell_refs == ("cell:north_fen:a2@1", "cell:north_fen:b1@1")
    assert policy.recovery_window_ticks == 12
    assert resource.resource_kind == "water"
    assert crop.nutrient_resource_refs == ("resource:freshwater:north_fen:a1@1",)
    assert species.habitat_cell_refs == ("cell:north_fen:a1@1", "cell:north_fen:a2@1")
    assert edge.priority_rank == 1
    assert hazard.impacted_cell_refs == ("cell:north_fen:a1@1", "cell:north_fen:a2@1")
    assert recovery.target_metric == "quantity"
    assert consumer.source_crop_refs == ("crop:marsh_rice:north_fen:a1@1",)
    assert signal.metric_kind == "population"


def test_region_and_species_reject_non_canonical_arrays() -> None:
    with pytest.raises(ValidationError, match="ecology_region_array_not_canonical"):
        RegionDefinition.model_validate(
            _region(biome_refs=["biome:temperate@1", "biome:freshwater@1"])
        )

    with pytest.raises(ValidationError, match="ecology_species_array_not_canonical"):
        SpeciesDefinition.model_validate(
            _species(habitat_cell_refs=["cell:north_fen:a2@1", "cell:north_fen:a1@1"])
        )


def test_ecology_platform_content_rejects_authority_shaped_or_code_like_payloads() -> None:
    with pytest.raises(ValidationError, match="platform_authority_shaped_payload"):
        HazardDefinition.model_validate(_hazard(owner_ref="authority:ecology"))

    with pytest.raises(ValidationError, match="platform_authority_shaped_payload"):
        PopulationSignalDefinition.model_validate(_population_signal(script="return 1"))


def test_ecology_platform_content_requires_versioned_refs_and_strict_integer_fields() -> None:
    with pytest.raises(ValidationError, match="ecology_reference_invalid"):
        ResourceDefinition.model_validate(_resource(resource_ref="resource:freshwater:north_fen:a1"))

    with pytest.raises(ValidationError):
        FoodWebEdge.model_validate(_food_web_edge(priority_rank=True))

    with pytest.raises(ValidationError):
        RecoveryPolicy.model_validate(_recovery_policy(recovery_units_per_tick=False))


def test_population_and_consumer_edges_enforce_digest_window_and_source_shape() -> None:
    with pytest.raises(ValidationError, match="ecology_population_signal_digest_invalid"):
        PopulationSignalDefinition.model_validate(_population_signal(public_digest="sha256:1234"))

    with pytest.raises(ValidationError, match="ecology_consumer_edge_source_missing"):
        ConsumerEdgeDefinition.model_validate(
            _consumer_edge(source_resource_refs=[], source_crop_refs=[])
        )
