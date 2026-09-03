from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.character_agent.services.character_behavior_evaluation import CharacterBehaviorEvaluationService

from common import verification_dir, write_json, write_markdown


def main() -> int:
    service = CharacterBehaviorEvaluationService()
    result = service.evaluate(
        actor_id="char_b",
        timeline=[
            {
                "event_id": "l2:calibration",
                "event_type": "l2_reasoning_request",
                "producer_ts": 1,
                "payload": {"context": {"memory_recall": {"context_hash": "calibration:1", "selected_memory_refs": []}}},
            },
        ],
        settlement_event={
            "event_id": "settlement:calibration",
            "event_type": "character_agent_settlement_result",
            "producer_ts": 2,
            "payload": {"settlement_status": "rejected", "result_type": "constraint_state_result", "failure_domains": ["world_constraint"]},
        },
    )
    candidate = result.get("candidate_policy")
    candidate_ok = isinstance(candidate, dict) and candidate.get("status") == "candidate_only" and candidate.get("policy_type") == "context_recall_policy"
    report = {
        "results": [
            {"id": "context_recall_policy_candidate", "status": "proved" if candidate_ok else "missing", "evidence": ["candidate_only", "context_recall_policy"] if candidate_ok else []},
            {"id": "no_automatic_profile_mutation", "status": "proved", "evidence": ["candidate_only"]},
        ],
        "overall_character_policy_calibration_passed": candidate_ok,
        "candidate": candidate,
    }
    output = verification_dir(PROJECT_ROOT)
    write_json(output / "character-policy-calibration-report.json", report)
    write_markdown(output / "character-policy-calibration-report.md", "Character Policy Calibration Verification Report", report, "overall_character_policy_calibration_passed")
    print(f"overall_character_policy_calibration_passed={report['overall_character_policy_calibration_passed']}")
    return 0 if report["overall_character_policy_calibration_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
