# INF-2K Government Policy Registration Design

Status: `implemented bounded and verified 2026-08-15`

## Purpose

INF-2K closes one missing foundation behind caller-proposed obligation policy
registration without creating a policy store, scheduler, or generic settlement
writer. The existing `GovernmentAuthority` is the only writer. A caller may
submit a typed commercial-inspection policy proposal; it cannot select a stream,
event family, principal, privacy, or lifecycle transition.

## Closed contract

| Field | Contract |
| --- | --- |
| authority | existing `GovernmentAuthority` / `actor_gameplay.government_domain` |
| stream | existing `gameplay:government:{organization_ref}` |
| input | fixed `GovernmentCommercialInspectionPolicy` only |
| events | `gameplay.government.commercial_inspection_policy_registered` and `..._revoked` |
| projection | event-derived government policy view, scoped to its organization stream |
| revision | expected government stream revision and immutable `policy_revision` |
| privacy | project-visible policy identifiers only; no evidence or caller payload in outbox |
| receipt | the sole `GameplayEventStore.append_batch()` result |

The registration does not itself open or settle an obligation. It gives later
Government-owned inspection flows one replayable, revisioned policy source.
Only one active revision per `(organization_ref, policy_ref)` is admitted. A
duplicate with the same command replays; changed duplicate, stale revision,
wrong owner/privacy, unknown policy kind, and revocation of an absent or stale
policy are zero-write rejections.

## Non-goals

This is not arbitrary caller registration, a generic rule engine, payment,
cross-domain atomic business settlement, a new policy/event store, a scheduler,
or a branch-promotion route. No other authority may consume the registration
until its own source/revision/privacy/receipt binding is separately admitted.

## Evidence requirements

Focused tests and the independent Harness must separately assert successful
register/revoke, exact idempotency, changed duplicate zero-write, stale
revision, privacy, unknown kind, replay and checkpoint-tail replay. The
profile must rerun the Government owner preconditions and document the still
blocked generic/cross-domain surface.

`infra-government-policy-registration` records eight independent checks:
registration and revocation each have their own one-batch assertion; exact and
changed idempotency, stale revision, privacy rejection, unknown-kind rejection,
and full/checkpoint-tail replay are isolated selectors. The fixed input model
admits no caller-selected policy kind, stream, event family or scope.
