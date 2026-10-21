from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile

from common import artifact_ref, evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    tests = [
        root / "backend/tests/test_economy_temporal_replay_application.py",
        root / "backend/tests/test_ecology_temporal_consumer.py",
    ]
    expression = "economy_and_ecology_share_application_checkpoint_tail_after_durable_restart or economy_application_strict_grant_rejection_is_zero_write or each_consumer_budget_excludes_other_domain_due_obligations or ecology_temporal_consumer_uses_confirmed_population_tick_and_existing_owner"
    log = Path(tempfile.gettempdir()) / "paralls-task6-economy-ecology-joint.log"
    result = run_command([python, "-m", "pytest", "-q", *map(str, tests), "-k", expression], root, log, timeout_seconds=2400)
    passed = result.returncode == 0 and bool(result.stdout.strip())
    log.unlink(missing_ok=True)
    command_log = verification_dir(root) / "command.log"
    evidence = [artifact_ref(root, command_log).replace("\\", "/")] if command_log.is_file() else []
    report = {
        "profile": "infra-task6-economy-ecology-joint",
        "overall_passed": passed,
        "focused_tests": [str(item.relative_to(root)).replace("\\", "/") for item in tests],
        "evidence": evidence,
        "run_id": f"infra-task6-economy-ecology-joint-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "scope": "same application cut for Economy and Ecology temporal participants, strict-grant zero-write and Durable restart/full-tail parity",
        "limitations": ["Does not include Inventory, Character, Social, Task3–5 or a global cross-domain transaction."],
    }
    path = verification_dir(root) / "infra-task6-economy-ecology-joint-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "Task6 Economy Ecology Joint Participant Report", {"results": [{"id": "economy-ecology-joint", "status": "proved" if passed else "missing", "title": "same application cut and Durable full/tail"}], "overall_passed": passed}, "overall_passed")
    print(f"infra_task6_economy_ecology_joint_report_json={path}")
    print(f"overall_infra_task6_economy_ecology_joint_passed={passed}")
    return 0 if passed else 1


if __name__ == "__main__":
    from run_context import run_scope

    with run_scope(Path(__file__).resolve().parents[2]):
        raise SystemExit(main())
