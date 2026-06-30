# Mainline Docs Truth Rewrite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite repository entrypoint documents so the new runtime organism replaces the old `Phase 0` top-level mission.

**Architecture:** Treat documentation truth as a first-class migration target. Promote the dedicated mainline tree into entrypoint docs, mark old top-level mission statements as historical/transitional, and preserve enough `Phase 0` language only where smoke compatibility is still a bounded engineering constraint.

**Tech Stack:** Markdown docs, harness doc verification, existing documentation regression tests.

**Progress Snapshot (`2026-06-30`):**
- Tasks `1-2` now have direct repository evidence.
- Current proof chain covers:
  - top-level entry docs promoting the dedicated mainline spec/plan tree
  - older `Phase 0` mission docs reframed as compatibility or historical surfaces
  - mainline tree/spec entrypoint docs updated to match current execution truth

**Direct Evidence Audit (`2026-06-30`):**
- Required outcome `1. dedicated mainline tree is promoted into repository entry docs`
  - Direct evidence:
    - `docs/INDEX.md`
    - `docs/ai-engineering-workflow.md`
    - `docs/character/character-agent-runtime-architecture.md`
    - `docs/character/character-actor-migration-status.md`
    - `backend/tests/test_documentation_entrypoints.py::test_mainline_docs_entrypoints_promote_world_character_siming_authority_tree`
- Required outcome `2. older repository mission framing is marked as historical/compatibility truth`
  - Direct evidence:
    - `AGENTS.md`
    - `PHASE0_README.md`
    - `docs/demo-script.md`
    - `backend/tests/test_documentation_entrypoints.py::test_phase0_mission_docs_are_marked_as_compatibility_surfaces`
    - `python scripts/verification/harness.py --profile docs`

**Completion Audit Conclusion (`2026-06-30`):**
- Within the current scope of this plan, both required outcomes now have direct repository evidence.
- Remaining non-goals for this plan:
  - no further architecture expansion here
  - no runtime behavior changes; this lane is documentation truth alignment only

---

### Task 1: Promote the dedicated mainline tree into top-level docs

**Files:**
- Modify: `docs/INDEX.md`
- Modify: `docs/ai-engineering-workflow.md`
- Modify: `docs/character/character-agent-runtime-architecture.md`
- Modify: `docs/character/character-actor-migration-status.md`
- Test: `python scripts/verification/harness.py --profile docs`

- [x] **Step 1: Write the failing doc entrypoint test**

```python
from pathlib import Path


def test_mainline_docs_entrypoints_promote_world_character_siming_authority_tree() -> None:
    index_text = Path("docs/INDEX.md").read_text(encoding="utf-8")
    workflow_text = Path("docs/ai-engineering-workflow.md").read_text(encoding="utf-8")
    runtime_text = Path("docs/character/character-agent-runtime-architecture.md").read_text(
        encoding="utf-8"
    )
    migration_text = Path("docs/character/character-actor-migration-status.md").read_text(
        encoding="utf-8"
    )

    assert "world-character-siming-authority-mainline/README.md" in index_text
    assert "world-character-siming-authority-mainline/README.md" in workflow_text
    assert "world-character-siming-authority-mainline-master-design.md" in runtime_text
    assert "world-character-siming-authority-mainline-master-design.md" in migration_text
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_documentation_entrypoints.py::test_mainline_docs_entrypoints_promote_world_character_siming_authority_tree -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```markdown
## Active Design And Plans

- `docs/superpowers/specs/world-character-siming-authority-mainline/README.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-world-character-siming-authority-mainline-master-design.md`
- `docs/superpowers/plans/world-character-siming-authority-mainline/README.md`

For character-runtime framing docs, point current-mainline truth to the dedicated
`world-character-siming-authority-mainline` spec tree rather than leaving
completed-mind-core files as the only top-level architectural reference.
```

- [x] **Step 4: Run docs verification**

Run: `python scripts/verification/harness.py --profile docs`
Expected: `PASS`

- [x] **Step 5: Commit**

```bash
git add docs/INDEX.md docs/ai-engineering-workflow.md docs/character/character-agent-runtime-architecture.md docs/character/character-actor-migration-status.md backend/tests/test_documentation_entrypoints.py
git commit -m "Promote dedicated world-character-Siming-authority tree in repo docs

Constraint: The new mainline cannot remain discoverable only through compatibility files
Rejected: Keep the dedicated tree hidden behind one flat spec entrypoint | too easy for future work to miss
Confidence: high
Scope-risk: narrow
Directive: Top-level docs must point to the dedicated mainline tree whenever architecture truth is discussed
Tested: python scripts/verification/harness.py --profile docs
Not-tested: non-doc runtime behavior"
```

### Task 2: Mark older repository mission framing as historical rather than current truth

**Files:**
- Modify: `AGENTS.md`
- Modify: `PHASE0_README.md`
- Modify: `docs/demo-script.md`
- Test: `python scripts/verification/harness.py --profile docs`

- [x] **Step 1: Write the failing mission-truth regression test**

```python
from pathlib import Path


def test_phase0_mission_docs_are_marked_as_compatibility_surfaces() -> None:
    phase0_text = Path("PHASE0_README.md").read_text(encoding="utf-8").lower()
    agents_text = Path("AGENTS.md").read_text(encoding="utf-8").lower()
    demo_text = Path("docs/demo-script.md").read_text(encoding="utf-8").lower()

    assert "historical" in phase0_text or "compatibility" in phase0_text
    assert "world-character-siming-authority-mainline" in agents_text
    assert "compatibility" in agents_text or "historical" in agents_text
    assert "compatibility" in demo_text or "historical" in demo_text
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_documentation_entrypoints.py::test_phase0_mission_docs_are_marked_as_compatibility_surfaces -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```markdown
This document now describes a preserved smoke-compatibility runtime surface.
It is no longer the top-level architectural mission for the repository.

Point `AGENTS.md` and demo-facing operator docs at the dedicated
`world-character-siming-authority-mainline` tree as current truth, while keeping
Phase 0 instructions only as preserved smoke-path guidance.
```

- [x] **Step 4: Run docs verification**

Run: `python scripts/verification/harness.py --profile docs`
Expected: `PASS`

- [x] **Step 5: Commit**

```bash
git add AGENTS.md PHASE0_README.md docs/demo-script.md backend/tests/test_documentation_entrypoints.py
git commit -m "Mark older Phase 0 mission framing as historical compatibility truth

Constraint: The new mainline cannot coexist with old top-level mission language as if both were current
Rejected: Leave legacy mission docs untouched and rely on readers to infer they are stale | too ambiguous
Confidence: medium
Scope-risk: moderate
Directive: Phase 0 docs may remain as smoke-path references, but they must not continue to read as the repo's current mainline destination
Tested: python scripts/verification/harness.py --profile docs
Not-tested: broader governance alignment"
```
