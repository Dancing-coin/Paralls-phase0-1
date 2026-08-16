# INF-4F Isolated Owner-Fragment Evaluation Design

Status: `implemented and independently verified for builder validation only; production settlement and promotion remain unsupported`

## Scope

INF-4F extends the isolated `BranchPreviewAuthority` buffer with a closed,
replayable consequence evaluation for the existing `supply` and `inspection`
candidate mappings. It calls the existing owner **fragment builder** as a pure
validation/read operation, never an owner settlement method and never
`GameplayEventStore.append_batch()`.

| Candidate | Existing owner validation | Branch-local record |
| --- | --- | --- |
| `supply` | `OrganizationAuthority.build_commerce_commitment_fragment` | `branch_owner_consequence_evaluated` |
| `inspection` | `GovernmentAuthority.build_commercial_inspection_fragment` | `branch_owner_consequence_evaluated` |
| other | none | `branch_owner_consequence_blocked` |

The record contains only branch ref, candidate ref, owner ref, evaluation
disposition, source revision vector and digest of the generated fragment. It
does not contain a production receipt, event id, outbox id or a domain fact.
The isolated buffer remains the only branch record surface and `promote()`
continues to return `branch_promotion_unsupported`.

## Admission and safety

The candidate must have one of the two registered owner mappings, a matching
existing owner stream/revision, project/actor permitted preview scope, and
valid owner-builder arguments. Stale revision, malformed payload, unknown kind,
private source or failed builder validation produces a branch-local rejected
record and zero production writes. The preview authority cannot select an
arbitrary builder, stream or event type.

The target owners retain sole production write authority. This package does not
add a branch event store, runtime, scheduler, population/NPC/social truth owner,
cross-domain receipt or promotion route.

## Verification

Focused tests and a dedicated Harness profile must independently prove accepted
evaluation, owner rejection, stale revision, duplicate deterministic replay,
privacy, checkpoint-tail branch projection and production zero writes.

Evidence: [INF-4F Harness report](../../../../../.harness/verification/infra-isolated-branch-owner-fragment-evaluation-report.json).
