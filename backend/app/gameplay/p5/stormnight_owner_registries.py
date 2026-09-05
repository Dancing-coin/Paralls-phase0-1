"""Minimal registry factories for the fixed Stormnight owner handoffs."""

from __future__ import annotations

from app.gameplay.p5.contracts import P5SchemaPin, QuestObjectiveDefinition, QuestPackageDefinition
from app.gameplay.p5.registry import OwnerAdapterAllowance, P5EventCatalogEntry, P5EventNamespace, P5PolicyRegistry, P5StreamGrammar, TrustedEvidenceProvider


def _digest(seed: str) -> str:
    return "sha256:" + (seed * 64)[:64]


def stormnight_social_registry() -> P5PolicyRegistry:
    events = ("gameplay.social.knowledge_observed",)
    schema = P5SchemaPin(schema_ref="schema:p5:stormnight:knowledge", schema_version=1, schema_digest=_digest("a"))
    return P5PolicyRegistry.build(
        registry_ref="registry:p5:stormnight-social",
        registry_revision="registry:p5:stormnight-social@1",
        trusted_evidence_providers=(TrustedEvidenceProvider(provider_ref="provider:stormnight:case@1", provider_revision="provider:stormnight:case@1", provider_digest=_digest("b"), allowed_evidence_kinds=("evidence:stormnight:physical@1",)),),
        owner_adapter_allowlist=(OwnerAdapterAllowance(owner_ref="authority:p5:social", allowed_event_names=events, allowed_stream_grammar_refs=("grammar:stormnight:knowledge@1",)),),
        quest_packages=(QuestPackageDefinition(package_ref="package:stormnight:social@1", package_revision="package:stormnight:social:v1@1", package_digest=_digest("c"), ruleset_revision="ruleset:stormnight:social@1", objectives=(QuestObjectiveDefinition(objective_ref="objective:stormnight:social@1", accepted_evidence_kind_refs=("evidence:stormnight:physical@1",), visibility="project", expiry_policy_ref="expiry:never@1"),)),),
        ruleset_revisions=("ruleset:stormnight:social@1",),
        schema_pins=(schema,),
        event_namespaces=(P5EventNamespace(namespace_ref="namespace:stormnight:social@1", event_name_prefix="gameplay.social.", allowed_event_names=events),),
        event_catalog=(P5EventCatalogEntry(event_name=events[0], namespace_ref="namespace:stormnight:social@1", schema_ref=schema.schema_ref, schema_version=1, stream_grammar_ref="grammar:stormnight:knowledge@1"),),
        stream_grammars=(P5StreamGrammar(grammar_ref="grammar:stormnight:knowledge@1", pattern=r"^gameplay:knowledge:.+$"),),
    )


def stormnight_quest_registry() -> P5PolicyRegistry:
    events = ("gameplay.quest.evidence_registered",)
    schema = P5SchemaPin(schema_ref="schema:p5:stormnight:evidence", schema_version=1, schema_digest=_digest("d"))
    return P5PolicyRegistry.build(
        registry_ref="registry:p5:stormnight-quest",
        registry_revision="registry:p5:stormnight-quest@1",
        trusted_evidence_providers=(TrustedEvidenceProvider(provider_ref="provider:stormnight:case@1", provider_revision="provider:stormnight:case@1", provider_digest=_digest("e"), allowed_evidence_kinds=("evidence:stormnight:physical@1",)),),
        owner_adapter_allowlist=(OwnerAdapterAllowance(owner_ref="authority:p5:quest-evidence", allowed_event_names=events, allowed_stream_grammar_refs=("grammar:stormnight:evidence@1",)),),
        quest_packages=(QuestPackageDefinition(package_ref="package:stormnight:quest@1", package_revision="package:stormnight:quest:v1@1", package_digest=_digest("f"), ruleset_revision="ruleset:stormnight:quest@1", objectives=(QuestObjectiveDefinition(objective_ref="objective:stormnight:quest@1", accepted_evidence_kind_refs=("evidence:stormnight:physical@1",), visibility="project", expiry_policy_ref="expiry:never@1"),)),),
        ruleset_revisions=("ruleset:stormnight:quest@1",),
        schema_pins=(schema,),
        event_namespaces=(P5EventNamespace(namespace_ref="namespace:stormnight:quest@1", event_name_prefix="gameplay.quest.", allowed_event_names=events),),
        event_catalog=(P5EventCatalogEntry(event_name=events[0], namespace_ref="namespace:stormnight:quest@1", schema_ref=schema.schema_ref, schema_version=1, stream_grammar_ref="grammar:stormnight:evidence@1"),),
        stream_grammars=(P5StreamGrammar(grammar_ref="grammar:stormnight:evidence@1", pattern=r"^gameplay:evidence:.+$"),),
    )


__all__ = ["stormnight_quest_registry", "stormnight_social_registry"]
