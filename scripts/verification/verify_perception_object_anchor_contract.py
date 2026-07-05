from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.character_agent.reasoning.actor_scene_knowledge import ActorSceneKnowledgeEntry, ActorSceneKnowledgeStore
from app.models.raw_fact import RawFactEvent, RawFactSource, RawFactTargets, RawFactWorld
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.services.siming_global_situation import SimingGlobalSituationLayer
from app.services.siming_runtime import SimingRuntime
from app.world_runtime.l1_occupancy import SpatialOccupancyService
from app.world_runtime.l1_runtime_perception_bridge import L1RuntimePerceptionBridge
from app.world_runtime.vla_percept_bridge import merge_vla_advisory_into_bundle
from app.world_runtime.vla_provider import VLAProviderResult, VLAProviderStatus
from common import repo_root, verification_dir, write_json, write_markdown


def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)

    occupancy = SpatialOccupancyService()
    occupancy.apply_actor_zone_update(
        actor_id="char_b",
        previous_zone_id="",
        next_zone_id="zone_focus",
        producer_ts=100,
        source_ref="raw_fact_event:actor_entered_zone:100",
    )
    fact = RawFactEvent(
        fact_family="spatial_access_fact",
        fact_type="actor_approached_object",
        relation_type="proximity",
        producer_ts=910,
        capture_root_id="capture_root:godot_main:room_demo:scene_demo:zone_focus:88",
        clock_domain="godot_main",
        monotonic_tick=88,
        source_frame_index=14,
        wall_clock_ts=910,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source=RawFactSource(layer="L1", system="verify.object_anchor", actor_id="char_b"),
        targets=RawFactTargets(object_id="obj_letter"),
        world=RawFactWorld(distance_m=1.2, state_after="near"),
    )
    bridge = L1RuntimePerceptionBridge().consume_projected_facts(
        occupancy=occupancy.snapshot(),
        projected_facts=[fact],
        character_runtime=CharacterAgentRuntime(),
        siming_runtime=SimingRuntime(),
        actor_id="char_b",
        provider_refs={
            "visual_inputs": [
                {
                    "provider_kind": "visual_patch",
                    "ref_id": "runtime://camera/MainCamera/frame/14",
                    "retention": "debug_artifact",
                }
            ]
        },
    )
    if bridge is None:
        raise RuntimeError("object anchor bridge proof did not produce a bundle")

    advisory = VLAProviderResult(
        result_id="vla_result:verify:obj_letter",
        request_id=bridge.character_frame["query_id"],
        status=VLAProviderStatus.MOCK_PROVIDER_VERIFIED,
        subject_ref="runtime://camera/MainCamera/frame/14",
        target_ref="obj_letter",
        world_anchor_id=fact.world_anchor_id,
        source_ref_lineage=[*fact.source_ref_lineage, "vla_result:verify:obj_letter"],
        provider_id="verify",
        model_id="mock",
        model_version="verify",
        findings=[{"finding_type": "visual_spatial_advisory", "summary": "letter may be partly occluded"}],
        confidence=0.61,
        conflict_refs=[fact.sample_ref_id],
        expires_at=911,
    )
    merged = merge_vla_advisory_into_bundle(
        CharacterAgentRuntimePerceptionBundleAdapter(bridge.character_bundle).bundle,
        advisory,
    )
    store = ActorSceneKnowledgeStore()
    updates = store.apply_canonical_percept_bundle(merged, session_id="verify", producer_ts=911)

    split_store = ActorSceneKnowledgeStore()
    split_store.upsert(
        ActorSceneKnowledgeEntry(
            entry_id="ask:char_b:box_a:l1",
            actor_id="char_b",
            session_id="verify",
            scene_id="scene_demo",
            world_anchor_id="world_anchor:object:obj_box_a",
            subject_ref="box",
            target_ref="obj_box_a",
            knowledge_type="space",
            summary="left box reachable",
            source_kind="l1_projected_fact",
            source_refs=["sample_ref:l1:box_a"],
            confidence=0.9,
            world_truth_marker="l1_projected_fact_ref",
        ),
        producer_ts=1,
    )
    split_store.upsert(
        ActorSceneKnowledgeEntry(
            entry_id="ask:char_b:box_b:l1",
            actor_id="char_b",
            session_id="verify",
            scene_id="scene_demo",
            world_anchor_id="world_anchor:object:obj_box_b",
            subject_ref="box",
            target_ref="obj_box_b",
            knowledge_type="space",
            summary="right box reachable",
            source_kind="l1_projected_fact",
            source_refs=["sample_ref:l1:box_b"],
            confidence=0.9,
            world_truth_marker="l1_projected_fact_ref",
        ),
        producer_ts=2,
    )

    siming = SimingGlobalSituationLayer()
    snapshot = siming.assemble_snapshot(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        context_id="siming_mm:room_demo:scene_demo",
        l1_projected_facts=[fact.sample_ref_id],
        vla_global_findings=[
            {
                "ref_id": "vla_global:verify:obj_letter",
                "summary": "global advisory references the same letter",
                "target_ref": "obj_letter",
                "world_anchor_id": fact.world_anchor_id,
                "source_ref_lineage": advisory.source_ref_lineage,
                "pressure": 0.5,
                "conflicts_with": fact.sample_ref_id,
            }
        ],
        producer_ts=912,
    )

    trace = {
        "fact": fact.model_dump(mode="json"),
        "character_bundle": bridge.character_bundle,
        "merged_bundle": merged.model_dump(mode="json"),
        "ask_updates": [update.model_dump(mode="json") for update in updates],
        "split_store_entries": [entry.model_dump(mode="json") for entry in split_store.entries_for_actor("char_b")],
        "siming_snapshot": snapshot.model_dump(mode="json"),
    }
    trace_path = log_dir / "perception-object-anchor-lineage.json"
    write_json(trace_path, trace)

    ask_entries = store.entries_for_actor("char_b", session_id="verify", scene_id="scene_demo")
    same_anchor_ok = (
        bridge.character_bundle["target_state"]["world_anchor_id"] == fact.world_anchor_id
        and merged.uncertainty["vla_advisory"]["world_anchor_id"] == fact.world_anchor_id
        and any(entry.world_anchor_id == fact.world_anchor_id for entry in ask_entries)
    )
    split_ok = {entry.world_anchor_id for entry in split_store.entries_for_actor("char_b")} == {
        "world_anchor:object:obj_box_a",
        "world_anchor:object:obj_box_b",
    }
    advisory_ok = all(
        entry.world_truth_marker == "subjective_not_world_truth"
        for entry in ask_entries
        if entry.source_kind == "vla_advisory"
    ) and advisory.writes_world_truth is False
    siming_ok = any(evidence.world_anchor_id == fact.world_anchor_id for evidence in snapshot.evidence_chain)

    results = [
        _result("same-object-cross-chain-anchor", "Fact, bundle, VLA advisory, and ASK share obj_letter world_anchor_id", same_anchor_ok, [str(trace_path)]),
        _result("nearby-same-name-not-merged", "Same subject label with different world_anchor_id remains split", split_ok, [str(trace_path)]),
        _result("advisory-not-world-truth", "VLA advisory remains subjective and cannot write world truth", advisory_ok, [str(trace_path)]),
        _result("siming-evidence-anchor-preserved", "Siming evidence chain preserves object anchor metadata", siming_ok, [str(trace_path)]),
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_perception_object_anchor_contract_passed": overall,
        "results": results,
        "artifacts": {"trace": str(trace_path)},
    }
    report_json = log_dir / "perception-object-anchor-contract-report.json"
    report_md = log_dir / "perception-object-anchor-contract-report.md"
    write_json(report_json, report)
    write_markdown(
        report_md,
        "Perception Object Anchor Contract Verification Report",
        report,
        "overall_perception_object_anchor_contract_passed",
    )
    print(f"perception_object_anchor_contract_report_json={report_json}")
    print(f"perception_object_anchor_contract_report_md={report_md}")
    print(f"overall_perception_object_anchor_contract_passed={overall}")
    for entry in results:
        print(f"{entry['id']}={entry['status']}")
    return 0 if overall else 1


class CharacterAgentRuntimePerceptionBundleAdapter:
    def __init__(self, payload: dict[str, object]) -> None:
        from app.world_runtime.intelligence_upgrade import CanonicalPerceptBundle

        self.bundle = CanonicalPerceptBundle(**payload)


if __name__ == "__main__":
    raise SystemExit(main())
