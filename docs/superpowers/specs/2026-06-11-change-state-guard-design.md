# Change State Guard Design

## Problem

The repository already documents the OpenSpec, Superpowers, Harness, Goal, and native subagent workflow in `docs/ai-engineering-workflow.md`, and the `change-lifecycle` harness profile proves that the workflow is discoverable. The remaining gap is that the relationship between an archived OpenSpec change, its Superpowers design/plan artifacts, and its durable Harness evidence is mostly textual.

Comet is a useful reference because it turns the OpenSpec + Superpowers handoff into a script-backed lifecycle with phase metadata, guard checks, verification report requirements, and archive automation. This project should borrow that guard pattern without installing Comet, adding npm dependencies, or introducing `.comet.yaml` as a new source of truth.

## Goals

- Add a project-owned change-state guard that verifies workflow closure using existing repository artifacts.
- Keep `.harness/verification/` as the durable evidence surface.
- Strengthen the existing `change-lifecycle` profile instead of creating a parallel profile.
- Keep the implementation Python-based and compatible with the current Harness runner.
- Make the guard useful for future workflow changes without changing Godot runtime or backend behavior.

## Non-Goals

- Do not run `comet init`.
- Do not add `@rpamis/comet` or any other npm dependency.
- Do not add `.comet.yaml` as project workflow state.
- Do not replace `AGENTS.md`, Goal, OpenSpec, Superpowers, or Harness.
- Do not change Phase 0/Phase 1 runtime behavior.

## Design

Add `scripts/verification/check_change_state.py` as a static guard used by `scripts/verification/check_change_lifecycle.py`.

The new guard evaluates archived OpenSpec changes under `openspec/changes/archive/` and returns structured rule results. It should focus on archived changes because active changes can legitimately be incomplete. For each archived change, it checks the minimum closure shape:

- required OpenSpec files exist: `.openspec.yaml`, `proposal.md`, `design.md`, and `tasks.md`
- `tasks.md` has checklist items and no unchecked tasks
- the archive includes at least one delta spec under `specs/*/spec.md`
- the change can be associated with repository workflow evidence through one of:
  - a matching Superpowers design or plan reference
  - a verification note in the archived change
  - a matching harness run artifact proving the relevant acceptance profile

The first implementation should stay conservative. It should not require every historical archive to already contain rich metadata if the current repository has only one archived change. Instead, the guard should validate all archived changes that exist and report actionable missing fields. The `change-lifecycle` profile then exposes the aggregated result as one additional rule.

## Integration

Modify `check_change_lifecycle.py` to include one new required rule:

`archived_changes_have_state_closure`

That rule passes only when `check_change_state.evaluate_change_state(project_root)` reports success. Its evidence should include:

- `openspec/changes/archive/`
- `docs/superpowers/specs/`
- `docs/superpowers/plans/`
- `.harness/verification/`

Update `.harness/rules/change-lifecycle-rules.json` so the new rule is registered and mapped to the generated `change-lifecycle` report.

Update `docs/ai-engineering-workflow.md` and `docs/harness.md` to document the new rule:

- OpenSpec records the change lifecycle.
- Superpowers records execution design and plans.
- Harness records durable acceptance evidence.
- The change-state guard checks that archived changes do not lose this chain.

## Testing

Add focused tests in `scripts/verification/tests/test_change_lifecycle_checks.py` or a new focused test file:

- archived changes with complete required files and checked tasks pass
- archived changes with unchecked tasks fail
- the `change-lifecycle` report includes `archived_changes_have_state_closure`

Run:

```powershell
python -m pytest -q scripts\verification\tests\test_change_lifecycle_checks.py
python scripts\verification\harness.py --profile change-lifecycle
```

For broad workflow confidence, run:

```powershell
python scripts\verification\harness.py --profile all
```

## Acceptance

- `scripts/verification/check_change_state.py` exists and is imported by `check_change_lifecycle.py`.
- `change-lifecycle` reports `archived_changes_have_state_closure=proved`.
- The new guard writes evidence through the existing Harness report path, not a new state directory.
- `python -m pytest -q scripts\verification\tests\test_change_lifecycle_checks.py` passes.
- `python scripts\verification\harness.py --profile change-lifecycle` passes.

