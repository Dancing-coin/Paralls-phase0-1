from __future__ import annotations

import pytest


def test_entity_ref_rejects_unknown_fields_under_strict_model_contract() -> None:
    from app.gameplay.shared_contracts import EntityRef

    with pytest.raises((TypeError, ValueError), match="extra|forbid|unexpected"):
        EntityRef(entity_type="actor", entity_id="entity:strict:1", unexpected_field="nope")


def test_semantic_registry_rejects_namespace_collision() -> None:
    from app.gameplay.semantic_registry import SemanticDefinition, SemanticRegistry

    registry = SemanticRegistry()
    registry.register(
        SemanticDefinition(
            namespace="core",
            semantic_id="tag.health",
            semantic_version="1",
            tags=("health",),
            materials=(),
            properties=(),
            source_revision="semantic:core:1",
        )
    )

    with pytest.raises((TypeError, ValueError), match="collision|namespace|duplicate"):
        registry.register(
            SemanticDefinition(
                namespace="other",
                semantic_id="tag.health",
                semantic_version="1",
                tags=("health",),
                materials=(),
                properties=(),
                source_revision="semantic:other:1",
            )
        )


def test_meta_rule_trace_is_deterministic_for_pinned_input() -> None:
    from app.gameplay.semantic_registry import MetaRuleDefinition, RuleEvaluationInput, SemanticRegistry, SemanticSnapshot

    registry = SemanticRegistry()
    registry.register_meta_rule(
        MetaRuleDefinition(
            rule_ref="rule:meta:1",
            rule_version="1",
            trigger_selectors=("action.attempt",),
            guard_expression="true",
            phase="pre",
            priority=10,
            conflict_policy="reject",
            evaluation_budget=8,
            proposal_templates=(),
            trace_policy="full",
            source_revision="semantic:rules:1",
        )
    )
    snapshot = SemanticSnapshot(
        entity_ref="entity:actor:1",
        component_refs=("component:core",),
        resolved_tags=("tag.health",),
        resolved_parameters={},
        statuses=(),
        relation_refs=(),
        policy_context_ref="policy:demo:v1",
        source_revision_vector={"semantic:core:1": 1},
        digest="sha256:trace",
    )
    evaluation = RuleEvaluationInput(
        trigger_ref="trigger:action:1",
        semantic_snapshot=snapshot,
        pinned_revisions={"semantic": 1, "policy": 3},
        explicit_time_inputs={"tick": 42},
        evidence_refs=("evidence:1",),
    )

    trace_1 = registry.evaluate(evaluation)
    trace_2 = registry.evaluate(evaluation)

    assert trace_1 == trace_2


def test_creator_authorization_decisions_remain_project_scoped() -> None:
    from app.gameplay.shared_contracts import AuthorizationDecision

    decision = AuthorizationDecision(
        decision_id="decision:creator:1",
        principal_ref="principal:reader",
        project_scope="project:demo",
        capability="reader",
        data_classification="project",
        policy_revision="policy:auth:v1",
        decision="allow",
        reason_code="within_project_scope",
        expires_at=None,
        audit_ref="audit:creator:1",
    )

    assert decision.project_scope == "project:demo"
    assert decision.capability == "reader"
