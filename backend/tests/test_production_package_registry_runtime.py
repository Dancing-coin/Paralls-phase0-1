from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import InventoryAuthorityService, InventoryDefinitionRegistry
from app.gameplay.p5.social_knowledge import SocialFactAuthority
from app.gameplay.p5.stormnight_owner_registries import stormnight_social_registry
from app.gameplay.production_package_registry import build_production_package_registry
from app.gameplay.production_package_registry import (
    build_production_inventory_definition_registry,
    build_production_social_policy_registry,
)


def test_production_registry_loads_source_manifests_and_activates_exact_families() -> None:
    registry = build_production_package_registry(Path(__file__).resolve().parents[2])

    assert registry.active_patch_set is not None
    families = {binding.family_ref for binding in registry.active_patch_set.capability_bindings}
    assert "production_output_certification@1" in families
    assert "production_output_custody@1" in families
    assert "population_signal_materialization@1" in families
    assert registry.active_patch_set.patch_revision_ids == (
        "package:output-certification-demo@1",
        "package:output-certification-kiln-demo@1",
        "package:output-certification-mill-demo@1",
        "package:population-materialization:v1",
        "package:production-output-custody:bread@1",
        "package:production-output-custody:flour@1",
    )


def test_domain_owners_receive_the_same_production_registry() -> None:
    registry = build_production_package_registry(Path(__file__).resolve().parents[2])
    store = GameplayEventStore()

    inventory = InventoryAuthorityService(
        store=store,
        registry=InventoryDefinitionRegistry(),
        package_registry=registry,
    )
    social = SocialFactAuthority(
        registry=stormnight_social_registry(),
        store=store,
        package_registry=registry,
    )

    assert inventory._package_registry is registry
    assert social._package_registry is registry


def test_default_runtime_injects_active_registry_into_population_owners(
    tmp_path: Path, monkeypatch
) -> None:
    import app.main as main

    store = GameplayEventStore()
    monkeypatch.setattr(main, "gameplay_event_store", store)
    monkeypatch.setattr(main, "production_package_registry", build_production_package_registry(Path(__file__).resolve().parents[2]))
    monkeypatch.setattr(main, "production_social_policy_registry", build_production_social_policy_registry())
    monkeypatch.setattr(main, "inventory_definition_registry", build_production_inventory_definition_registry())
    state = main.build_runtime_state(Settings(heavenly_graph_path=str(tmp_path / "runtime.sqlite3")))
    try:
        capability = state.siming_runtime._population_capability
        assert {
            "population:organization-production-work-contribution:v1",
            "population:inventory-output-custody:v1",
            "population:social-population-signal:v1",
        } <= set(capability._owner_executors)
        assert all(
            getattr(executor._authority, "_package_registry", None)
            is main.production_package_registry
            for executor in capability._owner_executors.values()
            if hasattr(executor, "_authority")
            and hasattr(executor._authority, "_package_registry")
        )
    finally:
        state.close()


def test_production_registry_rejects_missing_source_manifest(tmp_path: Path) -> None:
    source_root = Path(__file__).resolve().parents[2]
    missing = source_root / "docs" / "superpowers" / "specs" / "world-character-siming-authority-mainline" / "production-package-registry"
    with pytest.raises(FileNotFoundError):
        build_production_package_registry(tmp_path)
