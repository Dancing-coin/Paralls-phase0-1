from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import tempfile

from common import artifact_ref, evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main() -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    selected = [
        root / "backend/tests/test_world_admin_auth_service.py",
        root / "backend/tests/test_world_admin_cadence_revocation_application.py",
        root / "backend/tests/test_runtime_asgi.py::test_bootstrap_preserves_excluded_settings_and_real_http_enrollment",
        root / "backend/tests/test_runtime_asgi.py::test_actual_asgi_http_dispatches_original_typed_route_on_child_owner",
        root / "backend/tests/test_world_replay_checkpoint_application.py::test_inventory_participant_survives_durable_reopen_and_checkpoint_tail",
        root / "backend/tests/test_siming_population_inventory_vertical.py",
    ]
    log = Path(tempfile.gettempdir()) / "paralls-rw50-inventory-replay.log"
    result = run_command([python, "-m", "pytest", "-q", *map(str, selected)], root, log)
    passed = result.returncode == 0 and bool(result.stdout.strip())
    log.unlink(missing_ok=True)
    command_log = verification_dir(root) / "command.log"
    evidence = [artifact_ref(root, command_log).replace("\\", "/")] if command_log.is_file() else []
    report = {
        "profile": "infra-rw50-inventory-replay",
        "overall_passed": passed,
        "focused_tests": [str(item.relative_to(root)).replace("\\", "/") for item in selected],
        "evidence": evidence,
        "run_id": f"infra-rw50-inventory-replay-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "scope": "same application Durable store close/reopen, fresh Inventory authority, participant capture, full/checkpoint+tail equality",
        "assertions": ["rows", "event refs", "boundary", "revision vector", "view digest", "missing/deleted participant", "rows/digest tamper", "future event rejection"],
        "limitations": ["Inventory custody only; does not establish complete cross-domain SettlementWindow policy."],
    }
    path = verification_dir(root) / "infra-rw50-inventory-replay-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "RW-50 Inventory Replay Recheck", {"results": [{"id": "rw50", "status": "proved" if passed else "missing", "title": "Durable reopen and same-scope full/checkpoint+tail"}], "overall_passed": passed}, "overall_passed")
    print(f"infra_rw50_inventory_replay_report_json={path}")
    print(f"overall_infra_rw50_inventory_replay_passed={passed}")
    return 0 if passed else 1


if __name__ == "__main__":
    from run_context import run_scope

    with run_scope(Path(__file__).resolve().parents[2]):
        raise SystemExit(main())
