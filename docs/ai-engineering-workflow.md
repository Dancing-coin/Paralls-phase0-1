# AI Engineering Workflow

This repository uses a four-layer workflow for non-trivial AI-assisted changes:

1. **OpenSpec controls what changes.**
   A change starts from a written design/spec under `docs/superpowers/specs/` or an explicitly approved equivalent design. The spec records scope, acceptance criteria, and constraints before implementation.
   A Superpowers brainstorming spec may pause at `Status: awaiting-user-review`; that state is a review gate, not approval to plan or implement.
2. **Superpowers controls how changes are executed.**
   Agents use the relevant Superpowers skill for the task shape: brainstorming for new behavior, writing-plans for multi-step work, test-driven-development for code changes, systematic-debugging for failures, and verification-before-completion before claiming completion.
3. **Harness controls whether the result is accepted.**
   Every meaningful change maps to one or more harness profiles. The final acceptance command for broad changes is:

   ```powershell
   python scripts/verification/harness.py --profile all
   ```

4. **Goal tracks long-running execution state.**
   Goal is the active execution container for large demands. Use `create_goal` when a task spans multiple edits or verification loops, and `update_goal` only when the objective is genuinely complete or blocked.

## Source Of Truth

- The spec and plan are the source of truth for intent and scope.
- `.harness/profiles/` and `.harness/rules/` are the source of truth for machine-checkable acceptance.
- `.harness/verification/` is generated evidence.
- Goal is transient execution state; it does not replace specs, plans, or harness reports.

## Change-State Closure

Archived OpenSpec changes must retain enough machine-checkable evidence to prove the lifecycle did not lose intent, execution, or verification context. The `change-lifecycle` harness profile checks archived changes for required OpenSpec files, completed tasks, retained delta specs, and a connection to Superpowers or Harness evidence.

This guard borrows Comet's phase-guard idea but keeps the project source of truth unchanged: OpenSpec records change intent, Superpowers records design and execution planning, Harness records durable acceptance evidence, and Goal records active execution continuity.

## Large Change Flow

Use this flow for any change that touches runtime behavior, verification policy, agent workflow, or cross-component contracts:

```text
approved idea
  -> design spec draft
  -> user review and approval
  -> implementation plan
  -> Goal for execution continuity
  -> Superpowers discipline during edits
  -> focused tests
  -> relevant harness profile
  -> python scripts/verification/harness.py --profile all
  -> update_goal complete only after fresh evidence
```

## Agent Coordination

Use Codex native subagents for independent, bounded work lanes when parallelism improves throughput. The lead agent owns integration, conflict resolution, and final verification. Do not use child agents as a substitute for a written spec, plan, or harness evidence.

Goal is the long-running objective ledger for explicit tasks. New work should keep durable acceptance evidence in `.harness` and use Goal only for active task continuity; do not use either surface as a substitute for specs, plans, tests, or harness reports.

## Required Gates

- New behavior: write or reference a spec before code.
- Brainstorming handoff: a spec marked `Status: awaiting-user-review` may exist without an implementation plan until the user approves it.
- Multi-step change: write or reference an implementation plan after spec approval.
- Code change: use test-driven-development unless the change is generated or documentation-only.
- Failure investigation: use systematic-debugging before edits.
- Completion claim: use verification-before-completion and report fresh evidence.
- Broad workflow change: run `python scripts/verification/harness.py --profile change-lifecycle` and `python scripts/verification/harness.py --profile all`.
