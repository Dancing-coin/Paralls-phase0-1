# INF-3 Specification Tree

Status: `INF-3 finite ecology lifecycle, propagation, grain harvest, grain custody and recovery rows are implemented and verified; remaining unlisted edges are formally blocked; generic propagation and broader domain fanout remain incomplete`

The approved [formal blocker disposition contract](../2026-08-26-august-inf-formal-blocker-disposition-contract.md)
keeps the Goal active while unlisted target-owner edges remain blocked.
`drought_process_advanced` cannot substitute for the committed weather-front
source; no generic consumer registry, router, fanout, retry, or compensation
path is admitted.

1. [INF-3 ecology and disaster authority design](2026-08-12-inf-3-ecology-disaster-authority-design.md)
2. [INF-3R regional ecology propagation expansion design](2026-08-12-inf-3r-regional-ecology-propagation-expansion-design.md) - verified one fixed frost-to-due-production-finish edge only
3. [INF-3R-A frost-production admission design](2026-08-13-inf-3r-a-frost-production-admission-design.md) - verified existing-owner source/target read contracts only
4. [INF-3R-B production recipe admission design](2026-08-13-inf-3r-b-production-recipe-admission-design.md) - verified existing construction recipe read contract only
5. [INF-3X regional ecology truth and lifecycle design](2026-08-12-inf-3x-regional-ecology-truth-and-lifecycle-design.md) - verified canonical regional records and retirement rows on the existing ecology owner/stream
6. [INF-3Y hazard propagation consumer contract design](2026-08-12-inf-3y-hazard-propagation-consumer-contract-design.md) - verified one canonical frost -> construction finish edge only
7. [INF-3B seasonal Construction maintenance edge](2026-08-14-inf-3b-seasonal-construction-maintenance-edge-design.md) - verified one non-frost process -> existing Construction owner row
8. [INF-3D Ecology weather-front path propagation](2026-08-15-inf-3d-ecology-weather-front-path-propagation-design.md) - verified bounded explicit three-hop Ecology-only path; no fanout or non-Ecology write in this package
9. [INF-3E Ecology weather-front fanout](2026-08-15-inf-3e-ecology-weather-front-fanout-design.md) - verified bounded explicit three-target Ecology-only fanout; no multi-round fanout or non-Ecology write in this package
10. [INF-3F Ecology weather-front wave fanout](2026-08-15-inf-3f-ecology-weather-front-wave-fanout-design.md) - verified bounded two-wave, six-edge Ecology-only fanout; no non-Ecology write in this package
11. [INF-3G Weather-front Construction consumer edge](2026-08-15-inf-3g-weather-front-construction-edge-design.md) - verified one exact project-visible weather-front -> existing Construction maintenance edge; no generic consumer registry or additional domain writer
12. [INF-3H Weather-front Construction consumer fanout](2026-08-15-inf-3h-weather-front-construction-fanout-design.md) - verified one fixed two-facility same-owner fanout in one append batch; no generic fanout registry or additional domain writer
13. [INF-3I Weather-front Organization supply edge](2026-08-15-inf-3i-weather-front-organization-supply-edge-design.md) - verified one fixed existing-Organization commerce commitment edge; no generic consumer registry or arbitrary settlement
14. [INF-3J Weather-front Economy quote edge](2026-08-15-inf-3j-weather-front-economy-quote-edge-design.md) - verified one source-pinned project-visible weather-front -> existing Economy quote edge; no generic pricing or consumer registry
15. [INF-3K Ecology drought process](2026-08-16-inf-3k-ecology-drought-process-design.md) - verified bounded second Ecology process; no consumer or cross-domain write
16. [INF-3L weather-front owner-contract matrix](2026-08-16-inf-3l-weather-front-owner-contract-matrix-design.md) - verified finite catalog admission for the existing Construction, Organization and Economy consumer rows; not generic fanout
17. [INF-3M event-derived weather-front planner](2026-08-16-inf-3m-ecology-weather-front-event-derived-planner-design.md) - verified deterministic canonical-neighbor proposal and bounded Ecology-only append; not autonomous scheduling or generic graph propagation
18. [INF-3N weather-front Economy quote fanout](2026-08-16-inf-3n-weather-front-economy-quote-fanout-design.md) - verified one exact weather-front -> two distinct existing Economy quotes in one owner batch; not generic fanout, pricing or consumer registration
19. [INF-3O weather-front Organization supply fanout](2026-08-16-inf-3o-weather-front-organization-supply-fanout-design.md) - verified one exact weather-front -> two distinct existing Organization commitments in one owner batch; not generic fanout or arbitrary settlement
20. [INF-C4 ecology consumer admission contract](../2026-08-16-inf-c4-ecology-consumer-admission-contract-design.md) - verified finite read-only pre-fragment checks reused by existing Construction and Organization owners; not a consumer registry or target-domain writer
21. [INF-3Q unlisted consumer owner-contract audit](2026-08-17-inf-3q-unlisted-consumer-owner-contract-audit.md) - durable blocker evidence for why this exact row required admission; all other unlisted consumer edges remain blocked
22. [INF-3Q drought-to-dehydration Owner-Admission Contract](2026-08-17-inf-3q-drought-survival-dehydration-owner-admission-design.md) - verified one exact `weather:drought -> Survival dehydrated` edge with project source/assignment pins, fixed Survival apply/open events, receipt/replay, and no compensation or fanout
23. [INF-3R drought-to-Government advisory Owner-Admission Contract](2026-08-26-inf-3r-drought-government-advisory-owner-admission-design.md) - verified exact project-visible drought front -> existing Government advisory issuance; no restriction, payment, material, population, compensation, or fanout semantics
24. [INF-3R Government advisory presentation contract](2026-08-26-inf-3r-government-drought-advisory-presentation-contract.md) - fixed project/jurisdiction read-side delivery through server-issued WebSocket scope; no actor-scope substitution or truth write
25. [INF-3S Government advisory municipal assessment contract](2026-08-26-inf-3s-government-drought-advisory-municipal-assessment-contract-design.md) - implemented fixed authority-only Contract admission; no payment, generic contract writer, or advisory fanout
26. [INF-3T municipal assessment fulfillment contract](2026-08-26-inf-3t-municipal-drought-assessment-fulfillment-owner-admission-design.md) - implemented exact active municipal assessment Contract -> fixed Contract completion/fulfillment pair; no payment, generic contract completion, or fanout
27. [INF-3U municipal certificate Government acknowledgment contract](2026-08-27-inf-3u-municipal-certificate-government-acknowledgment-owner-admission-design.md) - implemented exact certificate -> authority-only Government advisory acknowledgment; no project scope widening or Government policy outcome

INF-3Q evidence: [independent dehydration Harness report](../../../../../.harness/verification/infra-weather-front-survival-dehydration-report.json).

INF-3R evidence: [independent Government advisory Harness report](../../../../../.harness/verification/infra-weather-front-government-drought-advisory-report.json).

INF-3R presentation evidence: [independent Government advisory presentation Harness report](../../../../../.harness/verification/infra-weather-front-government-drought-advisory-presentation-report.json).

INF-3T evidence: [independent municipal assessment fulfillment Harness report](../../../../../.harness/verification/inf3t-municipal-drought-assessment-fulfillment-report.json).

Municipal drought closed-loop evidence: [independent chain Harness report](../../../../../.harness/verification/inf-municipal-drought-closed-loop-report.json).

INF-3U evidence: [independent Government acknowledgment Harness report](../../../../../.harness/verification/inf3u-municipal-certificate-government-acknowledgment-report.json).

INF-3L/INF-3N/INF-3O evidence is [weather-front owner-contract matrix report](../../../../../.harness/verification/infra-ecology-weather-front-owner-contract-matrix-report.json). It enforces the existing Construction, Organization and Economy weather-front rows, including the fixed two-quote Economy fanout and fixed two-Organization supply fanout, as a finite catalog; all edges remain fixed and owner-bound.

 Evidence: [ecology focused Harness report](../../../../../.harness/verification/infra-ecology-disaster-report.json), [INF-3R-A admission report](../../../../../.harness/verification/infra-frost-production-admission-report.json), [INF-3R-B recipe report](../../../../../.harness/verification/infra-frost-production-recipe-admission-report.json), [INF-3R edge report](../../../../../.harness/verification/infra-regional-ecology-report.json), [INF-3X truth report](../../../../../.harness/verification/infra-regional-ecology-truth-report.json), [seasonal process report](../../../../../.harness/verification/infra-ecology-seasonal-process-report.json), [weather-front report](../../../../../.harness/verification/infra-ecology-weather-front-propagation-report.json), [INF-3D path report](../../../../../.harness/verification/infra-ecology-weather-front-path-propagation-report.json), [INF-3E fanout report](../../../../../.harness/verification/infra-ecology-weather-front-fanout-report.json), [INF-3F wave-fanout report](../../../../../.harness/verification/infra-ecology-weather-front-wave-fanout-report.json), [INF-3M event-derived planner report](../../../../../.harness/verification/infra-ecology-weather-front-event-derived-planner-report.json), [INF-3G report](../../../../../.harness/verification/infra-ecology-weather-front-construction-edge-report.json), [INF-3H report](../../../../../.harness/verification/infra-ecology-weather-front-construction-fanout-report.json), [INF-3I report](../../../../../.harness/verification/infra-ecology-weather-front-organization-supply-edge-report.json), [INF-3J report](../../../../../.harness/verification/infra-ecology-weather-front-economy-quote-edge-report.json), [INF-3N report](../../../../../.harness/verification/infra-ecology-weather-front-economy-quote-fanout-report.json), [INF-3O report](../../../../../.harness/verification/infra-ecology-weather-front-organization-supply-fanout-report.json), [INF-C4 admission report](../../../../../.harness/verification/infra-ecology-consumer-admission-contract-report.json), [INF-3Y report](../../../../../.harness/verification/infra-hazard-propagation-report.json), [seasonal maintenance report](../../../../../.harness/verification/infra-seasonal-construction-maintenance-report.json), and [continuation gate report](../../../../../.harness/verification/infra-continuation-gate-report.json). INF-3I, INF-3J, INF-3N and INF-3O add exact owner-bound consumer edges only. INF-C4 validates finite existing rows before their owner work. None of these authorize a generic consumer registry, arbitrary fanout, or arbitrary cross-domain settlement.

The [2026-08-20 candidate register](2026-08-20-inf-3-owner-admission-candidate-register.md) and [plan](../../../plans/world-character-siming-authority-mainline/inf-3/2026-08-20-inf-3-owner-admission-candidate-plan.md) preserve the finite map and list three blocked/unformed slots. No new Ecology source-to-owner edge is approval-ready; drought-process substitution and additional weather consumers remain zero-write.

## INF-3V Weather Rain -> Survival Hydration

`INF-3V` is an implemented narrow existing-owner consumer edge. A committed,
project-visible Ecology `weather_front.propagated` event with the exact
`weather:rain` source and a matching active profile-region assignment produces
the existing Survival `state:hydrated` plus scheduled obligation vector.
Focused tests and the independent `inf3v-weather-front-survival-hydration`
Harness cover source/assignment privacy, revisions, duplicate, receipt,
full/checkpoint-tail replay, expiry, and explicit rejection of
`drought_process_advanced`. No generic weather consumer, fanout, router,
compensation or cross-domain writer is admitted.

Status: `implemented narrow vertical; Goal active; August INF A-D not complete`.

The focused suite and independent Harness are green (`20 passed` including
the catalog regression). The row is a disjoint `weather:rain` partition;
existing cold, heat, and drought rows remain separate and no unlisted weather
edge is inferred.

## INF-3W Weather Rain -> Crop Recovery

`INF-3W` is an implemented narrow Ecology row. One committed project-visible
`weather:rain` front recovers exactly one owner-derived unique damaged crop in
its target region by fixed `+5` health capped at `100`. The event uses the
existing `crop.recorded` family only through its fixed provenance partition.
Zero/multiple crops, healthy crops, wrong/private/stale weather, changed
duplicates and `drought_process_advanced` source substitution are zero-write.
It creates no fanout, inventory, production, payment, material, or generic
crop recovery behavior.

## INF-3 Rain Crop-Recovery Disposition (Historical, Superseded)

The earlier review recorded this shape as `owner-contract blocked` while the
crop selector, damaged predicate, recovery policy, provenance partition, and
repeat rule were still missing. That blocker is historical and was superseded
by the implemented INF-3W exact unique-crop row documented above. The original
blocker packet remains an audit trail only; it does not describe the current
INF-3W disposition. `drought_process_advanced` remains inadmissible as a
source or substitute.

## 2026-08-28 Current Lane Checkpoint

INF-3's finite ecology lifecycle, weather-front map, drought Government
advisory, rain hydration, and rain crop-recovery rows remain implemented and
verified. No additional target-owner edge is formed from current committed
facts. `drought_process_advanced` cannot substitute for a weather-front
source, and generic consumer, fanout, retry, compensation, or router behavior
remains blocked. Current verification is `1246 passed` for the keyword-selected
INF/INFRA collection and `4004 passed` for the repository-root suite. Goal
remains active; August INF A-D remains not complete.

## 2026-08-28 INF-3 Grain Harvest

`INF-3 Grain Harvest` is an implemented narrow Ecology vertical. One committed,
project-visible `grain_crop.admitted` source with fixed
`species=grain:wheat`, `maturity_status=mature`, `yield_quantity=10`, and
exact plot/project binding yields one Ecology-owned `grain_harvested` event
with fixed `item_definition=grain:wheat@1`. The owner-derived idempotency key,
project privacy, exact revision pins, append receipt, full/checkpoint-tail
replay, and zero-write unknown/private/stale/ambiguous/duplicate paths are
verified by the focused suite and the independent `inf3-grain-harvest`
Harness.

This row does not add an Inventory writer, Economy writer, generic harvest API,
material conversion system, fanout, router, or compensation path. The earlier
[grain harvest blocker](2026-08-28-inf-3-grain-harvest-custody-source-blocker.md)
is retained as historical traceability only.

## 2026-08-28 INF-3AA Rain Water Resource Recovery

`INF-3AA` is an implemented narrow Ecology vertical. One committed,
project-visible `weather:rain` front plus exactly one target-region
`substance:water` ResourceNode below the fixed cap records one `resource.recorded`
recovery with `+10` quantity capped at `100`. The owner-derived source/resource
revision fence, project privacy, idempotency, append receipt, zero-write cases,
and full/checkpoint-tail replay are covered by the focused suite and the
independent `inf3aa-weather-rain-water-resource-recovery` Harness. Seasonal
regeneration, drought process, crop recovery, material conversion, Inventory,
Economy, fanout, and generic resource recovery remain separate and unchanged.

The replay reader also rejects forged `descriptor_revision` or terminal pins;
full and checkpoint-tail replay therefore fail closed on contract metadata
tampering as well as source/resource tampering.

The recovery additionally rejects authority-only source resources before append,
and replay revalidates the project-visible prior resource record. Private source
provenance therefore cannot become a project-scoped recovery fact.

## 2026-08-29 INF-3AB Grain Custody Disposition

The next candidate, `grain_harvested@1 -> Inventory custody`, is now an
implemented narrow vertical. It uses the fixed holder
`organization:district-milling-cooperative`, fixed destination
`container:district-milling-cooperative:grain-intake`, registered item
`grain:wheat@1`, quantity `10`, owner-derived item id, project privacy, and
append-derived receipt. No caller value, fixture, plot name, or generic output
receipt fills these fields. The original blocker and next gates are retained
as historical traceability in the
[INF-3AB blocker](2026-08-29-inf-3ab-grain-harvest-inventory-custody-blocker.md)
and its [plan](../../../plans/world-character-siming-authority-mainline/inf-3/2026-08-29-inf-3ab-grain-harvest-inventory-custody-blocker-plan.md).
The row-specific `grain_harvest_custody_view_for()` reader validates the source
event and produces equal full/checkpoint-tail projection digests.

The closed `harvest_to_custody@1` family is not promoted by this row. Only the
committed wheat source/content tuple exists; no second immutable harvest
manifest or Ecology source fact is present. Synthetic in-memory source
mutation is explicitly excluded from genericity evidence, and the aggregate
family verifier keeps the family `bounded_adapter` until two real,
digest-valid manifest/source pairs pass the same adapter.

## 2026-09-01 Ordered Continuation After INF-2AO

The post-INF-2AO scan found no new committed Ecology source paired with a
distinct existing target owner and exact outcome/event vector. Existing
weather-front and process-consumer candidates remain formally blocked;
`drought_process_advanced` is not admissible as a substitute for the
committed weather-front source. No generic consumer, fanout, router, retry,
compensation or second runtime was added.

The shared Inventory production-output custody reader now rejects invalid
checkpoint bounds and forged certification/provenance pins during replay. This
strengthens INF-3AB and Foundation custody evidence without creating a new
Ecology row or generic Inventory writer.

The custody replay hardening is covered by the shared custody regression and
does not alter INF-3AB's fixed grain row or create a new target-owner edge.

## 2026-09-01 Continuation Status

No additional committed Ecology source paired with a distinct existing target
owner and exact event vector was found. Unlisted target-owner edges remain
formally blocked; `drought_process_advanced` remains inadmissible as a weather
front substitute.
## 2026-08-28 Grain Harvest Closure

The fixed mature wheat admission and terminal `grain_harvested` Ecology row
are implemented and verified. The row is project-visible, owner-bound and
replay-safe, and creates no Inventory, Economy or generic harvest authority.
