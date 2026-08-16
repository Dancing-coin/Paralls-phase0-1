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
    required = {
        "f0": ".harness/verification/post-p5-f0-complete-report.json",
        "f1a": ".harness/verification/post-p5-f1a-complete-report.json",
        "f1b": ".harness/verification/post-p5-f1b-complete-report.json",
        "f1c": ".harness/verification/post-p5-f1c-complete-report.json",
        "f2": ".harness/verification/post-p5-f2-complete-report.json",
    }
    reports = {key: _read(root, path) for key, path in required.items()}
    rows = []
    for key, path in required.items():
        payload = reports[key]
        green = bool(payload.get("overall_passed") and payload.get("scope") == "complete")
        rows.append({"gate": key.upper(), "status": "green" if green else "blocked", "report": path, "run_id": payload.get("run_id"), "commit": payload.get("commit"), "owner": payload.get("owner", "mainline-maintainer"), "freshness": payload.get("freshness"), "invalidation": "owner/schema/privacy/assertion/migration/rollback changes", "rollback_target": payload.get("rollback_target", "re-run predecessor profile"), "successor": "P6/P7 remain unopened"})
    green = all(row["status"] == "green" for row in rows)
    report = {"profile": "post-p5-dg-opening", "status": "green" if green else "planned/blocked", "overall_passed": green, "p6_p7_authorized": False, "rows": rows, "run_id": f"post-p5-dg-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}", "commit": evidence_revision(root), "opening_rule": "P6/P7 may open only after all rows are fresh-green"}
    path = verification_dir(root) / "post-p5-dg-opening-report.json"
    write_json(path, report)
    write_markdown(path.with_suffix(".md"), "Post-P5 DG Opening Checklist", {"results": [{"id": row["gate"], "status": row["status"], "title": row["report"], "notes": f"run_id={row['run_id']} commit={row['commit']}"} for row in rows], "overall_passed": green}, "overall_passed")
    print(f"post_p5_dg_opening_report_json={path}")
    print(f"overall_post_p5_dg_opening_passed={green}")
    return 0 if green else 1


if __name__ == "__main__":
    raise SystemExit(main())
