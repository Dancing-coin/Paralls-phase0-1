# Formal Harness Engineering Completion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the remaining formal-project Harness Engineering foundation around rule evidence mapping, project-level profiles, evidence diffing, Godot static verification, and CI/release gate entry points.

**Architecture:** Keep `.harness/profiles/` and `.harness/rules/` as project-owned inputs. Add small standard-library verification scripts that emit JSON/Markdown reports through the existing `common.py` helpers and keep runtime authority in the existing `phase0` and `phase1-slice` profiles.

**Tech Stack:** Python standard library, Markdown docs, Godot project text resources, GitHub Actions YAML, existing harness runner.

---

## File Structure

- Modify: `.harness/profiles/*.json` for new project-level profiles.
- Modify: `.harness/rules/*.json` for rule-to-evidence mappings.
- Create: `.harness/ci/release-gate.json` for CI/release gate metadata.
- Modify: `scripts/verification/registry.py` to expose rule evidence mapping.
- Modify: `scripts/verification/harness.py` to write run manifests, baselines, and diffs.
- Create: `scripts/verification/evidence.py` for evidence manifest/baseline/diff helpers.
- Create: `scripts/verification/check_backend_contract.py`.
- Create: `scripts/verification/check_godot_project.py`.
- Create: `scripts/verification/check_release_gate.py`.
- Create: `.github/workflows/harness.yml`.
- Modify: `docs/harness.md` and `docs/INDEX.md`.

## Task 1: Rule Evidence Mapping

- [ ] Write failing tests that every rule manifest has stable rule IDs and evidence profile/check IDs.
- [ ] Update rule manifests to include `profile`, `rules[].id`, and `rules[].evidence`.
- [ ] Add registry helpers to flatten rule evidence mappings for checks and reports.
- [ ] Run registry focused tests.

## Task 2: Evidence Manifest, Baseline, And Diff

- [ ] Write failing tests for run manifest, baseline, and previous-run diff output.
- [ ] Implement standard-library evidence helpers.
- [ ] Wire harness report writing to archive run manifests, latest baseline, and latest diff.
- [ ] Run harness runner focused tests.

## Task 3: Formal Project Profiles

- [ ] Write failing tests that the registry includes formal profiles after `drift`.
- [ ] Add `backend-contract`, `godot-project`, and `release-gate` profile manifests.
- [ ] Add matching rule manifests and check scripts.
- [ ] Run registry and new profile tests.

## Task 4: Godot Engineering Static Verification

- [ ] Write failing tests for scene/resource/autoload integrity checks.
- [ ] Implement static Godot project checks without starting the editor.
- [ ] Ensure the check reports missing `res://` references with concrete paths.
- [ ] Run the `godot-project` profile.

## Task 5: CI And Release Gate

- [ ] Write failing tests for CI workflow and release gate metadata.
- [ ] Add `.github/workflows/harness.yml`.
- [ ] Add release gate checks that verify CI calls the harness and release metadata points at the full profile.
- [ ] Run the `release-gate` profile.

## Final Verification

- [ ] `python -m pytest -q scripts\verification\tests`
- [ ] `python -m py_compile scripts\verification\*.py`
- [ ] `python scripts\verification\harness.py --profile docs`
- [ ] `python scripts\verification\harness.py --profile drift`
- [ ] `python scripts\verification\harness.py --profile all`
