# AI Engineering Workflow Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a verifiable OpenSpec + Superpowers + Harness + Goal workflow layer to the Paralls repository.

**Architecture:** Keep the workflow in docs and `.harness` manifests. Add one static verification script that proves the workflow is discoverable, versioned, template-backed, and routed through `AGENTS.md`.

**Tech Stack:** Python verification scripts, JSON harness manifests, Markdown project docs, existing pytest harness tests.

---

### Task 1: Change Lifecycle Tests

**Files:**
- Create: `scripts/verification/tests/test_change_lifecycle_checks.py`
- Modify: `scripts/verification/tests/test_harness_registry.py`

- [x] **Step 1: Write failing tests**

Add tests that import `evaluate_change_lifecycle`, assert all expected result IDs are `proved`, and assert the profile/rule registry includes `change-lifecycle`.

- [x] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest -q scripts\verification\tests\test_change_lifecycle_checks.py scripts\verification\tests\test_harness_registry.py
```

Expected before implementation: fail because `check_change_lifecycle` does not exist.

### Task 2: Static Profile Implementation

**Files:**
- Create: `scripts/verification/check_change_lifecycle.py`
- Create: `.harness/profiles/change-lifecycle.json`
- Create: `.harness/rules/change-lifecycle-rules.json`
- Modify: `.harness/profiles/harness-reference.json`
- Modify: `.harness/profiles/phase0.json`
- Modify: `.harness/profiles/phase1-slice.json`

- [ ] **Step 1: Implement the check script**

The script writes `.harness/verification/change-lifecycle-report.json` and `.md`, prints result IDs, and exits non-zero when any rule is missing.

- [ ] **Step 2: Register profile and rules**

Add `change-lifecycle` after `harness-lifecycle` and before `harness-reference`, then update profile orders so runtime profiles still run after static profiles.

### Task 3: Workflow Documents And Templates

**Files:**
- Create: `docs/ai-engineering-workflow.md`
- Create: `docs/superpowers/specs/2026-06-10-ai-engineering-workflow-integration-design.md`
- Modify: `docs/INDEX.md`
- Modify: `docs/harness.md`
- Modify: `docs/harness-architecture.md`
- Modify: `.harness/templates/PLAN.md`
- Modify: `.harness/templates/IMPLEMENT.md`
- Modify: `.harness/templates/HARNESS_CHECKLIST.md`
- Modify: `.harness/features.json`
- Modify: `AGENTS.md`

- [ ] **Step 1: Document the four-layer chain**

Document OpenSpec/design artifacts, Superpowers skills, Harness evidence, and Goal execution state.

- [ ] **Step 2: Wire docs and templates**

Make the workflow discoverable from `docs/INDEX.md`, `AGENTS.md`, and the reusable harness templates.

### Task 4: Verification

**Files:**
- Modify as needed only when verification exposes a real gap.

- [ ] **Step 1: Run focused tests**

```powershell
python -m pytest -q scripts\verification\tests\test_change_lifecycle_checks.py scripts\verification\tests\test_harness_registry.py
```

- [ ] **Step 2: Run focused profile**

```powershell
python scripts\verification\harness.py --profile change-lifecycle
```

- [ ] **Step 3: Run full harness**

```powershell
python scripts\verification\harness.py --profile all
```

