# Branch Integration Map

## Purpose

This document records the currently discoverable local and remote branch/worktree state relevant to the architecture realignment effort.

It is **not** a merge instruction by itself.
It is a current-state inventory so later reintegration work does not start from guesswork.

## Current Main Branch

- branch: `main`
- worktree: `D:\Users\User\Documents\paralls-phase-0-demo`
- current HEAD at time of capture:
  - `284d77c2f86b4bd6aed28d4c75c72586f1bb62e1`

## Local Worktrees

### 1. `feat/l1-raw-fact-emitter`

- worktree:
  - `D:\Users\User\Documents\paralls-phase-0-demo\.worktrees\l1-raw-fact-emitter`
- branch:
  - `refs/heads/feat/l1-raw-fact-emitter`
- HEAD:
  - `bb47c95ff00eb2de52324d00b5d5ae61119ebd0e`

Interpretation:

- this is a clear local candidate for the already-known `L1` / raw-fact branch line
- it is directly relevant to the current architecture realignment effort

### 2. `main-merge-preview`

- worktree:
  - `D:\Users\User\Documents\paralls-phase-0-demo\.worktrees\main-merge-preview`
- branch:
  - `refs/heads/main-merge-preview`
- HEAD:
  - `a837751ab7e48d5e569530db88cb66457eff7434`

Interpretation:

- this appears to be a local preview/integration branch
- branch description in `git branch --all --verbose --no-abbrev` indicates it already includes a merge of `feat/l1-raw-fact-emitter`
- this makes it a likely staging surface for later reintegration testing

## Remote Branches Currently Visible

### 1. `origin/feat-l1-raw-fact-emitter`

- HEAD:
  - `4bc188c83f464ef0a071f9889031eaeb47680bf6`

Interpretation:

- remote branch exists for the raw-fact / Stage-B-adjacent line
- local `feat/l1-raw-fact-emitter` is the most obvious matching local branch

### 2. `origin/pjm_siming`

- HEAD:
  - `ad6f66ab68bf7cdb22748eee13cfff7af6973a7b`

Interpretation:

- this is the strongest currently visible remote candidate for the enhanced `Siming` line
- there is no matching local worktree visible yet in the current repository state

### 3. `origin/main`

- HEAD:
  - `76a7c559f9468e59dcae77aa28e1304ecf257adf`

Interpretation:

- upstream main has moved ahead of the local branch
- future reintegration work should expect divergence reconciliation, not just a trivial fast-forward

## What Is Not Yet Visible

Based on the current local evidence, there is **not yet** a clearly named local branch/worktree for:

- enhanced event-bus line
- enhanced `ESM` line

That does **not** prove those branches do not exist elsewhere.
It only means they are not currently obvious in this repository’s local branch/worktree state.

## Current Best Mapping To The Realignment Plan

Using only current evidence:

- `L1 / raw-fact / perception-chain-adjacent` candidate:
  - `feat/l1-raw-fact-emitter`
- `Siming` candidate:
  - `origin/pjm_siming`
- integration preview surface:
  - `main-merge-preview`

Unknown / not yet explicitly mapped from current evidence:

- enhanced authority/event-bus branch
- enhanced `ESM` branch

## Recommended Next Discovery Step

Before any actual reintegration begins, the operator should confirm:

1. whether there are additional remote branches for:
   - authority bus
   - `ESM`
2. whether `main-merge-preview` is intended to remain the integration branch
3. whether `origin/pjm_siming` should first be checked out into its own local worktree before any merge attempt

## Constraint

This file is an inventory only.

It does **not** authorize:

- starting any merge
- rebasing any branch
- changing worktree structure

Those actions should still follow:

- `README.md`
- `2026-06-08-enhanced-subsystems-conflict-preflight.md`
- `2026-06-08-enhanced-subsystems-merge-checklist.md`
