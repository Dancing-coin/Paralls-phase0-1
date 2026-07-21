# Simplify AI Engineering Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the repository's legacy external specification layer while preserving a generic, passing `change-lifecycle` workflow gate.

**Architecture:** Rewrite `check_change_lifecycle.py` so it validates repository-local design, Superpowers, Harness, Goal, and native-subagent handoffs without importing an archive-state evaluator. Remove the legacy artifact/skill surface, then clean every tracked reference and prove the resulting repository with focused tests, the workflow profile, and the full Harness.

**Tech Stack:** Python 3, pytest, JSON Harness manifests, Markdown workflow documentation, PowerShell, Git.

## Global Constraints

- The current Git-tracked tree must contain no path or content matching the removed product name.
- Keep the `change-lifecycle` profile and its non-legacy workflow checks.
- Do not change backend, Godot, authority, or runtime behavior.
- Do not modify independent repositories under `.worktrees/`.
- Do not uninstall user-global CLIs or user-global skills.
- Preserve unrelated user changes and unrelated generated Harness evidence.

---

### Task 1: Rebase The Change-Lifecycle Contract

**Files:**

- Modify: `scripts/verification/tests/test_change_lifecycle_checks.py`
- Modify: `scripts/verification/tests/test_formal_profile_checks.py`
- Modify: `scripts/verification/check_change_lifecycle.py`
- Modify: `.harness/profiles/change-lifecycle.json`
- Modify: `.harness/rules/change-lifecycle-rules.json`
- Modify: `.harness/templates/PLAN.md`
- Modify: `.harness/templates/HARNESS_CHECKLIST.md`
- Modify: `docs/ai-engineering-workflow.md`

**Interfaces:**

- Consumes: `evaluate_change_lifecycle(project_root: Path) -> dict[str, object]`, profile/rule registries, and repository workflow artifacts.
- Produces: the same evaluator signature and report paths, with six generic result IDs and no archive-state dependency.

- [ ] **Step 1: Change the focused tests to require the generic result set**

Replace the status assertions in both test files with this exact result contract:

```python
expected_result_ids = {
    "workflow_doc_exists",
    "change_lifecycle_profile_registered",
    "design_superpowers_harness_goal_chain_documented",
    "goal_owns_project_workflow_state",
    "workflow_templates_gate_execution",
    "agents_entry_map_routes_goal_superpowers_native_subagents",
}
assert set(statuses) == expected_result_ids
assert all(status == "proved" for status in statuses.values())
```

- [ ] **Step 2: Run the focused tests and verify the new contract fails**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_change_lifecycle_checks.py scripts/verification/tests/test_formal_profile_checks.py
```

Expected: FAIL because the evaluator still exposes the legacy chain ID and archived-change closure result.

- [ ] **Step 3: Remove the archive-state dependency from the evaluator**

Delete the `check_change_state` import, the `change_state_report` local, and the archived-change result block. Replace `REQUIRED_RULE_IDS` with:

```python
REQUIRED_RULE_IDS = {
    "workflow_doc_exists",
    "change_lifecycle_profile_registered",
    "design_superpowers_harness_goal_chain_documented",
    "goal_owns_project_workflow_state",
    "workflow_templates_gate_execution",
    "agents_entry_map_routes_goal_superpowers_native_subagents",
}
```

Replace the chain result with:

```python
_result(
    "design_superpowers_harness_goal_chain_documented",
    "Design, Superpowers, Harness, and Goal handoff chain is documented",
    all(
        marker in workflow_text
        for marker in [
            "Design controls what changes",
            "Superpowers controls how changes are executed",
            "Harness controls whether the result is accepted",
            "Goal tracks long-running execution state",
            "python scripts/verification/harness.py --profile all",
            "verification-before-completion",
        ]
    ),
    ["docs/ai-engineering-workflow.md"],
),
```

Update the workflow-document presence check to require `Design`, `Superpowers`, `Harness`, `Goal`, `native subagents`, and `change-lifecycle`. Update the template check to require `Design source` instead of the removed layer's name.

- [ ] **Step 4: Rewrite the profile and rule manifest**

Set the profile description to:

```json
"description": "Design, Superpowers, Harness, Goal, and native subagent workflow checks"
```

Keep the existing profile name, order, script, and `requires_godot` value. In the rule manifest, register the six IDs above, use the new chain ID/title, change the template-rule title to `Harness templates require the Design/Superpowers/Harness/Goal execution gates`, and remove the archived-change rule object.

- [ ] **Step 5: Rewrite the live workflow and template markers**

Start `docs/ai-engineering-workflow.md` with these responsibilities:

```markdown
1. **Design controls what changes.**
   A change starts from an approved repository-local design under `docs/superpowers/specs/` or an explicitly approved equivalent.
2. **Superpowers controls how changes are executed.**
3. **Harness controls whether the result is accepted.**
4. **Goal tracks long-running execution state.**
```

Remove the archived-change closure section. In `.harness/templates/PLAN.md` use `Design source:` for the intent link. In `.harness/templates/HARNESS_CHECKLIST.md` use `Design source` in planning and `design` in the workflow-change checklist.

- [ ] **Step 6: Run focused tests and the workflow profile**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_change_lifecycle_checks.py scripts/verification/tests/test_formal_profile_checks.py scripts/verification/tests/test_harness_registry.py
python scripts/verification/harness.py --profile change-lifecycle
```

Expected: all pytest tests PASS and `overall_passed=True` for `change-lifecycle`.

- [ ] **Step 7: Commit the generic lifecycle contract**

```powershell
git add -- scripts/verification/check_change_lifecycle.py scripts/verification/tests/test_change_lifecycle_checks.py scripts/verification/tests/test_formal_profile_checks.py .harness/profiles/change-lifecycle.json .harness/rules/change-lifecycle-rules.json .harness/templates/PLAN.md .harness/templates/HARNESS_CHECKLIST.md docs/ai-engineering-workflow.md
git commit -m "refactor: remove legacy specification workflow contract"
```

---

### Task 2: Remove Legacy Assets And Tracked References

**Files:**

- Delete: the top-level legacy artifact tree resolved by `$legacyName = "open" + "spec"`
- Delete: the five `.codex/skills/$legacyName-*` directories
- Delete: `scripts/verification/check_change_state.py`
- Delete: `scripts/verification/tests/test_change_state_checks.py`
- Delete: `docs/superpowers/specs/2026-06-11-change-state-guard-design.md`
- Delete: `docs/superpowers/plans/2026-06-11-change-state-guard-implementation-plan.md`
- Modify: `scripts/verification/check_boundaries.py`
- Modify: `docs/INDEX.md`
- Modify: `docs/harness.md`
- Modify: `docs/harness-architecture.md`
- Modify: `docs/superpowers/specs/2026-06-10-ai-engineering-workflow-integration-design.md`
- Modify: `docs/superpowers/plans/2026-06-10-ai-engineering-workflow-integration-implementation-plan.md`
- Modify: `docs/superpowers/plans/2026-06-10-siming-event-bus-final-merge-retrospective.md`

**Interfaces:**

- Consumes: the generic result contract produced by Task 1.
- Produces: a tracked repository tree with no legacy artifact paths, project-local legacy skills, archive evaluator, or textual references.

- [ ] **Step 1: Run tracked content and path scans and verify they fail**

```powershell
$pattern = 'open.?spec'
git grep -in -E $pattern
git ls-files | Select-String -Pattern $pattern
```

Expected: both scans report existing tracked references or paths.

- [ ] **Step 2: Resolve and inspect every recursive deletion target**

```powershell
$root = (Resolve-Path '.').Path
$legacyName = "open" + "spec"
$targets = @(
    $legacyName,
    ".codex/skills/$legacyName-apply-change",
    ".codex/skills/$legacyName-archive-change",
    ".codex/skills/$legacyName-explore",
    ".codex/skills/$legacyName-propose",
    ".codex/skills/$legacyName-sync-specs"
)
$resolvedTargets = $targets | ForEach-Object { (Resolve-Path -LiteralPath $_).Path }
$resolvedTargets
if ($resolvedTargets | Where-Object { -not $_.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase) }) {
    throw 'Deletion target escaped the repository root.'
}
```

Expected: six absolute targets, all under `D:\Paralls-phase0-1` and none under `.worktrees`.

- [ ] **Step 3: Delete the inspected legacy assets and archive guard**

Remove the six inspected directories, `scripts/verification/check_change_state.py`, its focused test, and the two 2026-06-11 change-state guard documents. Use `apply_patch` for repository edits and verify `git status --short` lists only the intended deletions.

- [ ] **Step 4: Remove the legacy root from boundary evaluation**

In `scripts/verification/check_boundaries.py`, remove the obsolete legacy artifact root from the list of directories scanned as project-owned workflow surfaces. Do not change runtime boundary rules.

- [ ] **Step 5: Rewrite current and historical documentation**

Apply these terminology rules consistently:

- current change intent comes from approved repository-local designs and plans;
- the live workflow is Design, Superpowers, Harness, Goal, and native subagents;
- the 2026-06-10 workflow design/plan describe the generic workflow profile rather than an external specification layer;
- the Siming event-bus retrospective refers to `harness and workflow assets`;
- `docs/INDEX.md`, `docs/harness.md`, and `docs/harness-architecture.md` describe the generic `change-lifecycle` profile and its six surviving checks;
- no document claims archived external changes are required evidence.

- [ ] **Step 6: Prove tracked references and paths are gone**

```powershell
$pattern = 'open.?spec'
$contentMatches = @(git grep -in -E $pattern)
$pathMatches = @(git ls-files | Select-String -Pattern $pattern)
if ($contentMatches.Count -ne 0 -or $pathMatches.Count -ne 0) {
    $contentMatches
    $pathMatches
    throw 'Legacy specification references remain.'
}
```

Expected: command exits 0 without printing a match.

- [ ] **Step 7: Run focused source, registry, and boundary tests**

```powershell
python -m pytest -q scripts/verification/tests/test_change_lifecycle_checks.py scripts/verification/tests/test_formal_profile_checks.py scripts/verification/tests/test_harness_registry.py scripts/verification/tests/test_boundary_checks.py
python scripts/verification/harness.py --profile boundaries
python scripts/verification/harness.py --profile change-lifecycle
```

Expected: all tests and both profiles PASS.

- [ ] **Step 8: Commit the complete removal**

```powershell
$legacyName = "open" + "spec"
git add -u -- `
  $legacyName `
  ".codex/skills/$legacyName-apply-change" `
  ".codex/skills/$legacyName-archive-change" `
  ".codex/skills/$legacyName-explore" `
  ".codex/skills/$legacyName-propose" `
  ".codex/skills/$legacyName-sync-specs" `
  scripts/verification/check_change_state.py `
  scripts/verification/check_boundaries.py `
  scripts/verification/tests/test_change_state_checks.py `
  docs/INDEX.md `
  docs/ai-engineering-workflow.md `
  docs/harness.md `
  docs/harness-architecture.md `
  docs/superpowers/specs/2026-06-10-ai-engineering-workflow-integration-design.md `
  docs/superpowers/specs/2026-06-11-change-state-guard-design.md `
  docs/superpowers/plans/2026-06-10-ai-engineering-workflow-integration-implementation-plan.md `
  docs/superpowers/plans/2026-06-10-siming-event-bus-final-merge-retrospective.md `
  docs/superpowers/plans/2026-06-11-change-state-guard-implementation-plan.md
git diff --cached --check
git commit -m "refactor: remove legacy specification integration"
```

Expected: the staged diff contains only the approved removals, workflow rewrites, tests, and documentation updates.

---

### Task 3: Run The Full Verification Ladder

**Files:**

- Verify: all source files changed by Tasks 1 and 2
- Inspect: `.harness/verification/` for generated evidence changes

**Interfaces:**

- Consumes: the completed generic lifecycle contract and clean tracked tree.
- Produces: fresh focused and broad verification evidence suitable for the final completion report.

- [ ] **Step 1: Run the complete verification test suite**

```powershell
python -m pytest -q scripts/verification/tests
```

Expected: PASS with no import of the deleted archive-state evaluator.

- [ ] **Step 2: Run the repository backend test gate**

```powershell
python -m pytest -v
```

Expected: PASS. Record exact failures if unrelated pre-existing tests fail.

- [ ] **Step 3: Run the broad Harness gate**

```powershell
python scripts/verification/harness.py --profile all
```

Expected: `overall_passed=True`. If a Godot-backed profile is unavailable or fails, report that profile and its exact evidence separately; do not treat focused workflow success as a full pass.

- [ ] **Step 4: Re-run zero-reference and diff checks after generated evidence**

```powershell
$pattern = 'open.?spec'
git grep -in -E $pattern
git ls-files | Select-String -Pattern $pattern
git diff --check
git status --short --branch
```

Expected: both scans print no matches, `git diff --check` prints nothing, and status contains no unrelated edits.

- [ ] **Step 5: Commit only intentional durable verification evidence, if any**

If tracked Harness reports changed and repository policy requires keeping them, inspect each diff and stage only evidence produced by this run:

```powershell
git diff -- .harness/verification
git add -- .harness/verification
git diff --cached --check
git commit -m "test: record simplified workflow verification"
```

If no tracked durable evidence changed, skip this commit and report the executed commands and results.
