# INF-4S Government Failed-Inspection Promotion Design

Status: `implemented and independently verified for one fixed Government failed-inspection promotion row; broader INF-4 remains incomplete`

INF-4S closes one additional production-equivalent branch consequence without
widening promotion into a generic API: a failed Government commercial
inspection that already exists as durable branch admission evidence and a
matching fixed Government remediation scenario row may be revalidated and
written by the existing Government authority to its existing production stream.
This does not create a generic remediation or branch promotion framework.

| Concern | Contract |
| --- | --- |
| Source admission | `gameplay:branch_preview:{branch_ref}` / `gameplay.branch_preview.inspection_admission_recorded`, `creator_debug`, `passed=False` |
| Source scenario | `gameplay:government_branch:{branch_ref}:{organization_ref}` / `gameplay.government.branch_inspection_remediation_recorded`, `creator_debug` |
| Sole writer | `GovernmentAuthority` / `actor_gameplay.government_domain` |
| Destination | `gameplay:government:{organization_ref}` / existing `gameplay.government.inspection_recorded`, `project`, `passed=False` |
| Receipt | immutable `GovernmentBranchPromotionReceipt` derived from the one `GameplayEventStore.append_batch()` result and production event identity |
| Pins | admission source Government revision must equal current production head; remediation event must reference the exact admission, candidate digest, remediation identity and fixed action |
| Privacy | source may be `creator_debug`; destination is always `project` |

The Government owner must validate the exact source stream/branch, failed
state, remediation scenario event, organization, inspection, policy, evidence,
fixed `follow_up_required` remediation action and source revision before it
constructs its existing commercial inspection fragment. The production append
reuses the canonical `gameplay.government.inspection_recorded` event with
`passed=False` and the existing Government owner/append/outbox/replay spine.

Stale production revision, cross-branch or forged source/event identity,
privacy mismatch and changed idempotency are zero-write. Exact duplicate
retries reconstruct the same append-derived receipt through the existing
idempotency record. The immutable governed-authority catalog must admit this
exact owner/stream/event/scope row before fragment construction.

This package does not create a remediation lifecycle owner, generic receipt
store, generic promotion authority, second store/runtime, social/population
truth, or automatic production append for other failed rows. All other
Government remediation/generic promotion inputs remain unsupported and
zero-write.

Evidence: `.harness/verification/infra-government-failed-inspection-promotion-report.json`.
