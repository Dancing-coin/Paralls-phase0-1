from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "verification"))

from verify_perception_input_alignment import REQUIRED_EVIDENCE_FIELDS, build_matrix_trace


def test_perception_identity_matrix_proves_all_required_behavior_scenarios() -> None:
    trace, results = build_matrix_trace()
    by_id = {str(result["id"]): result for result in results}

    assert set(by_id) == {
        "fact-provider-same-capture-same-object",
        "fact-provider-cross-capture-not-same-tick",
        "multi-actor-same-capture-same-object-private-attributes",
        "multi-actor-same-capture-nearby-different-objects-not-merged",
        "vla-late-advisory-not-original-capture-result",
        "siming-multi-actor-summary-retains-object-time-identity",
    }
    assert all(result["status"] == "proved" for result in results)
    for result in results:
        for evidence in result["evidence"]:
            assert REQUIRED_EVIDENCE_FIELDS.issubset(evidence.keys())

    split = trace["multi_actor_split_object"]
    char_a = split["actor_results"]["char_a"]["character_bundle"]
    char_b = split["actor_results"]["char_b"]["character_bundle"]
    assert char_a["world_anchor_id"] == "world_anchor:object:obj_box_a"
    assert char_b["world_anchor_id"] == "world_anchor:object:obj_box_b"
    assert set(split["multi_actor_patch"]["world_anchor_ids"]) == {
        "world_anchor:object:obj_box_a",
        "world_anchor:object:obj_box_b",
    }
