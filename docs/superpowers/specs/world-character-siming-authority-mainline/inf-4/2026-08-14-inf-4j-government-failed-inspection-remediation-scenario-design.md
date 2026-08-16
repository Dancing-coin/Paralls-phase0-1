# INF-4J Government Failed-Inspection Remediation Scenario Design

Status: `implemented and verified for one evidence-backed fixed non-production Government remediation row; broader INF-4 remains incomplete`

## Purpose

INF-4I intentionally rejected failed inspection candidates because no scenario
outcome existed for them. INF-4J admits one fixed, event-sourced remediation
record on the already existing Government branch scenario stream. It advances
the branch projection from a passed-only record while keeping all production
world truth, scheduling and promotion boundaries unchanged.

## Closed Contract

| Concern | Contract |
| --- | --- |
| Proposal producer | existing `BranchPreviewAuthority`, only an accepted `inspection` candidate with `passed=False` |
| Sole writer | existing `GovernmentAuthority` / `actor_gameplay.government_domain` |
| Store and stream | existing `GameplayEventStore` / `gameplay:government_branch:{branch_ref}:{organization_ref}` |
| Source pin | existing `gameplay:government:{organization_ref}` revision from the evaluated candidate |
| Event family | `gameplay.government.branch_inspection_remediation_recorded` only |
| Scenario state | fixed `follow_up_required`; `remediation_ref` is authority-derived from branch and inspection identity |
| Privacy | `creator_debug` only |
| Formal writes | Government authority -> `GameplayCommandEnvelope` -> `SettlementPlan` -> `GameplayEventStore.append_batch()` -> scoped outbox -> Government scenario projection |

The caller cannot select a production stream, remediation event type, owner,
privacy, remediation action, receipt, schedule, obligation policy or promotion.
The record is a non-production scenario fact, not a `ScheduledObligation`,
remediation scheduler, target-domain mutation or production Government write.

## Admission, Idempotency and Replay

The row requires the existing branch prefix, durable accepted-preview evidence, exact
`inspection` candidate, `passed=False`, matching base/candidate digests,
matching production Government revision, current scenario revision and
`creator_debug`. The derived remediation identity is
`branch-remediation:{branch_ref}:{inspection_ref}`. Exact retries replay the
same append result; changed duplicate, source/scenario revision conflict,
unknown candidate, passed inspection, privacy violation and forged candidate
mapping are zero-write.

INF-4L now supplies the event-derived evidence stream and Government-side
revalidation. The primitive and sealed-proposal experiments are not the
admission contract; missing or mismatched durable evidence is zero-write.

The existing Government scenario projection gains a distinct immutable
`remediation_refs` view alongside `inspection_refs`, with full and
checkpoint-tail equivalence. Production replay continues to exclude all
Government branch scenario streams. Branch promotion remains explicitly
unsupported.

## Completion Evidence

`infra-government-failed-inspection-remediation-scenario` must independently
assert owner append, fixed derived remediation identity/action, exact and
changed duplicate behavior, passed/unknown/privacy/source/scenario revision
zero-write, scoped outbox, full/checkpoint-tail replay, production isolation
and promotion zero-write. It must rerun INF-4I predecessor evidence.

This package does not provide generic branch settlement/receipts, a remediation
obligation lifecycle, cross-domain atomicity, production equivalence, promotion,
population truth or P6/P7 work. INF-4 overall remains incomplete.

Evidence: [INF-4J Harness report](../../../../../.harness/verification/infra-government-failed-inspection-remediation-scenario-report.json).
