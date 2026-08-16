# INF-4G Isolated Owner Consequence Projection Design

Status: `implemented and independently verified 2026-08-14; isolated branch-local projection only`

## Scope

INF-4G turns the INF-4F accepted fragment-builder evaluation into a real,
non-production branch-local consequence projection. It is restricted to the
two existing owner event semantics already admitted in production:

| Candidate | Owner event semantics copied into branch-local projection |
| --- | --- |
| `supply` | `gameplay.organization.commerce_commitment_accepted` -> planned commitment |
| `inspection` | `gameplay.government.inspection_recorded` -> planned inspection |

The branch buffer records a redacted `branch_owner_consequence_projected`
record produced from the already-validated owner fragment. The branch reducer
rebuilds planned commitments and planned inspections from those local records.
These are counterfactual branch outcomes only: their event type is deliberately
not a `GameplayEvent`, they are never put in the production event store/outbox,
and they have no `SettlementReceipt` or promotion path.

## Invariants

- Only a prior accepted INF-4F `supply`/`inspection` evaluation produces a
  projected record.
- Projection includes only display-safe identity/policy/result fields. Grant,
  reservation and evidence references remain outside public branch projection.
- Owner-builder rejection, stale revision, unknown kind and privacy/base/profile
  failure have zero production writes and no projected domain outcome.
- Full and checkpoint-tail branch replay must produce the same projection hash.
- `promote()` remains `branch_promotion_unsupported`.

This adds no runtime, event store, scheduler, authority, population/NPC/social
truth owner, production writer, branch receipt or cross-domain settlement.

## Evidence

- Focused backend coverage: `backend/tests/test_infra_population_branch_preview.py`
- Independent Harness profile: `infra-isolated-branch-owner-consequence-projection`
- Report: `.harness/verification/infra-isolated-branch-owner-consequence-projection-report.json`

## Remaining Boundary

This supersedes INF-4E only for the narrow ability to rebuild redacted,
branch-local planned commitment/inspection facts from an accepted existing-owner
fragment evaluation. It does not create a branch-domain authority, settle a
production-equivalent fragment, issue a `SettlementReceipt`, permit branch
promotion, or establish population, household, organization or social truth.
