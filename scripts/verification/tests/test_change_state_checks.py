from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_change_state import evaluate_change_state


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def create_archived_change(root: Path, name: str, tasks: str) -> Path:
    change_dir = root / "openspec" / "changes" / "archive" / f"2026-06-11-{name}"
    write(change_dir / ".openspec.yaml", "schema: spec-driven\n")
    write(change_dir / "proposal.md", "## Why\nKeep lifecycle evidence connected.\n")
    write(
        change_dir / "design.md",
        "## Design\nReference docs/superpowers/specs/2026-06-11-change-state-guard-design.md.\n",
    )
    write(change_dir / "tasks.md", tasks)
    write(
        change_dir / "specs" / name / "spec.md",
        "## ADDED Requirements\n\n### Requirement: Closure\n",
    )
    return change_dir


def test_complete_archived_change_state_passes(tmp_path: Path) -> None:
    create_archived_change(tmp_path, "change-state", "- [x] write guard\n- [x] run harness\n")
    write(
        tmp_path / "docs" / "superpowers" / "specs" / "2026-06-11-change-state-guard-design.md",
        "# Change State Guard Design\n\nRelated change: change-state\n",
    )
    write(
        tmp_path
        / "docs"
        / "superpowers"
        / "plans"
        / "2026-06-11-change-state-guard-implementation-plan.md",
        "# Change State Guard Implementation Plan\n\nRelated change: change-state\n",
    )
    write(
        tmp_path / ".harness" / "verification" / "change-lifecycle-report.md",
        "# Change Lifecycle Verification Report\n\narchived_changes_have_state_closure\n",
    )

    report = evaluate_change_state(tmp_path)
    statuses = {entry["id"]: entry["status"] for entry in report["results"]}

    assert report["overall_change_state_passed"] is True
    assert statuses["archived_changes_exist"] == "proved"
    assert statuses["archived_changes_have_required_files"] == "proved"
    assert statuses["archived_change_tasks_closed"] == "proved"
    assert statuses["archived_changes_have_delta_specs"] == "proved"
    assert statuses["archived_changes_have_workflow_evidence"] == "proved"


def test_archived_change_with_unchecked_task_fails(tmp_path: Path) -> None:
    create_archived_change(tmp_path, "open-task", "- [x] done\n- [ ] missing verification\n")

    report = evaluate_change_state(tmp_path)
    statuses = {entry["id"]: entry["status"] for entry in report["results"]}

    assert report["overall_change_state_passed"] is False
    assert statuses["archived_change_tasks_closed"] == "missing"
