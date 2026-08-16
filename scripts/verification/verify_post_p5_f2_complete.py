from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone

from common import evidence_revision, repo_root, verification_dir, write_json, write_markdown


def _read(root, relative):
    try:
        return json.loads((root / relative).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> int:
    root = repo_root()
    paths = {"f0": ".harness/verification/post-p5-f0-complete-report.json", "f1a": ".harness/verification/post-p5-f1a-complete-report.json", "f1b": ".harness/verification/post-p5-f1b-complete-report.json", "f1c": ".harness/verification/post-p5-f1c-complete-report.json"}
    reports = {key: _read(root, value) for key, value in paths.items()}
    complete = {key: bool(value.get("overall_passed") and value.get("scope") == "complete") for key, value in reports.items()}
    checks = {
        "complete_reports_read": all(reports.values()),
        "predecessor_complete": all(complete.values()),
        "success_and_deny_zero_write": all("rejected_zero_write" in reports[key].get("checks", {}) for key in ("f1a", "f1b", "f1c")),
        "idempotency_revision_replay": all(all(name in reports[key].get("checks", {}) for name in ("idempotency", "full_checkpoint_tail_replay")) for key in ("f1a", "f1b", "f1c")),
        "deterministic_projection_hash": all(reports[key].get("p7_proposal_result_separation", {}).get("read_only_result") for key in ("f1a", "f1b", "f1c")),
        "privacy_filter": bool(reports["f1b"].get("checks", {}).get("privacy_filter")),
        "permission_parity": bool(reports["f1c"].get("checks", {}).get("permission_parity")),
        "migration_rollback_audit": all(bool(reports["f1c"].get("checks", {}).get(name)) for name in ("migration_failure", "atomic_rollback", "audit_completeness")),
        "evidence_freshness": all(reports[key].get("commit") and reports[key].get("run_id") for key in reports),
        "proposal_result_separation": all(reports[key].get("p7_proposal_result_separation", {}).get("proposal_only") for key in ("f1a", "f1b", "f1c")),
    }
    report = {"profile": "post-p5-f2-complete", "scope": "complete", "overall_passed": all(checks.values()), "checks": checks, "required_reports": paths, "run_id": f"post-p5-f2-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}", "commit": evidence_revision(root), "freshness": "all upstream reports must be fresh at compatible commit"}
    path = verification_dir(root) / "post-p5-f2-complete-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "Post-P5 F2 Complete Report", {"results": [{"id": key, "status": "proved" if value else "missing", "title": key} for key, value in checks.items()], "overall_passed": report["overall_passed"]}, "overall_passed")
    print(f"post_p5_f2_complete_report_json={path}")
    print(f"overall_post_p5_f2_complete_passed={report['overall_passed']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
