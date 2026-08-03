# Interaction Session And Authority Settlement Design

Status: `implemented-foundation; broader-social-and-cross-domain-closure-planned`

Date: `2026-07-29`

Revision: `2026-07-31` (review remediation)

## Purpose

Define the authority-owned `InteractionSession` lifecycle and the observed
physical settlement protocol. This prevents two actors from treating a shared
interaction as unrelated animation requests and prevents a Godot observation
from becoming world truth without validation.

The Gameplay-event-spine-backed session foundation is now implemented for the
current bounded slices: handshake/session lifecycle, privacy-filtered
projections, and the first handoff plus grab-carry-place closures. This does
not claim generalized social clips, relationship settlement, or arbitrary
cross-domain session coverage.

## Session Model

```text
InteractionSession
  session_id, semantic_action, initiator_ref, participant_refs, target_refs
  state: proposed | awaiting_responses | authorized | realizing |
         settling | committed | rejected | cancelled | interrupted | expired
  participant_terms[], slot_assignments[], reservation_refs[]
  authority_preflight_ref, policy_revision, scene_revision
  causation_id, correlation_id, attempt_refs[], settlement_ref?
  visibility_policy, audit_refs
```

An object-only action has an implicit one-actor session/attempt envelope for
correlation, but need not expose social negotiation. A multi-actor action must
use an explicit session before local controllers start synchronized phases.

## Lifecycle

```text
proposal -> consent/policy checks -> authorized
  -> local slot reservation -> realizing
  -> terminal observations collected -> settling
  -> committed | rejected

proposal/authorized/realizing -> cancelled | interrupted | expired
```

Only authority transitions session state. Local controllers may request cancel
or report interruption; their report is validated before the authoritative
session changes. Any participant, target invalidation, conflict, or scene
revision mismatch may terminate realization according to policy.

## Physical Settlement

1. Authenticate the bridge principal, consume the controller-scoped execution
   grant, and validate its one-time nonce, connection epoch, request digest,
   terminal sequence, expiry, and revocation state before decoding the outcome.
2. Decode the authorized attempt/outcome and validate identity, schema,
   scene/binding/policy revisions, and idempotency.
3. Confirm that the observation is allowed by the registered affordance rule
   and belongs to the authorized actor/target/session slot.
4. Evaluate world/relationship/consent/capability constraints using backend
   truth and pinned revisions.
5. Produce a typed proposal, then settle through the selected authority writer.
6. Commit or reject exactly once; emit correlated result/evidence projections.
7. Return presentation and retry/recovery directives, then release local and
   authority reservations.

### Settlement Writer And Event-Spine Cutover

The first `kick-chair` closure uses `esm_compatibility_adapter`, the explicit
temporary writer. It calls the existing ESM physical-result/authority-event
path and durably records the attempt fingerprint, validation decision,
settlement receipt, and idempotency key in one authority-owned operation. It is
limited to the existing single-object state result; it must not claim generic
event-sourced replay, atomic cross-domain mutation, inventory, relationship,
body, consent, or multi-actor settlement.

`gameplay_event_batch_writer` is the required successor. It appends the
validated effect proposal through the gameplay foundation's atomic event batch,
with `transaction_id`, continuous `transaction_sequence`, aggregate revisions,
causation, correlation, and privacy scope. Every attempt records
`settlement_writer_kind`; a writer never dual-writes the same attempt.

The cutover gate is explicit: no `InteractionSession`, handoff, relationship,
body, ownership, or multi-aggregate action may start until
`gameplay_event_batch_writer` is implemented and its focused gameplay event
profiles pass. Existing in-flight compatibility attempts drain/settle before
the writer route changes; their receipts remain replayable by their recorded
writer kind. This resolves the temporary bridge without inventing a second
event store.

## Field-Level Projection And Siming

Projection is backend allowlist-only and default-deny. The following policy is
part of the contract and must be enforced before every Godot, participant,
mind, Siming, Observatory, or replay projection:

| Field family | Authority | Assigned controller | Participant | Character mind | Siming / public Observatory |
| --- | --- | --- | --- | --- | --- |
| IDs, route, safe phase/status | full | own attempt only | own session-safe view | own actor only | public-safe summary after policy permits |
| anchors/colliders/pose/contact detail | full | own bounded execution refs | no raw detail by default | own outcome summary only | public effect summary only |
| consent, participant terms, private reservations | full | own directive only | own accepted/refused term only | own actor result only | never |
| VLA prompt/context and private mind/memory | full audit scope only | never | never | own pre-existing private data only | never |
| raw skeletal/debug artifacts | restricted audit/debug role | approved local ref only | never | never | never |
| settled world effect/retry directive | full | own presentation directive | policy-filtered result | own filtered writeback | public settled projection only |

The backend derives named projections from typed fields; it must not forward an
opaque payload then rely on a client to hide fields. Siming may create a
catalyst only from the public settled projection and cannot infer hidden
consent or mutate session/controller state.

## Failure Semantics

| Condition | Authority result |
| --- | --- |
| duplicate terminal observation | return original settlement, no second mutation |
| grant/nonce/epoch/sequence mismatch or revoked grant | `outcome_attestation_invalid`, no mutation |
| expired/unknown attempt | reject as `attempt_invalid` |
| stale binding/policy revision | `revision_conflict`, no mutation |
| observation violates affordance rule | `observation_rejected`, no mutation |
| local miss/failure | settled failure/abort evidence, no claimed object effect |
| participant refuses/cancels | session rejected/cancelled, no synchronized local start |
| target changes while realizing | interrupted, release reservations, replan required |

## Acceptance Criteria

1. The chair action produces exactly one settlement for each attempt despite
   duplicate/local retry messages.
2. A fabricated, stale, mismatched, or missing contact observation cannot
   mutate object/environment/body authoritative state.
3. Commit/reject results retain request, attempt, session, causation, and
   correlation IDs and are routable as existing authority events.
4. A future handshake fixture proves propose/accept/reject/cancel/interrupted
   session transitions, slot ownership, and privacy filtering before any hug
   clip is added.
5. Controller completion and Observatory display are never used as settlement
   predicates.
6. Contract tests prove each field family above is absent from every
   ineligible controller, participant, mind, Siming, Godot, and Observatory
   projection.

## Dependencies

- Existing interaction orchestration, ESM, authority events, and world-result
  protocols.
- Scene registry and local controller/observation contracts.
- Future gameplay-foundation event settlement and relationship boundaries.
