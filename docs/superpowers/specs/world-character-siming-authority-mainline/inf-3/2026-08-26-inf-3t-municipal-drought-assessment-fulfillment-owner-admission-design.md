# INF-3T Municipal Drought Assessment Fulfillment Owner-Admission Contract

Status: `implemented narrow vertical; August INF A-D remain not complete`

## Product Loop

```text
committed INF-3S authority-only municipal assessment Contract record, active
-> existing ContractAuthorityService
-> one fixed service-completion record plus fulfilled Contract record
-> separately admitted INF-2AD settlement and INF-4U certificate consumers
```

The row closes the Contract-owned completion step deliberately left between
INF-3S admission and the later Economy and Ownership consumers. It records no
investigation finding outside the Contract completion record. It does not pay,
transfer inventory/right, change weather, issue Government policy, alter a
facility, create material/production output, add a permit/technology fact, or
append any cross-owner event.

## Exact Contract

| Field | Fixed rule |
| --- | --- |
| capability / outcome | `capability:municipal-drought-assessment-fulfillment@1` / `outcome:municipal-drought-assessment-fulfilled@1` |
| descriptor | `descriptor:municipal-drought-assessment-fulfillment@1`, same immutable revision; predicate `predicate:contract-municipal-drought-assessment-active@1`; effect `effect:municipal-drought-assessment-fulfilled@1` |
| catalog | `inf:municipal-drought-assessment-contract-fulfillment@1`, kind `contract_admission` |
| owner | existing `ContractAuthorityService` (`actor_gameplay.contract_domain`) only |
| committed source | one active ContractProjection record whose source event is exact INF-3S `gameplay.contract.record_created@1`, with `service:municipal-drought-assessment@1`, `simple_service`, evidence kind `evidence:municipal-drought-assessment@1`, provider `organization:municipal-assessment-office`, receiver `organization:district-works`, and an exact advisory-derived contract id/payload |
| source pins | source creation event id/revision, advisory event id/revision/jurisdiction source vector in that event, current Contract stream head, current active Contract revision, source event visibility `authority_only`, and `ContractProjector` record must all agree |
| fixed policy | `policy:municipal-drought-assessment-fulfillment@1`; it is executed only by the already-configured fixed Contract policy principal `authority:municipal-assessment`. Neither principal nor policy is caller input. |
| target stream / vector | `gameplay:contracts`; exactly `gameplay.contract.service_completion_recorded@1` followed by `gameplay.contract.record_fulfilled@1`, both authority-only |
| derived evidence | `evidence:municipal-drought-assessment:completed:{contract_id}`. The caller supplies no evidence kind or evidence ref. |
| idempotency | `contract:municipal-drought-assessment:fulfillment:{contract_created_event_id}:{contract_created_revision}:{advisory_revision}:{contract_stream_head}:v1`, derived and compared exactly by ContractAuthorityService; the first completion event also stores a digest of the complete strict intent, so a changed command, correlation, source pin, or submitted-at value is zero-write rather than a replay |
| receipt / replay | the one `GameplayEventStore.append_batch()` receipt; `ContractProjector` full replay equals checkpoint-tail replay |
| package binding | `not_applicable`: INF-3S fixes terms and evidence directly. This row creates no manifest, package registry entry, or package mutation. |
| lifecycle | v1 terminal `active -> fulfilled`; no termination, reopen, retry-as-new, correction, compensation, fanout, payment, or combined receipt |

## Conflict-Matrix Preflight

Disposition: `new`.

The claim is the Contract lifecycle fact `active municipal assessment service ->
fulfilled municipal assessment service`. INF-3S claims only creation of the
active record; INF-2AD claims a later Economy settlement; INF-4U claims a later
Ownership certificate. Existing generic `complete_simple_service_by_policy()`
is a bounded Contract foundation but is not an admitted municipal operation: it
accepts caller-supplied contract/evidence/policy coordinates. INF-3T fixes those
coordinates, narrows its source predicate, derives the evidence, and records a
separate immutable catalog/descriptor identity. No event, privacy, receipt,
replay, or lifecycle collision remains after that partition.

Rejected alternatives:

- Government advisory directly fulfills the service: rejected because an
  advisory is a request/admission fact, not completion evidence.
- INF-2AD settlement implies completion: rejected because Economy payment is
  downstream of Contract truth and cannot create it.
- a generic service-completion route: rejected because arbitrary terms,
  evidence, policy principals, and lifecycle semantics would recreate a generic
  contract writer.

## Required Zero-Write

Before append, reject missing, unknown, wrong-stream, wrong-type, wrong-terms,
wrong-party, wrong-evidence-kind, non-INF-3S-origin, private, foreign,
ambiguous, inactive, fulfilled, terminated, stale, source-vector conflicting,
Contract-head conflicting, policy-principal unavailable, descriptor/catalog
mismatched, duplicate-with-changed-payload, or caller-supplied evidence/policy/
owner/stream/event/privacy/receipt coordinates. Rejection writes neither
completion nor fulfilled event.

The existing generic `create_contract()`, `complete_simple_service_by_policy()`,
`fulfill_contract_by_policy()`, and `terminate_contract_by_policy()` helpers
must reject these exact municipal terms before append. They remain available for
their other registered terms, but cannot reserve the deterministic Contract id
or provide alternate completion or terminal paths for this row.

## Implementation Evidence

The only new behavior is one row-specific intent and ContractAuthorityService
method that validates the exact source before constructing a two-event
`GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`
batch. It reuses the existing Contract projector and EventStore. It does not
modify INF-3S, frozen INF-2AD package content, INF-4U certificate contract, or
any generic Contract API. Focused Contract/adjacent-row regression tests, the
independent `inf3t-municipal-drought-assessment-fulfillment` Harness, and the
continuation gate pass. Full and checkpoint-tail Contract projection rebuilds
are identical after the fixed two-event batch.

A static runtime audit of the municipal terms ref and the four generic Contract
entry points found no remaining non-test caller. Python `compileall` completed
for `backend/app`; the only generic references are the Contract owner's fenced
methods and their zero-write tests.
