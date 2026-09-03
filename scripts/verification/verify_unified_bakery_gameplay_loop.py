from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.gameplay.bakery_mirror_source import BakeryMirrorSource
from app.gameplay.bakery_reference_runtime import BakeryReferenceScenario
from app.gameplay.event_store import GameplayEventStore

def main() -> int:
    store = GameplayEventStore()
    scenario = BakeryReferenceScenario.default()
    periods = scenario.run_three_periods(store=store)
    view = BakeryMirrorSource(scenario=scenario, events=store.read_events()).godot_view()
    payload = dict(view.groups["bakery.gameplay"].payload)
    checks = {
        "three_periods": len(periods) == 3 and payload["period_count"] == 3,
        "facility": payload["facility_state"] == "acquired",
        "sales": payload["sale_count"] == 3,
        "permits": payload["permit_count"] == 3,
        "outputs": payload["output_count"] == 3,
        "wages_balanced": payload["wage_accrual_count"] == payload["wage_paid_count"],
        "survival_projection_available": payload["survival_tick_count"] >= 0,
        "committed_only": payload["failure_count"] == 0,
    }
    report = {
        "profile": "unified-bakery-gameplay-loop-v1",
        "overall_passed": all(checks.values()),
        "checks": checks,
        "view_payload": payload,
        "event_count": len(store.read_events()),
    }
    artifact = ROOT / ".harness" / "verification" / "unified-bakery-gameplay-loop-v1-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2, default=list), encoding="utf-8")
    print(f"unified_bakery_gameplay_loop_v1_report_json={artifact}")
    print(f"overall_unified_bakery_gameplay_loop_v1_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
