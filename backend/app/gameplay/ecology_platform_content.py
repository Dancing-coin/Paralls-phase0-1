"""Strict, owner-neutral Ecology platform content contracts.

These models describe immutable ecology package content only. They do not own
authority, execute code, or mutate ecology runtime state.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from app.gameplay.models import StrictGameplayModel
from app.gameplay.patch_runtime import _require_author_canonical, _validate_platform_content


NonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
PositiveInt = Annotated[int, Field(strict=True, gt=0)]
BasisPointInt = Annotated[int, Field(strict=True, ge=0, le=10_000)]


def _require_versioned_ref(value: str, *, prefix: str, error: str = "ecology_reference_invalid") -> str:
    if not value.startswith(prefix) or "@" not in value or value.endswith("@"):
        raise ValueError(error)
    return value


def _require_canonical_refs(
    values: tuple[str, ...], *, error: str = "ecology_array_not_canonical"
) -> None:
    try:
        _require_author_canonical(values, identity=lambda value: value)
    except ValueError as exc:
        raise ValueError(error) from exc
    if tuple(values) != tuple(sorted(values)):
        raise ValueError(error)


class _EcologyPlatformContentModel(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def reject_authority_shaped_payload(cls, value: object) -> object:
        if isinstance(value, cls):
            return value
        _validate_platform_content(value)
        return value


class RegionDefinition(_EcologyPlatformContentModel):
    region_ref: str = Field(min_length=1)
    region_schema_ref: str = Field(min_length=1)
    environment_policy_ref: str = Field(min_length=1)
    jurisdiction_ref: str = Field(min_length=1)
    biome_refs: tuple[str, ...] = Field(min_length=1)
    cell_refs: tuple[str, ...] = Field(min_length=1)
    average_temperature_centi_c: NonNegativeInt
    average_moisture_basis_points: BasisPointInt
    carrying_capacity_units: NonNegativeInt

    @model_validator(mode="after")
    def validate_region(self) -> "RegionDefinition":
        _require_versioned_ref(self.region_ref, prefix="region:")
        _require_versioned_ref(self.region_schema_ref, prefix="schema:")
        _require_versioned_ref(self.environment_policy_ref, prefix="policy:")
        _require_versioned_ref(self.jurisdiction_ref, prefix="jurisdiction:")
        for ref in self.biome_refs:
            _require_versioned_ref(ref, prefix="biome:")
        for ref in self.cell_refs:
            _require_versioned_ref(ref, prefix="cell:")
        _require_canonical_refs(self.biome_refs, error="ecology_region_array_not_canonical")
        _require_canonical_refs(self.cell_refs, error="ecology_region_array_not_canonical")
        return self


class CellDefinition(_EcologyPlatformContentModel):
    cell_ref: str = Field(min_length=1)
    cell_schema_ref: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    terrain_ref: str = Field(min_length=1)
    adjacency_cell_refs: tuple[str, ...] = Field(min_length=1)
    elevation_centimeters: NonNegativeInt
    freshwater_units: NonNegativeInt
    fertility_basis_points: BasisPointInt

    @model_validator(mode="after")
    def validate_cell(self) -> "CellDefinition":
        _require_versioned_ref(self.cell_ref, prefix="cell:")
        _require_versioned_ref(self.cell_schema_ref, prefix="schema:")
        _require_versioned_ref(self.region_ref, prefix="region:")
        _require_versioned_ref(self.terrain_ref, prefix="terrain:")
        for ref in self.adjacency_cell_refs:
            _require_versioned_ref(ref, prefix="cell:")
        _require_canonical_refs(self.adjacency_cell_refs, error="ecology_cell_array_not_canonical")
        return self


class EnvironmentPolicy(_EcologyPlatformContentModel):
    policy_ref: str = Field(min_length=1)
    climate_band_ref: str = Field(min_length=1)
    renewable_resource_cap_units: NonNegativeInt
    hazard_pressure_basis_points: BasisPointInt
    recovery_window_ticks: PositiveInt
    drought_trigger_moisture_basis_points: BasisPointInt

    @model_validator(mode="after")
    def validate_policy(self) -> "EnvironmentPolicy":
        _require_versioned_ref(self.policy_ref, prefix="policy:")
        _require_versioned_ref(self.climate_band_ref, prefix="climate:")
        return self


class ResourceDefinition(_EcologyPlatformContentModel):
    resource_ref: str = Field(min_length=1)
    resource_schema_ref: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    cell_ref: str = Field(min_length=1)
    resource_kind: Literal["water", "soil_nutrient", "forage", "timber", "fish"]
    quantity_units: NonNegativeInt
    regeneration_units_per_tick: NonNegativeInt
    carrying_capacity_units: NonNegativeInt
    renewal_policy_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_resource(self) -> "ResourceDefinition":
        _require_versioned_ref(self.resource_ref, prefix="resource:")
        _require_versioned_ref(self.resource_schema_ref, prefix="schema:")
        _require_versioned_ref(self.region_ref, prefix="region:")
        _require_versioned_ref(self.cell_ref, prefix="cell:")
        _require_versioned_ref(self.renewal_policy_ref, prefix="policy:")
        return self


class CropDefinition(_EcologyPlatformContentModel):
    crop_ref: str = Field(min_length=1)
    crop_schema_ref: str = Field(min_length=1)
    species_ref: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    cell_ref: str = Field(min_length=1)
    water_demand_basis_points: BasisPointInt
    growth_ticks: PositiveInt
    yield_units: NonNegativeInt
    nutrient_resource_refs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_crop(self) -> "CropDefinition":
        _require_versioned_ref(self.crop_ref, prefix="crop:")
        _require_versioned_ref(self.crop_schema_ref, prefix="schema:")
        _require_versioned_ref(self.species_ref, prefix="species:")
        _require_versioned_ref(self.region_ref, prefix="region:")
        _require_versioned_ref(self.cell_ref, prefix="cell:")
        for ref in self.nutrient_resource_refs:
            _require_versioned_ref(ref, prefix="resource:")
        _require_canonical_refs(self.nutrient_resource_refs, error="ecology_crop_array_not_canonical")
        return self


class SpeciesDefinition(_EcologyPlatformContentModel):
    species_ref: str = Field(min_length=1)
    species_schema_ref: str = Field(min_length=1)
    trophic_level: Literal["producer", "herbivore", "omnivore", "carnivore", "decomposer"]
    native_region_refs: tuple[str, ...] = Field(min_length=1)
    habitat_cell_refs: tuple[str, ...] = Field(min_length=1)
    reproduction_ticks: PositiveInt
    base_population_units: NonNegativeInt
    stress_tolerance_basis_points: BasisPointInt

    @model_validator(mode="after")
    def validate_species(self) -> "SpeciesDefinition":
        _require_versioned_ref(self.species_ref, prefix="species:")
        _require_versioned_ref(self.species_schema_ref, prefix="schema:")
        for ref in self.native_region_refs:
            _require_versioned_ref(ref, prefix="region:")
        for ref in self.habitat_cell_refs:
            _require_versioned_ref(ref, prefix="cell:")
        _require_canonical_refs(self.native_region_refs, error="ecology_species_array_not_canonical")
        _require_canonical_refs(self.habitat_cell_refs, error="ecology_species_array_not_canonical")
        return self


class FoodWebEdge(_EcologyPlatformContentModel):
    edge_ref: str = Field(min_length=1)
    predator_species_ref: str = Field(min_length=1)
    prey_species_ref: str = Field(min_length=1)
    consumption_basis_points: BasisPointInt
    conversion_basis_points: BasisPointInt
    priority_rank: NonNegativeInt

    @model_validator(mode="after")
    def validate_edge(self) -> "FoodWebEdge":
        _require_versioned_ref(self.edge_ref, prefix="edge:")
        _require_versioned_ref(self.predator_species_ref, prefix="species:")
        _require_versioned_ref(self.prey_species_ref, prefix="species:")
        if self.predator_species_ref == self.prey_species_ref:
            raise ValueError("ecology_food_web_edge_self_loop")
        return self


class HazardDefinition(_EcologyPlatformContentModel):
    hazard_ref: str = Field(min_length=1)
    hazard_schema_ref: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    hazard_kind: Literal["drought", "frost", "blight", "flood", "heatwave"]
    severity_basis_points: BasisPointInt
    duration_ticks: PositiveInt
    impacted_cell_refs: tuple[str, ...] = Field(min_length=1)
    recovery_policy_ref: str = Field(min_length=1)
    trigger_policy_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_hazard(self) -> "HazardDefinition":
        _require_versioned_ref(self.hazard_ref, prefix="hazard:")
        _require_versioned_ref(self.hazard_schema_ref, prefix="schema:")
        _require_versioned_ref(self.region_ref, prefix="region:")
        _require_versioned_ref(self.recovery_policy_ref, prefix="policy:")
        _require_versioned_ref(self.trigger_policy_ref, prefix="policy:")
        for ref in self.impacted_cell_refs:
            _require_versioned_ref(ref, prefix="cell:")
        _require_canonical_refs(self.impacted_cell_refs, error="ecology_hazard_array_not_canonical")
        return self


class RecoveryPolicy(_EcologyPlatformContentModel):
    policy_ref: str = Field(min_length=1)
    target_kind: Literal["resource", "crop", "species", "region"]
    target_metric: Literal["quantity", "health", "population", "moisture"]
    recovery_units_per_tick: NonNegativeInt
    recovery_cap_basis_points: BasisPointInt
    activation_threshold_basis_points: BasisPointInt

    @model_validator(mode="after")
    def validate_recovery_policy(self) -> "RecoveryPolicy":
        _require_versioned_ref(self.policy_ref, prefix="policy:")
        if self.activation_threshold_basis_points > self.recovery_cap_basis_points:
            raise ValueError("ecology_recovery_policy_window_invalid")
        return self


class ConsumerEdgeDefinition(_EcologyPlatformContentModel):
    edge_ref: str = Field(min_length=1)
    consumer_species_ref: str = Field(min_length=1)
    source_resource_refs: tuple[str, ...] = ()
    source_crop_refs: tuple[str, ...] = ()
    demand_units_per_tick: PositiveInt
    priority_rank: NonNegativeInt
    policy_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_consumer_edge(self) -> "ConsumerEdgeDefinition":
        _require_versioned_ref(self.edge_ref, prefix="edge:")
        _require_versioned_ref(self.consumer_species_ref, prefix="species:")
        _require_versioned_ref(self.policy_ref, prefix="policy:")
        if not self.source_resource_refs and not self.source_crop_refs:
            raise ValueError("ecology_consumer_edge_source_missing")
        for ref in self.source_resource_refs:
            _require_versioned_ref(ref, prefix="resource:")
        for ref in self.source_crop_refs:
            _require_versioned_ref(ref, prefix="crop:")
        if self.source_resource_refs:
            _require_canonical_refs(self.source_resource_refs, error="ecology_consumer_edge_array_not_canonical")
        if self.source_crop_refs:
            _require_canonical_refs(self.source_crop_refs, error="ecology_consumer_edge_array_not_canonical")
        return self


class PopulationSignalDefinition(_EcologyPlatformContentModel):
    signal_ref: str = Field(min_length=1)
    signal_schema_ref: str = Field(min_length=1)
    species_ref: str = Field(min_length=1)
    region_ref: str = Field(min_length=1)
    metric_kind: Literal["population", "stress", "scarcity", "growth"]
    measurement_window_ticks: PositiveInt
    quantity_units: NonNegativeInt
    normalized_basis_points: BasisPointInt
    source_revision_ref: str = Field(min_length=1)
    public_digest: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_signal(self) -> "PopulationSignalDefinition":
        _require_versioned_ref(self.signal_ref, prefix="signal:")
        _require_versioned_ref(self.signal_schema_ref, prefix="schema:")
        _require_versioned_ref(self.species_ref, prefix="species:")
        _require_versioned_ref(self.region_ref, prefix="region:")
        _require_versioned_ref(self.source_revision_ref, prefix="population:")
        if not self.public_digest.startswith("sha256:") or len(self.public_digest) != 71:
            raise ValueError("ecology_population_signal_digest_invalid")
        return self


__all__ = [
    "CellDefinition",
    "ConsumerEdgeDefinition",
    "CropDefinition",
    "EnvironmentPolicy",
    "FoodWebEdge",
    "HazardDefinition",
    "PopulationSignalDefinition",
    "RecoveryPolicy",
    "RegionDefinition",
    "ResourceDefinition",
    "SpeciesDefinition",
]
