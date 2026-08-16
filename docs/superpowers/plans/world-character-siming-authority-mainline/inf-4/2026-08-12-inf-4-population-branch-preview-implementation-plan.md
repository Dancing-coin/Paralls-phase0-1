# INF-4 Population And Branch Preview Implementation Plan

> **Evidence status:** The documented production-planning and isolated-preview vertical below is implemented and independently verified. Full population simulation remains follow-up work.

**Goal:** Add deterministic, authority-bound population planning and isolated branch preview without a new truth store.

**Architecture:** Build from profile identity and scoped source projections; production keeps its current append path, while branch events stay in an explicitly non-production in-memory buffer.

**Tech Stack:** Python, Pydantic, pytest, existing character registry/event replay/Harness.

---

### Task 1: Specify test-first input and preview contracts

**Files:** Modify `backend/app/population_continuity/models.py`; create `backend/tests/test_infra_population_branch_preview.py`.

- [x] Added validation coverage for reference/calibration, scoped family/organization input, and branch requests.
- [x] Added frozen digestible models with provenance, license, privacy, and revision fields.
- [x] Focused model tests pass.

### Task 2: Extend batch planning without new identity ownership

**Files:** Modify `backend/app/population_continuity/batch.py`; modify focused tests.

- [x] Proved shuffled equivalent candidates yield an identical plan digest and order.
- [x] Pinned profile, projection, activation-lock, and calibration revisions in pure plan/envelopes.
- [x] Verified unknown profile, unauthorized projection, stale revision, and duplicate merge outcomes.

### Task 3: Implement isolated preview replay

**Files:** Create `backend/app/population_continuity/branch_preview.py`; extend tests.

- [x] Proved deterministic repeat preview reports while production event count and heads remain unchanged.
- [x] Implemented an explicit branch buffer/replay adapter that reads fixed production state without production append.
- [x] Independently verified base mismatch, dataset-scope denial, redaction, and replay equivalence.
  Superseded for authoritative license admission by INF-4Z-A:
  `ReferenceDataAuthority` now provides the owner stream, scoped projection and
  frozen revision/digest input. This base preview plan remains metadata-only and
  does not implement replayable branch event evolution or promotion.
- [x] Focused INF-4 tests pass.

### Task 4: Close activation lock integration

**Files:** Modify `backend/app/population_continuity/activation.py`; modify its tests.

- [x] Added preview-during-activation and owner-authorized pending merge coverage.
- [x] Reused INF-2 lock/pending records without adding an activation owner.
- [x] Verified revision-conflict and unauthorized merge paths leave production unchanged.

### Task 5: Harness, reports, and docs sync

**Files:** Create `.harness/profiles/infra-population-branch-preview.json`; create `scripts/verification/verify_infra_population_branch_preview.py`; update August status/spec/plan.

- [x] Executed every named capability through a distinct focused assertion.
- [x] Preserved `.harness/verification/infra-population-branch-preview-report.json` and its limitations.
- [x] Ran full pytest (`2504 passed`; one pre-existing pytest-asyncio configuration deprecation warning) and `git diff --check`.

## Verification

```powershell
python -m pytest backend/tests/test_infra_population_branch_preview.py -q
python scripts/verification/harness.py --profile infra-population-branch-preview
git diff --check
```

The documented base INF-4 population planning and branch-preview vertical is a
verified narrow predecessor. INF-4Z/INF-4Z-A supersede its source/revision/
digest/calibration-admission gaps, but neither implements real branch event
evolution, promotion, or full population simulation.
