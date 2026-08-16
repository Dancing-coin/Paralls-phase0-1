# INF-1L Ecology Frost State Obligation Admission

Status: `implemented and verified closed Ecology owner row; generic matrix remains incomplete`

## Decision

Under the user's explicit authorization to extend existing owners, INF-1L
admits one additional closed effect/state row. It does not create a new truth
owner, store, clock, scheduler, or semantic direct-write path.

| Field | Fixed value |
| --- | --- |
| effect/state | `effect:frost -> state:frosted@1` |
| owner | existing `EcologyHazardAuthority` (`authority:ecology`) |
| stream | existing `gameplay:ecology:{region_ref}` |
| apply event | `gameplay.ecology.crop_state_applied` |
| obligation open event | `gameplay.ecology.crop_state_obligation_opened` |
| expiry event | `gameplay.ecology.crop_state_expired` |
| terminal event | `gameplay.ecology.crop_state_obligation_settled` |
| fragment builder | `EcologyHazardAuthority.build_frost_crop_state_fragment` |
| policy | `policy:ecology_frost_crop_state_expiry@1` |
| visibility | `project` only |
| revision identity | exactly the target ecology stream head plus immutable hazard/crop refs |
| receipt | the existing `GameplayEventStore.append_batch()` result summarized by the existing coordinator; no cross-stream receipt |

The state definition is fixed to `refresh`, stack limit `1`, and scheduled
expiry. A later frost on the same crop can only refresh the existing closed
row when its expected ecology revision and source hazard evidence match; it
cannot change the effect, state, stream, policy, visibility, or target owner.

## Write Boundary

`EcologyHazardAuthority` validates committed project-visible hazard and crop
records, builds the named owner fragment, and submits it through
`GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`.
The event store supplies the sole outbox/replay source. Semantic evaluation may
remain proposal-only and cannot append `crop_state_*` events.

When due, the existing caller-driven obligation coordinator may settle only a
previously committed INF-1L obligation through an ecology-owner fragment. This
package adds no background scheduler, clock, catch-up loop, retry,
compensation, consumer edge, or direct cross-domain mutation.

## Admission Fences

- only `effect:frost/state:frosted@1` and the fixed policy are admitted;
- only a project-visible hazard and crop in the same region may source the
  row;
- non-project privacy, stale revisions, forged/missing source evidence,
  caller-selected streams, changed idempotency inputs, and all other effect or
  state rows are zero-write rejected;
- duplicate inputs replay the committed append result; changed inputs with the
  same key are rejected without a second write;
- expiry requires the committed open identity and exact owner fragment;
- the canonical ecology record, regional propagation, and the two existing
  target-owner consumer edges remain unchanged.

## Required Proof Before Status Changes

Focused tests must independently cover apply success, refresh, exact duplicate,
changed duplicate, revision conflict, command and source privacy rejection,
unknown row rejection, due expiry/settlement, full replay, checkpoint-tail replay, and scoped outbox
projection. A dedicated Harness profile must expose a separate assertion for
each capability. The matching August analysis, root dependency spec/plan, and
INF-1 tree may describe this row as verified only after those tests and the
Harness report are green.

Evidence: `.harness/verification/infra-ecology-frost-state-obligation-report.json`
records twelve independent passing checks for apply, refresh, exact/changed
idempotency, revision/command-and-source-privacy/unknown-row zero writes, coordinator settlement,
scoped outbox, and full/checkpoint-tail replay.

## Non-goals

This is one Ecology-owned row, not generic effect registration, arbitrary
StateDefinition dispatch, generic ecology lifecycle, multi-hop propagation,
new ecology consumers, payment/account truth, or INF-1 closure.
