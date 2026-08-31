# INF-2AN Grain Intake Acceptance Owner-Admission Contract

Status: `implemented and verified narrow vertical; generic payment/transfer remains blocked`

## Exact Source And Outcome

```text
committed project-visible gameplay.organization.grain_intake_recorded@1
  + its committed project-visible gameplay.inventory.grain_harvest_received@1 provenance
-> existing EconomyAuthorityService
-> one authority-only gameplay.economy.grain_intake_accepted@1 marker
```

The marker records that the district milling cooperative accepted the fixed
grain intake. It does not debit or credit an account and is not a payment,
transfer, price quote, inventory mutation, production result, or settlement.

## Fixed Contract

| Field | Fixed value |
| --- | --- |
| capability / outcome | `capability:economy-grain-intake-acceptance@1` / `outcome:economy-grain-intake-accepted@1` |
| owner | `EconomyAuthorityService` / `actor_gameplay.economy_domain` |
| source owner/evidence | `OrganizationAuthority` / project-visible `gameplay.organization.grain_intake_recorded@1` |
| source provenance | project-visible `gameplay.inventory.grain_harvest_received@1`, fixed organization, holder, container, item and quantity |
| target stream/event | `gameplay:economy` / authority-only `gameplay.economy.grain_intake_accepted@1` |
| policy / descriptor / catalog | `policy:economy-grain-intake-acceptance@1`; `descriptor:economy-grain-intake-acceptance@1`; `inf:economy-grain-intake-acceptance@1` |
| predicate / subject | `predicate:organization-grain-intake-recorded@1`; project/plot binding inherited from the committed source pair |
| idempotency | `economy:grain-intake-acceptance:{source_event_id}:{source_revision}:{economy_head}:v1`, derived by Economy |
| receipt / replay | `GameplayEventStore.append_batch()` authority receipt; `grain_intake_acceptance_projection` full and checkpoint-tail replay |
| lifecycle | v1 terminal `accepted`; exact duplicate replay, changed duplicate and corrections/reversals/compensation are zero-write |

## Eligibility And Zero-Write Rules

Economy accepts only the exact organization, Inventory provenance, project/plot
binding, item `grain:wheat@1`, quantity `10`, source revisions, source stream
heads and authority-only target stream head. Unknown, private, stale, malformed,
ambiguous, forged, mismatched, duplicate, changed-duplicate or caller-selected
source/owner/stream/event/privacy/account/amount input rejects before append.
Boolean values are not valid source or target revision pins and also reject
before append.
The Inventory source event revision must also equal the current Inventory owner
stream head; stale custody provenance rejects before append.

The event vector contains exactly one Economy marker. Full replay and
checkpoint-tail replay validate both source events and reconstruct identical
acceptance projection state. The append-derived receipt remains authority-only.
Replay also validates the target stream revision relation: the committed event
revision is exactly the pinned pre-append Economy head plus one.
The committed acceptance event's causation id is pinned to the exact
Organization source event id during replay.
Replay derives stream heads from the supplied event sequence; the projector
does not access a second store or runtime service.

## Explicit Non-Goals

This row does not create payment, transfer, debit, credit, market pricing,
account selection, inventory custody, material, production, compensation,
fanout, generic settlement, router, registry, coordinator, writer, new owner,
or second runtime/store/bus/clock/scheduler.
