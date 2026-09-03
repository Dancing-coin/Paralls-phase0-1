# August INF A-D Formal Blocker Disposition Contract

Status: `approved formal disposition; Goal active; August INF A-D not complete`

This contract records the approved governance decision that formal blocker
disposition is not a completion substitute. It restores the mainline Goal to
`active` while preserving zero-write and independent owner-admission gates for
all unformed rows.

## Verified Narrow Verticals

The following rows remain valid only within their own immutable owner contracts,
package and descriptor pins, privacy, revision, idempotency, receipt, replay,
and terminal boundaries:

- INF-1AE facility repair;
- INF-1AF `bakery -> bakery_reinforced`;
- INF-1AG `oven -> kiln` and `mill -> mill_reinforced`;
- INF-1AH `mill_reinforced -> facility_decommissioned@1`;
- INF-1AI completed Construction Production run -> facility operational
  verification;
- INF-1AI committed completed Production run -> Construction facility
  operational verification;
- INF-2AA delivery payment, INF-2AB tax payment, and INF-2AC
  package-declared negotiated exchange;
- INF-2AD fulfilled municipal drought-assessment service -> fixed Economy
  package exchange settlement;
- INF-2AE completed facility operational verification -> fixed commissioning-
  review service Contract and Economy exchange;
- INF-2AF public-project commitment -> fixed owner-derived budget commitment;
- INF-2AG exact public-workshop service -> fixed Contract/Economy exchange;
- INF-2AH public-project budget commitment -> fixed owner-derived reservation;
- INF-2AI completed public-workshop activity + matching reservation -> fixed
  authority-only budget consumption marker;
- INF-2AK consumed public-project budget + funded execution -> fixed
  authority-only budget close marker;
- INF-2AN committed Organization grain intake -> fixed authority-only Economy
  acceptance marker;
- INF-2AO committed Inventory production-output custody -> fixed authority-only
  Economy market-eligibility marker;
- INF-3Q `weather:drought -> Survival dehydrated`;
- INF-3R `weather:drought -> Government drought advisory issued`;
- INF-3S Government drought advisory -> fixed Contract municipal-assessment
  service admission;
- INF-3T active INF-3S municipal-assessment Contract -> fixed Contract
  completion/fulfilled pair;
- INF-3U exact INF-4U certificate -> fixed authority-only Government advisory
  assessment acknowledgment;
- INF-3W `weather:rain` front -> fixed Ecology unique damaged-crop recovery;
- INF-4V/W committed Production completion -> Organization work-history
  acceptance and terminal work-order fulfillment;
- INF-4AG/AH/AI public-workshop activity -> Government notice and committed
  two-party handshake -> actor-private shared-experience history;
- INF-4AK funded public-project execution -> fixed Government authority-only
  administrative acknowledgment;
- INF-4AJ exact funded public-project activity/budget execution -> Organization
  project execution fact;
- INF-4T committed Production evidence -> Economy wage, plus separately
  admitted Government/Organization rows.

These rows are references, not generic fallback authorities.

## Remaining Dispositions

| Area | Disposition | Boundary |
| --- | --- | --- |
| INF-1 | INF-1AH, INF-1AI, INF-1AJ, INF-1AK and INF-1AL are implemented and verified; remaining unformed slots are `owner-contract blocked`; duplicate/closed shapes stay closed | no fourth owner discovery and no inferred Construction outcome |
| INF-2 | Slot A is closed for the exact INF-2AG public-workshop exchange, INF-2AH reservation, INF-2AI consumption, INF-2AK budget close and INF-2AN grain-intake acceptance marker; Slot B is closed only for INF-2AL public milling; Slot C and generic payment/transfer/settlement remain `owner-contract blocked` or `unimplemented` | existing INF-2 rows cannot be generalized |
| INF-3 | INF-3Q, INF-3R, INF-3S, INF-3T, INF-3U, INF-3V, INF-3W, INF-3AA and INF-3AB are implemented and verified; other unlisted target-owner edges are `owner-contract blocked`; `drought_process_advanced` cannot replace weather-front evidence | no generic consumer registry, router, fanout, retry, or compensation |
| INF-4 | INF-4T, INF-4U, INF-4V, INF-4W, INF-4AG, INF-4AH, INF-4AI, INF-4AJ, INF-4AK, INF-4AL, INF-4AM, INF-4AO and INF-4AP are implemented and verified; new branch consequences and population/social/group truth are `owner-contract blocked` or `unimplemented` | branch candidates cannot replace committed Production/domain truth |

## Zero-Write And Continuation Rules

Every remaining row rejects before mutation when source, existing owner,
outcome, package, binding, privacy, revision, idempotency, receipt, replay,
terminal, correction, or compensation semantics are missing, unknown,
private, stale, ambiguous, conflicting, duplicate, or caller-selected.

The next row may begin only from an explicit:

```text
one committed source event/state
-> one existing truth owner
-> one exact outcome/event vector
```

That row must separately define source/target revisions, subject and privacy
binding, owner-derived idempotency, append-derived receipt, full replay,
checkpoint-tail replay, and terminal/correction/compensation semantics.

This disposition does not authorize a generic payment/transfer/transform/
promotion/settlement authority, router, registry, coordinator, writer, second
runtime/store/bus/clock/scheduler, or a completion shortcut. The approved
autonomous mandate may admit a strictly row-specific new owner only after its
owner-operation conflict-matrix preflight, full contract, and evidence plan.
INF-P remains a platform prerequisite and is not counted as August INF A-D
business completion.

Package-declared economic rows also retain a fail-closed rule: if a declaration
does not resolve exactly one immutable economic outcome, the owner must reject
before account lookup or append. Currency, amount, party, account, and
settlement terms may not be inferred from source content or defaults.

The package exchange definition schema also makes privacy, compensation,
source-selection and capability references explicit required fields; omitted
policy metadata is rejected before admission.

Its `eligibility_refs` array is likewise required and may be empty only when
the author explicitly supplies `[]`; omission is not a default.

## Approval Effect

The mainline Goal is `active`. August INF A-D remains `not complete`. The
[autonomous row-resolution mandate](2026-08-26-autonomous-row-resolution-mandate-design.md)
authorizes evidence-led row selection and delivery without per-row waiting.
Every row must pass the [owner-operation conflict matrix](2026-08-26-owner-operation-conflict-matrix-design.md)
and remain fully traceable; no generic authority is admitted.

The later INF-4AI actor-private P5 expression amendment is a shared-platform
closure for one exact Social row, not a generic social capability. Its event
schema, catalog scope, source verifier, append receipt, privacy, and replay
evidence are recorded separately; remaining social, attendance, population,
and group rows retain their original dispositions.

## Current Ordered Ledger (2026-08-29)

The current implementation ledger, in order, is:

```text
INF-1: AE, AF, AG, AH, AI, AJ, AK, AL, AM = implemented narrow verticals
INF-2: AA, AB, AC, AD, AE, AF, AG, AH, AI, AK, AL, AM, AN, AO = implemented narrow verticals
INF-3: Q, R, S, T, U, V, W, AA, AB = implemented narrow verticals
INF-4: T, U, V, W, AG, AH, AI, AJ, AK, AL, AM, AO, AP = implemented narrow verticals
```

This is an index of exact rows, not a generic capability claim. INF-2 Slot C,
remaining INF-1 shapes, unlisted INF-3 target edges, and INF-4 generic
branch/population/social/group outcomes remain separately blocked or
unimplemented. INF-P remains a prerequisite and August INF A-D remains
`not complete`.

The 2026-08-29 continuation adds INF-2AN's exact grain-intake acceptance
marker and the 2026-09-01 continuation adds INF-2AO's exact production-output
market-eligibility marker. It records INF-3AB/INF-4AP as the latest Ecology-to-Inventory and
Inventory-to-Organization rows. These are fixed, owner-bound rows only; they
do not open generic payment, transfer, consumer, activity, social, population,
or group semantics.

The same continuation records INF-4AO's actor-private acknowledgment row and
keeps the complete current INF-4 ledger aligned with the ordered audit.

## 2026-09-01 Ordered Continuation

INF-2AO is part of the implemented ledger: one committed, project-visible
Inventory `production_output_custody@1` source yields one authority-only
Economy `production_output_market_eligible@1` marker. It adds no price,
currency, account, buyer, receiver, payment, transfer, or market-order fact.
Its catalog/descriptor, source fences, append receipt, idempotency and
full/checkpoint-tail replay evidence are verified. The next INF-3 -> INF-4
scan found no new legal tuple; remaining row-level blockers stay in force.
