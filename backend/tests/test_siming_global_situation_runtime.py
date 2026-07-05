from __future__ import annotations

import pytest

from app.services.siming_global_situation import SimingGlobalSituationLayer


def test_global_situation_uses_public_facts_and_siming_context_for_fairness_candidate() -> None:
    layer = SimingGlobalSituationLayer()
    snapshot = layer.assemble_snapshot(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        context_id="siming_mm:room_demo:scene_demo",
        l1_projected_facts=["l1_fact:lamp:light_drop"],
        authority_events=[{"event_id": "authority:1", "event_type": "visual_fact_event"}],
        world_results=[{"result_id": "world_result:1", "result_type": "environment_state_result"}],
        environment_events=[{"event_id": "env:1", "summary": "light level dropped"}],
        multi_actor_patch={"patch_refs": ["patch:public:1"], "actor_visibility": {"char_a": 0.9, "char_b": 0.2}},
        producer_ts=10,
    )
    fairness = layer.to_fairness_snapshot(snapshot)
    candidate = layer.to_intervention_candidate(snapshot)

    assert snapshot.context_id.startswith("siming_mm:")
    assert snapshot.visibility_imbalance == pytest.approx(0.7)
    assert snapshot.fairness_pressure >= 0.7
    assert "l1_fact:lamp:light_drop" in fairness.known_fact_ids
    assert candidate.established_fact_ids
    assert "situation_evidence_refs" in candidate.reason_tags


def test_vla_global_advisory_enhances_but_does_not_override_world_truth() -> None:
    layer = SimingGlobalSituationLayer()
    snapshot = layer.assemble_snapshot(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        context_id="siming_mm:room_demo:scene_demo",
        l1_projected_facts=["l1_fact:door:open"],
        world_results=[{"result_id": "world_result:door:open", "result_type": "object_state_result"}],
        vla_global_findings=[
            {
                "ref_id": "vla_global:1",
                "summary": "VLA advisory says door may be blocked",
                "target_ref": "obj_door",
                "world_anchor_id": "world_anchor:object:obj_door",
                "source_ref_lineage": ["sample_ref:vla:door"],
                "pressure": 1.0,
                "conflicts_with": "l1_fact:door:open",
            }
        ],
        multi_actor_patch={"actor_visibility": {"char_a": 0.5, "char_b": 0.5}},
        producer_ts=11,
    )

    assert snapshot.advisory_metadata["advisory_only"] is True
    assert snapshot.advisory_metadata["cannot_override_world_truth"] is True
    assert snapshot.conflict_refs == ["vla_advisory_conflict:vla_global:1:l1_fact:door:open"]
    assert "l1_fact:door:open" in snapshot.public_fact_refs
    vla_evidence = next(evidence for evidence in snapshot.evidence_chain if evidence.ref_id == "vla_global:1")
    assert vla_evidence.world_anchor_id == "world_anchor:object:obj_door"
    assert vla_evidence.target_ref == "obj_door"
    assert "sample_ref:vla:door" in vla_evidence.source_ref_lineage
    assert "world_anchor:object:obj_door" in snapshot.workbench_explanation["object_anchors"]


def test_siming_global_situation_rejects_character_private_cache() -> None:
    layer = SimingGlobalSituationLayer()

    with pytest.raises(ValueError, match="siming_mm"):
        layer.assemble_snapshot(
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            context_id="character_mm:char_a",
        )
    with pytest.raises(ValueError, match="private"):
        layer.assemble_snapshot(
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            context_id="siming_mm:room_demo:scene_demo",
            multi_actor_patch={"patch_refs": ["character_private_cache:char_a"]},
        )


def test_siming_global_situation_keeps_public_multi_actor_patch_anchor_without_private_context() -> None:
    layer = SimingGlobalSituationLayer()
    snapshot = layer.assemble_snapshot(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        context_id="siming_mm:room_demo:scene_demo",
        multi_actor_patch={
            "patch_refs": ["multi_actor_patch:capture_root:88"],
            "target_ref": "obj_letter",
            "world_anchor_id": "world_anchor:object:obj_letter",
            "source_ref_lineage": ["sample_ref:char_a", "sample_ref:char_b"],
            "actor_visibility": {"char_a": 0.9, "char_b": 0.4},
        },
        producer_ts=88,
    )

    patch_evidence = next(evidence for evidence in snapshot.evidence_chain if evidence.source_kind == "multi_actor_patch")
    assert patch_evidence.ref_id == "multi_actor_patch:capture_root:88"
    assert patch_evidence.world_anchor_id == "world_anchor:object:obj_letter"
    assert patch_evidence.target_ref == "obj_letter"
    assert "sample_ref:char_a" in patch_evidence.source_ref_lineage
    assert "character_mm:" not in str(snapshot.model_dump())
