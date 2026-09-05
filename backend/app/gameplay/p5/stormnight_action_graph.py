"""Stormnight's finite action graph and P5 action-window registry."""

from __future__ import annotations

from app.gameplay.action_graph_content import ActionGraphAdmissionResult, ActionGraphDefinition, ActionGraphNode
from app.gameplay.p5.registry import OwnerAdapterAllowance, P5EventCatalogEntry, P5EventNamespace, P5PolicyRegistry, P5StreamGrammar, TrustedEvidenceProvider
from app.gameplay.p5.contracts import P5SchemaPin, QuestObjectiveDefinition, QuestPackageDefinition
from app.gameplay.shared_contracts import ActionPrimitiveDefinition


_EVENTS = (
    "gameplay.conflict.action_window_resolved",
    "gameplay.conflict.control_changed",
    "gameplay.conflict.encounter_closed",
    "gameplay.conflict.encounter_started",
    "gameplay.conflict.terminal_outcome_recorded",
)


def stormnight_action_graph() -> ActionGraphDefinition:
    return ActionGraphDefinition(
        graph_ref="graph:stormnight-investigation@1",
        graph_revision="graph:stormnight-investigation@1",
        action_family="scripted_mystery",
        role_refs=("role:pursuer@1", "role:survivor@1", "role:witness@1"),
        primitive_refs=("primitive:advance@1", "primitive:loop@1", "primitive:recover@1", "primitive:resolve@1"),
        nodes=(
            ActionGraphNode(node_ref="arrival", primitive_ref="primitive:advance@1", phase="active", duration_window=(0, 1), cancel_targets=("arrival",), condition_refs=("state:arrival@1",), asset_ref="asset:stormnight:door@1", contact_marker_refs=("marker:stormnight:door@1",)),
            ActionGraphNode(node_ref="investigate", primitive_ref="primitive:loop@1", phase="active", duration_window=(1, 2), cancel_targets=("arrival",), condition_refs=("state:investigation@1",), asset_ref="asset:stormnight:hall@1", contact_marker_refs=("marker:stormnight:clue@1",)),
            ActionGraphNode(node_ref="recover", primitive_ref="primitive:recover@1", phase="recovery", duration_window=(2, 3), cancel_targets=("investigate",), condition_refs=("policy:stormnight:recovery@1",), asset_ref="asset:stormnight:safe@1", contact_marker_refs=("marker:stormnight:hide@1",)),
            ActionGraphNode(node_ref="terminal", primitive_ref="primitive:resolve@1", phase="terminal", duration_window=(3, 4), cancel_targets=("recover",), condition_refs=("policy:stormnight:terminal@1",), asset_ref="asset:stormnight:case-file@1", contact_marker_refs=("marker:stormnight:close@1",)),
        ),
        edges=(
            {"from_node": "arrival", "to_node": "investigate", "trigger": "advance", "priority": 1, "condition_refs": ("state:visible@1",)},
            {"from_node": "investigate", "to_node": "recover", "trigger": "recover", "priority": 1, "condition_refs": ("policy:stormnight:cooldown@1",)},
            {"from_node": "recover", "to_node": "terminal", "trigger": "close", "priority": 1, "condition_refs": ("policy:stormnight:terminal-close@1",)},
        ),
        capability_refs=("capability:recovery@1", "capability:stealth@1"),
        observation_requirements=("observation:sound@1", "observation:visibility@1"),
        asset_refs=("asset:stormnight:case-file@1", "asset:stormnight:door@1", "asset:stormnight:hall@1", "asset:stormnight:safe@1"),
        interruption_policy="policy:stormnight:interrupt@1",
        recovery_policy="policy:stormnight:recovery@1",
        policy_revision="policy:stormnight:graph@1",
    )


def stormnight_primitive_catalog() -> tuple[ActionPrimitiveDefinition, ...]:
    return tuple(
        ActionPrimitiveDefinition.model_validate({"action_ref": ref, "action_version": "1", "target_kinds": ["room"], "required_capabilities": [capability], "observation_requirements": [observation], "physical_or_logical_fact_kind": "physical", "cost_policy": {}, "failure_policy": {}})
        for ref, capability, observation in (
            ("primitive:advance@1", "capability:movement@1", "observation:visibility@1"),
            ("primitive:loop@1", "capability:stealth@1", "observation:sound@1"),
            ("primitive:recover@1", "capability:recovery@1", "observation:control@1"),
            ("primitive:resolve@1", "capability:terminal@1", "observation:terminal@1"),
        )
    )


def admit_stormnight_action_graph() -> ActionGraphAdmissionResult:
    graph = stormnight_action_graph()
    catalogs = {
        "role": graph.role_refs,
        "capability": graph.capability_refs,
        "observation": graph.observation_requirements,
        "asset": graph.asset_refs,
        "policy": (graph.policy_revision, graph.recovery_policy, graph.interruption_policy),
    }
    return ActionGraphAdmissionResult.admit(graph, primitive_catalog=stormnight_primitive_catalog(), reference_catalogs=catalogs)


def stormnight_action_registry() -> P5PolicyRegistry:
    digest = "sha256:" + "a" * 64
    schemas = tuple(P5SchemaPin(schema_ref=f"schema:stormnight:action:{index}", schema_version=1, schema_digest=digest) for index in range(5))
    return P5PolicyRegistry.build(
        registry_ref="registry:p5:stormnight-action",
        registry_revision="registry:p5:stormnight-action@1",
        trusted_evidence_providers=(TrustedEvidenceProvider(provider_ref="provider:stormnight:action@1", provider_revision="provider:stormnight:action@1", provider_digest=digest, allowed_evidence_kinds=("evidence:stormnight:window@1",)),),
        owner_adapter_allowlist=(OwnerAdapterAllowance(owner_ref="authority:p5:investigation-conflict", allowed_event_names=_EVENTS, allowed_stream_grammar_refs=("grammar:stormnight:encounter@1",)),),
        quest_packages=(QuestPackageDefinition(package_ref="package:stormnight-action@1", package_revision="package:stormnight-action:v1@1", package_digest=digest, ruleset_revision="ruleset:stormnight:action@1", objectives=(QuestObjectiveDefinition(objective_ref="objective:stormnight:action@1", accepted_evidence_kind_refs=("evidence:stormnight:window@1",), visibility="project", expiry_policy_ref="expiry:never@1"),)),),
        ruleset_revisions=("ruleset:stormnight:action@1",),
        schema_pins=schemas,
        event_namespaces=(P5EventNamespace(namespace_ref="namespace:stormnight:action@1", event_name_prefix="gameplay.conflict.", allowed_event_names=_EVENTS),),
        event_catalog=tuple(P5EventCatalogEntry(event_name=event, namespace_ref="namespace:stormnight:action@1", schema_ref=schemas[index].schema_ref, schema_version=1, stream_grammar_ref="grammar:stormnight:encounter@1") for index, event in enumerate(_EVENTS)),
        stream_grammars=(P5StreamGrammar(grammar_ref="grammar:stormnight:encounter@1", pattern=r"^gameplay:conflict:encounter:[^:]+$"),),
    )


__all__ = ["admit_stormnight_action_graph", "stormnight_action_graph", "stormnight_action_registry", "stormnight_primitive_catalog"]
