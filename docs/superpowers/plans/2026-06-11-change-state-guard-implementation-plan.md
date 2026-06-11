# Change State Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a project-owned change-state guard that proves archived OpenSpec changes keep their Superpowers and Harness evidence chain.

**Architecture:** Implement a focused Python evaluator and call it from the existing `change-lifecycle` profile. Keep generated proof in the existing Harness report; do not introduce Comet state files, npm packages, or runtime behavior changes.

**Tech Stack:** Python verification scripts, pytest, JSON harness manifests, Markdown workflow docs.

---

## File Structure

- Create `scripts/verification/check_change_state.py`: evaluates archived OpenSpec change closure and returns structured Harness-style results.
- Create `scripts/verification/tests/test_change_state_checks.py`: focused unit tests for complete and incomplete archived change states.
- Modify `scripts/verification/check_change_lifecycle.py`: imports the new evaluator and adds the `archived_changes_have_state_closure` rule.
- Modify `scripts/verification/tests/test_change_lifecycle_checks.py`: asserts the new lifecycle rule is proved.
- Modify `scripts/verification/tests/test_formal_profile_checks.py`: asserts the new lifecycle rule is proved in the combined profile coverage test.
- Modify `.harness/rules/change-lifecycle-rules.json`: registers the new rule evidence.
- Modify `docs/ai-engineering-workflow.md`: documents change-state closure as part of the workflow chain.
- Modify `docs/harness.md`: documents the `change-lifecycle` profile's new invariant.
- Modify `docs/superpowers/specs/2026-06-11-change-state-guard-design.md`: update acceptance if implementation reveals a narrower rule shape.

---

### Task 1: Failing Change-State Unit Tests

**Files:**
- Create: `scripts/verification/tests/test_change_state_checks.py`

- [x] **Step 1: Write the failing tests**

Create `scripts/verification/tests/test_change_state_checks.py` with:

```python
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
    write(change_dir / "design.md", "## Design\nReference docs/superpowers/specs/2026-06-11-change-state-guard-design.md.\n")
    write(change_dir / "tasks.md", tasks)
    write(change_dir / "specs" / name / "spec.md", "## ADDED Requirements\n\n### Requirement: Closure\n")
    return change_dir


def test_complete_archived_change_state_passes(tmp_path: Path) -> None:
    create_archived_change(tmp_path, "change-state", "- [x] write guard\n- [x] run harness\n")
    write(
        tmp_path / "docs" / "superpowers" / "specs" / "2026-06-11-change-state-guard-design.md",
        "# Change State Guard Design\n\nRelated change: change-state\n",
    )
    write(
        tmp_path / "docs" / "superpowers" / "plans" / "2026-06-11-change-state-guard-implementation-plan.md",
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
```

- [x] **Step 2: Run the tests to verify they fail**

Run:

```powershell
python -m pytest -q scripts\verification\tests\test_change_state_checks.py
```

Expected before implementation: collection fails with `ModuleNotFoundError: No module named 'check_change_state'`.

---

### Task 2: Implement Change-State Evaluator

**Files:**
- Create: `scripts/verification/check_change_state.py`

- [x] **Step 1: Add the minimal evaluator**

Create `scripts/verification/check_change_state.py` with:

```python
from __future__ import annotations

from pathlib import Path

from common import read_text, repo_root, verification_dir, write_json, write_markdown


REQUIRED_CHANGE_FILES = [".openspec.yaml", "proposal.md", "design.md", "tasks.md"]


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
    open_lines = [
        line.strip()
        for line in tasks_text.splitlines()
        if line.lstrip().startswith("- [ ]")
    ]
    if open_lines:
        return False, f"{change_dir.name}: unchecked tasks: {' | '.join(open_lines)}"
    return True, ""


def _has_delta_spec(change_dir: Path) -> bool:
    return any((change_dir / "specs").glob("*/spec.md"))


def _has_workflow_evidence(project_root: Path, change_dir: Path) -> bool:
    haystack_paths = [
        *sorted((project_root / "docs" / "superpowers" / "specs").glob("*.md")),
        *sorted((project_root / "docs" / "superpowers" / "plans").glob("*.md")),
        *sorted((project_root / ".harness" / "verification").glob("*.md")),
        *sorted((project_root / ".harness" / "verification").glob("*.json")),
        change_dir / "design.md",
        change_dir / "proposal.md",
        change_dir / "tasks.md",
    ]
    change_tokens = {
        change_dir.name,
        change_dir.name.removeprefix("2026-06-11-"),
        change_dir.name.split("-", 3)[-1] if len(change_dir.name.split("-", 3)) == 4 else change_dir.name,
    }
    for path in haystack_paths:
        text = read_text(path)
        if any(token and token in text for token in change_tokens):
            return True
    return False


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
```

- [x] **Step 2: Run the focused tests**

Run:

```powershell
python -m pytest -q scripts\verification\tests\test_change_state_checks.py
```

Expected after implementation: `2 passed`.

---

### Task 3: Integrate With Change Lifecycle Profile

**Files:**
- Modify: `scripts/verification/check_change_lifecycle.py`
- Modify: `scripts/verification/tests/test_change_lifecycle_checks.py`
- Modify: `scripts/verification/tests/test_formal_profile_checks.py`
- Modify: `.harness/rules/change-lifecycle-rules.json`

- [x] **Step 1: Extend the lifecycle test expectation**

In `scripts/verification/tests/test_change_lifecycle_checks.py`, add:

```python
    assert statuses["archived_changes_have_state_closure"] == "proved"
```

In `scripts/verification/tests/test_formal_profile_checks.py`, add the same assertion inside `test_change_lifecycle_profile_proves_ai_engineering_workflow`.

- [x] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest -q scripts\verification\tests\test_change_lifecycle_checks.py scripts\verification\tests\test_formal_profile_checks.py
```

Expected before integration: fail with missing `archived_changes_have_state_closure`.

- [x] **Step 3: Integrate evaluator in `check_change_lifecycle.py`**

Add import:

```python
from check_change_state import evaluate_change_state
```

Add to `REQUIRED_RULE_IDS`:

```python
    "archived_changes_have_state_closure",
```

Inside `evaluate_change_lifecycle`, compute:

```python
    change_state_report = evaluate_change_state(project_root)
```

Add a `_result(...)` entry:

```python
        _result(
            "archived_changes_have_state_closure",
            "Archived OpenSpec changes retain required files, closed tasks, delta specs, and workflow evidence",
            bool(change_state_report.get("overall_change_state_passed")),
            [
                "openspec/changes/archive/",
                "docs/superpowers/specs/",
                "docs/superpowers/plans/",
                ".harness/verification/",
            ],
            "\n".join(
                str(entry.get("notes", ""))
                for entry in change_state_report.get("results", [])
                if entry.get("status") != "proved" and entry.get("notes")
            ),
        ),
```

- [x] **Step 4: Register rule evidence**

Add this rule object to `.harness/rules/change-lifecycle-rules.json`:

```json
{
  "id": "archived_changes_have_state_closure",
  "title": "Archived OpenSpec changes retain required files, closed tasks, delta specs, and workflow evidence",
  "evidence": [
    ".harness/verification/change-lifecycle-report.json:results.archived_changes_have_state_closure"
  ]
}
```

- [x] **Step 5: Run the integration tests**

Run:

```powershell
python -m pytest -q scripts\verification\tests\test_change_lifecycle_checks.py scripts\verification\tests\test_formal_profile_checks.py
```

Expected after integration: both tests pass.

---

### Task 4: Document The Guard

**Files:**
- Modify: `docs/ai-engineering-workflow.md`
- Modify: `docs/harness.md`

- [x] **Step 1: Update workflow documentation**

Add a short section to `docs/ai-engineering-workflow.md` after "Source Of Truth":

```markdown
## Change-State Closure

Archived OpenSpec changes must retain enough machine-checkable evidence to prove the lifecycle did not lose intent, execution, or verification context. The `change-lifecycle` harness profile checks archived changes for required OpenSpec files, completed tasks, retained delta specs, and a connection to Superpowers or Harness evidence.

This guard borrows Comet's phase-guard idea but keeps the project source of truth unchanged: OpenSpec records change intent, Superpowers records design and execution planning, Harness records durable acceptance evidence, and Goal records active execution continuity.
```

- [x] **Step 2: Update harness profile docs**

In `docs/harness.md`, under `change-lifecycle`, add this invariant to the list:

```markdown
- archived OpenSpec changes keep required lifecycle files, completed tasks, delta specs, and a Superpowers/Harness evidence link
```

- [x] **Step 3: Run docs-focused tests**

Run:

```powershell
python -m pytest -q scripts\verification\tests\test_docs_checks.py scripts\verification\tests\test_change_lifecycle_checks.py
```

Expected: tests pass.

---

### Task 5: Verification

**Files:**
- Modify as needed only if verification exposes a real gap.

- [x] **Step 1: Run focused unit tests**

```powershell
python -m pytest -q scripts\verification\tests\test_change_state_checks.py scripts\verification\tests\test_change_lifecycle_checks.py scripts\verification\tests\test_formal_profile_checks.py
```

Expected: all tests pass.

- [x] **Step 2: Run focused harness profile**

```powershell
python scripts\verification\harness.py --profile change-lifecycle
```

Expected: `overall_harness_passed=True` and `archived_changes_have_state_closure=proved`.

- [x] **Step 3: Run docs profile**

```powershell
python scripts\verification\harness.py --profile docs
```

Expected: docs profile passes with the new design/plan pair.

- [x] **Step 4: Run full harness if time allows**

```powershell
python scripts\verification\harness.py --profile all
```

Expected: full harness passes. If a Godot/runtime prerequisite blocks full harness, record the exact blocker and keep the focused profile evidence.

Result: full harness passed all static profiles through `harness-reference`, then stopped at `phase0`. The blocking evidence is unrelated to this workflow guard change: `backend/tests/test_health.py::test_health_exposes_current_backend_identity` still expects the old `paralls-phase-0-demo` path or `.worktrees\`, while this worktree reports `D:\Paralls-phase0-1`; Godot scene load also fails on missing `res://assets/environment/throne_room_existing/MI_CathedralPillar03_BaseColor.png`, leaving the Phase 0 runtime trace empty.
