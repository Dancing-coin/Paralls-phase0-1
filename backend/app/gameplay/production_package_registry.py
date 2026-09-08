from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from app.gameplay.inventory_runtime import InventoryDefinitionRegistry, ItemDefinition
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry
from app.gameplay.p5.contracts import P5SchemaPin, QuestObjectiveDefinition, QuestPackageDefinition
from app.gameplay.p5.registry import (
    OwnerAdapterAllowance,
    P5EventCatalogEntry,
    P5EventNamespace,
    P5PolicyRegistry,
    P5StreamGrammar,
    TrustedEvidenceProvider,
)


_TRUSTED_AUTHORS = frozenset({"author:repo"})
_APPROVED_MANIFESTS = (
    "closed-generic/production-output-certification/package-production-output-certification-demo-v1.manifest.json",
    "closed-generic/production-output-certification/package-production-output-certification-mill-demo-v1.manifest.json",
    "closed-generic/production-output-certification/package-production-output-certification-kiln-demo-v1.manifest.json",
    "closed-generic/production-output-custody/package-production-output-custody-bread.manifest.json",
    "closed-generic/production-output-custody/package-production-output-custody-flour.manifest.json",
    "population-signal/package-population-materialization-v1.manifest.json",
)


def _load_manifest(path: Path) -> GameplayPatchManifest:
    return GameplayPatchManifest.model_validate_json(path.read_text(encoding="utf-8"))


def build_production_package_registry(repo_root: Path) -> GameplayPatchRegistry:
    """Load the committed production manifest set and activate one exact patch set."""
    base = repo_root / "docs" / "superpowers" / "specs" / "world-character-siming-authority-mainline"
    paths = tuple(base / relative for relative in _APPROVED_MANIFESTS)
    manifests = tuple(_load_manifest(path) for path in paths)
    registry = GameplayPatchRegistry(trusted_authors=_TRUSTED_AUTHORS)
    registry.install_many(manifests)
    registry.activate(tuple(manifest.patch_revision_id for manifest in manifests))
    return registry


def build_production_inventory_definition_registry() -> InventoryDefinitionRegistry:
    registry = InventoryDefinitionRegistry()
    for definition_id in (
        "archive_token",
        "item:bread@1",
        "item:industrial-facilities:flour@1",
        "item:brick@1",
    ):
        registry.register_item(ItemDefinition(definition_id, "v1", 1, 1))
    return registry


def build_production_social_policy_registry() -> P5PolicyRegistry:
    digest = "sha256:" + sha256(b"production:population-signal").hexdigest()
    event = "gameplay.social.population_signal_recorded@1"
    schema = P5SchemaPin(
        schema_ref="schema:population:signal-materialization",
        schema_version=1,
        schema_digest=digest,
    )
    return P5PolicyRegistry.build(
        registry_ref="registry:production-social",
        registry_revision="registry:production-social@1",
        trusted_evidence_providers=(
            TrustedEvidenceProvider(
                provider_ref="provider:production:population-signal@1",
                provider_revision="provider:production:population-signal@1",
                provider_digest=digest,
                allowed_evidence_kinds=("evidence:population-signal@1",),
            ),
        ),
        owner_adapter_allowlist=(
            OwnerAdapterAllowance(
                owner_ref="authority:p5:social",
                allowed_event_names=(event,),
                allowed_stream_grammar_refs=("grammar:production:population-signal@1",),
            ),
        ),
        quest_packages=(
            QuestPackageDefinition(
                package_ref="package:production:population-signal@1",
                package_revision="package:production:population-signal:v1@1",
                package_digest=digest,
                ruleset_revision="ruleset:production:population-signal@1",
                objectives=(
                    QuestObjectiveDefinition(
                        objective_ref="objective:production:population-signal@1",
                        accepted_evidence_kind_refs=("evidence:population-signal@1",),
                        visibility="project",
                        expiry_policy_ref="expiry:never@1",
                    ),
                ),
            ),
        ),
        ruleset_revisions=("ruleset:production:population-signal@1",),
        schema_pins=(schema,),
        event_namespaces=(
            P5EventNamespace(
                namespace_ref="namespace:production:population-signal@1",
                event_name_prefix="gameplay.social.",
                allowed_event_names=(event,),
            ),
        ),
        event_catalog=(
            P5EventCatalogEntry(
                event_name=event,
                namespace_ref="namespace:production:population-signal@1",
                schema_ref=schema.schema_ref,
                schema_version=1,
                stream_grammar_ref="grammar:production:population-signal@1",
            ),
        ),
        stream_grammars=(
            P5StreamGrammar(
                grammar_ref="grammar:production:population-signal@1",
                pattern=r"^gameplay:social:population:.+$",
            ),
        ),
    )


__all__ = [
    "build_production_inventory_definition_registry",
    "build_production_package_registry",
    "build_production_social_policy_registry",
]
