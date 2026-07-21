# Harness Review Checklist

> Adapted from ai-boost/awesome-harness-engineering. Use before shipping or handing off a harness change.

## Agent Instructions

- [ ] Project overview is current.
- [ ] Repository structure is current.
- [ ] Tool permissions and destructive-operation boundaries are explicit.
- [ ] Verification gates list exact commands.

## Context Delivery

- [ ] Long-lived state is stored in files.
- [ ] Context entry points are discoverable from `docs/INDEX.md`.
- [ ] Sensitive data is not included in agent-facing harness files.

## Planning Artifacts

- [ ] Non-trivial tasks have a plan.
- [ ] Design source is linked for behavior or workflow changes.
- [ ] Goal is used for long-running execution state when the task spans multiple edits.
- [ ] Superpowers skill gates are recorded for planning, TDD, debugging, review, or completion verification.
- [ ] Milestones include verification commands.
- [ ] Implementation deviations are recorded.

## Verification Loop

- [ ] Focused tests exist for new check scripts.
- [ ] The agent can run the verification commands directly.
- [ ] `change-lifecycle` passes when workflow, Goal, Superpowers, design, or native subagent routing changes.
- [ ] Full harness evidence is archived under `.harness/verification/runs/<run-id>/`.

## Removal Criteria

| Component | Exists because | Can be removed when |
| --- | --- | --- |
| | | |
