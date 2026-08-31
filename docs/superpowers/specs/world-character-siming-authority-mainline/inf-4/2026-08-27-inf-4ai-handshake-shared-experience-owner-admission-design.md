# INF-4AI Handshake Shared-Experience Owner-Admission Contract

Status: `implemented narrow vertical; Goal active; August INF A-D not complete`

## Product Decision And Conflict Preflight

The product requires a completed mutual interaction to be available as one
durable shared-experience fact without treating a handshake as friendship,
reputation, attendance, a public relationship, a payment, or a population
fact. The exact existing source is stronger than a branch candidate: it has
two named participants, an explicit acceptance transition, two completed
terminal observations, and a committed terminal session event.

```text
committed embodied InteractionSession
  semantic_action = handshake
  state = committed
  exactly two character participants
  both participant observations = completed
-> existing SocialFactAuthority
-> one paired private shared-experience event vector
```

The rejected alternative was `relationship_fact_recorded(shared_experience)`.
That existing event's semantics require `observed_at` and optional confidence
decay, while `InteractionSession` deliberately stores no canonical observed
time. Inventing a timestamp or deriving one from a clock/fixture would create
false provenance. INF-4AI therefore owns the narrower historical fact
`handshake_shared_experience_recorded@1`; it has no score, decay, reputation,
or relationship-state meaning.

## Fixed Contract

| Field | Fixed rule |
| --- | --- |
| capability / outcome | `capability:social-handshake-shared-experience@1` / `outcome:social-handshake-shared-experience-recorded@1` |
| descriptor / catalog | `descriptor:social-handshake-shared-experience@1` / `inf:social-handshake-shared-experience@1`, kind `social_fact` |
| owner | existing `SocialFactAuthority` (`authority:p5:social`) |
| source | one committed `embodied.interaction_session.committed@1` on `session:{session_id}` |
| source vector | exact same-stream `proposed`, `accepted`, `authorized`, `realizing`, exactly two `participant_observed`, then `committed`; no extra tail event; all source events are `session_public_safe` |
| source eligibility | proposal must name `semantic_action=handshake`, exactly two distinct `character:` participants, and the non-initiator must own the accepted event; both observation events must be `completed`; committed settlement ref and source session id must agree |
| target vector | exactly two `gameplay.social.handshake_shared_experience_recorded@1` events, one on each participant's deterministic private interaction stream |
| target payload | fixed interaction ref, source session id/event/revision/head, actor and counterpart refs, `interaction_kind=handshake`, `status=completed`, session policy/scene revisions, descriptor/catalog pins; no relationship score, reputation, payment, material, or participant-private terms |
| privacy | each target event is visible only to `actor:{participant_ref}`; no public, project, authority substitution, or cross-participant view is allowed |
| idempotency | `social:handshake-shared-experience:{session_event_id}:{session_revision}:{source_head}:{first_target_head}:{second_target_head}:v1`, derived and compared exactly by the Social owner |
| receipt / replay | one append-derived `GameplayEventStore.append_batch()` receipt for the same-owner two-event vector; `SocialFactAuthority.handshake_shared_experience_view_for` must agree under full and checkpoint-tail replay |
| lifecycle | terminal historic fact per source session; no deletion, correction, retry-as-new source, compensation, fanout, relationship mutation, or reversal in v1 |

The source session owner retains consent, slot, terminal-observation, and
session lifecycle truth. Social retains only the separate participant-private
historical facts. The public-safe session projection does not grant access to
participant-private terms, and this row never reads those terms.

## Zero-Write Rules

Reject before fragment construction or append for unknown/missing/non-terminal
source; wrong stream, event, session id, semantic action, visibility, source
vector, participant cardinality, participant identity, acceptance, terminal
observation, settlement ref, source revision/head; stale or conflicting target
heads; missing or changed derived idempotency key; pre-existing source-session
fact; catalog/descriptor mismatch; caller-selected actor, counterpart, stream,
event, privacy, receipt, fragment, relationship score, reputation, timestamp,
payment, material, or compensation field.

Exact duplicate delivery returns only the original append-derived receipt.
Changed duplicate is zero-write. There is no caller-selected relation kind or
generic session-to-social route.

## Boundaries

This row introduces no new owner, package, runtime, registry, router,
coordinator, writer, scheduler, settlement authority, social graph policy,
relationship score, attendance system, population truth, payment, material,
inventory, or cross-owner receipt. It is not a generic `InteractionSession ->
SocialFactAuthority` mapping and does not admit handoff, embrace, support,
tabletop, public-workshop, or any other semantic action.

## Precise Blocker Evidence

The exact event/schema registration, closed actor-private catalog scope,
Social owner adapter, focused tests, and independent Harness are now
implemented and verified. Existing P5 registry revisions remain immutable;
the new static vocabulary is source-controlled and limited to this exact
handshake row. No generic social writer or second registry is present.
