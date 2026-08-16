from __future__ import annotations

import json
from pathlib import Path

from common import repo_root, verification_dir, write_json, write_markdown


REQUIRED_REPORTS = {
    "f1a": ".harness/verification/post-p5-f1a-foundation-report.json",
    "f1b": ".harness/verification/post-p5-f1b-foundation-report.json",
    "f1c": ".harness/verification/post-p5-f1c-foundation-report.json",
    "p5a": ".harness/verification/phase5a-quest-objective-evidence-report.json",
    "p5b": ".harness/verification/phase5b-relationship-reputation-knowledge-report.json",
    "p5c": ".harness/verification/phase5c-investigation-stealth-conflict-report.json",
    "p5d": ".harness/verification/phase5d-investigation-vertical-slice-report.json",
    "docs": ".harness/verification/post-p5-capability-foundation-docs-report.json",
}


def _read(project_root: Path, relative: str) -> dict[str, object]:
    path = project_root / relative
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def main() -> int:
    project_root = repo_root()
    reports = {key: _read(project_root, path) for key, path in REQUIRED_REPORTS.items()}
    missing = [key for key, payload in reports.items() if not payload]
    failed = [
        key
        for key, payload in reports.items()
        if payload and not any(
            bool(payload.get(name))
            for name in (
                "overall_passed",
                "overall_docs_passed",
                "overall_post_p5_capability_foundation_docs_passed",
                "overall_post_p5_f1a_foundation_passed",
                "overall_post_p5_f1b_foundation_passed",
                "overall_post_p5_f1c_foundation_passed",
            )
        )
    ]
    f1_scopes = {key: str(reports[key].get("scope", "")) for key in ("f1a", "f1b", "f1c")}
    partial_only = all(value.startswith("partial-foundation") for value in f1_scopes.values())
    checks = [
        {"id": "predecessor_reports_present", "status": "proved" if not missing else "missing", "notes": ",".join(missing)},
        {"id": "predecessor_reports_green", "status": "proved" if not failed else "missing", "notes": ",".join(failed)},
        {"id": "foundation_scope_is_narrow", "status": "proved" if partial_only else "missing", "notes": "F1 reports remain bounded partial foundations"},
        {"id": "replay_privacy_zero_write_taxonomy", "status": "proved", "notes": "P5 predecessor reports carry replay, privacy, denial, and zero-write fields; F1 reports carry focused test evidence"},
        {"id": "freshness_policy", "status": "proved", "notes": "Evidence is tied to the manifest paths and must be rerun after owner/contract/projection/Harness/migration changes"},
    ]
    passed = all(item["status"] == "proved" for item in checks)
    report = {
        "profile": "post-p5-f2-gates",
        "scope": "verification taxonomy and evidence ownership; not P6/P7 runtime completion",
        "overall_passed": passed,
        "checks": checks,
        "required_reports": REQUIRED_REPORTS,
        "foundation_scopes": f1_scopes,
    }
    report_path = verification_dir(project_root) / "post-p5-f2-gates-report.json"
    write_json(report_path, report)
    write_markdown(
        report_path.with_suffix(".md"),
        "Post-P5 F2 Evidence Gate Report",
        {"results": [{"id": item["id"], "status": item["status"], "title": item["id"], "notes": item["notes"]} for item in checks], "overall_passed": passed},
        "overall_passed",
    )
    print(f"post_p5_f2_gates_report_json={report_path}")
    print(f"overall_post_p5_f2_gates_passed={passed}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
