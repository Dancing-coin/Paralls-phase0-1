from __future__ import annotations

import re
from pathlib import Path

from common import read_text, repo_root, verification_dir, write_json, write_markdown


REQUIRED_CHANGE_FILES = [".openspec.yaml", "proposal.md", "design.md", "tasks.md"]
DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}-")


def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def _relative(path: Path, project_root: Path) -> str:
    return str(path.relative_to(project_root)).replace("\\", "/")


def _archived_changes(project_root: Path) -> list[Path]:
    archive_root = project_root / "openspec" / "changes" / "archive"
    if not archive_root.exists():
        return []
    return sorted(path for path in archive_root.iterdir() if path.is_dir())


def _missing_required_files(change_dir: Path) -> list[str]:
    return [name for name in REQUIRED_CHANGE_FILES if not (change_dir / name).is_file()]


def _tasks_closed(change_dir: Path) -> tuple[bool, str]:
    tasks_text = read_text(change_dir / "tasks.md")
    if "- [" not in tasks_text:
        return False, f"{change_dir.name}: tasks.md has no checklist items"
    open_lines = [line.strip() for line in tasks_text.splitlines() if line.lstrip().startswith("- [ ]")]
    if open_lines:
        return False, f"{change_dir.name}: unchecked tasks: {' | '.join(open_lines)}"
    return True, ""


def _has_delta_spec(change_dir: Path) -> bool:
    return any((change_dir / "specs").glob("*/spec.md"))


def _change_tokens(change_dir: Path) -> set[str]:
    without_date = DATE_PREFIX.sub("", change_dir.name)
    return {change_dir.name, without_date}


def _external_evidence_paths(project_root: Path) -> list[Path]:
    roots = [
        project_root / "docs" / "superpowers" / "specs",
        project_root / "docs" / "superpowers" / "plans",
        project_root / ".harness" / "verification",
    ]
    paths: list[Path] = []
    for root in roots:
        if root.exists():
            paths.extend(sorted(root.glob("*.md")))
            paths.extend(sorted(root.glob("*.json")))
    return paths


def _has_internal_verification_note(change_dir: Path) -> bool:
    for filename in ["proposal.md", "design.md", "tasks.md"]:
        text = read_text(change_dir / filename).lower()
        if "verification note" in text or "verification" in text and "harness" in text:
            return True
    return False


def _has_workflow_evidence(project_root: Path, change_dir: Path) -> bool:
    tokens = _change_tokens(change_dir)
    for path in _external_evidence_paths(project_root):
        text = read_text(path)
        if any(token and token in text for token in tokens):
            return True
    return _has_internal_verification_note(change_dir)


def evaluate_change_state(project_root: Path) -> dict[str, object]:
    changes = _archived_changes(project_root)
    missing_files: list[str] = []
    task_failures: list[str] = []
    missing_specs: list[str] = []
    missing_evidence: list[str] = []

    for change_dir in changes:
        for filename in _missing_required_files(change_dir):
            missing_files.append(f"{_relative(change_dir, project_root)}/{filename}")

        tasks_ok, tasks_note = _tasks_closed(change_dir)
        if not tasks_ok:
            task_failures.append(tasks_note)

        if not _has_delta_spec(change_dir):
            missing_specs.append(_relative(change_dir, project_root))

        if not _has_workflow_evidence(project_root, change_dir):
            missing_evidence.append(_relative(change_dir, project_root))

    results = [
        _result(
            "archived_changes_exist",
            "At least one archived OpenSpec change exists",
            bool(changes),
            [_relative(path, project_root) for path in changes],
        ),
        _result(
            "archived_changes_have_required_files",
            "Archived OpenSpec changes include required lifecycle files",
            bool(changes) and not missing_files,
            ["openspec/changes/archive/"],
            "\n".join(missing_files),
        ),
        _result(
            "archived_change_tasks_closed",
            "Archived OpenSpec change tasks are fully checked off",
            bool(changes) and not task_failures,
            ["openspec/changes/archive/*/tasks.md"],
            "\n".join(task_failures),
        ),
        _result(
            "archived_changes_have_delta_specs",
            "Archived OpenSpec changes retain delta specs",
            bool(changes) and not missing_specs,
            ["openspec/changes/archive/*/specs/*/spec.md"],
            "\n".join(missing_specs),
        ),
        _result(
            "archived_changes_have_workflow_evidence",
            "Archived OpenSpec changes remain connected to Superpowers or Harness evidence",
            bool(changes) and not missing_evidence,
            [
                "docs/superpowers/specs/",
                "docs/superpowers/plans/",
                ".harness/verification/",
                "openspec/changes/archive/",
            ],
            "\n".join(missing_evidence),
        ),
    ]
    return {
        "results": results,
        "archived_change_count": len(changes),
        "overall_change_state_passed": all(str(entry["status"]) == "proved" for entry in results),
    }


def main() -> int:
    project_root = repo_root()
    report = evaluate_change_state(project_root)
    log_dir = verification_dir(project_root)
    json_path = log_dir / "change-state-report.json"
    md_path = log_dir / "change-state-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Change State Verification Report", report, "overall_change_state_passed")

    print(f"change_state_report_json={json_path}")
    print(f"change_state_report_md={md_path}")
    print(f"overall_change_state_passed={report['overall_change_state_passed']}")
    for entry in report["results"]:
        print(f"{entry['id']}={entry['status']}")
    return 0 if report["overall_change_state_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
