# M6-5 Gate Impact Layered Execution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the Facility-owned door-leaf, latch-durability, and integrity resolution stages for `impact_gate`, then retain separate Presence assessment and restart recovery.

**Architecture:** A versioned signed v2 impact receipt pins all Facility layer streams. Facility resolves server-owned demo or production content and commits ordered Pool adjustments plus the latch Machine state. Stable idempotency keys let startup recovery continue after any committed layer. Existing v1 receipt replay keeps its integrity-only semantics.

**Tech Stack:** Python 3.12.2, Pydantic, GameplayEventStore, Pool runtime, rule packs, FastAPI, pytest, frozen `compare_selection.py`.

**Spec:** `docs/superpowers/specs/2026-11-24-m6-5-impact-gate-layered-execution-design.md`.

## Global Constraints

- Do not merge B or modify `integration`.
- Do not modify `event_store.py`, `models.py`, `economy_runtime.py`, or `inventory_runtime.py`.
- A changes to shared `main.py` are listed in `docs/v2-coordination/comms/2026-11-24-thread-a.md` before implementation.
- Python must be 3.12.2. Before every pytest run set `PYTHONPATH` to this A worktree's `backend` and verify `app.__file__` resolves here.
- Test temporary files and verification output stay under a unique F: directory.
- Production config remains empty by default. Demo content is labeled and loaded explicitly.
- Preserve v1 signed input events and their existing integrity-only recovery semantics.

## Review Focus

- V1 persisted receipt canonical bytes remain verifiable and v1 replay never damages newly introduced layers.
- V2 signatures cover the full pinned revision vector and reject unknown, missing or stale layer heads before writes.
- A layer boundary crash resumes the same signed impact without duplicate or lost damage.
- Concurrent impacts cannot apply residual damage against a stale layer revision.
- A latch Machine transition is sourced from committed Facility-owned latch durability and cannot write Presence.
- Missing profile or changed content identity leaves all domain streams unchanged.
- Presence remains unknown and zero-write until an independent signed assessment cites current source revisions.
- Existing report source, casualty/Morale path, old integrity events and checkpoint rebuild remain compatible.

---

### Task 1: Version the signed multi-layer impact input

**Files:**
- Modify `backend/app/gameplay/siege_physical_input_runtime.py`
- Modify `backend/app/gameplay/siege_physical_input_event_schema.py`
- Modify its replay participant and focused tests

**Interfaces:**
- Preserve `GateImpactReceipt` and its current v1 EventSchema.
- Add a v2 receipt with a required exact revision vector for door leaf, latch durability, and integrity streams.
- Add a v2 evidence event type and authority reader. V1 readers continue to parse old payloads unchanged.

- [x] Add tests for v2 canonical signature, required revision vector, stable replay, and v1 compatibility.
- [ ] Run the focused input tests and verify new tests fail for missing v2 implementation.
- [x] Implement v2 receipt/event/readers and replay registration.
- [x] Run focused tests, including replay-participant checkpoint tests.

### Task 2: Add the ordered Facility damage layers

**Files:**
- Modify `backend/app/gameplay/facility_integrity_runtime.py`
- Modify `backend/app/gameplay/m6_5_siege_runtime.py`
- Add Facility layer declarations to `packs/county_siege_facility/`
- Extend `backend/tests/test_facility_integrity_runtime.py` and `backend/tests/test_m6_5_siege_runtime.py`

**Interfaces:**
- Add Facility-owned door-leaf and latch-durability Pool streams alongside the existing integrity Pool.
- Resolve positive damage magnitude from server-owned profile content. Apply it to the first non-depleted layer and carry residual damage in the declared order.
- Reconcile the `gate_latch@1` Machine state from committed latch durability thresholds. The Machine state never writes Place.
- Give each layer commit a deterministic idempotency key based on the immutable v2 receipt event and layer.

- [x] Add tests for per-layer damage, residual damage, zero durability, latch state transitions, breach hysteresis, and exact retry.
- [ ] Run tests to verify the new behavior fails before implementation.
- [x] Implement Facility layer pools and latch-state reconciliation. Existing Facility integrity streams are validated and reused during layered profile startup.
- [ ] Add an explicit `gate-03` demo profile with 0–100 layers, initial values 100, ram magnitude 20, and integrity threshold 40/reset 45. Keep production startup unconfigured unless separately configured.
- [x] Run Facility, Pool, and pack-loader tests in the M6-5 focused command.

### Task 3: Recover the durable `impact_gate` obligation

**Files:**
- Modify `backend/app/gameplay/m6_5_siege_runtime.py`
- Modify `backend/app/config.py` and `backend/app/main.py` if profile/Gateway assembly changes
- Append the shared `main.py` notice before editing it
- Extend `backend/tests/test_m6_5_siege_runtime.py` and `backend/tests/test_runtime_asgi.py`

**Interfaces:**
- Recovery scans committed v2 impact inputs and reconciles uncommitted Facility layers in order using each Owner receipt.
- Layer profile values and initializations are code/content configuration, not client values.
- Existing v1 endpoint payloads continue to use the current integrity-only path. The v2 request has an explicit discriminator and returns the complete ordered receipt set.
- L5 dispatches the existing breach reaction only when a breach event commits. Every signed v2 impact can independently receive a signed Presence assessment after the Facility transaction, whether or not that impact breaches integrity.

- [x] Use one atomic multi-stream Facility commit for all changed layers. Durable restart tests cover recovery after signed input and exact replay after the commit, so there is no partial per-layer commit boundary to interrupt.
- [ ] Add HTTP tests for configured v2 profile, missing profile, stale revisions, replay, and v1 route compatibility.
- [x] Run tests and verify each new failure corresponds to missing layered recovery or Gateway behavior.
- [x] Implement profile loading, v2 route assembly, ordered Facility recovery and an on-demand obligation projection.
- [x] Run the targeted Gateway, L5, Facility, Presence and replay tests.

### Task 4: Exact verification and evidence

**Files:**
- Add `docs/verification/m6-5-impact-gate-layered-execution-20261124.md`
- Add `docs/verification/selection/m6-5-impact-gate-layered-execution.json`
- Update `docs/v2-coordination/board.md`, `handoff.md`, `daily/2026-11-24.md`, and the M6-5 status

**Interfaces:**
- [x] Run the focused tests and all five frozen selections on the final code SHA. Also run the registered Information and M6-5 selections. All listed selections returned zero problems and improvements.
- [x] Run the full backend suite on the exact code SHA and compare failed node IDs against the exact parent. Nineteen failures reproduced as the same nodes on parent `9b46742e`; repository-root pytest collection also reported a missing `jsonschema` dependency for scripts/verification tests.
- Verify durable database restart and report UE transport as unverified unless a live trusted host actually sends receipts.

- [x] Run focused and frozen selections in a detached worktree with F-drive output.
- [x] Run parent comparison for full-suite failures that remain.
- [x] Record Python version, import path, SQLite version, raw output paths, status counts, and uncovered runtime work.
- [x] Commit the implementation and exact-code evidence updates and push only the A branch.

## Completion checks

The follow-up uses an independent UE assessment pinned to the three current Facility revisions and the current Place revision. It references the signed impact and its gate incarnation after a Facility commit. This permits evaluation even when a hit produces no breach. Test both breach and non-breach through the existing HTTP route, then cover an unchanged decision, stale inputs, exact retry, and restart from the committed assessment. Preserve prior breach receipts and write a private Presence acknowledgment when its decision leaves Place unchanged. The Place receipt read vector includes the signed impact event stream as well as Facility, Place and Presence input streams. Run the registered selections on the implementation SHA and update the evidence and board.

- A single v2 impact resolves door-leaf Pool, latch durability Pool and integrity Pool in order, including residual damage.
- The latch Machine state follows its durability evidence. Presence remains independently owned.
- Invalid, stale, unknown-profile and changed-receipt inputs do not partially mutate the domain state.
- Exact retries and restart recovery do not double apply any layer.
- V1 archives remain readable with their previous event and receipt semantics.
- M6-5 claims are limited to what exact-code tests and live-runtime evidence establish.
