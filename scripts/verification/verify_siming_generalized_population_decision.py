from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.population_continuity.vertical import GeneralizedPopulationDecisionFixture


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    fixture = GeneralizedPopulationDecisionFixture.create()
    scenarios = {
        name: fixture.run_scenario(name)
        for name in (
            "competing_candidates", "budget_exhaustion", "stale_receipt",
            "owner_rejection", "player_proximity", "propagation_pressure", "noop_defer",
        )
    }
    replay = fixture.replay_scenario("competing_candidates")
    predecessor_path = root / ".harness" / "verification" / "siming-governed-three-actor-cohort-continuity-v1-report.json"
    predecessor = False
    if predecessor_path.exists():
        try:
            predecessor = json.loads(predecessor_path.read_text(encoding="utf-8")).get("overall_passed") is True
        except (OSError, ValueError):
            predecessor = False
    competing = scenarios["competing_candidates"]
    player = scenarios["player_proximity"]
    zero_write = all(scenarios[name]["zero_write"] for name in ("stale_receipt", "owner_rejection", "noop_defer"))
    report = {
        "overall_passed": bool(
            predecessor
            and competing["status"] == "accepted"
            and player["status"] == "accepted"
            and competing["selected"] != player["selected"]
            and competing["owner_refs"] == ["character:char_a"]
            and player["owner_refs"] == []
            and replay["decision_digest"] == competing["decision_digest"]
            and not competing["uses_actor_specific_fixture"]
            and zero_write
        ),
        "predecessors": {"siming-governed-three-actor-cohort-continuity-v1": predecessor},
        "harness_checks": {
            "multiple_valid_selections": competing["selected"] != player["selected"],
            "owner_boundary": competing["owner_refs"] == ["character:char_a"],
            "activation_only_boundary": player["owner_refs"] == [],
            "fixture_not_generic_contract": not competing["uses_actor_specific_fixture"],
        },
        "scenarios": scenarios,
        "replay": {"equal": replay["decision_digest"] == competing["decision_digest"], "decision_digest": replay["decision_digest"]},
        "zero_write": zero_write,
    }
    artifact = root / ".harness" / "verification" / "siming-generalized-population-decision-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    print(f"overall_siming_generalized_population_decision_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
