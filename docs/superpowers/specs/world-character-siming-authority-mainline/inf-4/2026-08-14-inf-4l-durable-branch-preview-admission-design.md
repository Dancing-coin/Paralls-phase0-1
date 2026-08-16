# INF-4L Durable Branch Preview Admission Evidence Design

Status: `implemented and verified; repairs INF-4I/INF-4J provenance only`

## Problem

INF-4I and INF-4J previously let the Government scenario writer receive raw
candidate fields, or an in-process proposal object. Neither proves that the
candidate was accepted by `BranchPreviewAuthority`: a caller can construct the
input without an accepted evaluation. This is a write-boundary defect, not a
receipt or promotion gap.

## Closed Contract

| Concern | Contract |
| --- | --- |
| Evidence owner | existing `BranchPreviewAuthority` extended as `authority:branch_preview` for proposal evidence only |
| Evidence stream | `gameplay:branch_preview:{branch_ref}` on the existing `GameplayEventStore` |
| Evidence event | `gameplay.branch_preview.inspection_admission_recorded` only |
| Evidence payload | accepted `intent_ref`, `passed`, base/candidate/fragment digests, organization/inspection/jurisdiction/policy/evidence refs and pinned Government source revision |
| Evidence privacy | `creator_debug` only, with a scoped outbox projection; no production stream/event is selectable |
| Evidence append | BranchPreview authority -> `GameplayCommandEnvelope` -> `SettlementPlan` -> `GameplayEventStore.append_batch()` -> outbox/replay -> authority-scoped admission reader |
| Consequence owner | existing `GovernmentAuthority` only |
| Consequence streams | existing `gameplay:government_branch:{branch_ref}:{organization_ref}` only |
| Consequence admission | Government receives only an admission event id, reloads it from the sole store, validates event/stream/payload/privacy/source revision and derives all scenario fields itself |
| Replay | evidence and Government scenario projection both have full/checkpoint-tail equivalence; production replay ignores both non-production prefixes |

The preview evidence is not population, NPC, social or Government truth. It is
a durable proposal/evidence record. It cannot settle a scenario by itself;
`BranchPreviewAuthority` may submit it only after its existing accepted
inspection evaluation. Government remains the only writer of passed inspection
or fixed failed-inspection remediation scenario facts.

## Required Rejections

Missing, unknown, wrong-stream, wrong-event, mismatched branch/organization,
wrong `passed`, stale Government source revision, privacy mismatch, changed
duplicate and direct primitive/proposal calls must produce zero scenario writes.
The previous public primitive scenario methods are removed or made incapable of
appending without a durable admission event. `creator_debug` scope, source
revision, expected scenario revision and idempotency are revalidated by
Government. No background scheduler, second event store, branch promotion,
generic receipt, remediation lifecycle or cross-owner coordinator is admitted.

## Completion Evidence

Focused RED tests must precede code. The dedicated Harness needs independent
assertions for evidence append, accepted passed and failed Government settlement,
direct forged/missing/mismatched/stale/privacy zero writes, idempotency,
scoped outbox, evidence and consequence replay, production isolation and
unsupported promotion. INF-4I/4J/4K may be revalidated only after this profile
passes.
