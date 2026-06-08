# Architecture Realignment Index

This folder is the single root-level home for the current architecture realignment effort.

It contains:

- the architecture realignment design
- the Stage 1 completed implementation record
- the Stage 1 handoff summary
- the current branch/worktree integration inventory
- the enhanced-subsystem merge playbooks
- the Stage 2 relocation and downlink v0 plan
- the current `L1` gap assessment note

## Read Order

If you are new to this work, read in this order:

1. [2026-06-08-architecture-realignment-and-downlink-prep-design.md](</d:/Users/User/Documents/paralls-phase-0-demo/architecture-realignment/2026-06-08-architecture-realignment-and-downlink-prep-design.md>)
2. [2026-06-08-stage1-handoff-summary.md](</d:/Users/User/Documents/paralls-phase-0-demo/architecture-realignment/2026-06-08-stage1-handoff-summary.md>)
3. [l1-main-project-gap-assessment.md](</d:/Users/User/Documents/paralls-phase-0-demo/architecture-realignment/l1-main-project-gap-assessment.md>)
4. [2026-06-08-branch-integration-map.md](</d:/Users/User/Documents/paralls-phase-0-demo/architecture-realignment/2026-06-08-branch-integration-map.md>)

That sequence explains:

- why the reorganization exists
- what Stage 1 already accomplished
- what part of the main-project `L1` gap is already closed
- what branch/worktree surfaces are currently visible for later reintegration

## Execution Order

If you are continuing the engineering work, follow this order:

### 1. Stage 1 Reference

Use:

- [2026-06-08-stage1-architecture-realignment-implementation-plan.md](</d:/Users/User/Documents/paralls-phase-0-demo/architecture-realignment/2026-06-08-stage1-architecture-realignment-implementation-plan.md>)

Status:

- already implemented in the current branch

Use it as:

- a record of what was introduced
- a reference for the intended Stage 1 boundaries

### 2. Before Enhanced Branch Merge

Use:

- [2026-06-08-enhanced-subsystems-conflict-preflight.md](</d:/Users/User/Documents/paralls-phase-0-demo/architecture-realignment/2026-06-08-enhanced-subsystems-conflict-preflight.md>)

Fast command:

```bash
python scripts/verification/verify_enhanced_merge_preflight.py
```

Use it as:

- the shortest operator-facing preflight before the first enhanced branch merge

### 3. During Enhanced Branch Merge

Use:

- [2026-06-08-enhanced-subsystems-merge-checklist.md](</d:/Users/User/Documents/paralls-phase-0-demo/architecture-realignment/2026-06-08-enhanced-subsystems-merge-checklist.md>)

Use it as:

- the full merge procedure
- the seam-preservation checklist
- the conflict-resolution landing guide

### 4. After Enhanced Branch Merge

Use:

- [2026-06-08-stage2-merge-and-downlink-v0-implementation-plan.md](</d:/Users/User/Documents/paralls-phase-0-demo/architecture-realignment/2026-06-08-stage2-merge-and-downlink-v0-implementation-plan.md>)

Start gate:

```bash
python scripts/verification/verify_stage2_start_gate.py
```

Use it as:

- the Stage 2 relocation plan
- the first downlink v0 implementation plan

## Current Status

Current branch status:

- Stage 1 architecture seam work is complete
- architecture realignment docs are consolidated in this folder
- enhanced merge preflight tooling exists
- Stage 2 has a written plan
- downlink v0 is **not implemented yet**

## Stop Condition

If you are not actively merging enhanced branches back, stop after reviewing the design, handoff, and relevant checklist.

Do not start Stage 2 or downlink v0 work until the enhanced `ESM`, `Siming`, and event-bus branches are merged and the start gate is green.
