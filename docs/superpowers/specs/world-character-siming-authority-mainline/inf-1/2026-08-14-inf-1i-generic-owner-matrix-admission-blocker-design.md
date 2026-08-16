# INF-1I Generic Effect/State Owner Matrix Admission Blocker

Status: `bounded registered matrix implemented and verified; INF-1L admits one further closed Ecology row; generic additional rows remain blocked`

## Decision

INF-1H closes state dispatch only for the three registered Survival rows and
the Construction maintenance row. INF-1J separately admits the exact
`effect:wage_accrual_due -> EconomyAuthority` obligation row. The August INF-1
requirement for a generic effect/state owner matrix and event-derived lifecycle
cannot be implemented until each remaining row names an existing authority,
stream pattern, event family, scoped projection, revision vector, privacy
policy, idempotency key and replay reader.

The historical Ecology frost path is proposal-only (`semantic.effect.settled`
on the crop stream). INF-1L separately admits one replacement
Ecology-owned `effect:frost -> state:frosted@1` lifecycle row on the canonical
ecology stream; it does not turn the historical proposal path into a generic
route or admit any other Ecology effect/state row.

The current implementation exposes one deterministic state matrix for exactly
those four rows and one separate closed Economy obligation route. Neither is
an open registration API or evidence that unregistered domains have lifecycle
support. Existing Survival dispel/transform fragments are owner helpers with
their own obligation contract; they are not semantic proposal rows until a
separate row fixes their source evidence and admitted replacement semantics.

## Admission fence

- four registered state rows remain the only rows accepted by
  `settle_registered_state()`;
- the separately registered Economy row remains the only row accepted by
  `settle_registered_wage_obligation()`;
- unknown effect/state pairs and caller-selected owner/stream/event metadata
  return structured rejection before `append_batch()`;
- scheduled rows without a named owner lifecycle remain zero-write;
- no registry/projection/clock may synthesize lifecycle truth or receipts.

## Required unblock evidence

The next implementation package must provide an owner matrix table for every
new row, RED tests for successful owner submission and all zero-write fences,
and an independent Harness profile proving append/outbox/replay/privacy and
revision behavior. Until then this package has no production code change.
