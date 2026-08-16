# INF-2I Organization/Economy Commerce Commitment Design

Status: `implemented bounded and verified 2026-08-14`

## Scope

INF-2I formalizes one already-present, bounded commerce commitment settlement.
`CommerceAuthority` is a fixed assembly surface, not a domain truth owner or a
generic cross-domain writer. It may only submit owner-authorized fragments for
the named commitment operation through the one existing gameplay event store:

```text
CommerceAuthority -> GameplayCommandEnvelope / SettlementPlan
-> OwnerAuthorizedFragment (Organization, Economy, Inventory, optional Wage)
-> GameplayEventStore.append_batch() -> outbox -> scoped projections/replay
```

The required buyer and seller organization streams are
`gameplay:organization:{organization_ref}`. The buyer consideration stream is
`gameplay:economy`; seller custody remains on the already-required
`gameplay:inventory:{seller_organization_ref}`. When a labor reference is
present, the existing wage and contract streams are additional fixed inputs;
they do not turn this package into a general multi-owner API.

## Owner Matrix

| Fact | Existing owner | Stream | Event family | Reader / scope |
| --- | --- | --- | --- | --- |
| buyer/seller commitment acceptance | `OrganizationAuthority` | `gameplay:organization:{organization_ref}` | `gameplay.organization.commerce_commitment_accepted` | organization commerce projection; organization-scoped refs |
| buyer budget reservation and consideration pin | `EconomyAuthorityService` | `gameplay:economy` | `gameplay.economy.commerce_obligation_recorded` | `EconomyProjector`; authority-scoped account detail |
| seller custody/capacity | `InventoryAuthorityService` | `gameplay:inventory:{seller_organization_ref}` | existing commerce custody family | inventory projector and its existing scope |
| optional earned wage | `Econ1EconomyAuthority` | `gameplay:economy:wage:{worker_ref}` | `gameplay.economy.wage_accrued` | wage projector and worker scope |

`CommerceAuthority` (`actor_gameplay.commerce_authority`) owns neither row in
this table. Its sole receipt is the result of the one `append_batch()` call;
it must expose no independent receipt state, store, scheduler, or retry loop.

## Admission and Consistency

- A commitment names fixed buyer, seller, policy revision, owner references,
  complete revision vector, and idempotency key. The source vector covers every
  stream needed by the selected fixed owner rows.
- Each owner revalidates only its own pins before emitting its fragment. The
  assembly surface accepts no caller-supplied stream/event mapping.
- The append batch carries all fragment expected/read revisions and is atomic:
  a stale Organization, Economy, Inventory, Contract, or Wage revision writes
  no event and no outbox entry.
- Same key plus the identical canonical commitment replays the append result
  without writing. A changed commitment under the same key is
  `idempotency_key_reused`, zero-write, even if its stale vector would otherwise
  reject first.
- A missing/mismatched organization grant, economy reservation, account owner,
  capacity reservation, or labor contract is zero-write.

## Privacy and Replay

Public commitment projection exposes only public identifiers and evidence.
Organization projection alone may expose account-obligation, grant, reservation
and custody references. No outbox projection may disclose account balances,
amounts, or account owners. The focused evidence must prove the one append
receipt, authority/organization outbox scope, full replay, and true
checkpoint-tail replay over the exact committed streams.

## Non-goals

This package does not admit caller-open policy registration, arbitrary payment,
arbitrary cross-domain settlement, a commerce truth store, a generic owner
router, account debit/credit payment completion, a scheduler, or branch
promotion. Group simulation remains separately deferred.
