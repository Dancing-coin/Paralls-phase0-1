# M6-5 Information Report Source Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Publish an authenticated, recipient-scoped siege report through the Information Owner, then verify its production EventSchema, Gateway, SocialDelivery, and L5 knowledge update.

**Architecture:** A signed Information receipt creates a report source event in the existing GameplayEventStore. The same publication call records SocialDelivery at the server's authoritative tick, and the existing L5 callback emits the recipient-private knowledge event. Event, FactType, and command declarations are registered in the Stormnight factory and Information pack.

**Tech Stack:** Python 3.12.2, Pydantic, FastAPI, GameplayEventStore, pytest, frozen `compare_selection.py`.

**Spec:** `docs/superpowers/specs/2026-11-24-m6-5-information-report-source-design.md` (approved 2026-11-24)

## Global Constraints

- Do not merge B or modify `integration`.
- Do not modify `event_store.py`, `models.py`, `economy_runtime.py`, or `inventory_runtime.py`.
- Changes to shared `backend/app/main.py` require a prior A coordination notice.
- Before every pytest invocation, set `PYTHONPATH` to this A worktree's `backend` and verify `app.__file__` resolves here.
- Python must be 3.12.2. Keep test temporary directories and verification output on F:.
- Use explicit git paths. Push only the A branch.

## Files and ownership

- Modify `backend/app/gameplay/information_runtime.py` for the signed report receipt and Information-owned report/delivery write.
- Modify `backend/app/gameplay/information_event_schema.py` and `backend/app/gameplay/event_schema_registry.py` for the registered source EventSchema.
- Add `packs/county_siege_information/fact_types/report.yaml` and `machine_defs/report.yaml`; update that pack's manifest and command catalog.
- Modify `backend/app/gameplay/m6_5_siege_runtime.py` for report publication assembly and exact committed-Owner L5 recognition.
- Modify `backend/app/config.py` and `backend/app/main.py` for dedicated signer configuration and the approved HTTP route.
- Extend `backend/tests/test_information_production_wiring.py`, `backend/tests/test_siege_information_runtime.py`, and the applicable main Gateway tests.
- Record exact evidence in `docs/verification/m6-5-information-report-source-20261124.md` and update the M6-5 board, handoff, and daily entry.

## Review Focus

- Unknown authority or invalid signature must create no report, delivery, or knowledge event. Test the production Owner and HTTP route.
- Missing source event, mismatched source stream/revision, or stale source head must create no report. Test both missing and stale cases.
- Reusing a receipt ID with changed content must reject with no additional events, while exact retry after the delivery window closes returns the original receipts. Test both paths.
- A committed publication must result in one actor-scoped report event, one delivery, and one actor-scoped knowledge event through the production L5 callback. Test the production runtime and HTTP route.
- Report FactType and source EventSchema must load in the production factory/Information pack, and source recognition must require the Information Owner transaction. Test registration and reject an unowned lookalike event.

---

### Task 1: Information report Owner, source schema, and pack declaration

**Files:**
- Modify `backend/app/gameplay/information_runtime.py`
- Modify `backend/app/gameplay/information_event_schema.py`
- Modify `backend/app/gameplay/event_schema_registry.py`
- Add `packs/county_siege_information/fact_types/report.yaml`
- Add `packs/county_siege_information/machine_defs/report.yaml`
- Modify `packs/county_siege_information/pack.yaml`
- Modify `packs/county_siege_information/command_catalog/commands.yaml`
- Test `backend/tests/test_siege_information_runtime.py`
- Test `backend/tests/test_information_production_wiring.py`

**Interfaces:**
- Produce `SiegeReportPublicationReceipt`, `InformationReportPublicationResult`, `InformationAuthority.publish_siege_report(receipt, world_now)`, and a verifier helper that signs canonical receipt bytes in tests.
- Use event `gameplay.information.siege_report_published@1`, FactType `fact:information:siege:report`, and principal `authority:information:report-publisher`.
- The report stream is recipient/report scoped. The report event contains the FactType, report identity, recipient, summary, source event/stream/revision, and signed effective window. Its visibility is `actor:<recipient>`.
- Source append uses the source stream/revision as an atomic read revision. Delivery uses the existing `SocialDeliveryAuthority` with the current world tick.
- Exact retry verifies the original payload and reuses the original report and delivery receipts, including after the effective window closes. Changed receipt content rejects.

- [x] **Step 1: Write failing Owner and registration tests.** Cover valid publication, invalid signature, unknown authority, missing/stale source, exact retry, changed-content retry, post-window retry, schema registration, and Information pack FactType/command loading.
- [x] **Step 2: Run the focused new tests and verify expected failures.** Use Python 3.12.2, A `PYTHONPATH`, and an F: `TEMP` directory.
- [x] **Step 3: Implement the receipt, Information Owner publication, EventSchema, and pack declarations.** Keep existing knowledge update behavior unchanged.
- [x] **Step 4: Re-run focused tests and the related Information runtime tests.** Confirm invalid submissions leave event counts unchanged and successful events retain actor visibility.
- [x] **Step 5: Commit Task 1 with explicit file paths.**

### Task 2: Production Gateway, SocialDelivery dispatch, and L5 source recognition

**Files:**
- Modify `backend/app/config.py`
- Modify `backend/app/gameplay/m6_5_siege_runtime.py`
- Modify `backend/app/main.py`
- Modify `backend/app/gameplay/event_schema_registry.py` if the production factory wiring needs an additional assertion
- Test `backend/tests/test_information_production_wiring.py`
- Test the relevant M6-5 Gateway tests
- Append prior shared-file notice to `docs/v2-coordination/comms/2026-11-24-thread-a.md`

**Interfaces:**
- Add `Settings.siege_information_report_authority_secrets`, loaded only from `SIEGE_INFORMATION_REPORT_AUTHORITY_SECRETS_JSON` and hidden from repr/errors.
- `build_m6_5_siege_runtime` receives that map and creates the report publisher with the same authoritative world-tick provider used by Information L5.
- Add `POST /api/v2/siege/information/report-publication-input`, accepting `SiegeReportPublicationReceipt` and returning report/delivery results.
- After committing delivery, dispatch only the recipient-delivery outbox topic so the existing production L5 callback writes knowledge. Remove the obsolete free-form report source event-type allowlist and its tests.
- `_fact_type_for` recognizes the report source only when the event type, schema version, FactType, and committed transaction principal match the Information report Owner.

- [x] **Step 1: Record the shared `main.py` route change in A's communication log.**
- [x] **Step 2: Write failing production wiring and HTTP tests.** Cover configured/unconfigured authority, exact source recognition, unrelated-owner lookalike rejection, recipient privacy, delivery/L5 knowledge output, and same-receipt HTTP retry.
- [x] **Step 3: Run those tests and verify expected failures.**
- [x] **Step 4: Wire the dedicated signer setting, runtime publisher, route, topic-scoped dispatch, and exact Information Owner matcher.**
- [x] **Step 5: Run all affected tests plus Gateway/L5/Information regression files.**
- [x] **Step 6: Commit Task 2 with explicit file paths.**

### Task 3: Exact-commit verification and handoff evidence

**Files:**
- Add `docs/verification/m6-5-information-report-source-20261124.md`
- Add `docs/verification/selection/m6-5-information-report-source.json`
- Update `docs/v2-coordination/board.md`
- Append the result to `docs/v2-coordination/handoff.md` and `docs/v2-coordination/daily/2026-11-24.md`

**Interfaces:**
- Use `docs/verification/absorb-main-3bf3418e/compare_selection.py` and the frozen 24-node ownership and 990-node shared-replay groups, plus the registered Information report selection.
- Run verification on a detached worktree at the exact implementation commit. Keep raw output under a unique new `F:\paralls-verification\thread-a\` directory.

- [x] **Step 1: Add the new permanent selection and verify collection on the exact implementation SHA.**
- [x] **Step 2: Run focused Information, Gateway, EventSchema, pack, and L5 tests on that exact SHA.**
- [x] **Step 3: Run ownership and shared-replay frozen selections and the new Information selection.** Reproduce any environmental shared-replay failure on the exact parent SHA before attributing it.
- [x] **Step 4: Scan staged and branch-added lines under P-1, record public-status evidence without printing matched values, and write exact outputs and unrun coverage.**
- [x] **Step 5: Update evidence and coordination records, commit documentation, and push only the A branch.**

## Completion checks

- The report FactType and EventSchema are registered and load in the production composition.
- Valid signed report publication creates the recipient-scoped source, committed SocialDelivery, and one recipient-private knowledge event through Gateway/L5.
- Invalid and stale inputs write nothing. Exact retries replay original receipts and changed retries reject.
- The exact commit's focused and frozen verification results, environmental failures, and unrun scope are recorded without calling M6-5 complete.
