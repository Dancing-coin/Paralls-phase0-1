from __future__ import annotations

from app.gameplay.shared_contracts import GameplayPackageManifest


def frost_farm_manifest() -> GameplayPackageManifest:
    return GameplayPackageManifest(
        package_id="package:frost-farm",
        package_revision="package:frost-farm:v1",
        domain_id="frost-farm",
        maturity_level="sample",
        required_core_version="gameplay-core:v1",
        owned_aggregates=("farm_plot", "crop_state"),
        commands=("farm.apply_frost",),
        events=("farm.crop_frost_evaluated",),
        projections=("projection:frost-farm",),
        declared_schemas=("farm.crop_frost_evaluated:v1",),
        dependencies=("world:environment-fact",),
        capabilities=(),
        compatibility_range="gameplay-core:v1",
        migration_refs=(),
        content_digest="sha256:frost-farm-v1",
    )


__all__ = ["frost_farm_manifest"]
