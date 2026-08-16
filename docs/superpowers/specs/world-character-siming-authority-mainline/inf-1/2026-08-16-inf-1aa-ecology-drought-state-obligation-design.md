# INF-1AA Ecology Drought State Obligation

Status: `implemented and verified seventh finite lifecycle row with opening-event-derived settlement provenance; generic lifecycle closure remains incomplete`

## Decision

INF-1AA admits one additional closed state/effect row over the existing
`EcologyHazardAuthority`. It does not create a new truth owner, store, clock,
scheduler, generic registration API, or semantic writer.

| Field | Fixed value |
| --- | --- |
| package | `INF-1AA` |
| effect/state | `effect:drought -> state:drought@1` |
| owner | existing `EcologyHazardAuthority` (`authority:ecology`) |
| stream | existing `gameplay:ecology:{region_ref}` |
| canonical source | committed project-visible `gameplay.ecology.drought_process_advanced` |
| apply event | `gameplay.ecology.drought_state_applied` |
| obligation open event | `gameplay.ecology.drought_state_obligation_opened` |
| expiry event | `gameplay.ecology.drought_state_expired` |
| terminal event | `gameplay.ecology.drought_state_obligation_settled` |
| policy | `policy:ecology_drought_state_expiry@1` |
| semantic entry | `SemanticSettlementAuthority.settle_closed_ecology_drought` |
| fragment builder | `EcologyHazardAuthority.build_drought_state_fragment` |
| replay reader | `EcologyHazardAuthority.drought_state_replay` |
| visibility | `project` only |
| definition | `refresh`, stack limit `1`, scheduled expiry, no dispel, no transform |

The source event ID, source event revision, and current ecology stream head are
all pinned. A newer drought-process cursor makes a historical source stale; a
second active obligation is rejected without a write.

## Write Boundary

`SemanticEcologyDroughtCommand` is proposal-only. The semantic authority
validates the immutable adapter, owner, lifecycle, and StateDefinition catalog
row, derives the existing ecology stream, and delegates through
`GameplayCommandEnvelope`. `EcologyHazardAuthority.apply_drought_state()` then
revalidates the committed source event, owner contract, state definition,
privacy, revision, idempotency, and active-obligation guard before the sole
`GameplayEventStore.append_batch()` call.

Due expiry is caller-driven through the existing
`ObligationSettlementCoordinator`; only the Ecology owner builds and commits
the expiry/settled fragment. The expiry fragment derives its drought-process
source from the committed opening event carried by the lifecycle projection;
the caller supplies no source event identity. Outbox entries and replay are
append-derived.

## Admission Fences

- only `effect:drought/state:drought@1` and the fixed policy are admitted;
- the source must be the latest committed project-visible drought-process event
  on the exact region stream;
- missing, private, forged, stale, wrong-region, wrong-effect, wrong-state,
  wrong-definition, wrong-owner, wrong-stream, wrong-revision, non-project,
  changed-duplicate, and second-active-obligation inputs are zero-write rejected;
- exact duplicate commands replay the committed append result;
- no dispel, transform, scheduler, retry/compensation, consumer edge, or
  cross-domain write is introduced.

## Required Proof

Focused tests cover owner success, every listed guard, exact/changed
idempotency, owner-only due expiry, append-derived outbox/receipt, full replay,
checkpoint-tail replay, strict semantic input/adapter admission, and the finite
state/lifecycle/adapter catalog rows.

Evidence: `.harness/verification/infra-ecology-drought-state-obligation-report.json`.

## Non-goals

This is the seventh finite state-owner row, not generic lifecycle closure,
generic Ecology effect routing, caller-open registration, or a new runtime
authority.
