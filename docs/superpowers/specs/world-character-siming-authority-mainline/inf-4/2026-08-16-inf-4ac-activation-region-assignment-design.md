# INF-4AC Activation-Owned Profile Region Assignment

Status: `implemented and independently verified`

## Purpose

INF-4AC fills only the missing event-derived target mapping needed before a
future Ecology-to-Survival consumer row can be considered. The existing
`ProfileActivationAuthority` owns an active authored profile's placement in a
world and appends the assignment to its existing `population:{world_ref}`
stream. `EcologyHazardAuthority` remains the owner of the source region fact;
it cannot write a profile, Survival state, or population decision.

## Fixed Contract

| Field | Value |
| --- | --- |
| placement owner | existing `ProfileActivationAuthority` / `world_runtime.activation_authority` |
| identity source | existing registered `CharacterProfile` and committed activation |
| evidence owner | existing `EcologyHazardAuthority` / `authority:ecology` |
| evidence event | committed project-visible `gameplay.ecology.region.recorded` |
| target stream | existing `population:{world_ref}` |
| target event | `population.activation.region_assigned` |
| projection | event-derived profile-to-region map, project-scoped only |
| write path | activation authority -> `GameplayCommandEnvelope` / `SettlementPlan` -> `GameplayEventStore.append_batch()` -> outbox/replay -> scoped projection |
| receipt | only the resulting activation append result |

## Admission

The Activation owner must revalidate all of the following before building its
owner fragment:

- the profile is registered and currently active in the named world;
- the source event exists, is project-visible, is exactly
  `gameplay.ecology.region.recorded`, and its canonical record matches the
  requested `region_ref`;
- the assignment command pins the current activation stream revision and the
  source Ecology stream revision; and
- the only writable stream/event/scope are the fixed values above.

Unknown profile, inactive profile, forged or private Ecology evidence,
region/source mismatch, stale revisions, changed idempotency reuse and a
non-project reader must be zero-write. The assignment does not infer location
from `CharacterProfile.homeland`, Godot/client position, or household
`residence_ref`.

## Non-goals

This is neither a population/NPC/social truth store nor a generic location
system. It does not accept free-form evidence, select profiles, drive a clock,
write Survival state, or authorize a weather-front consumer. A later package
must separately bind this read-only projection to one exact Survival owner
fragment, with its own receipt and replay evidence.

Verification: `backend/tests/test_infra_activation_profile_region_assignment.py`
has ten independent focused assertions. The
`infra-activation-profile-region-assignment` Harness separately proves the
owner append, forged/private/inactive zero-write, idempotency, both revision
pins, reader scope, and scoped full/checkpoint-tail projection replay.
