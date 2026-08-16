# INF-2G Activation-Obligation Binding Contract Design

Status: `implemented and independently verified 2026-08-14; one finite reader for four existing rows, not a generic router`

## Purpose

The verified INF-2B, INF-2E, INF-2F and schedule-gated supply paths all
derive a pending activation record from one existing activation stream and
settle through an existing domain owner. Their admission identities were
previously repeated as local conditionals. INF-2G records those identities in
one immutable, closed binding contract and makes both the activation pending
writer and the released consumers validate against it.

This is not a new scheduler, queue owner, coordinator writer, event store,
clock, target-domain router, or cross-stream receipt. It adds no caller chosen
owner, stream, event type or fragment.

## Closed binding rows

| Binding | Pending kind | Existing target owner | Target contract | Privacy | Notes |
| --- | --- | --- | --- | --- | --- |
| `activation-binding:survival-state-expiry:cold:v1` | `survival_state_expiry` | `SurvivalAuthority` | `policy:survival_state_expiry@1`, `gameplay:survival:{profile_ref}`, `build_state_expiry_fragment()` | `project` | exact existing cold row |
| `activation-binding:survival-state-expiry:dehydrated:v1` | `survival_state_expiry` | `SurvivalAuthority` | same | `project` | exact existing dehydrated row |
| `activation-binding:survival-state-expiry:overheated:v1` | `survival_state_expiry` | `SurvivalAuthority` | same | `project` | exact existing overheated row |
| `activation-binding:schedule-gated-supply:v1` | `schedule_gated_supply` | `OrganizationAuthority` | existing frozen schedule plan -> `merge_schedule_gated_supply()` -> existing Organization fragment | plan report scope only | target stream and fragment remain resolved by the frozen existing-owner plan |

The canonical writer derives the binding reference from the closed reader. A
caller supplied `binding_ref`, owner, stream, event family, policy, state,
privacy or revision metadata cannot widen the row and must produce a
zero-write rejection. The activation event persists the derived binding ref so
the released projection is replayable and independently auditable.

## Formal write path and receipts

`ProfileActivationAuthority.record_pending()` writes exactly one
`population.activation.pending_recorded` event through
`GameplayEventStore.append_batch()`. `release_lock()` separately writes one
activation release event. A released row is then validated by its already
existing consumer and settles through its existing owner fragment and one
owner `append_batch()`.

The activation append receipt and the target owner `SettlementReceipt` or
`ContinuityMergeReceipt` remain distinct. INF-2G does not fabricate a
cross-stream atomic receipt. Replay reads the activation stream first and
then the existing scoped target projection.

## Admission and rejection rules

- The reader has exactly the four rows above and no registration API.
- A Survival row requires the committed obligation identity, policy revision
  `1`, a non-negative target revision, one admitted state, and `project`
  privacy.
- The schedule row requires only the canonical frozen-plan digest at pending
  admission; the existing schedule consumer still verifies social, household,
  organization, revision, privacy and owner-fragment pins at settlement.
- Unknown kind, forged binding metadata, missing required fields, changed
  idempotency payload, stale revision and privacy mismatch are zero-write for
  the relevant activation or target stream. Existing compatibility diagnostics
  may record a structurally valid but unregistered Survival expiry with an
  empty binding ref; it is not a contract row and the released target consumer
  rejects it with zero target writes.
- Exact duplicates replay only the committed append result. The binding table
  does not authorize retry, cancellation, compensation, payment/account truth
  or any unlisted owner route. The binding and obligation identity are checked
  before a duplicate target receipt can replay, so an unbound historical
  pending cannot borrow a valid prior settlement receipt.

## Completion evidence

`infra-activation-obligation-binding-contract` must independently assert the
exact closed table, unknown lookup, forged pending zero-write, canonical
event-derived binding reference, exact duplicate behavior, Survival and
Organization target receipt separation, scoped privacy, and full plus
checkpoint-tail replay. It must rerun the four predecessor release profiles.

INF-2 remains incomplete after this package: generic policy registration,
payment/account truth, arbitrary cross-domain atomic settlement and any
unregistered activation binding remain out of scope.
