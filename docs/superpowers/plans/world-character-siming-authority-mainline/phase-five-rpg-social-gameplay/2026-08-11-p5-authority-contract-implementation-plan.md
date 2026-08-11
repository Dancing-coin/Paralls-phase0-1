# P5 Authority Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Deliver P5A-P5D as bounded, replay-safe authority extensions over the existing Gameplay settlement path.

**Architecture:** A shared batch-contract update supplies read-set concurrency, event-level visibility, and provenance-aware idempotency. Quest evidence, public social facts, and bounded investigation policies use that contract; existing owners retain rewards and nonlethal status/resource consequences.

**Tech Stack:** Python, Pydantic, pytest, existing GameplayEventStore, SettlementPlan, StateGroup mirror, Harness.

## Global Constraints

- No second store, bus, scheduler, or universal coordinator.
- No CharacterAgent, Godot, or narrative canonical write.
- Character Core owns private memory, affect, beliefs, and goals.
- P5 conflict is discrete and nonlethal; no real-time combat.
- P5 profile order is P5A -> P5B -> P5C -> P5D.

### Task 1: Make the existing batch path P5-safe

**Files:** modify `backend/app/gameplay/models.py`, `shared_contracts.py`, `settlement_plan.py`, `event_store.py`; create `backend/tests/test_gameplay_p5_batch_contract.py`.

- [x] Write RED tests for read/write revision separation, read/write conflicts, event-level visibility, provenance-changing idempotency reuse, and legacy P4 compatibility.
- [x] Add `read_revisions` to commands/fragments, `read_stream_revisions` to batches, explicit fragment event visibility, deterministic fragment digest, and atomic event-store read-head validation.
- [x] Run `python -m pytest -q backend/tests/test_gameplay_p5_batch_contract.py`.

### Task 2: Define P5 typed contracts and registry

**Files:** create `backend/app/gameplay/p5/contracts.py`, `registry.py`; create `backend/tests/test_p5_contracts.py`.

- [x] Write RED tests for fail-closed provider/owner/package/ruleset registration and opaque directed relationship refs.
- [x] Add immutable registry, typed resolution requests/results, canonical event catalog, owner/event/stream allowlists, and deterministic digest inputs.
- [x] Run `python -m pytest -q backend/tests/test_p5_contracts.py`.

### Task 3: Implement P5A quest and evidence

**Files:** create `backend/app/gameplay/p5/quest_evidence.py`; create `backend/tests/test_p5_quest_evidence.py`.

- [x] Write RED tests for provenance, wrong subject, visibility/expiry, duplicate, stale objective, reward rejection, legal transition, and zero-write failure.
- [x] Implement QuestEvidenceAuthority and replay projector using only quest/evidence fragments; reward fragments must originate from a registered owner adapter.
- [x] Run `python -m pytest -q backend/tests/test_p5_quest_evidence.py`.

### Task 4: Implement P5B social facts and knowledge

**Files:** create `backend/app/gameplay/p5/social_knowledge.py`; create `backend/tests/test_p5_social_knowledge.py`.

- [x] Write RED tests for public/private redaction, conflicting observations, confidence decay, revoked visibility, stale revision, derived reputation, and no Character Core mutation.
- [x] Implement SocialFactAuthority, public knowledge projection, visibility-revocation reducer, and authorization-aware view construction.
- [x] Run `python -m pytest -q backend/tests/test_p5_social_knowledge.py`.

### Task 5: Implement P5C bounded investigation and conflict

**Files:** create `backend/app/gameplay/p5/investigation_conflict.py`; create `backend/tests/test_p5_investigation_conflict.py`.

- [x] Write RED tests for perception, affordance/skill, resistance, status revision, alarm, nonlethal status fragment, structured zero-write rejection, idempotency, atomicity, and privacy.
- [x] Implement typed revalidation and discrete resolution; commit only investigation/conflict fragments plus registered status/resource owner fragments.
- [x] Run `python -m pytest -q backend/tests/test_p5_investigation_conflict.py`.

### Task 6: Add P5 projectors, mirrors, and replay

**Files:** replay/projector methods in the P5 authorities and vertical slice; focused replay coverage in the P5A-P5D tests and Harness reports.

- [x] Write RED tests for checkpoint restoration, full/checkpoint/live hash equality, recipient-specific redaction, mirror revocation resync, and unknown schema failure.
- [x] Register versioned quest/social/investigation projection schemas with existing filtered mirror delivery.
- [x] Run the phase-specific replay and mirror tests in the P5A-P5D suites.

### Task 7: Compose P5D bakery-theft vertical slice

**Files:** create `backend/app/gameplay/p5/bakery_theft_slice.py`; create `backend/tests/test_p5_bakery_theft_slice.py`.

- [x] Write RED tests for success, hidden-clue rejection, alarm/nonlethal adverse outcome, public-private mirror split, duplicate recovery, late-append rollback, corrupted checkpoint rejection, and DISABLED/NARRATIVE Survival.
- [x] Compose only committed P5A-C facts and registered owner fragments; do not create fixture truth or a new writer.
- [x] Run `python -m pytest -q backend/tests/test_p5_bakery_theft_slice.py`.

### Task 8: Add focused Harness closure

**Files:** create four `.harness/profiles/phase5*.json` and `scripts/verification/verify_phase5*.py`; update `docs/harness.md` and P5 docs.

- [x] Add P5A, P5B, P5C, and P5D profiles in order, retaining reports and traces under `.harness/verification/`.
- [x] Each verifier runs its focused tests, required predecessors, replay, privacy, receipt, and zero-write assertions.
- [x] Run P5A -> P5B -> P5C -> P5D profiles and `python -m pytest -v` (`2449 passed`).
- [x] Complete the P5 closure sequence with P5A -> P5B -> P5C -> P5D focused profiles and the required P4D -> P3 -> P2 -> P1D predecessors. The repository-wide `all` profile excludes P5 focused profiles and remains a separate repository-release exercise, not a P5 phase gate.
