# INF-3S Government Drought Advisory To Municipal Assessment Contract

Status: `implemented and verified narrow vertical; generic Contract creation remains fenced`

## Product Loop

```text
committed project-visible Government drought advisory
-> existing ContractAuthority
-> one authority-only municipal drought-assessment simple_service contract
-> later independent Contract completion and INF-2AD fixed settlement
```

The advisory is a contract-admission source only. It never settles payment,
creates an Economy posting, alters weather, inventory, material, production,
maintenance, permit, population, social or Government policy truth.

## Fixed Boundary

| Field | Rule |
| --- | --- |
| capability / outcome | `capability:government-drought-advisory-municipal-assessment-contract@1` / `outcome:government-drought-advisory-municipal-assessment-contract@1` |
| source | exact project-visible `gameplay.government.drought_advisory_issued@1`, jurisdiction and advisory stream/event revision pinned |
| owner | existing `ContractAuthorityService` owns the one `simple_service` contract fact |
| terms | static `service:municipal-drought-assessment@1`, exact evidence `evidence:municipal-drought-assessment@1`, two fixed organization parties |
| parties | provider `organization:municipal-assessment-office`; receiver `organization:district-works`; caller cannot select them |
| stream/event | `gameplay:contracts`; fixed `gameplay.contract.record_created@1` only |
| privacy | source project -> target authority-only narrowing only |
| idempotency | authority-derived advisory event/revision/jurisdiction/terms key |
| receipt / replay | append-derived receipt; Contract full/checkpoint-tail projector |
| lifecycle | contract creation is terminal for this capability; service fulfillment and Economy settlement remain separate owner rows; no cancellation, compensation, fanout or retry-as-new |

## Conflict Preflight

Disposition: `new`. It does not collide with existing advisory issuance,
presentation, delivery payment, wage, or package exchange facts. Contract owns
the created contract, and the source advisory retains Government ownership.
Authority-only target scope narrows the project source. INF-2AD consumes only a
later fulfilled Contract record, not this admission event.

## Required Zero-Write

Missing/private/foreign/stale advisory; wrong stream/event/jurisdiction;
duplicate or changed duplicate; contract terms mismatch; any caller supplied
party, stream, event, privacy, receipt, or revision; Contract stream revision
conflict; and source/target replay mismatch all reject before append.

## Implementation Closure

The exact advisory-to-Contract row is implemented through the owner-bound
envelope/plan adapter and existing `GameplayEventStore.append_batch()` spine.
Focused source/privacy/revision/duplicate tests and the independent
`inf3s-government-drought-assessment-contract` Harness pass. The gate below is
retained as historical pre-implementation rationale; it is superseded for this
exact row only. Fulfillment, payment, certificate, and generic Contract paths
remain separate or fenced.

## Historical Implementation Gate (superseded for this exact row)

The existing Contract authority currently writes through its local append helper,
not the mandated `GameplayCommandEnvelope -> SettlementPlan ->
GameplayEventStore.append_batch()` path. Before this row was implemented, the
Contract owner received one exact row-specific envelope/plan append adapter
that preserved all existing contract behavior. This was not permission to
introduce a generic contract writer or router. Focused RED tests, an immutable
catalog row, independent Harness, and full/checkpoint-tail evidence were
required before implementation.
