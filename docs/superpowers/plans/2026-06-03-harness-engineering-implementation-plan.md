# Harness Engineering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a narrow Harness Engineering layer so agents can discover project knowledge, run stable verification profiles, check mechanical invariants, and retain durable evidence per run.

**Architecture:** Keep existing Phase 0 and Phase1-slice verification scripts as runtime authorities. Add a thin unified runner, static docs/boundary/drift checks, versioned profile/rule manifests, and docs entry points that make the harness discoverable.

**Tech Stack:** Python 3.11 standard library, existing Godot verification scripts, Markdown docs, `.harness/profiles`, `.harness/rules`, `.harness/verification` artifacts.

---

## File Structure

- Create: `docs/INDEX.md` as the repository knowledge map.
- Create: `docs/harness.md` as the verification harness guide.
- Create: `scripts/verification/harness.py` as the unified command entry point.
- Create: `scripts/verification/registry.py` as the profile/rule manifest loader.
- Create: `scripts/verification/check_boundaries.py` as the static invariant checker.
- Create: `scripts/verification/check_docs.py` as the docs freshness checker.
- Create: `scripts/verification/check_drift.py` as the local drift checker.
- Create: `.harness/profiles/*.json` as versioned profile manifests.
- Create: `.harness/rules/*.json` as versioned rule manifests.
- Read: `scripts/verification/verify_phase0.py` for existing strict runtime validation.
- Read: `scripts/verification/verify_phase1_slice.py` for existing Phase1-shaped slice validation.
- Read: `scripts/verification/common.py` for report directory and helper conventions.

## Task 1: Add Agent-Readable Documentation Entry Points

**Files:**
- Create: `docs/INDEX.md`
- Create: `docs/harness.md`

- [ ] **Step 1: Create `docs/INDEX.md`**

Add a short map that points agents to the active mission, harness, specs, plans, and reference docs.

- [ ] **Step 2: Create `docs/harness.md`**

Document the verification profiles and when to use each profile.

- [ ] **Step 3: Verify docs are discoverable**

Run:

```powershell
rg -n "Harness|phase0|phase1-slice|boundaries" docs/INDEX.md docs/harness.md
```

Expected: both files contain the harness entry points.

## Task 2: Add Static Boundary Checker

**Files:**
- Create: `scripts/verification/check_boundaries.py`

- [ ] **Step 1: Implement checks**

The checker should inspect repository files without running Godot or backend services.

Required checks:

- `docs_index_exists`
- `harness_doc_exists`
- `visual_fact_emitter_exists`
- `direct_visual_fact_send_bypass_absent`
- `websocket_envelope_model_exists`
- `phase0_report_writes_json_and_markdown`

- [ ] **Step 2: Run the checker**

Run:

```powershell
python scripts/verification/check_boundaries.py
```

Expected: writes `.harness/verification/boundary-report.json` and `.harness/verification/boundary-report.md`.

## Task 3: Add Unified Harness Runner

**Files:**
- Create: `scripts/verification/harness.py`

- [ ] **Step 1: Implement profile dispatch**

Supported profiles:

- `docs`
- `boundaries`
- `drift`
- `phase0`
- `phase1-slice`
- `all`

- [ ] **Step 2: Pass through executable overrides**

Forward `--godot-exe` and `--python-exe` to profiles that need them.

- [ ] **Step 3: Run boundaries through the unified runner**

Run:

```powershell
python scripts/verification/harness.py --profile boundaries
```

Expected: the boundary profile runs and returns the same exit code as `check_boundaries.py`.

## Task 3.5: Add Registry And Evidence Retention

**Files:**
- Create: `.harness/profiles/*.json`
- Create: `.harness/rules/*.json`
- Create: `scripts/verification/registry.py`
- Update: `scripts/verification/harness.py`
- Update: `.gitignore`

- [ ] **Step 1: Add versioned manifests**

Add `schema_version: 1` profile manifests for `docs`, `boundaries`, `drift`, `phase0`, and `phase1-slice`. Add matching rule manifests for docs, boundaries, and drift.

- [ ] **Step 2: Load profile order from registry**

Update the runner so `--profile all` follows `.harness/profiles/*.json` order and each profile dispatches through its manifest script.

- [ ] **Step 3: Retain per-run evidence**

Write latest reports under `.harness/verification/` and archived reports under `.harness/verification/runs/<run-id>/`.

- [ ] **Step 4: Keep registry versionable**

Ignore `.harness/verification/` only. Do not ignore `.harness/profiles/` or `.harness/rules/`.

## Task 4: Verify And Report

**Files:**
- Read generated reports under `.harness/verification/`

- [ ] **Step 1: Run boundary verification**

Run:

```powershell
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile drift
```

Expected: docs and drift reports pass, including registry discoverability and versionability checks.

- [ ] **Step 2: Run boundary verification**

Run:

```powershell
python scripts/verification/harness.py --profile boundaries
```

Expected: report paths and `overall_boundaries_passed=True`.

- [ ] **Step 3: Run full harness**

Run:

```powershell
python scripts/verification/harness.py --profile all
```

Expected: all registered profiles pass in registry order and the final report contains `overall_harness_passed: true`.

- [ ] **Step 4: Inspect git diff**

Run:

```powershell
git diff -- docs scripts/verification
```

Expected: only harness docs and verification scripts changed.

- [ ] **Step 5: Record completion limits**

Report whether runtime profiles were run. If Godot is unavailable, state that runtime proof remains pending.
