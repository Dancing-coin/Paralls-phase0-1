# INF-1P Construction Maintenance State-Action Admission Audit

Status: `implemented bounded and verified; transform remains blocked`

## Decision

The existing Construction maintenance row is a durable expiry lifecycle, not a
general state-action contract. It has one exact owner and stream:

| Field | Existing contract |
| --- | --- |
| owner | `ConstructionProductionAuthority` |
| stream | `gameplay:construction_production:{facility_ref}` |
| apply event | `gameplay.construction_production.maintenance_state_applied` |
| obligation open | `gameplay.construction_production.maintenance_state_obligation_opened` |
| terminal events | `maintenance_state_expired`, `maintenance_state_obligation_settled` |
| projection | project-scoped `maintenance_states` |
| receipt | append-derived coordinator receipt |

Inspection found no existing Construction repair or transform event family.
The only existing mutation that removes `state:maintenance_due` is the
policy-owned expiry event. Reusing that event as a semantic "dispel" would
falsify its causal meaning.

The existing Construction owner, facility stream, state projection, committed
maintenance-obligation identity and append-derived receipt do support one
different, bounded action: a semantic disposition may clear the currently
projected maintenance state while cancelling its exact committed expiry
obligation in the same append batch. It does not mean repair, payment,
materials or service completion.

| Contract field | INF-1P dispel value |
| --- | --- |
| effect | `effect:maintenance_state_dispel` |
| source state | `state:maintenance_due` only |
| owner | `ConstructionProductionAuthority` |
| stream | `gameplay:construction_production:{facility_ref}` |
| action event | `gameplay.construction_production.maintenance_state_dispelled` |
| terminal event | `gameplay.construction_production.maintenance_state_obligation_cancelled` |
| projection | remove only the matching active project-scoped maintenance state |
| receipt | existing `ObligationSettlementCoordinator.cancel()` receipt from one append batch |

The semantic bridge remains proposal-only. It can submit only this fixed
contract and only after checking the committed maintenance-state application
and exact open obligation. It evaluates the closed `StateDefinition` dispel
policy before it asks Construction for a fragment. It cannot submit a
caller-selected Construction event, state, stream, transform target or
cancellation reason.

## Required unblock contract

A future Construction transform package may start only when a concrete
existing Construction business action owns all of the following:

1. an action source and permitted actor;
2. a named construction stream event family distinct from expiry;
3. a project-scoped projection meaning for the resulting facility state;
4. revision and idempotency rules;
5. privacy-safe outbox shape, append-derived receipt and replay reader; and
6. a semantic effect/state row that maps to that exact action, rather than a
   caller-selected clear operation.

`effect:state_dispel` remains Survival-only. The Construction-specific
`effect:maintenance_state_dispel` is not a generic action row. Transform and
every other Construction action input remain unsupported and zero-write.

## Evidence reviewed

- `infra-construction-maintenance-state-obligation` proves apply -> open ->
  expired/settled, full/checkpoint-tail replay, revision/privacy/idempotency
  and unsupported retry/cancel/compensation zero-write.
- `infra-state-action-lifecycle-closure` proves exactly the three Survival
  source states and fixed `state:recovering` transform target; it does not
  authorize Construction. INF-1P must add its own independent evidence.
