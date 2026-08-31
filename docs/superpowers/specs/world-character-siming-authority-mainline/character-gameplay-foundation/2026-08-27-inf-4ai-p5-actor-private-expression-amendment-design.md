# INF-4AI P5 Actor-Private Expression Amendment Design

Status: `implemented narrow platform extension for INF-4AI; generic social/session expansion remains unapproved`

## Purpose

Close only the expression gap found by the INF-4AI candidate:

```text
committed completed two-party handshake InteractionSession
-> existing SocialFactAuthority
-> two paired actor-private shared-experience history events
```

The source is real committed gameplay evidence. The proposed outcome is not a
relationship score, reputation, attendance record, public social fact, or
Character Core memory write. It is one terminal private historical fact for
each participant. This document defines the smallest platform/P5 vocabulary
change needed to express that row without creating a generic session-to-social
writer or a second registry.

## Current Expression Failure

| Existing boundary | Exact deficiency |
| --- | --- |
| `P5PolicyRegistry` | the immutable model supports event catalog entries, but no admitted runtime revision registers `gameplay.social.handshake_shared_experience_recorded@1` or its schema/digest |
| P5 social event catalog | only relationship, knowledge, and visibility-revocation events are registered; reusing relationship would invent `observed_at`, confidence, decay, and reputation semantics |
| `GovernedAuthorityContract` | `projection_scope` supports only `project`, `authority_only`, and `mixed`; the row requires the existing P5-style `actor:{participant_ref}` privacy boundary |
| package activation | no immutable P5 social package/revision exists for this row; a test fixture registry is not an active content revision or truth source |

The source is `session_public_safe`, never authority-only, but target payloads
must not include session private terms, reservation details, raw controller
observations, pose data, or any score/relationship inference.

## Considered Expressions

| Expression | Result | Reason |
| --- | --- | --- |
| Reuse `relationship_fact_recorded@1` | rejected | requires timestamp/confidence/decay semantics absent from the committed session source and changes reputation projection meaning |
| Add a generic `InteractionSession -> SocialFactAuthority` adapter | rejected | admits arbitrary action semantics and becomes a forbidden generic social writer/router |
| Add this exact actor-private P5 event vocabulary | candidate | preserves one existing owner, one source vector, fixed event/streams/privacy, separate receipt and replay, and no generic route |

## Exact Amendment

The amendment is static, source-controlled vocabulary. It does not create a
runtime-writable registry or a new manifest type.

1. Extend the existing P5 event catalog vocabulary with exactly:

```text
event_type       = gameplay.social.handshake_shared_experience_recorded@1
schema_ref       = schema:p5:social:handshake-shared-experience-recorded@1
namespace        = namespace:p5:social
stream grammar   = ^gameplay:social:shared-experience:character:[^:]+$
owner            = authority:p5:social
```

2. Add the one immutable descriptor/catalog pair:

```text
descriptor_ref   = descriptor:social-handshake-shared-experience@1
capability_ref   = capability:social-handshake-shared-experience@1
outcome_ref      = outcome:social-handshake-shared-experience-recorded@1
predicate_ref    = predicate:embodied-completed-two-party-handshake@1
effect_ref       = effect:social-handshake-shared-experience-recorded@1
catalog_ref      = inf:social-handshake-shared-experience@1
```

3. Extend `GovernedAuthorityContract.projection_scope` with the closed value
`actor_private` only. An `actor_private` catalog row must use an exact
`character:` stream placeholder and require the owner to derive the matching
`actor:{participant_ref}` visibility for each event. It is not an arbitrary
scope string and does not permit public/project/authority substitution.

4. Add one static P5 social vocabulary revision:

```text
registry_ref      = registry:p5:social
registry_revision = registry:p5:social:v2
package_ref       = package:p5-social-handshake-history
package_revision  = package:p5-social-handshake-history:v1
```

The package is content metadata only. It may declare the exact event schema,
owner-admitted predicate, effect, reader reference, and verification profile;
it may not select owner, stream, privacy, receipt, idempotency, or any event
vector. Its canonical digest is derived and verified through the existing
INF-P v2 immutable manifest boundary only after a separately approved content
packet. No caller supplies a trusted digest claim.

## Fixed Execution Contract After Approval

The Social owner must reread only this source vector on one session stream:

```text
proposed(handshake, two distinct character participants)
-> accepted(non-initiator)
-> authorized
-> realizing
-> participant_observed(completed) x2
-> committed
```

The source event id/revision/head, both target heads, session policy/scene
revisions, participant identities, and settlement ref are owner-verified.
The owner appends exactly two same-owner events via the existing
`GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`
spine. Each participant receives only their own actor-private event. The
receipt is append-derived; full and checkpoint-tail replay use the one exact
Social reader. Unknown/non-terminal/wrong semantic/missing consent-completion
vector/private/stale source, target conflict, duplicate, changed duplicate,
or caller coordinates are zero-write.

## Non-Goals

This amendment does not add a generic social registry, generic interaction
adapter, new owner, relationship/reputation mutation, attendance, household
truth, population truth, payment, material, compensation, fanout, router,
coordinator, writer, settlement authority, second runtime/store/bus/clock, or
any change to frozen packages or existing INF rows.

## Approval Gates

1. Approve this exact static vocabulary and closed `actor_private` catalog
   scope.
2. Approve a file-by-file implementation plan for the existing P5 registry,
   catalog, social owner, event schema registration, and replay reader.
3. Approve the immutable P5 social handshake package content/freeze/digest.
4. The exact INF-4AI event/schema, actor-private catalog scope, owner method,
   focused tests, and independent Harness are now implemented. Any other
   event family, privacy scope, or InteractionSession mapping still requires a
   separate contract and approval.
