# Ownership Bond Expiry Implementation Plan

> **For agentic workers:** Execute this plan natively in the current A worktree. Keep each test change before its implementation.

**Goal:** Emit durable `bond.expired` events from confirmed Population world time when an Ownership Bond reaches its expiry tick.

**Architecture:** Add an Ownership temporal consumer that calls the existing Ownership authority and never writes events directly. Population cadence issues a separate, bounded Ownership temporal grant, and `main.py` invokes the consumer beside the existing temporal consumers. Historical cadence pins without the new grant remain restorable and cannot authorize expiry writes.

**Tech Stack:** Python 3.12.2, pytest, existing Population temporal authorization and Ownership event-sourced runtime.

**Spec:** External Architecture v2 `02-六原语规格.md` §4 and `04-事件schema规格.md` Bond events; A worktree `docs/v2-coordination/BOUNDARIES.md` and existing temporal consumer contracts.

## Global Constraints

- Use confirmed Population cadence time and its durable temporal authorization.
- Expiry is committed through `OwnershipAuthorityService.expire_bond`.
- Do not change event type, schema version, payload meaning, storage core, or Bond attribute behavior.
- Accept legacy cadence records that lack only the new Ownership temporal grant; reject other stale pins as before.
- Keep all verification output on F drive and verify Python 3.12.2 and A-worktree imports.

## Review Focus

- A cadence record already persisted before this grant was introduced must restore without rewriting history.
- An old pin without an Ownership grant must not authorize an expiry write.
- Missing, altered, wrongly scoped, or wrong-boundary Ownership grants must not authorize expiry writes.
- A late cadence boundary must use the actual confirmed processing tick in the event, while `term_expires_at` controls due selection and stable command identity. Never backdate a committed event to an unobserved boundary.
- Repeated delivery of a confirmed boundary must not add duplicate expiry events.

### Task 1: Population-authorized Bond expiry

**Files:**
- Create `backend/app/gameplay/ownership_bond_temporal_consumer.py`.
- Modify `backend/app/world_runtime/population_driver.py` to issue the bounded Ownership grant and accept the exact pre-grant pin shape on restore.
- Modify `backend/app/main.py` to construct and invoke the consumer from `advance_confirmed`.
- Test in `backend/tests/test_ownership_bond_temporal_consumer.py`, `backend/tests/test_population_runtime_driver.py`, and `backend/tests/test_population_durable_cadence_recovery.py`.

**Interfaces:** `OwnershipBondExpiryConsumer(store).advance(driver)` reads active Bonds from the Ownership projection, verifies the confirmed Ownership grant, and submits one `expire_bond` command per due Bond. Command identity and idempotency identity are deterministic from `bond_ref` and `term_expires_at`.

- [x] Add tests for on-time/late due processing, repeated boundary delivery, no early expiry, and missing or invalid authorization with zero writes.
- [x] Add tests that newly issued cadence pins contain the Ownership grant and legacy pins restore while other pin mismatches still reject.
- [x] Run the new tests against parent `6276757f`; all six fail because the consumer is absent.
- [x] Implement the consumer, grant issuance and narrow legacy-pin compatibility, then wire the consumer into `main.py` (`aba7dea9`).
- [x] Run focused Ownership and Population cadence tests, then the registered M1-1 and frozen verification selections.
- [x] Record exact results and remaining coverage in the A handoff, board and verification evidence.

## Rulings

- Ruling: expiry selection uses `term_expires_at`, but a late scheduler callback persists the actual confirmed Population tick as `world_tick`. The grant proves the processing boundary, while backdating would claim an unobserved confirmation; command identity remains stable from the Bond reference and declared expiry tick.
- Ruling: pre-change cadence pins are accepted only when the `ownership` grant alone is absent. This preserves durable legacy recovery without allowing a cadence record missing any earlier grant or carrying changed pins to pass.
