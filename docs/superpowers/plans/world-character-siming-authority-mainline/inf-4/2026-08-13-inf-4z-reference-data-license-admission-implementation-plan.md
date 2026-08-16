# INF-4Z Reference-Data License Admission Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to execute this plan test-first.

**Goal:** Admit authority-verified reference datasets for branch calibration without creating a second store or turning caller metadata into truth.

**Architecture:** Add one `ReferenceDataAuthority` on the existing gameplay event store. Freeze its authority-scoped projection before `BranchPreviewAuthority.preview_authorized()` consumes it; the existing preview buffer remains non-production.

**Tech Stack:** Python, Pydantic, existing owner fragments, `GameplayEventStore`, replay, pytest, Harness.

---

### Task 1: Lock the owner contract with failing tests

**Files:** Create `backend/tests/test_infra_reference_data_license_admission.py`; create `backend/app/gameplay/reference_data_runtime.py`.

- [x] Wrote focused RED tests, then registered one permitted dataset through an owner envelope, froze an authority view, and proved an authorized branch accepts it without production events.
- [x] Added separate canonical append/outbox, correction projection/outbox, stale revision, forged frozen digest, revoked preview, privacy denial, duplicate/changed duplicate, and checkpoint-tail replay tests. Every rejected case asserts unchanged event/outbox counts.
- [x] Confirmed RED before implementation, then GREEN: `10 passed`.

### Task 2: Implement the one owner and authoritative branch read

**Files:** Create `backend/app/gameplay/reference_data_runtime.py`; modify `backend/app/population_continuity/branch_preview.py`.

- [x] Implemented `ReferenceDataAuthority` with the exact principal, stream and three events defined in the design. It builds an owner fragment from `GameplayCommandEnvelope`, appends once through the existing store, and publishes only a redacted scoped outbox projection.
- [x] Rebuilds `ReferenceDatasetView` exclusively from this stream and exposes `view_for(..., reader_scope="authority")` with revision, source event and digest pins.
- [x] Added `FrozenReferenceDatasetInput.freeze()` and `validate_against()` plus `preview_authorized()`; validation occurs before existing isolated branch logic and never appends production truth.
- [x] Focused GREEN verification passed: `10 passed`.

### Task 3: Independent evidence and documentation

**Files:** Create `.harness/profiles/infra-reference-data-license-admission.json`; create `scripts/verification/verify_infra_reference_data_license_admission.py`; modify `docs/harness.md`, INF-4Z/dependency design and plan, and August INF-14 analysis.

- [x] The verifier executes every named capability as a separate pytest `-k` invocation; no result substitutes for another capability.
- [x] Recorded the new authoritative calibration admission as the only reference-data scope; external ingestion, branch promotion, generic work and P6/P7 remain excluded.
- [x] Ran the package-focused cross-profile suite (`39 passed`),
  `infra-reference-data-license-admission`, `infra-population-branch-preview`,
  `infra-population-world-mode-complete`, `infra-continuation-gate`, full pytest
  (`2728 passed`), and `git diff --check` after documentation synchronization.
