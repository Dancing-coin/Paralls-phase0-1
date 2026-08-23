# Harness Execution Contract

## Status

- Date: `2026-08-22`
- Scope: `D:\Paralls-phase0-1`
- Decision mode: user-approved implementation slice

## Goal

Add a thin, domain-neutral Harness contract for task lifecycle, failure disposition, and task-level trace correlation. The contract wraps existing ESM, Gameplay authority, embodied, and production workflows without becoming a new authority owner.

## Motivation

The Harness Engineering reference identifies orchestration, error handling, state management, and observability as separate production concerns. The repository already has domain-specific state machines, revision checks, replay, and evidence reports, but lacks one small contract that can describe a task from creation through terminal verification and classify failures consistently.

## Design

### Execution envelope

`ExecutionEnvelope` carries `task_id`, `run_id`, `correlation_id`, `causation_id`, policy/authority revision pins, attempt budget, current phase, optional checkpoint, and the latest failure disposition. Phases are:

```text
created -> running -> waiting | recovering | committed | failed | aborted
waiting -> running | aborted
failed -> recovering | aborted
recovering -> running | failed | aborted
```

`committed` and `aborted` are terminal. Invalid transitions fail closed.

### Failure disposition

`FailureDisposition` maps a closed set of failure kinds to deterministic recovery actions:

| Kind | Action | Retry |
| --- | --- | --- |
| `transient` | `retry` | bounded |
| `invalid_input` | `repair_input` | no |
| `permission_denied` | `request_approval` | no |
| `constraint_conflict` | `replan` | no |
| `dependency_missing` | `wait_dependency` | no hot retry |
| `stale_revision` | `refresh_revision` | no hot retry |
| `unknown` | `abort` | no |

The mapping is deterministic and does not inspect model prose. A committed write is never undone by the Harness contract.

### Task trace

`TaskTraceRecord` is an append-only in-memory record with sequence, task/run/correlation identity, stage, status, producer timestamp, and redacted metadata. `HarnessExecutionTraceService` owns envelopes and traces for one process. It exposes `start`, `transition`, `record`, `get_envelope`, and `get_trace`; it has no authority write method.

## Boundaries

- The service does not execute tools, append Gameplay events, mutate Godot state, or choose domain owners.
- Persistence, distributed recovery, and transport delivery remain later work.
- Existing domain receipts and replay evidence remain the source of truth for committed outcomes.

## Acceptance criteria

1. Pydantic models reject invalid phases, failure kinds, empty identity fields, and negative budgets.
2. The service accepts only the declared lifecycle transitions and rejects writes after terminal phases.
3. Every failure kind returns the documented action/retry policy.
4. Trace records preserve task/run/correlation identity and monotonically increasing sequence.
5. The focused Harness profile produces JSON and Markdown evidence.
6. No existing authority owner or runtime protocol changes.

## Non-goals

- No generic Agent framework.
- No automatic retry loop.
- No persistence or cross-process resume.
- No changes to Siming or CharacterAgent behavior.
