# INF-1Z Ecology Frost State-Action Design

Status: `implemented and independently verified for the fixed Ecology frost dispel row; broader INF-1 remains incomplete`

## Purpose

INF-1Z extends the already admitted `effect:frost -> state:frosted@1` row with
its one missing `StateDefinition.dispel_allowed` action. It is a fixed
Ecology-owned lifecycle completion, not a generic action registry.

| Concern | Fixed contract |
| --- | --- |
| Proposal surface | `SemanticEcologyFrostStateActionCommand`, emitted only by `authority:semantic` |
| Effect/state | `effect:ecology_frost_state_dispel` / `state:frosted@1` |
| Sole writer | `EcologyHazardAuthority` / `authority:ecology` |
| Canonical stream | `gameplay:ecology:{region_ref}` |
| Required committed source | canonical project-visible frost hazard, crop relation, prior crop-state apply and its exact open frost obligation |
| Owner event family | `gameplay.ecology.crop_state_dispelled` and `gameplay.ecology.crop_state_obligation_cancelled` in one owner batch |
| Privacy/projection | `project` only, existing `world.ecology.scoped_projection` outbox |
| Revision/idempotency | exact stream head; owner principal plus action-command digest; changed duplicate is zero-write |
| Receipt/replay | one append-derived result and existing `EcologyHazardAuthority.crop_state_replay` full/checkpoint-tail reader |

The semantic authority may only validate the immutable adapter/action contract
and produce the exact owner command. `EcologyHazardAuthority` must revalidate
the stream, relation, active obligation and exact event family before building
the two-event fragment. It is the sole append owner.

Rejected inputs are zero-write: forged region/hazard/crop relation, inactive or
already terminal obligation, stale revision, non-project scope, unknown action,
catalog/adapter mismatch and changed duplicate. Exact duplicate replay returns
the original append result without a second write.

This package creates no action registration API, generic effect/state matrix,
scheduler, clock, store, bus, coordinator writer, population/NPC/social truth
store or Ecology-to-other-domain consumer edge.
