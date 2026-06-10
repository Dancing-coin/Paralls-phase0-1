# Harness Lifecycle Hardening Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining operational Harness Engineering gaps by adding lifecycle artifacts, local CI equivalence, future profile templates, retention policy, and clean handoff checks.

**Architecture:** Adapt the `walkinglabs/learn-harness-engineering` Project 06 solution pattern to Paralls instead of copying its Electron-specific scripts. Keep Paralls verification authoritative through `.harness/profiles`, `.harness/rules`, `scripts/verification`, and generated `.harness/verification` evidence.

**Tech Stack:** Python standard library, PowerShell local CI script, Markdown lifecycle docs, JSON harness manifests.

---

## Source Patterns Adapted

- `feature_list.json` becomes `.harness/features.json` with profile-level evidence.
- `init.sh` becomes `.harness/ci/local-ci-gate.ps1`, because this workspace is Windows/Godot oriented.
- `clean-state-checklist.md` becomes `.harness/clean-state-checklist.md`.
- `session-handoff.md`, `quality-document.md`, and `evaluator-rubric.md` become `.harness/session-handoff.md`, `.harness/quality-document.md`, and `.harness/evaluator-rubric.md`.
- `scripts/benchmark.sh` and `cleanup-scanner.sh` become harness-native `harness-lifecycle` checks plus the existing `drift`, `phase0`, and `phase1-slice` profiles.
- `docs/ARCHITECTURE.md` and `docs/RELIABILITY.md` become `docs/harness-architecture.md` and `docs/harness-reliability.md`.

## Task 1: Lifecycle Tests

- [ ] Write failing tests for a new `harness-lifecycle` profile.
- [ ] Assert lifecycle artifacts exist and reference current profile evidence.
- [ ] Assert local CI gate invokes focused tests, compile, and full harness.
- [ ] Assert future profile and rule templates exist.
- [ ] Assert retention policy defines max archived runs and baseline/diff rules.

## Task 2: Lifecycle Implementation

- [ ] Add `.harness/features.json`.
- [ ] Add `.harness/retention-policy.json`.
- [ ] Add `.harness/templates/profile-template.json` and `.harness/templates/rule-template.json`.
- [ ] Add `.harness/ci/local-ci-gate.ps1`.
- [ ] Add lifecycle docs and checklists.
- [ ] Implement `scripts/verification/check_harness_lifecycle.py`.

## Task 3: Registry And Release Gate Integration

- [ ] Add `.harness/profiles/harness-lifecycle.json`.
- [ ] Add `.harness/rules/harness-lifecycle-rules.json`.
- [ ] Extend release gate checks to require local CI equivalence.
- [ ] Update docs to include lifecycle profile and source adaptation notes.

## Final Verification

- [ ] `python -m pytest -q scripts\verification\tests`
- [ ] `python -m compileall -q scripts\verification`
- [ ] `python scripts\verification\harness.py --profile harness-lifecycle`
- [ ] `python scripts\verification\harness.py --profile release-gate`
- [ ] `python scripts\verification\harness.py --profile all`
