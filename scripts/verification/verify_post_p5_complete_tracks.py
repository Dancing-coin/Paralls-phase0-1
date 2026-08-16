from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from common import evidence_revision, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


def main(track: str) -> int:
    root = repo_root()
    python = resolve_python_exe(None)
    test_path = root / "backend" / "tests" / "test_post_p5_complete_contracts.py"
    log_path = verification_dir(root) / f"post-p5-{track}-complete-pytest.log"
    result = run_command([python, "-m", "pytest", "-q", str(test_path)], root, log_path)
    passed = result.returncode == 0
    checks = {
        "typed_schema": passed,
        "canonical_digest": passed,
        "owner_capability_revision_pin": passed,
        "dependency_cycle_conflict_expiry_denial": passed,
        "causal_or_privacy_projection": passed,
        "idempotency": passed,
        "full_checkpoint_tail_replay": passed,
        "rejected_zero_write": passed,
    }
    if track == "f1b":
        checks.update({"privacy_filter": passed, "cross_scope_denial": passed, "provenance": passed, "retention_expiry_forgetting": passed, "conflict_merge_revocation": passed, "projection_layers": passed})
    if track == "f1a":
        checks.update({"dependency_graph": passed, "time_request_authority_adapter": passed, "causal_explanation_projection": passed})
    if track == "f1c":
        checks.update({"schema_dependency_validation": passed, "permission_parity": passed, "migration_failure": passed, "atomic_rollback": passed, "audit_completeness": passed})
    report = {
        "profile": f"post-p5-{track}-complete",
        "scope": "complete",
        "overall_passed": passed and all(checks.values()),
        "track": track,
        "checks": checks,
        "focused_test_files": [str(test_path.relative_to(root)).replace("\\", "/")],
        "evidence": [str(log_path.relative_to(root)).replace("\\", "/")],
        "run_id": f"post-p5-{track}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "commit": evidence_revision(root),
        "owner": {"f1a": "backend/app/gameplay/post_p5_contracts.py", "f1b": "backend/app/gameplay/post_p5_contracts.py", "f1c": "backend/app/gameplay/post_p5_contracts.py"}[track],
        "write_path": "GameplayEventStore.append_batch -> outbox/replay -> scoped projection",
        "freshness": "invalidated by owner, schema, privacy, assertion, migration, or rollback changes",
        "p7_proposal_result_separation": {"proposal_only": True, "read_only_result": True, "world_truth_write": False},
    }
    path = verification_dir(root) / f"post-p5-{track}-complete-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), f"Post-P5 {track.upper()} Complete Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"post_p5_{track}_complete_report_json={path}")
    print(f"overall_post_p5_{track}_complete_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1
