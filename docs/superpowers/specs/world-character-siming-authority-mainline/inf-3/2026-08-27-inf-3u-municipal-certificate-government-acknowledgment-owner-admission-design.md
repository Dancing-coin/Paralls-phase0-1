# INF-3U Municipal Certificate Government Acknowledgment Owner-Admission Contract

Status: `implemented narrow vertical; August INF A-D remain not complete`

## Product Loop

```text
exact authority-only INF-4U municipal assessment certificate title
-> existing GovernmentAuthority
-> one authority-only assessment acknowledgment on the originating drought advisory
```

This closes the Government-owned administrative follow-up after the assessment
certificate has been granted. It records only that Government acknowledged the
already-certified assessment for its own advisory. It does not make a drought
restriction, permit, tax, payment, material, inventory, production, weather,
maintenance, social, population, public presentation, correction, reversal, or
compensation fact.

## Exact Contract

| Field | Fixed rule |
| --- | --- |
| capability / outcome | `capability:government-drought-assessment-acknowledgment@1` / `outcome:government-drought-assessment-acknowledged@1` |
| descriptor | `descriptor:government-drought-assessment-acknowledgment@1`, same immutable revision; predicate `predicate:ownership-municipal-drought-assessment-certificate@1`; effect `effect:government-drought-assessment-acknowledged@1` |
| catalog | `inf:ownership-certificate-government-drought-assessment-acknowledgment@1`, kind `settlement` |
| source | exact authority-only INF-4U `gameplay.ownership.right_granted@1` certificate event on `gameplay:ownership`, fixed deterministic right/asset/holder, contract id and advisory event id |
| source pins | certificate event id/revision; current Ownership head; exact completed municipal Contract record and current Contract head; original project-visible advisory event/revision/jurisdiction and current advisory stream head |
| target owner | existing `GovernmentAuthority` (`actor_gameplay.government_domain`) only |
| target stream / vector | `gameplay:government:advisory:{jurisdiction_ref}`; exactly one authority-only `gameplay.government.drought_assessment_acknowledged@1` |
| payload | fixed acknowledgment ref, certificate event/right/asset, Contract id, advisory id/ref and the fixed policy `policy:government-drought-assessment-acknowledgment@1`; caller supplies none of these coordinates |
| privacy | source and target are authority-only. The existing project advisory view/WebSocket presentation must not expose the acknowledgment. |
| idempotency | `government:drought-assessment-acknowledgment:{certificate_event_id}:{certificate_revision}:{contract_head}:{advisory_revision}:{government_head}:v1`, derived and compared exactly by GovernmentAuthority |
| receipt / replay | one `GameplayEventStore.append_batch()` receipt; new fixed authority-only Government acknowledgment full/checkpoint-tail view |
| package binding | `not_applicable`; INF-4U certificate and earlier Contract package pins remain immutable source evidence only |
| lifecycle | v1 terminal one acknowledgment per certificate; no retry-as-new, revoke, reopen, correction, compensation, fanout, combined receipt, or downstream automatic action |

## Conflict-Matrix Preflight

Disposition: `new`.

INF-3R owns project-visible advisory issuance, INF-3S/3T own Contract creation
and fulfillment, INF-2AD owns Economy settlement, and INF-4U owns the
certificate title. INF-3U owns only the distinct Government acknowledgment
fact. Its event family, authority-only projection, source certificate predicate,
receipt, replay reader, idempotency, and terminal semantics are all disjoint.

Rejected alternatives:

- Treat the certificate as a public advisory update: rejected because the
  authority-only source cannot widen privacy.
- Make certificate issuance automatically append Government acknowledgement:
  rejected because ownership and Government retain independent receipts.
- Reuse advisory issuance or generic Government policy registration: rejected
  because neither represents acknowledgment of a certified assessment.

## Required Zero-Write

Reject before append: missing/foreign/private/wrong-type certificate; wrong
right, asset, holder, contract or advisory binding; incomplete/unfulfilled/
stale Contract; missing/private/stale/foreign advisory; Ownership, Contract,
advisory, or target Government revision conflict; duplicate/changed duplicate;
catalog or descriptor mismatch; caller-selected source/owner/stream/event/
privacy/receipt/policy; or any multiple-acknowledgment condition.

## Implementation Boundary

Add one strict Government intent, one fixed owner method, one immutable catalog
row/descriptor, and one authority-only acknowledgment replay view. Use only
`GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`.
Do not alter certificate issuance, package content, project advisory presentation,
or any generic Government method.

## Implementation Evidence

Focused source/privacy/revision/idempotency tests, immutable catalog/descriptor
checks, the independent `inf3u-municipal-certificate-government-acknowledgment`
Harness, municipal closed-loop Harness, and continuation gate pass. The fixed
authority acknowledgment view has full/checkpoint-tail replay equivalence, while
the existing project advisory view and WebSocket presentation remain unchanged.
An authorized existing advisory subscriber receives no delivery when the
acknowledgment transaction is dispatched because its batch has no outbox entry.
The authority view retains the acknowledgement Government stream revision plus
the pinned Ownership and Contract source revisions; the original advisory
revision remains in the fixed acknowledgment event payload.
