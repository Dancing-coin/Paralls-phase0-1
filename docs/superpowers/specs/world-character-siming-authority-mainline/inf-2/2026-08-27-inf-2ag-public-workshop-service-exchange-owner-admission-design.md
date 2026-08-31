# INF-2AG Public Workshop Service Exchange Owner-Admission Contract

Status: `implemented and verified narrow vertical; generic service/payment remains blocked`

## Exact Product Row

```text
committed project-visible Construction
  gameplay.construction_production.facility_public_use_enabled@1
  (facility_kind=oven, public_use_status=enabled)
-> existing ContractAuthorityService creates and fulfills one fixed
   simple_service contract
-> existing EconomyAuthorityService settles one fixed package exchange
```

This row turns the already committed public-use readiness fact into one
town-facing workshop session. It creates no new owner and changes no
Construction, Production, Inventory, Ownership, weather, maintenance, permit,
technology, social, population, treasury, or generic payment fact.

## Fixed Business Contract

| Field | Fixed value |
| --- | --- |
| package | `package:industrial-facilities:v5`, version `5.0.0`, patch `5.0.0` |
| author/trust | `author:repo` / `trust:repo` |
| source | exact project-visible `gameplay.construction_production.facility_public_use_enabled` for `facility_kind=oven`, with acquisition, operational-verification, facility/project and stream-head pins |
| service terms | `service:industrial-facility-public-workshop-session@1` |
| completion evidence | `evidence:industrial-facility-public-workshop-session@1` |
| provider | `organization:municipal-assessment-office` |
| receiver | exact `facility_acquired.payload.owner_ref` for the source facility; no caller selection |
| capability/outcome | `capability:package-declared-negotiated-exchange@1` / `outcome:industrial-facility-public-workshop-session-settlement@1` |
| binding/predicate | `binding:industrial-facility-public-workshop-session@1` / `predicate:construction-facility-public-use-enabled@1` |
| policy | `policy:industrial-facility-public-workshop-session-price@1`, fixed `12 currency:local`, `consent:mutual@1` |
| subject | `slot:facility-project@1`; proof binds committed `facility_ref` and `project_ref=facility.plot_ref` |
| target streams | Contract `gameplay:contracts`; Economy `gameplay:economy` |
| privacy | Contract and Economy owner facts are `authority_only`; source Construction evidence remains `project` |
| lifecycle | Contract active -> fulfilled; Economy debit/credit/settled; v1 terminal, no refund, reversal, compensation, retry-as-new, fanout or combined receipt |

The service means one fixed workshop session admission and completion only. It
does not grant a permit, alter facility kind/public-use state, create output,
consume material, reserve inventory, or imply a market price beyond the fixed
package policy.

## Owner, Replay And Receipt Boundaries

`ContractAuthorityService` owns `record_created`, `service_completion_recorded`
and `record_fulfilled` for this terms ref. `EconomyAuthorityService` owns the
existing package exchange vector: receiver debit, provider credit and settled
event. Each owner append returns its own `GameplayEventStore.append_batch()`
receipt. Contract and Economy projectors must each produce equal full and
checkpoint-tail replay; no combined receipt or coordinator is introduced.

The source verifier re-reads the exact public-use event, acquisition event,
operational-verification event and current facility projection. It requires
project visibility, `oven`, `enabled`, matching facility/project binding,
source revisions and current stream head. Economy resolves exactly one active
fulfilled Contract and exactly one currency account per fixed party; zero or
multiple accounts are zero-write.

## Idempotency And Zero-Write

All idempotency keys are authority-derived from the source event id/revision,
contract/economy heads, package revision, declaration digest, outcome ref and
fixed parties. Caller-supplied owner, stream, event, currency, price,
privacy, receipt, package or compensation coordinates are ignored and rejected
as invalid claims.

Unknown/inactive package, malformed or mismatched declaration/content digest,
unknown terms/evidence/outcome, wrong or multiple public-use source,
non-oven/disabled/decommissioned facility, missing or private/stale/forged
source, facility/project binding conflict, stale owner head, wrong party or
consent, missing/multiple account, insufficient funds, price mismatch,
multiple/unadmitted binding, duplicate with changed intent, revision conflict,
or any payment/material/inventory/output/permit/technology/weather/social
extension is rejected before either owner appends. An exact duplicate replays
the original owner-local receipt.

## Conflict-Matrix Decision

Disposition: `new` and disjoint. INF-1AJ owns Construction public-use status;
INF-2AG owns one Contract service and one Economy exchange sourced from that
status. INF-2AD and INF-2AE service terms, all generic payment/transfer paths,
and all market pricing are not reused. The row uses only existing owners and
the existing envelope -> SettlementPlan -> append spine.
