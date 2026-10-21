from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    tests = [
        "backend/tests/test_population_economy_random_caller.py",
        "backend/tests/test_economy_random_registry.py",
        "backend/tests/test_economy_random_owner.py",
        "backend/tests/test_economy_random_command_service.py",
        "backend/tests/test_economy_random_command_application.py",
        "backend/tests/test_random_business_admission.py",
        "backend/tests/test_economy_temporal_consumer.py",
        "backend/tests/test_economy_temporal_replay_participant.py",
        "backend/tests/test_combat_durable_adapter.py",
    ]
    log = Path(tempfile.gettempdir()) / "paralls-economy-random-owner.log"
    result = run_command(
        [resolve_python_exe(None), "-m", "pytest", "-q", *[str(root / item) for item in tests]],
        root, log, timeout_seconds=1500,
    )
    log.unlink(missing_ok=True)
    passed = result.returncode == 0
    report = {
        "profile": "infra-economy-random-owner",
        "overall_passed": passed,
        "run_id": f"infra-economy-random-owner-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "revision": evidence_revision(root),
        "focused_tests": tests,
        "verified": [
            "confirmed Population cadence and temporal grant admission",
            "durable cadence/revocation read-set CAS including revoke race",
            "source registry freeze/reload and version rejection",
            "Economy-owned seed/result/receipt and exact/changed duplicate recovery",
            "durable replay and private receipt boundaries",
        ],
        "limitations": [
            "The stage-three typed Economy random command is a bounded self-draw demand producer under the newly authored bakery policy; it does not prove an external network producer or loot issuance.",
            "Controller-bound trusted-local identity is used by the application test; no general world-admin or external session identity issuer is established.",
            "T07 has a real typed self-draw producer at the ASGI WebSocket boundary; this bounded evidence does not prove loot delivery or all Task2 requirements.",
        ],
        "pytest_output": ((result.stdout or "") + "\n" + (result.stderr or ""))[-4000:],
        "exit_code": result.returncode,
    }
    path = verification_dir(root) / "infra-economy-random-owner-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "Economy Random Owner Bounded Verification", {
        "results": [{"id": item, "status": "proved" if passed else "missing"} for item in report["verified"]],
        "overall_passed": passed,
        "limitations": report["limitations"],
    }, "overall_passed")
    print(f"economy_random_owner_report_json={path}")
    print(f"overall_economy_random_owner_passed={passed}")
    return 0 if passed else 1


if __name__ == "__main__":
    from run_context import run_scope
    with run_scope(Path(__file__).resolve().parents[2]):
        raise SystemExit(main())
