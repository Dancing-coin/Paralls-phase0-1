# General Economy Platform C Implementation Plan

Status: `implemented-and-verified; General Economy Platform C`

## Goal

Implement the approved complete regulated Economy platform without replacing
existing owners or frozen narrow rows. Use `GameplayPatchManifest v3` paired
with `platform_schema_version="2.0"`; retain read-only v1/v2 compatibility.

## Global constraints

- Economy owns currency, FX, accounts, ledger, holds, obligations, quotes,
  clearing and regional macro projections only.
- Inventory, Organization, Government, Contract/Debt, Ownership and Population
  retain their facts and writers.
- Population aggregates are public market signals only; they cannot settle.
- Cross-owner writes use precompiled descriptor-bound recipes and owner
  fragments through the existing SettlementPlan/append_batch spine.
- No arbitrary code, caller-selected authority coordinates, generic router,
  coordinator, writer, registry, settlement authority or second runtime.
- v1/v2 manifests and readers remain unchanged and are never re-digested.

## Tasks

1. Add v3/2.0 manifest pairing, strict Economy typed-content schemas,
   canonicalization and digest validation; add RED tests and schema Harness.
2. Add immutable descriptors/catalog entries and owner-local runtime for
   currency issuance, FX fixing, account/ledger, holds and obligations.
3. Add quote/order/clearing and commerce-delivery recipes with deterministic
   matching, reservations, privacy, idempotency, receipts and replay.
4. Add organization labor/period, tax/regulation, credit/collateral,
   insurance, security/holding and insolvency families using existing owners.
5. Add regional macro close and Population aggregate signal adapter; prove
   CPI/供需/interest/money-supply/FX replay determinism and no aggregate
   settlement authority.
6. Update specs, plans, README, completion audit, remaining-scope, blocker
   taxonomy and continuation checkpoint; run focused suites, Harness profiles,
   full pytest, compileall and diff checks.

## Verification gates

Each task follows RED → GREEN → refactor, has a focused Harness profile,
full/checkpoint-tail replay evidence, privacy and zero-write coverage. A task
must pass before the next task starts.

## Completion Record

All fourteen owner-bound Economy families are represented by strict immutable
content, exact descriptor metadata and owner-local adapter/projection evidence.
The `general-economy-platform` Harness is the aggregate completion gate.
Existing phase-four cross-owner commerce recipes remain the canonical delivery,
inventory, organization and Government owner boundaries; the new platform does
not introduce a replacement coordinator.
