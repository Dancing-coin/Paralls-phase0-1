# P2D-R Authored Bakery Authority Re-closure

Status: `implemented-and-verified; bounded owner re-closure`

## Purpose

Replace the historical P2D sample with one actual two-worker bakery operating-window vertical.
It uses existing CharacterProfile identities as read-only actor inputs and preserves one
`GameplayEventStore`. No vertical-slice coordinator, population/NPC truth, clock, scheduler or
direct CharacterAgent writer is introduced.

## Fixed owner contract

| Capability | Existing owner | Stream and event family | Projection / receipt |
| --- | --- | --- | --- |
| baker schedule and counter schedule | `OrganizationAuthority` | `gameplay:organization:org:bakery-authored`; membership/role/shift/work-order records | recipient-scoped organization schedule outbox and replayable view |
| operating window | `OrganizationAuthority` | `gameplay:organization:window:window:bakery-authored`; open/close/due records | project-scoped window view and append result |
| baker completed work source | `ConstructionProductionAuthority` | `gameplay:construction_production:facility:bakery-authored`; run start/finish/completion-evidence records | actor-scoped production evidence view and append result |
| counter procurement work source | `EconomyAuthority` | existing buyer Economy stream; fixed `purchase_posted` event with the scheduled counter work-order link | counter-scoped procurement outbox and Economy append result |
| baker wage obligation, accrual and payment/overdue | `EconomyAuthority` | existing wage stream plus `gameplay:economy` accounts | actor-scoped wage outbox; unique append result per owner command |

The only new business mapping admitted by this design is the fixed counter schedule input to the
existing Economy procurement event. Economy independently reconstructs the Organization schedule
from the unique store, pins its source revision and accepts only the named recipient/work-order.
It does not receive an open consumer registry or generic Organization fragment.

## Formal write path

Every P2D-R write is an existing owner command followed by
`GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch() -> outbox/replay`.
Production start/finish retain their existing Construction owner plan path. A read-only profile
lookup, actor intent or work-evidence view can never append itself.

## Acceptance boundary

P2D-R must independently prove: two existing authored identities with separate schedule rows;
one committed baker production evidence; one committed counter procurement event linked to its
exact schedule; window close plus baker wage payment and insufficient-funds overdue; exact
idempotency, changed-key zero-write, stale revision zero-write, privacy scope denial, and full
versus checkpoint-tail replay. The Harness must have one assertion per capability.

The final review hard-binds the Economy reader to `org:bakery-authored`, `character:char_c`,
`work:flour`, `counter/procurement` and an `actor:character:char_c` source row; other
organizations and public/summary source rows are zero-write rejected.

Evidence: `backend/tests/test_p2dr_authored_bakery_authority_reclosure.py` and
`.harness/verification/p2dr-authored-bakery-authority-reclosure-report.json` record nine
independent success, rejection, idempotency, revision, scope, replay, payment and overdue checks.

It does not implement customer/supplier private truth, dynamic market, generic work evidence,
generic cross-domain settlement, the envelope-only actor-intent consumer, full three-role/Godot
mirror closure, Population Simulation or promotion.
