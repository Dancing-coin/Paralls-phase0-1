# Simplify AI Engineering Workflow Design

**Date:** 2026-07-14
**Status:** approved

## Context

The repository still contains a legacy external change-specification layer even though current work already uses repository-local Superpowers designs and plans as its durable intent source. The legacy layer is coupled to project-local Codex skills, archived change artifacts, Harness rules, verification scripts, tests, templates, and workflow documentation.

Removing only its top-level artifact directory would leave broken verification and misleading agent guidance. The removal must therefore update the full repository-owned integration while preserving the useful workflow checks that do not depend on that layer.

## Decision

Remove the legacy external specification integration completely from the current Git-tracked repository state. Keep `change-lifecycle` as a generic workflow profile and make repository-local designs and plans the sole durable source of change intent.

The resulting workflow has these responsibilities:

1. Superpowers governs design, planning, implementation discipline, and completion verification.
2. Harness provides machine-checkable acceptance and durable evidence.
3. Goal provides active continuity for explicitly created long-running objectives.
4. Native subagents may execute independent bounded work while the lead agent owns integration and final verification.

## Scope

Delete:

- the top-level legacy change-artifact tree;
- the five project-local Codex skills dedicated to that external layer;
- the archived-change state evaluator and its focused tests;
- design and plan artifacts whose only purpose is the archived-change state guard.

Rewrite:

- `docs/ai-engineering-workflow.md`, `docs/INDEX.md`, `docs/harness.md`, and `docs/harness-architecture.md`;
- Harness planning and review templates;
- the `change-lifecycle` profile, rules, evaluator, registry assertions, and focused tests;
- boundary checks and historical documents that would otherwise retain a tracked reference to the removed integration.

Preserve:

- the `change-lifecycle` profile name and its non-legacy workflow checks;
- repository-local Superpowers designs and implementation plans;
- Harness reports and existing runtime verification surfaces;
- runtime, backend, Godot, and authority behavior.

## Verification Contract

The revised `change-lifecycle` evaluator will retain these concerns:

- the AI engineering workflow document and its matching design and plan exist;
- the profile and rule manifest are registered;
- the design, Superpowers, Harness, and Goal handoff chain is documented;
- Goal ownership of active workflow continuity is explicit;
- reusable templates gate execution and verification;
- `AGENTS.md` routes large work through Goal, Superpowers, Harness, and native subagents.

The archived-change closure result and its underlying evaluator will be removed rather than translated into a replacement archive format.

## Failure Handling

The removal is incomplete if any tracked path or tracked file content still matches the removed product name, or if any surviving Harness rule references a deleted evaluator or result ID. Focused tests must fail on stale registry mappings, stale rule IDs, or missing workflow markers before the broad Harness run is attempted.

Generated verification evidence may change when the focused profiles run. Only intended source and durable evidence changes should be retained; unrelated generated churn must not be folded into the removal.

## Out Of Scope

- rewriting Git history;
- uninstalling a user-global CLI or user-global skills;
- modifying independent repositories under `.worktrees/`;
- changing runtime behavior or Godot scenes.

## Acceptance Criteria

1. No Git-tracked path or content matches `git grep -in -E 'open.?spec'` or the equivalent tracked-path scan.
2. The legacy artifact tree and its project-local skills no longer exist in the current worktree.
3. No surviving script, rule, template, or test expects archived change artifacts.
4. Focused verification tests pass.
5. `python scripts/verification/harness.py --profile change-lifecycle` passes.
6. `python scripts/verification/harness.py --profile all` passes, with any Godot/runtime limitation reported separately rather than hidden.
