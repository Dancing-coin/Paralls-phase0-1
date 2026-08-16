# INF-4Y Civilization Capability Read Interface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve INF-4Y-A's minimum civilization capability owner and add
the user-approved supply and inspection capability-gated consumer edges
without P7 implementation.

**Architecture:** `CivilizationCapabilityAuthority` owns only its canonical
stream and lifecycle events through the existing event store. Each admitted
consumer freezes an authority-scoped capability view and submits only an
existing Organization supply or Government inspection fragment. No semantic or
generic population consumer is introduced.

**Tech Stack:** Existing event store/replay/scoped-projection contracts, Python, pytest, Harness.

---

### Task 1: Establish the authorized owner admission

**Files:** Update INF-4Y design/plan; add
`backend/tests/test_infra_civilization_capability_read.py` first.

- [ ] Record the approved principal, stream, event family, jurisdiction,
  revision, scope and non-goal boundaries in the design.
- [ ] Write focused failing tests for canonical append/outbox, duplicate,
  altered duplicate, revision conflict, jurisdiction/effective tick, scopes,
  event-derived revoke/correction, and full/checkpoint-tail replay.

### Task 2: Publish the minimum owner view

**Files:** Modify only the independently approved owner module/projection and its tests; create `backend/tests/test_infra_civilization_capability_read.py`.

- [ ] Add `backend/app/gameplay/civilization_capability_runtime.py` with
  versioned activation/revocation/correction events and a jurisdiction-scoped
  `CivilizationCapabilityView`; every formal write uses an owner fragment and
  the existing store.
- [ ] Enforce effective tick, source revision, jurisdiction, and
  authority/actor/public/creator scope behavior before any consumer exists.
- [ ] Keep rollback event-based; do not add advancement, scheduler, generic
  policy writer, or consumer writes.

### Task 3: Implement the approved consumer row and preserve all other fences

**Files:** No `semantic_registry.py` or `population_continuity` changes in
INF-4Y-A.

- [x] Retain unsupported generic consumer input behavior; this owner admission
  does not make any generic capability input supported. A real owner-scoped
  `CivilizationCapabilityView` passed to `plan_from_world_inputs()` returns
  `civilization_capability_consumer_not_admitted` before planning/source
  admission or any write attempt; `infra-population-world-mode` asserts it
  independently.
- [x] Write focused failing tests for the one approved `capability -> supply ->
  OrganizationAuthority` row: success, inactive/stale/forged/mismatched input
  zero-write, duplicate, revision conflict, authority privacy, owner receipt,
  event redaction, and full/checkpoint-tail replay.
- [x] Freeze only authority-scoped active `CivilizationCapabilityView` inputs;
  pin digest/capability revision/stream revision and submit the existing
  organization commerce fragment. Keep `work`, semantic and all unlisted
  consumer paths zero-write rejected.
- [x] Add the separately approved `capability -> inspection -> GovernmentAuthority`
  row only after focused tests fail. Reuse
  `GovernmentAuthority.build_commercial_inspection_fragment`, pin the
  authority-scoped capability input plus the Government target-stream revision,
  require exact capability/jurisdiction and target-jurisdiction matching, and
  persist only opaque eligibility/inspection-plan digests. Do not broaden
  `plan_from_world_inputs()` or `merge_world_plan()`.
- [x] Prove independently: Government receipt/event redaction, stale/forged/
  revoked/non-effective/non-authority/jurisdiction-mismatch zero-write,
  Government revision conflict, duplicate/changed-duplicate, replay, and the
  continuing rejection of `work` and unlisted capability consumers.

### Task 4: Evidence and stop condition

**Files:** Create the independent `infra-civilization-capability-read` and
`infra-civilization-capability-inspection-consumer` Harness profiles, verifiers
and reports; update docs.

- [x] Add independent assertions for all scopes, jurisdiction, effective tick,
  revocation, rejection, duplicate, privacy and full/checkpoint-tail replay.
- [x] Run focused tests, profile, predecessor continuation profile, full pytest
  and `git diff --check`; record the report under `.harness/verification/`.

## INF-4Y-A completion evidence

- [x] Focused lifecycle/read suite: `backend/tests/test_infra_civilization_capability_read.py`.
- [x] Independent Harness: `infra-civilization-capability-read`, report at
  `.harness/verification/infra-civilization-capability-read-report.json`.
- [x] Predecessor rechecks: `infra-continuation-gate` and
  `infra-hazard-propagation`.
- [x] Full suite and whitespace check: `python -m pytest -q` and
  `git diff --check`.

INF-4Y-A owner admission plus the separately authorized supply and inspection
rows are complete for their documented scopes. The inspection profile separately
proves owner receipt, outbox/privacy, effective/revoked/forged/stale source
zero-writes, policy/target revision, idempotency and replay. All other consumer
bindings remain blocked.
