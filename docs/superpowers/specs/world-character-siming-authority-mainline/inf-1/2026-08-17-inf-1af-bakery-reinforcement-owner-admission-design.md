# INF-1AF Bakery Reinforcement Owner-Admission Design

Status: `implemented narrow vertical; verified 2026-08-17`

## Scope And Decision Boundary

This proposal evaluates one Construction-owner extension only:

```text
committed facility_acquired(facility_kind=bakery)
  -> existing ConstructionProductionAuthority
  -> facility_kind=bakery_reinforced
```

It does not admit an arbitrary facility transform, construction action router,
material/payment settlement, blueprint registry, replacement-kind selector, or
new truth owner. `ConstructionProductionAuthority` already owns the canonical
facility fact and its `gameplay:construction_production:{facility_ref}` stream.
This candidate adds no separate Construction owner and does not authorize any
other `facility_kind` pair.

## Owned And Non-Owned Facts

| Fact or operation | Owner | Boundary |
| --- | --- | --- |
| facility identity, plot binding, kind, condition, and revision | existing `ConstructionProductionAuthority` | one facility stream and existing projector |
| one exact `bakery -> bakery_reinforced` transition | existing `ConstructionProductionAuthority` if approved | fixed capability, one event family, one target kind |
| acquisition source | existing `ConstructionProductionAuthority` | committed project-visible `facility_acquired` event only |
| plot ownership, permits, blueprints, materials, payment, production output, and work completion | existing neighboring owners or unadmitted | not inferred or written by this capability |
| generic transform, target-kind selection, compensation, reopen, retry, or fanout | not admitted | reject before append |

## Proposed Capability And Intent Surface

Proposed capability reference:
`capability:construction-facility-bakery-reinforcement@1`.

The authenticated facility actor envelope may name only the logical facility,
its committed acquisition event, the required concurrency pins, and the fixed
idempotency key. The pins fence an already fixed owner outcome; they do not
select a target, event family, scope, or policy.
The owner resolves the sole target kind `bakery_reinforced`, target stream,
event family, project scope, receipt rule, and terminal behavior. The caller
cannot provide a replacement kind, source stream, event type, privacy scope,
payment/material reference, receipt, retry, or compensation policy.

Admission requires all of the following:

1. the source is the committed project-visible
   `gameplay.construction_production.facility_acquired` event in
   `gameplay:construction_production:{facility_ref}`;
2. its payload binds the authenticated facility and has exactly
   `facility_kind=bakery`;
3. the current Construction projection for that same facility still has
   `facility_kind=bakery`, the same `plot_ref`, and a pinned facility revision;
4. the sole target stream head equals the fixed expected revision; and
5. the immutable catalog admits only this Construction owner, stream, event
   vector, and project scope.

The acquisition event is durable source evidence, not a requirement that its
stream revision remain the current head. The current facility projection and
expected stream head are the concurrency fence; any intervening transition,
repair-derived revision mismatch, or source/target identity mismatch rejects
before append.

## Fixed Event, Revision, And Privacy Contract

| Boundary | Fixed value |
| --- | --- |
| source event | `gameplay.construction_production.facility_acquired@1` with `facility_kind=bakery` |
| target stream | `gameplay:construction_production:{facility_ref}` |
| target event | `gameplay.construction_production.facility_transformed@1` only |
| payload | facility ref, source acquisition event id/revision, prior kind `bakery`, next kind `bakery_reinforced`, prior/next facility revision, and a fixed transform policy revision |
| append path | `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()` through the existing Construction owner |
| revision vector | exact target stream head plus acquisition event revision and current facility revision pin |
| privacy | source, target event, scoped projection, and outbox are `project`; outbox contains only facility ref and next kind |
| catalog row | immutable `inf:construction-facility-bakery-reinforcement@1`, owned by `actor_gameplay.construction_production_domain` |

The projector must apply `facility_transformed` only when the current facility
kind and revision equal the payload's prior values, then replace only
`facility_kind` and increment the facility revision. No payment, material,
permit, or blueprint truth enters this event.

## Idempotency, Receipt, Replay, And Terminal Semantics

The canonical idempotency key is:

```text
facility-transform:bakery-reinforcement:{facility_ref}:{acquisition_event_id}:v1
```

Its request digest covers the acquisition event id/revision, facility stream
head, prior facility revision, fixed target kind, and transform policy
revision. An exact duplicate returns the original one-append Construction
result; a changed duplicate is zero-write.

The receipt derives solely from that `append_batch()` result. It carries the
target event id/revision and an actor-safe projection digest; the acquisition
event id/revision remains committed source evidence rather than a second
receipt. Full replay and checkpoint-plus-tail replay through the existing
Construction projector must reconstruct the same facility kind, revision, and
scoped projection digest.

`facility_transformed` is terminal for this capability. No reversal,
compensation, reopen, retry, automatic downgrade, source retraction, or
fanout is admitted. A future reversal requires a separately approved
Construction owner-local contract and must not be inferred from repair
compensation.

## Required Zero-Write Rejections

- missing, private, forged, wrong-stream, or wrong-type acquisition source;
- source or current facility kind other than exactly `bakery`;
- source facility/plot mismatch, stale facility revision, or stale stream head;
- caller-selected next kind, event family, owner, stream, privacy, receipt,
  payment/material, retry, compensation, or multiple facility values;
- unknown/unapproved capability or catalog mismatch; and
- exact idempotency key with a changed request digest.

## Implementation Evidence

The approved row is implemented only by
`ConstructionProductionAuthority.reinforce_bakery_facility`. It emits one
`facility_transformed` event through
`GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`.
Focused RED-to-green coverage is in
`backend/tests/test_infra_construction_bakery_reinforcement.py`; the
independent `infra-construction-bakery-reinforcement` Harness proves success,
zero-write rejection, privacy, revisions, idempotency, append-derived receipt,
full/checkpoint-tail replay, and the no-compensation/no-fanout boundary.
