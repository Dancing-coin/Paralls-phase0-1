# INF-4N Government Inspection Promotion Design

Status: `implemented and independently verified for one fixed Government passed-inspection promotion row; broader INF-4 remains incomplete`

INF-4N closes exactly one production-equivalent branch consequence: a passed
Government commercial inspection that already exists as durable branch
evidence may be revalidated and written by the existing Government authority
to its existing production stream. This is not a generic branch promotion API.

| Concern | Contract |
| --- | --- |
| Source admission | `gameplay:branch_preview:{branch_ref}` / `gameplay.branch_preview.inspection_admission_recorded`, `creator_debug` |
| Source scenario | `gameplay:government_branch:{branch_ref}:{organization_ref}` / `gameplay.government.branch_inspection_recorded`, `creator_debug` |
| Sole writer | `GovernmentAuthority` / `actor_gameplay.government_domain` |
| Destination | `gameplay:government:{organization_ref}` / existing `gameplay.government.inspection_recorded`, `project` |
| Receipt | immutable `GovernmentBranchPromotionReceipt` derived from the one `GameplayEventStore.append_batch()` result and production event identity |
| Pins | admission source Government revision must equal current production head; branch event must reference the exact admission and candidate/inspection digests |
| Privacy | source may be `creator_debug`; destination is always `project` |

The Government owner must validate the exact source stream/branch, passed state,
scenario event, organization, inspection, policy, evidence and source revision
before constructing its fixed inspection fragment. Stale production revision,
cross-branch or forged source/event identity, failed inspection, privacy and
changed idempotency are zero-write. Exact duplicate retries reconstruct the
same receipt through the existing idempotency record.

The operation is intentionally named and fixed to Government inspection. It
does not promote Organization supply, remediation, work, civilization,
population or arbitrary owner fragments. `BranchPreviewAuthority` remains a
proposal/evidence surface and never calls the production writer. No second
store, runtime, scheduler, receipt store or promotion coordinator is created.

Required evidence: focused success, duplicate, changed duplicate, source
revision conflict, branch forgery, privacy and zero-write tests; production
full/checkpoint-tail replay; scoped project outbox; and an independent Harness
profile. Complete group simulation remains deferred.

Evidence: `.harness/verification/infra-government-inspection-promotion-report.json`.
