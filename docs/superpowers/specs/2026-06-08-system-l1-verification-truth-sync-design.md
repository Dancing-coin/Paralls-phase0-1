# System L1 Verification Truth Sync Design

## Goal

Define how repository truth stays synchronized across:

- implementation
- verification
- status/checklist documentation

for `System L1`.

## Problem

A repository can pass tests and still mislead future work if:

- checklists are stale
- audit criteria are incomplete
- summary docs lag behind code

That is a real completeness gap.

## Required Truth Surfaces

The repository should maintain four aligned truth surfaces:

1. code truth
2. focused backend test truth
3. runtime verification truth
4. repository-local status/checklist truth

## Rules

### 1. New L1 domain work must update the audit surface

If a new `L1` fact family becomes part of the supported domain, then:

- `verification_audit.py`
- or one of the verification scripts

must explicitly prove it where appropriate.

### 2. Positive fixtures and negative fixtures must both be updated

When an audit grows stricter:

- positive proof fixtures must add the new evidence
- negative fixtures must remove it

This avoids false failures and false passes.

### 3. Checklist docs cannot drift

If a repository-local checklist exists, it must be updated or removed when it contradicts the current implementation state.

## Success Criteria

This spec is satisfied when future `System L1` work cannot quietly become “implemented but undocumented” or “documented but untrue”.

