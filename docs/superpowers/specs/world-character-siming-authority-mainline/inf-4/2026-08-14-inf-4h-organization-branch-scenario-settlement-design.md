# INF-4H Organization Branch Scenario Settlement Design

Status: `implemented and verified for one Organization-owned supply scenario row; broader INF-4 remains incomplete`

## Scope

INF-4H turns one already accepted isolated `supply` branch candidate into an
event-sourced, non-production Organization scenario record. It does not add a
branch authority, a second store, a second runtime, a scheduler, a population
owner, a social truth owner, a generic branch settlement surface, or promotion.

| Concern | Contract |
| --- | --- |
| Proposal producer | existing `BranchPreviewAuthority`, after its closed supply evaluation only |
| Sole writer | existing `OrganizationAuthority` / `actor_gameplay.organization_domain` |
| Store | the existing `GameplayEventStore` only |
| Scenario stream | `gameplay:organization_branch:{branch_ref}:{organization_ref}` |
| Event family | `gameplay.organization.branch_commerce_commitment_recorded` only |
| Input row | one already evaluated `supply` candidate with a pinned branch base digest, source candidate digest, policy revision and target scenario-stream revision |
| Append path | Organization authority -> `GameplayCommandEnvelope` / `SettlementPlan` -> `GameplayEventStore.append_batch()` -> scoped outbox -> scenario projection/replay |
| Privacy | `creator_debug` only; public/authority/private scopes reject before append |
| Receipt | the ordinary single-append `AppendBatchResult`; this is not a production `SettlementReceipt` nor a cross-stream receipt |

The Organization authority validates the exact closed supply payload and writes
only the scenario stream. Production commerce authorization and production
organization streams remain read-only inputs to this package. The normal
production commerce projection must not read scenario streams, and the
production replay helper must exclude them.

## Admission and rejection

Only the explicit branch scenario stream pattern, `creator_debug` scope, a
non-empty branch/base/candidate digest, a valid Organization supply payload,
and the exact expected scenario stream head are admitted. Forged or missing
branch data, stale scenario revision, changed duplicate idempotency payload,
wrong stream/prefix, non-supply candidate, and any non-`creator_debug` scope
must return zero writes.

`BranchPreviewAuthority` may create a proposal and read the Organization's
scenario projection, but it must not call `GameplayEventStore.append_batch()`.
`promote()` remains `branch_promotion_unsupported` and must not use scenario
events as production inputs.

## Replay and completion

The Organization scenario projection is rebuilt solely from the scenario stream
and has full/checkpoint-tail equivalence. The existing production replay remains
unchanged when scenario events are present. Focused tests and a dedicated
Harness profile must independently assert success, duplicate idempotency,
revision conflict zero-write, privacy zero-write, wrong-stream/input zero-write,
scenario replay, production replay isolation, and unsupported promotion.

`infra-organization-branch-scenario-settlement` independently proves the
Organization-owned scenario append, duplicate replay, privacy/unknown-candidate/
revision zero-write, scoped outbox, checkpoint-tail scenario replay, production
replay isolation and unsupported promotion. Evidence is
`.harness/verification/infra-organization-branch-scenario-settlement-report.json`.

This package deliberately covers one Organization `supply` scenario row only.
Government inspection, generic work, generic branch lifecycle, aggregate group
truth, cross-domain scenario receipts and promotion remain blocked.
