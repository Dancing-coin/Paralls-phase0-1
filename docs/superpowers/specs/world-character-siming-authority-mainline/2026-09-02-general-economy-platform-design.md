# General Economy Platform C Design

Status: `implemented-and-verified; owner-bound Economy platform C foundation`

This design establishes a complete regulated Economy target while preserving
existing owner boundaries. Economy owns currency, FX, accounts, ledger, holds,
obligations, quotes, clearing and regional macro projections. Inventory,
Organization, Government, Contract/Debt, Ownership and Population retain their
canonical facts and writers.

Population aggregates are public, revision-pinned market signals only. They
cannot own accounts, inventory, orders, payments or settlement outcomes.

The platform uses strict typed content and precompiled descriptor-bound recipes:

```text
typed intent -> source/policy/revision/privacy checks -> exact descriptor
-> owner fragments -> SettlementPlan -> append_batch -> projections/replay
```

Manifest compatibility is additive: `(1, absent)` and `(2, "1.0")` remain
read-only compatible; `(3, "2.0")` is the new Economy content pairing. Other
pairs fail closed. Digests are adapter-derived and caller claims are compared,
never silently corrected.

The target family portfolio is currency issuance, FX fixing, account/ledger,
hold/obligation, quote/order, deterministic clearing, commerce delivery,
organization labor/period, tax/regulation, credit/collateral, insurance,
security/holding, insolvency resolution and regional macro close. Each family
has immutable typed content, exact-one descriptor binding, owner-derived
idempotency, append-derived receipt, privacy filtering and full/checkpoint-tail
replay evidence.

No generic writer/router/coordinator/settlement authority, arbitrary event
vector, implicit scheduler, or second runtime is introduced.

## Verification

The `general-economy-platform` Harness proves strict schema pairing, content
validation, descriptor uniqueness, owner-local core/commerce/market/financial/
macro writes, zero-write rejection and full/checkpoint-tail projection replay.
Existing phase-four quote-clearing, multi-organization commerce and Economy
regressions remain green. This platform result is independent of August INF
A-D, which remains `not complete`.
