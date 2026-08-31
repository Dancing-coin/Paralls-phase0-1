from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    tests = [
        "backend/tests/test_inf4ao_public_milling_social_ack.py",
        "backend/tests/test_inf4am_public_milling_notice.py",
        "backend/tests/test_inf4al_public_milling_activity.py",
        "backend/tests/test_inf2al_public_milling_session.py",
        "backend/tests/test_inf4ai_p5_actor_private_expression.py",
    ]
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *tests, "--basetemp=.pytest-tmp/harness-inf4ao"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    report = {
        "profile": "inf4ao-public-milling-social-ack",
        "row": "completed public milling notice -> two actor-private Social acknowledgment histories",
        "focused_tests": tests,
        "test_exit_code": result.returncode,
        "test_output": result.stdout[-4000:],
        "stderr": result.stderr[-2000:],
        "overall_passed": result.returncode == 0,
        "boundaries": [
            "existing SocialFactAuthority only",
            "exact project-visible Government public milling notice source",
            "provider organization and acquisition-derived contract receiver only",
            "two derived actor-private streams and no caller-selected participants",
            "source/provenance/revision and immutable schema/catalog pins",
            "one GameplayEventStore.append_batch receipt",
            "full/checkpoint-tail recipient replay",
            "zero-write unknown/private/stale/multiple/binding-conflict/duplicate paths",
            "no generic social API, relationship, reputation, attendance, population, payment, or world mutation",
        ],
    }
    artifact = ROOT / ".harness" / "verification" / "inf4ao-public-milling-social-ack-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"inf4ao_report_json={artifact}")
    print(f"overall_inf4ao_public_milling_social_ack_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
