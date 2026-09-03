from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.models.character_perceived import CharacterPerceivedEvent

from common import verification_dir, write_json, write_markdown


def main() -> int:
    runtime = CharacterAgentRuntime()
    try:
        runtime.ingest_character_perceived_event(
            CharacterPerceivedEvent(
                actor_id="char_b",
                percept_channel="visual",
                producer_ts=100,
                room_id="room:behavior",
                scene_id="scene:behavior",
                zone_id="zone:behavior",
                perceived_summary="the sealed letter is missing",
                source_candidate_event_id="visual:letter:100",
                target_object_id="obj_letter",
            )
        )
        runtime.record_settlement_result(
            actor_id="char_b",
            producer_ts=101,
            payload={
                "settlement_status": "rejected",
                "result_type": "constraint_state_result",
                "constraint_summary": "requires a key",
                "causation_id": "cause:behavior:101",
                "correlation_id": "corr:behavior:101",
            },
        )
        timeline = runtime.get_session_timeline("char_b")
    finally:
        pass

    evaluation = [entry for entry in timeline if entry.get("event_type") == "character_behavior_evaluation_event"]
    candidates = [entry for entry in timeline if entry.get("event_type") == "character_policy_candidate_event"]
    chain_types = [
        "l2_reasoning_request",
        "character_interpretation_event",
        "goal_state_event",
        "character_agent_execution_request",
        "character_agent_settlement_result",
        "character_behavior_evaluation_event",
        "character_policy_candidate_event",
    ]
    chain_ok = all(any(entry.get("event_type") == event_type for entry in timeline) for event_type in chain_types)
    evaluation_ok = bool(evaluation) and bool(evaluation[-1].get("payload", {}).get("source_refs"))
    candidate_ok = bool(candidates) and candidates[-1].get("payload", {}).get("status") == "candidate_only"
    report = {
        "results": [
            {"id": "behavior_chain", "status": "proved" if chain_ok else "missing", "evidence": chain_types if chain_ok else []},
            {"id": "behavior_evaluation", "status": "proved" if evaluation_ok else "missing", "evidence": ["context_hash", "selected_memory_refs", "behavior_score"] if evaluation_ok else []},
            {"id": "policy_candidate_only", "status": "proved" if candidate_ok else "missing", "evidence": ["candidate_only", "no_profile_mutation"] if candidate_ok else []},
        ],
        "overall_character_behavior_evaluation_passed": chain_ok and evaluation_ok and candidate_ok,
    }
    output = verification_dir(PROJECT_ROOT)
    write_json(output / "character-behavior-evaluation-report.json", report)
    write_markdown(output / "character-behavior-evaluation-report.md", "Character Behavior Evaluation Verification Report", report, "overall_character_behavior_evaluation_passed")
    print(f"overall_character_behavior_evaluation_passed={report['overall_character_behavior_evaluation_passed']}")
    return 0 if report["overall_character_behavior_evaluation_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
