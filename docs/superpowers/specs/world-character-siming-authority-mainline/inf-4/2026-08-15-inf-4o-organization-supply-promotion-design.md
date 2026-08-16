# INF-4O Organization Supply Promotion Design

Status: `implemented and independently verified for one fixed Organization-owned supply promotion row; broader INF-4 remains incomplete`

INF-4O closes exactly one production-equivalent branch consequence: a durable
Organization `supply` admission already emitted by `BranchPreviewAuthority`
on `gameplay:branch_preview:{branch_ref}` and a matching Organization branch
scenario row may be revalidated and written by the existing `OrganizationAuthority`
to its existing production `gameplay:organization:{organization_ref}` stream.
This is not a generic branch promotion API.

| Concern | Contract |
| --- | --- |
| Source admission | `gameplay:branch_preview:{branch_ref}` / `gameplay.branch_preview.supply_admission_recorded`, `creator_debug` |
| Source scenario | `gameplay:organization_branch:{branch_ref}:{organization_ref}` / `gameplay.organization.branch_commerce_commitment_recorded`, `creator_debug` |
| Sole writer | `OrganizationAuthority` / `actor_gameplay.organization_domain` |
| Destination | `gameplay:organization:{organization_ref}` / existing `gameplay.organization.commerce_commitment_accepted`, `project` |
| Receipt | immutable `OrganizationBranchPromotionReceipt` derived from the one `GameplayEventStore.append_batch()` result and production event identity |
| Pins | admission source Organization revision must equal current production head; branch event must reference the exact admission and candidate/fragment digests |
| Privacy | source may be `creator_debug`; destination is always `project` |

The Organization owner must validate the exact source stream/branch, supply
admission, scenario event, organization, commitment, policy, evidence and
source revision before constructing its fixed commerce fragment. Stale
production revision, cross-branch or forged source/event identity, privacy and
changed idempotency are zero-write. Exact duplicate retries reconstruct the
same receipt through the existing idempotency record.

The operation is intentionally named and fixed to Organization supply. It does
not promote Government inspection, remediation, generic branch rows or arbitrary
owner fragments. `BranchPreviewAuthority` remains a proposal/evidence surface and
never calls the production writer. No second store, runtime, scheduler, receipt
store or promotion coordinator is created.

Required evidence: focused success, duplicate, changed duplicate, source
revision conflict, privacy, forged source/scenario and full/checkpoint-tail
production replay. Complete group simulation remains deferred.

Evidence: `.harness/verification/infra-organization-supply-promotion-report.json`.
