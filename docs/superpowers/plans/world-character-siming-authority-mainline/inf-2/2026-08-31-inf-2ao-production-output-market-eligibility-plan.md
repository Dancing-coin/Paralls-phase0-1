# INF-2AO Production Output Market Eligibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development before implementation. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record one Economy-owned authority-only eligibility marker from committed Inventory production-output custody without creating payment, pricing, transfer, or market-order semantics.

**Architecture:** Add a row-specific typed intent and Economy adapter. The adapter rereads exactly one project-visible `production_output_custody@1` event, validates source stream/revision/provenance, derives a fixed Economy event and idempotency key, and appends through the existing envelope/SettlementPlan/store spine. Inventory and Economy keep separate receipts and projections.

**Tech Stack:** Python, Pydantic strict models, existing Economy/Inventory owners, GameplayEventStore, SettlementPlan, pytest, Harness.

---

### Task 1: Add typed intent and RED tests

**Files:**
- Create: `backend/app/gameplay/inf2ao_market_eligibility.py`
- Create: `backend/tests/test_inf2ao_production_output_market_eligibility.py`

- [x] Define `ProductionOutputMarketEligibilityIntent` with only source event/revision, command, correlation and submission fields (`extra="forbid"`, frozen).
- [x] Write RED tests for success, source privacy/staleness/wrong stream, forged custody provenance, duplicate/changed duplicate, no account mutation, receipt and full/checkpoint-tail replay.
- [x] Run the focused suite after implementation: `6 passed`.

### Task 2: Add immutable Economy catalog/schema boundary

**Files:**
- Modify: `backend/app/gameplay/governed_contract_catalog.py`
- Modify: `backend/app/gameplay/event_schema_registry.py`
- Test: `backend/tests/test_inf2ao_production_output_market_eligibility.py`

- [x] Add one immutable `inf:economy-production-output-market-eligibility@1` contract and descriptor with fixed owner, stream, event, authority-only privacy, receipt and replay reader.
- [x] Register `gameplay.economy.production_output_market_eligible@1` with a fixed schema digest through the existing schema registry.
- [x] Reject unknown catalog/schema or mismatched owner/event/privacy before append.

### Task 3: Implement the Economy adapter

**Files:**
- Modify: `backend/app/gameplay/economy_runtime.py`
- Modify: `backend/app/gameplay/inf2ao_market_eligibility.py`

- [x] Resolve exactly one source event from the existing store and validate `production_output_custody@1`, project visibility, source stream head, positive quantity, item/holder/container and provenance mapping.
- [x] Derive the fixed authority-only Economy event, policy/descriptor refs and idempotency key; never accept caller-selected account, amount, currency, price, owner, stream, event or receipt.
- [x] Append through `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`.
- [x] Add a full/checkpoint-tail projection reader and append-derived receipt helper.
- [x] Keep the marker terminal/no-compensation and account-neutral.

### Task 4: Add independent Harness and synchronize docs

**Files:**
- Create: `scripts/verification/verify_inf2ao_production_output_market_eligibility.py`
- Create: `.harness/profiles/inf2ao-production-output-market-eligibility.json`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-29-inf-ordered-completion-audit.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-29-inf-residual-blocker-register.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/README.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-17-inf-mainline-continuation-checkpoint.md`

- [x] Verify all zero-write, privacy, revision, idempotency, receipt and replay cases independently.
- [x] Register the profile with Harness schema version 1 and `include_in_all=true`.
- [x] Record INF-2AO as an implemented narrow vertical; keep generic payment/transfer/market pricing blocked.
- [x] Run focused tests, Harness, continuation gate, docs check, compileall and diff check.

Completion evidence: focused `11 passed`; INF-2 regression collection `83
passed`; INF/INFRA filename collection `1336 passed`; local Harness profiles
green. The external `siming-heavenly-runtime` preflight remains an
environment-only limitation.

## Post-closure boundary hardening (2026-09-01)

- [x] Remove the legacy `declared_exchange` fallback that inferred
  `currency:local` and fixed amounts when a bound declaration lacked its
  immutable `economic_outcome`.
- [x] Add a zero-write regression for the missing-outcome case and rerun the
  approved exchange suite and repository suite.

Evidence: missing economic terms now reject before account lookup/append;
declared/fixed exchange suites pass `36` focused tests and the repository
passes `4285` tests. This is contract hardening, not a new INF business row.

The same hardening rejects bounded price policies when the accepted intent has
no owner-authorized amount slot. A minimum/maximum range is never silently
resolved to zero, a bound, or a legacy fixed price.

The fixed-service branch now applies the same rule: a bounded service price
without an explicit owner-authorized amount rejects before account lookup or
append and cannot fall through to a legacy settlement amount.

Fixed-service package selection is source-deterministic: the adapter resolves
a unique fulfilled Contract `terms_ref` and ignores proposal-digest substrings
as package selectors. Multiple matching service packages or missing fixed
price terms reject before account lookup/append.

Additional replay hardening (2026-09-01): Inventory
`production_output_custody_view_for` now rejects checkpoint values beyond the
store head and validates certification, stream, subject and mapping pins during
full/checkpoint-tail reconstruction. Custody/INF-2AO regression coverage is
`14 passed`; INF-2AO focused is `11 passed`; INF-2 regression is `83 passed`; INF/INFRA is `1341 passed`; full
repository pytest is `4291 passed`.

Fixed-service settlement events now retain immutable package/content/declaration
and active-set pins when a matching declaration exists; replay resolves and
validates those pins, including exact outcome, currency, and fixed amount.
Legacy events without pins remain historical compatibility records and are not
rewritten.

Generic declared-exchange replay now additionally requires the binding to be
present in the current active-set capability bindings with matching package,
content and declaration pins; an unadmitted or removed binding fails closed.
