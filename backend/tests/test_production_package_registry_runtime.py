from __future__ import annotations

from dataclasses import replace
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
            "population:organization-window-due:v1",
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


@pytest.mark.parametrize(
    ("owner_ref", "family_ref"),
    [
        ("population:inventory-output-custody:v1", "production_output_custody@1"),
        ("population:social-population-signal:v1", "population_signal_materialization@1"),
    ],
)
def test_runtime_refuses_population_owner_without_exact_unique_bindings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    owner_ref: str,
    family_ref: str,
) -> None:
    import app.main as main

    registry = build_production_package_registry(Path(__file__).resolve().parents[2])
    active = registry.active_patch_set
    assert active is not None
    family_bindings = tuple(
        binding for binding in active.capability_bindings if binding.family_ref == family_ref
    )
    other_bindings = tuple(
        binding for binding in active.capability_bindings if binding.family_ref != family_ref
    )
    mutations = [family_bindings[:-1], family_bindings + (family_bindings[0],)]
    for index, binding in enumerate(family_bindings):
        for field, wrong_value in (
            ("binding_ref", "binding:wrong@1"),
            ("package_revision", "package:wrong@1"),
            ("descriptor_ref", "descriptor:wrong@1"),
            ("descriptor_revision", "descriptor:wrong@1"),
        ):
            mutations.append(
                family_bindings[:index]
                + (replace(binding, **{field: wrong_value}),)
                + family_bindings[index + 1 :]
            )
    monkeypatch.setattr(main, "gameplay_event_store", GameplayEventStore())
    monkeypatch.setattr(main, "production_package_registry", registry)
    monkeypatch.setattr(main, "production_social_policy_registry", build_production_social_policy_registry())
    monkeypatch.setattr(main, "inventory_definition_registry", build_production_inventory_definition_registry())

    for index, mutated_family in enumerate(mutations):
        registry._active = replace(
            active, capability_bindings=other_bindings + mutated_family
        )
        state = main.build_runtime_state(Settings(heavenly_graph_path=str(tmp_path / f"{index}.sqlite3")))
        try:
            assert owner_ref not in state.siming_runtime._population_capability._owner_executors
        finally:
            state.close()


def test_production_registry_rejects_missing_source_manifest(tmp_path: Path) -> None:
    source_root = Path(__file__).resolve().parents[2]
    missing = source_root / "docs" / "superpowers" / "specs" / "world-character-siming-authority-mainline" / "production-package-registry"
    with pytest.raises(FileNotFoundError):
        build_production_package_registry(tmp_path)
