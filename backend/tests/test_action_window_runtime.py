from __future__ import annotations

import pytest

from app.gameplay.action_graph_content import ActionGraphDefinition, ActionGraphEdge, ActionGraphNode
from app.gameplay.action_window_runtime import ActionWindowIntent, ActionWindowValidator, SpatialSnapshotRef


def _valid_graph() -> ActionGraphDefinition:
    return ActionGraphDefinition(
        graph_ref="graph:warehouse-case",
        graph_revision="graph:warehouse-case@1",
        action_family="scripted_mystery",
        role_refs=("role:pursuer@1", "role:survivor@1", "role:witness@1"),
        primitive_refs=("primitive:advance@1", "primitive:loop@1", "primitive:recover@1", "primitive:resolve@1"),
        nodes=(
            ActionGraphNode(node_ref="a_start", primitive_ref="primitive:advance@1", phase="active", duration_window=(0, 1), cancel_targets=("a_start",), condition_refs=("state:entry@1",), asset_ref="asset:door@1", contact_marker_refs=("marker:doorway@1",)),
            ActionGraphNode(node_ref="b_patrol", primitive_ref="primitive:loop@1", phase="active", duration_window=(1, 2), cancel_targets=("a_start",), condition_refs=("state:patrol@1",), asset_ref="asset:hallway@1", contact_marker_refs=("marker:halls@1",)),
            ActionGraphNode(node_ref="c_recovery", primitive_ref="primitive:recover@1", phase="recovery", duration_window=(2, 3), cancel_targets=("b_patrol",), condition_refs=("policy:recovery@1",), asset_ref="asset:safe-room@1", contact_marker_refs=("marker:safe-room@1",)),
            ActionGraphNode(node_ref="d_terminal", primitive_ref="primitive:resolve@1", phase="terminal", duration_window=(3, 4), cancel_targets=("c_recovery",), condition_refs=("policy:terminal@1",), asset_ref="asset:case-file@1", contact_marker_refs=("marker:case-close@1",)),
        ),
        edges=(
            ActionGraphEdge(from_node="a_start", to_node="b_patrol", trigger="advance", priority=1, condition_refs=("state:visible@1",)),
            ActionGraphEdge(from_node="b_patrol", to_node="c_recovery", trigger="recover", priority=1, condition_refs=("policy:cooldown-recover@1",)),
            ActionGraphEdge(from_node="c_recovery", to_node="d_terminal", trigger="close", priority=1, condition_refs=("policy:terminal-close@1",)),
        ),
        capability_refs=("capability:recovery@1", "capability:stealth@1"),
        observation_requirements=("observation:visibility@1", "observation:sound@1"),
        asset_refs=("asset:case-file@1", "asset:door@1"),
        interruption_policy="policy:interrupt-default@1",
        recovery_policy="policy:recovery@1",
        policy_revision="policy:action-graph@1",
    )


def _intent(**overrides: object) -> ActionWindowIntent:
    payload: dict[str, object] = {
        "attempt_ref": "attempt:1",
        "encounter_ref": "encounter:1",
        "actor_ref": "character:survivor",
        "window_index": 0,
        "window_start_tick": 0,
        "window_end_tick": 1,
        "graph_ref": "graph:warehouse-case",
        "graph_revision": "graph:warehouse-case@1",
        "node_ref": "a_start",
        "target_refs": ("room:hall",),
        "expected_revision_vector": {"scene:warehouse": 1},
        "local_position_sample": (0.0, 0.0, 0.0),
        "facing_sample": (0.0, 0.0, 1.0),
        "visibility_sample": {"visible": False, "distance_band": "near"},
        "sound_sample": {"heard": False},
        "contact_sample": {"in_contact": False},
        "navigation_revision": "nav:warehouse@1",
        "collision_revision": "collision:warehouse@1",
        "occlusion_revision": "occlusion:warehouse@1",
        "sound_zone_revision": "sound:warehouse@1",
        "deterministic_seed": "seed:1",
        "evidence_refs": ("evidence:sample@1",),
    }
    payload.update(overrides)
    return ActionWindowIntent.model_validate(payload)


def _snapshot() -> SpatialSnapshotRef:
    return SpatialSnapshotRef(
        snapshot_ref="snapshot:warehouse@1",
        navigation_revision="nav:warehouse@1",
        collision_revision="collision:warehouse@1",
        occlusion_revision="occlusion:warehouse@1",
        sound_zone_revision="sound:warehouse@1",
    )


def test_action_window_accepts_valid_sample_without_store_access() -> None:
    result = ActionWindowValidator.validate(_intent(), graph=_valid_graph(), spatial_snapshot=_snapshot())
    assert result.accepted
    assert result.perception is not None


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"navigation_revision": "nav:warehouse@2"}, "action_window_spatial_revision_conflict"),
        ({"visibility_sample": {"scope": "actor:other", "visible": True}}, "action_window_private_evidence_leaked"),
        ({"contact_sample": {"tampered": True}}, "action_window_measurement_conflict"),
    ],
)
def test_action_window_rejects_invalid_evidence_zero_write(overrides: dict[str, object], error: str) -> None:
    result = ActionWindowValidator.validate(_intent(**overrides), graph=_valid_graph(), spatial_snapshot=_snapshot())
    assert not result.accepted
    assert result.error_code == error


def test_action_window_rejects_out_of_order_and_changed_duplicate() -> None:
    graph = _valid_graph()
    snapshot = _snapshot()
    ordered = ActionWindowValidator.validate(_intent(), graph=graph, spatial_snapshot=snapshot)
    assert ordered.accepted
    out_of_order = ActionWindowValidator.validate(_intent(window_index=2), graph=graph, spatial_snapshot=snapshot, previous_window_index=0)
    assert not out_of_order.accepted
    assert out_of_order.error_code == "action_window_order_conflict"
    changed = ActionWindowValidator.validate(_intent(window_index=0, deterministic_seed="seed:changed"), graph=graph, spatial_snapshot=snapshot, prior_intent_digest=ordered.intent_digest)
    assert not changed.accepted
    assert changed.error_code == "action_window_idempotency_reused"
