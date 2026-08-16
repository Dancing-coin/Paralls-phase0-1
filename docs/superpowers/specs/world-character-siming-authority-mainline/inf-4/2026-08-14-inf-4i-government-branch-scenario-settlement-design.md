# INF-4I Government Branch Scenario Settlement Design

Status: `implemented and verified for one evidence-backed Government passed-inspection scenario row; broader INF-4 remains incomplete`

## Scope

INF-4I turns one already evaluated, accepted `inspection` branch candidate with
`passed=True` into a non-production Government scenario record. The existing
`BranchPreviewAuthority` remains a proposal/evaluation surface; the existing
`GovernmentAuthority` is the sole writer and uses the existing
`GameplayEventStore`.

| Concern | Contract |
| --- | --- |
| Proposal producer | `BranchPreviewAuthority`, only after its closed inspection evaluation |
| Sole writer | `GovernmentAuthority` / `actor_gameplay.government_domain` |
| Store | existing `GameplayEventStore` only |
| Scenario stream | `gameplay:government_branch:{branch_ref}:{organization_ref}` |
| Event family | `gameplay.government.branch_inspection_recorded` only |
| Input row | one evaluated inspection with pinned base/candidate digests, production Government revision, scenario revision and `passed=True` |
| Append path | Government authority -> `GameplayCommandEnvelope` / `SettlementPlan` -> `GameplayEventStore.append_batch()` -> scoped outbox -> Government scenario projection/replay |
| Privacy | `creator_debug` only |

The non-production passed-inspection record has no remediation obligation. At
this INF-4I endpoint a failed inspection is rejected before append. INF-4J
subsequently admits one separate fixed `follow_up_required` remediation record
for an accepted failed inspection on the same non-production Government scenario
stream; neither package admits a remediation-obligation lifecycle or receipt
contract.

## Admission and Replay

Only the exact scenario prefix, `creator_debug`, durable accepted `inspection` evidence,
`passed=True`, matching source Government revision, matching scenario head and
unchanged idempotency payload are admitted. Changed duplicates, stale revisions,
unknown candidates, privacy violations and failed inspections at this
passed-inspection endpoint are zero-write.

The Government-owned scenario projection supports full and checkpoint-tail
replay. Production replay filters both Organization and Government scenario
prefixes, so scenario events cannot become production world truth. Promotion,
generic scenario receipts, cross-domain settlement and production-equivalent
branch progression remain unsupported.

INF-4L now supplies and independently verifies the required durable,
replayable preview-evidence contract. Government reloads and revalidates that
event before its scenario append; direct primitive input remains zero-write.

`infra-government-branch-scenario-settlement` exercises the mechanical scenario
row and writes evidence to
`.harness/verification/infra-government-branch-scenario-settlement-report.json`.
