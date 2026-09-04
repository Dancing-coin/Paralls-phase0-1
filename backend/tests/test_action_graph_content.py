from __future__ import annotations

import pytest

from app.gameplay import action_graph_content as action_graph_content_module
from app.gameplay.action_graph_content import ActionGraphAdmissionResult, ActionGraphDefinition
from app.gameplay.shared_contracts import ActionPrimitiveDefinition


def _primitive_catalog() -> tuple[ActionPrimitiveDefinition, ...]:
    return (
        ActionPrimitiveDefinition.model_validate(
            {
                "action_ref": "primitive:advance@1",
                "action_version": "1",
                "target_kinds": ["room"],
                "required_capabilities": ["capability:movement@1"],
                "observation_requirements": ["observation:visibility@1"],
                "physical_or_logical_fact_kind": "physical",
                "cost_policy": {},
                "failure_policy": {},
            }
        ),
        ActionPrimitiveDefinition.model_validate(
            {
                "action_ref": "primitive:loop@1",
                "action_version": "1",
                "target_kinds": ["room"],
                "required_capabilities": ["capability:stealth@1"],
                "observation_requirements": ["observation:sound@1"],
                "physical_or_logical_fact_kind": "logical",
                "cost_policy": {},
                "failure_policy": {},
            }
        ),
        ActionPrimitiveDefinition.model_validate(
            {
                "action_ref": "primitive:recover@1",
                "action_version": "1",
                "target_kinds": ["room"],
                "required_capabilities": ["capability:recovery@1"],
                "observation_requirements": ["observation:control@1"],
                "physical_or_logical_fact_kind": "logical",
                "cost_policy": {},
                "failure_policy": {},
            }
        ),
        ActionPrimitiveDefinition.model_validate(
            {
                "action_ref": "primitive:resolve@1",
                "action_version": "1",
                "target_kinds": ["room"],
                "required_capabilities": ["capability:terminal@1"],
                "observation_requirements": ["observation:terminal@1"],
                "physical_or_logical_fact_kind": "physical",
                "cost_policy": {},
                "failure_policy": {},
            }
        ),
    )


def _graph(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "graph_ref": "graph:warehouse-case",
        "graph_revision": "graph:warehouse-case@1",
        "action_family": "scripted_mystery",
        "role_refs": ["role:pursuer@1", "role:survivor@1", "role:witness@1"],
        "primitive_refs": [
            "primitive:advance@1",
            "primitive:loop@1",
            "primitive:recover@1",
            "primitive:resolve@1",
        ],
        "nodes": [
            {
                "node_ref": "a_start",
                "primitive_ref": "primitive:advance@1",
                "phase": "active",
                "duration_window": [0, 1],
                "cancel_targets": ["a_start"],
                "condition_refs": ["state:entry@1"],
                "asset_ref": "asset:door@1",
                "contact_marker_refs": ["marker:doorway@1"],
            },
            {
                "node_ref": "b_patrol",
                "primitive_ref": "primitive:loop@1",
                "phase": "active",
                "duration_window": [1, 2],
                "cancel_targets": ["a_start"],
                "condition_refs": ["state:patrol@1"],
                "asset_ref": "asset:hallway@1",
                "contact_marker_refs": ["marker:halls@1"],
            },
            {
                "node_ref": "c_recovery",
                "primitive_ref": "primitive:recover@1",
                "phase": "recovery",
                "duration_window": [2, 3],
                "cancel_targets": ["b_patrol"],
                "condition_refs": ["policy:recovery@1"],
                "asset_ref": "asset:safe-room@1",
                "contact_marker_refs": ["marker:safe-room@1"],
            },
            {
                "node_ref": "d_terminal",
                "primitive_ref": "primitive:resolve@1",
                "phase": "terminal",
                "duration_window": [3, 4],
                "cancel_targets": ["c_recovery"],
                "condition_refs": ["policy:terminal@1"],
                "asset_ref": "asset:case-file@1",
                "contact_marker_refs": ["marker:case-close@1"],
            },
        ],
        "edges": [
            {
                "from_node": "a_start",
                "to_node": "b_patrol",
                "trigger": "advance",
                "priority": 1,
                "condition_refs": ["state:visible@1"],
            },
            {
                "from_node": "b_patrol",
                "to_node": "c_recovery",
                "trigger": "recover",
                "priority": 1,
                "condition_refs": ["policy:cooldown-recover@1"],
            },
            {
                "from_node": "c_recovery",
                "to_node": "d_terminal",
                "trigger": "close",
                "priority": 1,
                "condition_refs": ["policy:terminal-close@1"],
            },
        ],
        "capability_refs": ["capability:recovery@1", "capability:stealth@1"],
        "observation_requirements": ["observation:visibility@1", "observation:sound@1"],
        "asset_refs": ["asset:case-file@1", "asset:door@1"],
        "interruption_policy": "policy:interrupt-default@1",
        "recovery_policy": "policy:recovery@1",
        "policy_revision": "policy:action-graph@1",
    }
    value.update(overrides)
    return value


def test_action_graph_admission_accepts_canonical_graph_without_store_access(monkeypatch: pytest.MonkeyPatch) -> None:
    class ExplodingStore:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("event store should not be touched")

    monkeypatch.setattr(action_graph_content_module, "GameplayEventStore", ExplodingStore, raising=False)

    graph = ActionGraphDefinition.model_validate(_graph())
    result = ActionGraphAdmissionResult.admit(graph, primitive_catalog=_primitive_catalog())

    assert result.accepted is True
    assert result.error_code is None
    assert result.graph_digest is not None


def test_action_graph_admission_rejects_unknown_primitive() -> None:
    graph = ActionGraphDefinition.model_validate(
        _graph(
            nodes=[
                {
                    "node_ref": "a_start",
                    "primitive_ref": "primitive:advance@1",
                    "phase": "active",
                    "duration_window": [0, 1],
                    "cancel_targets": ["a_start"],
                    "condition_refs": ["state:entry@1"],
                    "asset_ref": "asset:door@1",
                    "contact_marker_refs": ["marker:doorway@1"],
                },
                {
                    "node_ref": "b_patrol",
                    "primitive_ref": "primitive:missing@1",
                    "phase": "active",
                    "duration_window": [1, 2],
                    "cancel_targets": ["a_start"],
                    "condition_refs": ["state:patrol@1"],
                    "asset_ref": "asset:hallway@1",
                    "contact_marker_refs": ["marker:halls@1"],
                },
                {
                    "node_ref": "c_recovery",
                    "primitive_ref": "primitive:recover@1",
                    "phase": "recovery",
                    "duration_window": [2, 3],
                    "cancel_targets": ["b_patrol"],
                    "condition_refs": ["policy:recovery@1"],
                    "asset_ref": "asset:safe-room@1",
                    "contact_marker_refs": ["marker:safe-room@1"],
                },
                {
                    "node_ref": "d_terminal",
                    "primitive_ref": "primitive:resolve@1",
                    "phase": "terminal",
                    "duration_window": [3, 4],
                    "cancel_targets": ["c_recovery"],
                    "condition_refs": ["policy:terminal@1"],
                    "asset_ref": "asset:case-file@1",
                    "contact_marker_refs": ["marker:case-close@1"],
                },
            ]
        )
    )

    result = ActionGraphAdmissionResult.admit(graph, primitive_catalog=_primitive_catalog())

    assert not result.accepted
    assert result.error_code == "action_graph_primitive_unknown"


def test_action_graph_admission_rejects_duplicate_node() -> None:
    graph = ActionGraphDefinition.model_validate(
        _graph(
            nodes=[
                _graph()["nodes"][0],
                _graph()["nodes"][1],
                _graph()["nodes"][1],
                _graph()["nodes"][3],
            ]
        )
    )

    result = ActionGraphAdmissionResult.admit(graph, primitive_catalog=_primitive_catalog())

    assert not result.accepted
    assert result.error_code == "action_graph_node_duplicate"


def test_action_graph_admission_rejects_cycle_without_bounded_loop() -> None:
    graph = ActionGraphDefinition.model_validate(
        _graph(
            edges=[
                {
                    "from_node": "a_start",
                    "to_node": "b_patrol",
                    "trigger": "advance",
                    "priority": 1,
                    "condition_refs": ["state:visible@1"],
                },
                {
                    "from_node": "b_patrol",
                    "to_node": "a_start",
                    "trigger": "repeat",
                    "priority": 1,
                    "condition_refs": ["state:repeat@1"],
                },
                {
                    "from_node": "b_patrol",
                    "to_node": "c_recovery",
                    "trigger": "recover",
                    "priority": 1,
                    "condition_refs": ["policy:cooldown-recover@1"],
                },
                {
                    "from_node": "c_recovery",
                    "to_node": "d_terminal",
                    "trigger": "close",
                    "priority": 1,
                    "condition_refs": ["policy:terminal-close@1"],
                },
            ]
        )
    )

    result = ActionGraphAdmissionResult.admit(graph, primitive_catalog=_primitive_catalog())

    assert not result.accepted
    assert result.error_code == "action_graph_cycle_invalid"


def test_action_graph_admission_rejects_conflicting_edge() -> None:
    graph = ActionGraphDefinition.model_validate(
        _graph(
            edges=[
                {
                    "from_node": "a_start",
                    "to_node": "b_patrol",
                    "trigger": "advance",
                    "priority": 1,
                    "condition_refs": ["state:visible@1"],
                },
                {
                    "from_node": "a_start",
                    "to_node": "c_recovery",
                    "trigger": "advance",
                    "priority": 2,
                    "condition_refs": ["policy:conflict@1"],
                },
                {
                    "from_node": "b_patrol",
                    "to_node": "c_recovery",
                    "trigger": "recover",
                    "priority": 1,
                    "condition_refs": ["policy:cooldown-recover@1"],
                },
                {
                    "from_node": "c_recovery",
                    "to_node": "d_terminal",
                    "trigger": "close",
                    "priority": 1,
                    "condition_refs": ["policy:terminal-close@1"],
                },
            ]
        )
    )

    result = ActionGraphAdmissionResult.admit(graph, primitive_catalog=_primitive_catalog())

    assert not result.accepted
    assert result.error_code == "action_graph_edge_conflict"


def test_action_graph_admission_rejects_missing_recovery_path() -> None:
    graph = ActionGraphDefinition.model_validate(
        _graph(
            nodes=[
                _graph()["nodes"][0],
                _graph()["nodes"][1],
                {
                    "node_ref": "c_recovery",
                    "primitive_ref": "primitive:recover@1",
                    "phase": "active",
                    "duration_window": [2, 3],
                    "cancel_targets": ["b_patrol"],
                    "condition_refs": ["policy:recovery@1"],
                    "asset_ref": "asset:safe-room@1",
                    "contact_marker_refs": ["marker:safe-room@1"],
                },
                _graph()["nodes"][3],
            ]
        )
    )

    result = ActionGraphAdmissionResult.admit(graph, primitive_catalog=_primitive_catalog())

    assert not result.accepted
    assert result.error_code == "action_graph_recovery_path_missing"


def test_action_graph_admission_rejects_unknown_declared_reference_when_catalog_is_supplied() -> None:
    graph = ActionGraphDefinition.model_validate(_graph())
    result = ActionGraphAdmissionResult.admit(
        graph,
        primitive_catalog=_primitive_catalog(),
        reference_catalogs={
            "role": graph.role_refs,
            "capability": graph.capability_refs,
            "observation": graph.observation_requirements,
            "asset": ("asset:door@1",),
            "policy": (graph.policy_revision, graph.recovery_policy, graph.interruption_policy),
        },
    )
    assert not result.accepted
    assert result.error_code == "action_graph_asset_unknown"
