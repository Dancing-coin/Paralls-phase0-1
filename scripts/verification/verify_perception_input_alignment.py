from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.models.capture_clock import same_capture_tick
from app.models.raw_fact import RawFactEvent, RawFactObservability, RawFactSource, RawFactTargets, RawFactWorld
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.services.siming_runtime import SimingRuntime
from app.world_runtime.intelligence_upgrade import PerceptionQueryFrame, SampleInputRef
from app.world_runtime.l1_occupancy import SpatialOccupancyService
from app.world_runtime.l1_perception_frame import L1PerceptionFrameService
from app.world_runtime.l1_runtime_perception_bridge import L1ActorProjectionInput, L1RuntimePerceptionBridge
from app.world_runtime.vla_provider import VLAProviderRequest
from app.world_runtime.vla_slow_path_scheduler import VLASlowPathScheduler
from common import repo_root, verification_dir, write_json, write_markdown


REQUIRED_EVIDENCE_FIELDS = {
    "capture_root_id",
    "capture_id",
    "actor_id",
    "world_anchor_id",
    "subject_ref",
    "target_ref",
    "source_ref_lineage",
    "clock_domain",
    "monotonic_tick",
    "result_kind",
}


def _result(
    result_id: str,
    title: str,
    proved: bool,
    evidence: list[dict[str, object]],
    notes: str = "",
    failure_domain: str = "",
) -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "failure_domain": failure_domain,
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def _identity_evidence(value: Any, *, result_kind: str, actor_id: str = "") -> dict[str, object]:
    if isinstance(value, dict):
        getter = value.get
    else:
        getter = lambda key, default=None: getattr(value, key, default)
    subject_ref = str(getter("subject_ref", "") or getter("subject_id", "") or actor_id or "")
    return {
        "capture_root_id": str(getter("capture_root_id", "") or ""),
        "capture_id": str(getter("capture_id", "") or ""),
        "actor_id": actor_id or str(getter("actor_id", "") or getter("subject_id", "") or ""),
        "world_anchor_id": str(getter("world_anchor_id", "") or ""),
        "subject_ref": subject_ref,
        "target_ref": str(getter("target_ref", "") or ""),
        "source_ref_lineage": list(getter("source_ref_lineage", []) or []),
        "clock_domain": str(getter("clock_domain", "") or ""),
        "monotonic_tick": getter("monotonic_tick", None),
        "result_kind": result_kind,
    }


def _fact(
    actor_id: str,
    object_id: str,
    *,
    capture_root_id: str,
    monotonic_tick: int,
    source_frame_index: int,
    producer_ts: int,
    fact_type: str = "object_visible",
    occluded: bool = False,
) -> RawFactEvent:
    return RawFactEvent(
        fact_family="visual_fact",
        fact_type=fact_type,
        relation_type="actor_sees_object",
        producer_ts=producer_ts,
        capture_root_id=capture_root_id,
        clock_domain="godot_main",
        monotonic_tick=monotonic_tick,
        source_frame_index=source_frame_index,
        wall_clock_ts=producer_ts,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source=RawFactSource(layer="L1", system="verify.identity_matrix", actor_id=actor_id),
        targets=RawFactTargets(object_id=object_id),
        world=RawFactWorld(distance_m=1.0 if not occluded else 2.5, state_after=fact_type),
        observability=RawFactObservability(visual=True, occluded=occluded),
    )


def _occupancy(*actor_ids: str) -> SpatialOccupancyService:
    occupancy = SpatialOccupancyService()
    for actor_id in actor_ids:
        occupancy.apply_actor_zone_update(
            actor_id=actor_id,
            previous_zone_id="",
            next_zone_id="zone_focus",
            producer_ts=100,
            source_ref=f"raw_fact_event:actor_entered_zone:{actor_id}:100",
        )
    return occupancy


def _has_required_evidence_fields(results: list[dict[str, object]]) -> bool:
    for result in results:
        if result["status"] != "proved":
            continue
        evidence_entries = result.get("evidence", [])
        if not isinstance(evidence_entries, list) or not evidence_entries:
            return False
        for evidence in evidence_entries:
            if not isinstance(evidence, dict):
                return False
            if not REQUIRED_EVIDENCE_FIELDS.issubset(evidence.keys()):
                return False
    return True


def build_matrix_trace() -> tuple[dict[str, object], list[dict[str, object]]]:
    frame_service = L1PerceptionFrameService()
    bridge = L1RuntimePerceptionBridge()
    trace: dict[str, object] = {}
    results: list[dict[str, object]] = []

    same_root = "capture_root:godot_main:room_demo:scene_demo:zone_focus:201"
    same_fact = _fact("char_b", "obj_letter", capture_root_id=same_root, monotonic_tick=201, source_frame_index=21, producer_ts=1201)
    same_bridge = bridge.consume_projected_facts(
        occupancy=_occupancy("char_b").snapshot(),
        projected_facts=[same_fact],
        character_runtime=CharacterAgentRuntime(),
        siming_runtime=SimingRuntime(),
        actor_id="char_b",
        provider_refs={
            "visual_inputs": [
                {
                    "provider_kind": "visual_patch",
                    "ref_id": "runtime://camera/char_b/frame/21",
                    "retention": "debug_artifact",
                }
            ]
        },
    )
    if same_bridge is None:
        raise RuntimeError("same capture bridge did not produce a result")
    trace["same_capture_same_object"] = same_bridge.model_dump(mode="json")
    same_evidence = [
        _identity_evidence(same_fact, result_kind="fact_chain_same_capture", actor_id="char_b"),
        _identity_evidence(same_bridge.character_frame, result_kind="provider_pqf_same_capture", actor_id="char_b"),
        _identity_evidence(same_bridge.character_bundle, result_kind="canonical_bundle_same_capture", actor_id="char_b"),
    ]
    results.append(
        _result(
            "fact-provider-same-capture-same-object",
            "Fact chain and provider chain same capture/same object resolve to one world anchor",
            same_capture_tick(same_fact, same_bridge.character_bundle)
            and same_bridge.character_bundle["world_anchor_id"] == same_fact.world_anchor_id
            and same_bridge.character_frame["visual_inputs"][0]["capture_root_id"] == same_fact.capture_root_id,
            same_evidence,
            failure_domain="time-or-object",
        )
    )

    cross_frame = frame_service.build_character_frame(
        subject_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        started_at=1300,
        ended_at=1301,
        capture_root_id="capture_root:godot_main:room_demo:scene_demo:zone_focus:202",
        clock_domain="godot_main",
        monotonic_tick=202,
        source_frame_index=22,
        visual_inputs=[SampleInputRef(provider_kind="visual_patch", ref_id="runtime://camera/char_b/frame/22")],
        structured_fact_refs=[same_fact.sample_ref_id],
        attention_target_object_ids=["obj_letter"],
    )
    cross_bundle = frame_service.build_canonical_bundle(
        cross_frame,
        local_spatial_state={"zone_id": "zone_focus"},
        target_state={"target_ref": "obj_letter"},
        environment_state={},
    )
    trace["cross_capture_same_object"] = {
        "fact": same_fact.model_dump(mode="json"),
        "provider_frame": cross_frame.model_dump(mode="json"),
        "provider_bundle": cross_bundle.model_dump(mode="json"),
    }
    results.append(
        _result(
            "fact-provider-cross-capture-not-same-tick",
            "Fact chain and provider chain across captures are not treated as same tick",
            not same_capture_tick(same_fact, cross_bundle)
            and cross_bundle.capture_root_id != same_fact.capture_root_id
            and cross_bundle.monotonic_tick != same_fact.monotonic_tick,
            [
                _identity_evidence(same_fact, result_kind="fact_chain_original_capture", actor_id="char_b"),
                _identity_evidence(cross_bundle, result_kind="provider_bundle_later_capture", actor_id="char_b"),
            ],
            failure_domain="time",
        )
    )

    multi_same_root = "capture_root:godot_main:room_demo:scene_demo:zone_focus:203"
    same_actor_result = bridge.consume_multi_actor_projected_facts(
        occupancy=_occupancy("char_a", "char_b").snapshot(),
        actor_projections=[
            L1ActorProjectionInput(
                actor_id="char_a",
                projected_facts=[
                    _fact("char_a", "obj_letter", capture_root_id=multi_same_root, monotonic_tick=203, source_frame_index=23, producer_ts=1203)
                ],
                actor_frame_ref="actor_frame:char_a:203",
                camera_frame_ref="camera:char_a:203",
                listener_frame_ref="listener:char_a:203",
            ),
            L1ActorProjectionInput(
                actor_id="char_b",
                projected_facts=[
                    _fact(
                        "char_b",
                        "obj_letter",
                        capture_root_id=multi_same_root,
                        monotonic_tick=203,
                        source_frame_index=23,
                        producer_ts=1204,
                        fact_type="object_partly_occluded",
                        occluded=True,
                    )
                ],
                actor_frame_ref="actor_frame:char_b:203",
                camera_frame_ref="camera:char_b:203",
                listener_frame_ref="listener:char_b:203",
            ),
        ],
        character_runtime=CharacterAgentRuntime(),
        siming_runtime=SimingRuntime(),
    )
    if same_actor_result is None:
        raise RuntimeError("same-object multi-actor bridge did not produce a result")
    trace["multi_actor_same_object"] = same_actor_result.model_dump(mode="json")
    char_a_same = same_actor_result.actor_results["char_a"]
    char_b_same = same_actor_result.actor_results["char_b"]
    results.append(
        _result(
            "multi-actor-same-capture-same-object-private-attributes",
            "Actor A/B same capture can share object anchor while retaining different private attributes",
            char_a_same["character_bundle"]["world_anchor_id"] == char_b_same["character_bundle"]["world_anchor_id"]
            and char_a_same["character_frame"]["capture_id"] != char_b_same["character_frame"]["capture_id"]
            and char_a_same["character_bundle"]["uncertainty"]["occluded_fact_count"]
            != char_b_same["character_bundle"]["uncertainty"]["occluded_fact_count"],
            [
                _identity_evidence(char_a_same["character_bundle"], result_kind="actor_private_same_object", actor_id="char_a"),
                _identity_evidence(char_b_same["character_bundle"], result_kind="actor_private_same_object", actor_id="char_b"),
            ],
            failure_domain="view",
        )
    )

    multi_split_root = "capture_root:godot_main:room_demo:scene_demo:zone_focus:204"
    split_actor_result = bridge.consume_multi_actor_projected_facts(
        occupancy=_occupancy("char_a", "char_b").snapshot(),
        actor_projections=[
            L1ActorProjectionInput(
                actor_id="char_a",
                projected_facts=[
                    _fact("char_a", "obj_box_a", capture_root_id=multi_split_root, monotonic_tick=204, source_frame_index=24, producer_ts=1205)
                ],
                camera_frame_ref="camera:char_a:204",
            ),
            L1ActorProjectionInput(
                actor_id="char_b",
                projected_facts=[
                    _fact("char_b", "obj_box_b", capture_root_id=multi_split_root, monotonic_tick=204, source_frame_index=24, producer_ts=1206)
                ],
                camera_frame_ref="camera:char_b:204",
            ),
        ],
        character_runtime=CharacterAgentRuntime(),
        siming_runtime=SimingRuntime(),
    )
    if split_actor_result is None:
        raise RuntimeError("split-object multi-actor bridge did not produce a result")
    trace["multi_actor_split_object"] = split_actor_result.model_dump(mode="json")
    char_a_split = split_actor_result.actor_results["char_a"]
    char_b_split = split_actor_result.actor_results["char_b"]
    split_anchors = set(split_actor_result.multi_actor_patch["world_anchor_ids"])
    results.append(
        _result(
            "multi-actor-same-capture-nearby-different-objects-not-merged",
            "Actor A/B same capture looking at nearby different objects retain separate object anchors",
            char_a_split["character_bundle"]["world_anchor_id"] == "world_anchor:object:obj_box_a"
            and char_b_split["character_bundle"]["world_anchor_id"] == "world_anchor:object:obj_box_b"
            and char_a_split["character_bundle"]["world_anchor_id"] != char_b_split["character_bundle"]["world_anchor_id"]
            and split_anchors == {"world_anchor:object:obj_box_a", "world_anchor:object:obj_box_b"},
            [
                _identity_evidence(char_a_split["character_bundle"], result_kind="actor_private_split_object", actor_id="char_a"),
                _identity_evidence(char_b_split["character_bundle"], result_kind="actor_private_split_object", actor_id="char_b"),
            ],
            failure_domain="object",
        )
    )

    request = VLAProviderRequest.from_pqf(
        PerceptionQueryFrame(**same_bridge.character_frame),
        owner_kind="character",
        owner_id="char_b",
        model_id="qwen3-vl-plus",
    )
    late_result = VLASlowPathScheduler(timeout_seconds=0.01).timeout_result(request)
    trace["vla_late_advisory"] = late_result.model_dump(mode="json")
    results.append(
        _result(
            "vla-late-advisory-not-original-capture-result",
            "VLA slow-path timeout keeps capture identity but marks itself late advisory",
            late_result.capture_root_id == same_root
            and late_result.capture_relation == "late_advisory"
            and late_result.advisory is True,
            [_identity_evidence(late_result, result_kind="vla_late_advisory", actor_id="char_b")],
            failure_domain="advisory",
        )
    )

    siming_identity = same_actor_result.siming_result["read_model"]["current_state"]["perception_identity"]
    siming_patch = same_actor_result.siming_bundle["target_state"]["multi_actor_patch"]
    trace["siming_multi_actor_identity"] = {
        "read_model_identity": siming_identity,
        "multi_actor_patch": siming_patch,
    }
    results.append(
        _result(
            "siming-multi-actor-summary-retains-object-time-identity",
            "Siming multi-actor summary retains object and time identity",
            siming_identity["capture_root_id"] == multi_same_root
            and siming_identity["world_anchor_id"] == "world_anchor:object:obj_letter"
            and siming_identity["monotonic_tick"] == 203
            and siming_patch["world_anchor_id"] == "world_anchor:object:obj_letter",
            [
                {
                    **siming_identity,
                    "actor_id": "siming",
                    "result_kind": "siming_multi_actor_summary",
                }
            ],
            failure_domain="siming",
        )
    )

    return trace, results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    trace, results = build_matrix_trace()
    evidence_shape_ok = _has_required_evidence_fields(results)
    if not evidence_shape_ok:
        results.append(
            _result(
                "matrix-evidence-shape",
                "Every proved matrix result includes the required identity evidence fields",
                False,
                [],
                notes=f"required_fields={sorted(REQUIRED_EVIDENCE_FIELDS)}",
                failure_domain="evidence",
            )
        )

    trace_path = log_dir / "perception-input-alignment-matrix-trace.json"
    write_json(trace_path, trace)
    for result in results:
        if result["status"] == "proved":
            result["trace_artifact"] = str(trace_path)

    overall = evidence_shape_ok and all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_perception_input_alignment_passed": overall,
        "required_evidence_fields": sorted(REQUIRED_EVIDENCE_FIELDS),
        "results": results,
        "artifacts": {"trace": str(trace_path)},
    }
    report_json = log_dir / "perception-input-alignment-report.json"
    report_md = log_dir / "perception-input-alignment-report.md"
    write_json(report_json, report)
    write_markdown(
        report_md,
        "Perception Input Alignment Matrix Verification Report",
        report,
        "overall_perception_input_alignment_passed",
    )
    print(f"perception_input_alignment_report_json={report_json}")
    print(f"perception_input_alignment_report_md={report_md}")
    print(f"overall_perception_input_alignment_passed={overall}")
    for entry in results:
        print(f"{entry['id']}={entry['status']} failure_domain={entry.get('failure_domain', '')}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
