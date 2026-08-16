# INF-3 Ecology And Disaster Authority Implementation Plan

> **Evidence status:** The documented frost/crop vertical below is implemented and independently verified. Broader ecology propagation remains follow-up work.

**Goal:** Replace the frost-farm sample boundary with an append-backed ecology disaster vertical slice.

**Architecture:** Ecology produces only authorized environmental/hazard proposals; effects resolve through INF-1 and INF-2 owner fragments into the current store.

**Tech Stack:** Python, Pydantic, existing event/replay, pytest, Harness.

---

### Task 1: Define ecology records test-first

**Files:** Create `backend/app/gameplay/ecology_runtime.py`; create `backend/tests/test_infra_ecology_disaster.py`.

- [x] Added record validation coverage for IDs, revisions, lifecycle, and invalid schemas.
- [x] Implemented frozen ecology records without a direct store dependency.
- [x] Focused record tests pass.

### Task 2: Make frost an authority vertical

**Files:** Modify `backend/app/gameplay/frost_farm_runtime.py`; modify/add ecology tests.

- [x] Proved a due frost command reaches one append batch through semantic lifecycle authority.
- [x] Replaced sample-only settlement with the INF-1 authority and SettlementPlan/event spine.
- [x] Verified resistance, stale revision, unsupported hazard, duplicate, and rejection zero-write behavior.
- [x] Focused INF-3 tests pass.

### Task 3: Add causal scoped projection and replay proof

**Files:** Modify `backend/app/gameplay/entity_causal_projection.py`; add tests.

- [x] Added hazard-parent, public redaction, authority trace, full replay, and checkpoint-tail equivalence coverage.
- [x] Extended only scoped read projections with ecology references and filtered trace data.
- [x] Focused replay/projection tests pass.

### Task 4: Harness and evidence

**Files:** Create `.harness/profiles/infra-ecology-disaster.json`; create `scripts/verification/verify_infra_ecology_disaster.py`; modify August status documents.

- [x] Gave every profile capability a separate assertion.
- [x] Preserved `.harness/verification/infra-ecology-disaster-report.json` and updated documented scope/limitations.
- [x] No Godot mirror changed; therefore no Godot-visible completion claim is made.

## Verification

```powershell
python -m pytest backend/tests/test_infra_ecology_disaster.py -q
python scripts/verification/harness.py --profile infra-ecology-disaster
git diff --check
```

The final repository suite completed with `2504 passed` (one pre-existing
pytest-asyncio configuration deprecation warning). The documented INF-3
frost/crop vertical is complete; it does not close wider ecology or climate work.
