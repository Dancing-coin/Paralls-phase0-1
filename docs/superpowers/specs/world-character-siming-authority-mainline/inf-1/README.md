# INF-1 Specification Tree

Status: `approved INF-1 narrow verticals are verified through INF-1AM; remaining unformed Construction slots are owner-contract blocked or duplicate/closed; August INF-1 closure remains incomplete`

The approved [formal blocker disposition contract](../2026-08-26-august-inf-formal-blocker-disposition-contract.md)
keeps the Goal active while preserving INF-1AH as the implemented narrow
vertical. INF-1AI, INF-1AJ, INF-1AK, INF-1AL, and INF-1AM are the latest sequential Construction
follow-on rows; unformed Construction slots remain owner-contract blocked or
duplicate/closed; no fourth owner discovery or inferred Construction outcome is
permitted.

Date: `2026-08-12`

## Purpose

This tree is the independent formal specification surface for `INF-1` in the
post-P5 capability foundation. `INF-1` is the first mainline infrastructure
package after the bounded P1-P5 gameplay slices.

Its job is to define one governed semantic/entity/causal foundation over the
existing backend authority path:

- semantic tag definitions and assignments;
- immutable semantic snapshots and constrained selectors;
- event-derived entity/thing/environment/relationship dossiers;
- append-only causal trace and parent/child query surface; and
- proposal-only rule outputs that never bypass existing owners.

`INF-1` does not create a second runtime, event store, scheduler, social truth
store, or creator write path.

## Source alignment

This tree is aligned with:

1. `../post-p5-capability-foundation/2026-08-12-mainline-capability-implementation-decomposition.md`
2. `../post-p5-capability-foundation/2026-08-12-f1a-semantic-rule-and-causal-extension-gate-design.md`
3. `../../../../8月分析/世界基础设施增量指导/00-标签体系与元规则引擎.md`
4. `../../../../8月分析/世界基础设施增量指导/13-实体档案语义因果与元规则.md`
5. `../../../../8月分析/12-实现收口与证据映射.md`

## Documents

1. [INF-1 semantic/entity/causal foundation design](2026-08-12-inf-1-semantic-entity-causal-foundation-design.md)
2. [INF-1R semantic rule and cross-domain settlement expansion design](2026-08-12-inf-1r-semantic-rule-and-cross-domain-settlement-expansion-design.md)
3. [INF-1X general semantic rule closure design](2026-08-12-inf-1x-general-semantic-rule-closure-design.md)
4. [INF-1A Survival state obligation lifecycle design](2026-08-13-inf-1a-survival-state-obligation-lifecycle-design.md) - verified `state:cold@1` durable Survival owner row; INF-1D adds the separately evidenced heat row
5. [INF-1B semantic Survival state bridge design](2026-08-14-inf-1b-semantic-survival-state-bridge-design.md) - verified closed proposal-to-owner entrypoints for the registered cold/heat rows
6. [INF-1C closed guard composition design](2026-08-14-inf-1c-closed-guard-composition-design.md) - verified finite proposal-only multi-condition guards
7. [INF-1E Survival dehydration effect owner row design](2026-08-14-inf-1e-survival-dehydration-effect-owner-row-design.md) - verified exact third Survival row; it does not widen the owner matrix
8. [INF-1F registered Survival state owner matrix design](2026-08-14-inf-1f-registered-survival-state-owner-matrix-design.md) - verified single registration representation for the three existing Survival rows; it does not admit new owners
9. [INF-1G Construction maintenance state owner row design](2026-08-14-inf-1g-construction-maintenance-state-owner-row-design.md) - verified exact `maintenance_required -> maintenance_due` Construction row; it does not widen the matrix
10. [INF-1H registered state owner dispatch design](2026-08-14-inf-1h-registered-state-owner-dispatch-design.md) - verified closed routing for the four registered rows only; direct helpers retain the same exact source-vector fence
11. [INF-1I generic owner matrix admission blocker](2026-08-14-inf-1i-generic-owner-matrix-admission-blocker-design.md) - blocked until each additional effect/state lifecycle row has an approved existing owner and event-family mapping
12. [INF-1J semantic Economy wage obligation owner row](2026-08-14-inf-1j-semantic-economy-wage-obligation-owner-row-design.md) - verified closed third-owner semantic obligation row; not generic effect routing
13. [INF-1K semantic Survival state action lifecycle](2026-08-14-inf-1k-semantic-survival-state-action-lifecycle-design.md) - verified closed dispel/recovery-transform rows over existing Survival obligations; not a generic action router
14. [INF-1L Ecology frost state-obligation admission](2026-08-14-inf-1l-ecology-frost-state-obligation-admission-design.md) - verified exact `effect:frost -> state:frosted@1` Ecology row; not a generic lifecycle router
15. [INF-1M closed state owner contract matrix](2026-08-14-inf-1m-closed-state-owner-contract-matrix-design.md) - verified seven-row owner-contract reader enforced by existing Survival, Construction and Ecology writers; not generic routing
16. [INF-1N Construction maintenance state obligation](2026-08-14-inf-1n-construction-maintenance-state-obligation-design.md) - verified fixed Construction apply -> open -> expired/settled lifecycle on the existing facility stream; no generic matrix, scheduler, retry, cancellation or compensation
17. [INF-1O State action lifecycle closure](2026-08-15-inf-1o-state-action-lifecycle-closure-design.md) - verified pure dispel/fixed-transform decisions consumed by the existing three-row Survival action route; no generic action registry or state writer
18. [INF-1P Construction maintenance state-action admission audit](2026-08-15-inf-1p-construction-maintenance-state-action-admission-audit.md) - verified exact `maintenance_state_dispel` plus cancellation on the existing Construction facility stream; transform/repair/payment semantics remain blocked
19. [INF-1Q finite lifecycle contract closure](2026-08-15-inf-1q-finite-lifecycle-contract-closure-design.md) - verified: consolidates only existing seven state and one wage-obligation contracts into an immutable admission reader; it adds no owner, row, registration, or writer
20. [INF-1S Survival fatigue owner row](2026-08-15-inf-1s-survival-fatigue-owner-row-design.md) - verified finite fourth Survival row; not generic registration or routing
21. [INF-1T Survival fatigue state action](2026-08-15-inf-1t-survival-fatigue-state-action-design.md) - verified bounded dispel/fixed-recovery transform extension; not generic action registration
22. [INF-1U weather-front Survival admission blocker](2026-08-15-inf-1u-weather-front-survival-admission-blocker-design.md) - partially superseded by INF-4AC's event-derived active profile-to-region projection; no weather-front -> Survival owner/event/projection/receipt contract exists, so consumer inputs remain zero-write
23. [INF-1V unregistered Survival reject-state admission audit](2026-08-15-inf-1v-survival-reject-state-owner-row-design.md) - blocked: no reject owner row exists; the Survival writer now proves unregistered rows are zero-write
24. [INF-1W closed state lifecycle adapter matrix](2026-08-15-inf-1w-closed-state-lifecycle-adapter-matrix-design.md) - implemented and verified bounded Survival/Construction semantic adapter admission; Ecology/Economy remain blocked and INF-1 remains incomplete
25. [INF-1AC weather-front Survival cold owner row](2026-08-16-inf-1ac-weather-front-survival-cold-design.md) - independently verified exact `weather:frost -> state:cold` contract using the INF-4AC profile-region prerequisite; no generic weather consumer
25. [INF-1X Ecology frost semantic adapter](2026-08-16-inf-1x-ecology-frost-semantic-adapter-design.md) - verified closed proposal-to-Ecology owner contract for `effect:frost -> state:frosted@1`; not a generic Ecology adapter
26. [INF-1Y Ecology semantic adapter matrix admission](2026-08-16-inf-1y-ecology-semantic-adapter-matrix-admission-design.md) - verified immutable matrix admission and entry gate for the existing strict Ecology frost adapter; not generic state dispatch
27. [INF-1Z Ecology frost state action](2026-08-16-inf-1z-ecology-frost-state-action-design.md) - fixed project-visible frost dispel/cancel owner row; no generic action registry
28. [INF-1AA Ecology drought state obligation](2026-08-16-inf-1aa-ecology-drought-state-obligation-design.md) - verified seventh finite state-owner row from committed drought-process evidence, with opening-event-derived settlement provenance; not generic lifecycle closure
29. [INF-1AB drought opening-event provenance](2026-08-16-inf-1ab-drought-opening-event-provenance-design.md) - repaired the existing INF-1AA settlement fragment to derive source provenance from the committed opening event; not a new row
30. [INF-1C1 reusable state transition plan](2026-08-16-inf-1c1-reusable-state-transition-plan-design.md) - verified a pure typed add/replace/refresh/reject/expiry/dispel/transform proposal shape reused by existing Survival, Construction and Ecology definitions; no writer or registration
31. [INF-1AD weather-front Survival overheated owner row](2026-08-17-inf-1ad-weather-front-survival-overheated-design.md) - independently verified one exact `weather:heat -> effect:heat_exposure -> state:overheated` source edge through the existing Survival owner; no generic weather mapping
32. [INF-1AE Construction action owner-contract audit](2026-08-17-inf-1ae-construction-action-owner-contract-audit.md) - bounded facility repair/compensation implemented and verified; transform/payment remain blocked
33. [INF-1AF Construction facility transform owner-contract audit](2026-08-17-inf-1af-construction-facility-transform-owner-contract-audit.md) - generic transforms remain owner-contract blocked; one separately approved `bakery -> bakery_reinforced` existing-Construction-owner capability is implemented and verified
34. [INF-1AF bakery reinforcement Owner-Admission Contract](2026-08-17-inf-1af-bakery-reinforcement-owner-admission-design.md) - implemented narrow vertical with focused tests and independent Harness; it does not admit generic transforms
35. [INF-1AG Construction package-declared facility-transform Owner-Admission design](2026-08-17-inf-1ag-construction-candidate-owner-admission-design.md) - exact frozen `package:industrial-facilities:v1` `oven -> kiln` existing-Construction-owner row is implemented and verified; it does not admit generic transforms
36. [INF-1AG facility-transform content-authoring packet](2026-08-18-inf-1ag-facility-transform-content-authoring-packet-design.md) - design-only authoring templates for a future immutable package row; includes a strictly non-admitted example and cannot authorize runtime work
37. [Federated Gameplay Extension Platform design](../character-gameplay-foundation/2026-08-18-federated-gameplay-extension-platform-design.md) - design-only platform schema, canonicalization, immutable admission, proof, privacy, and replay boundary; no runtime or manifest change
38. [Federated Gameplay Extension Platform blocker taxonomy](../character-gameplay-foundation/2026-08-18-federated-gameplay-extension-platform-blocker-taxonomy.md) - separates platform-contract, package-content, owner-contract, implementation, and environment blockers
39. [INF-1AG package-content/read-only-binding sequencing design](2026-08-18-inf-1ag-package-content-readonly-binding-sequencing-design.md) - P1 verifies candidate-time structural validation plus activation-time exact-one descriptor binding/pin retention; it is historical sequencing evidence for the exact frozen `oven -> kiln` row only
40. [INF-1AG industrial facilities v1 freeze record](2026-08-19-inf-1ag-industrial-facilities-v1-freeze-record.md) - frozen canonical v2 manifest bytes plus verified declaration/content digest claims for the exact implemented row; no additional candidate, descriptor, catalog row, or Construction write path is admitted
41. [INF-1AG Construction descriptor/catalog admission packet](2026-08-19-inf-1ag-construction-owner-operation-descriptor-admission-packet.md) - approved immutable descriptor and existing-Construction contract row with focused binding evidence; the subsequent narrow vertical is separately verified
42. [INF-1AG industrial facilities v2 mill freeze record](2026-08-20-inf-1ag-industrial-facilities-v2-mill-freeze-record.md) - frozen canonical v2 package, exact immutable mill descriptor/catalog admission, and verified one-row Construction vertical
43. [INF-1AH mill reinforced decommission Owner-Admission Contract design](2026-08-20-inf-1ah-mill-reinforced-decommission-owner-admission-design.md) - exact active `mill_reinforced -> decommissioned` lifecycle row with fixed active-run zero-write rejection; implementation closure is recorded below
44. [INF-1AH minimum business decision and admission closure packet](2026-08-20-inf-1ah-minimum-business-decision-admission-closure-packet.md) - historical literal-field closure for the distinct frozen v3 decommission package; v2 remains source evidence only
45. [INF-1AH industrial facilities v3 decommission freeze record](2026-08-20-inf-1ah-industrial-facilities-v3-decommission-freeze-record.md) - frozen digest-verified v3 content and exact read-only binding; the later runtime closure does not modify either frozen package
46. [INF-1AH Construction descriptor/catalog admission packet](2026-08-20-inf-1ah-construction-owner-operation-descriptor-catalog-admission-packet.md) - exact immutable descriptor/catalog admission and read-only v3 binding evidence, preserved as the runtime's prerequisite
47. [INF-1AH package freeze and future admission checklist](2026-08-20-inf-1ah-decommission-package-freeze-checklist.md) - fixed/mechanical/missing field classification and future gate order
48. [INF-1AH lifecycle runtime closure](2026-08-21-inf-1ah-mill-decommission-lifecycle-runtime-closure.md) - verified owner-bound projection, verifier, fixed reducer, append receipt, replay, and terminal zero-write evidence
49. [INF-1AI facility operational verification](2026-08-27-inf-1ai-facility-operational-verification-owner-admission-design.md) - implemented exact completed Production run -> Construction verification projection; no output, payment, maintenance, or generic transform semantics
49. [INF-1 owner-admission candidate register](2026-08-20-inf-1-owner-admission-candidate-register.md) - August Construction candidate inventory: one implemented row plus two non-formed slots; not an INF-1 completion denominator

## 2026-08-20 Mill Reinforcement Narrow Vertical

Status: `implemented narrow vertical: exact frozen mill -> mill_reinforced row verified`.

The next INF-1AG row is now an implemented narrow vertical for the exact
`mill -> mill_reinforced` Construction facility identity contract. Its contract and
implementation evidence are recorded in the existing
[INF-1AG candidate design](2026-08-17-inf-1ag-construction-candidate-owner-admission-design.md)
and [plan](../../../plans/world-character-siming-authority-mainline/inf-1/2026-08-17-inf-1ag-construction-candidate-owner-admission-plan.md).
The v2 package is frozen with verified digests, resolves exactly one immutable
descriptor, and is covered by focused tests plus its independent Harness. It
does not modify frozen v1 or authorize a generic transform, another catalog
row, or another INF runtime.

## 2026-08-20 INF-1AH Decommission Design

The selected row is now `implemented narrow vertical`: the exact
active `mill_reinforced -> facility_decommissioned@1` lifecycle transition. It uses
only `ConstructionProductionAuthority`, the committed acquisition and frozen
v2 reinforcement facts, a project-scoped facility stream, and append/replay
boundaries already owned by Construction. It must preserve facility kind and
all non-Construction facts. The active-run rule is fixed: a committed started
`ProductionRun` rejects before append without cancellation, reservation
release, output disposal, refund, compensation, or a substitute event. The
[minimum business decision and admission closure packet](2026-08-20-inf-1ah-minimum-business-decision-admission-closure-packet.md)
records the literals that produced the distinct frozen v3 record. Its exact
descriptor/catalog admission and read-only binding pins are verified. This
historical design gate is now followed by the separately implemented
row-specific lifecycle-status projection and business-event runtime.

The exact descriptor/catalog literals and activation boundary were
isolated in the [INF-1AH descriptor/catalog admission packet](2026-08-20-inf-1ah-construction-owner-operation-descriptor-catalog-admission-packet.md).
The [lifecycle runtime closure](2026-08-21-inf-1ah-mill-decommission-lifecycle-runtime-closure.md)
is implemented and verified. Neither record admits a generic lifecycle action
or another Construction write path.

## Current implementation boundary

The repository already has a bounded verified `INF-1` slice:

- `backend/app/gameplay/semantic_registry.py`
- `backend/app/gameplay/entity_causal_projection.py`
- `backend/app/gameplay/shared_contracts.py`
- `backend/app/gameplay/event_store.py`
- `backend/app/gameplay/replay.py`
- `backend/tests/test_infra_semantic_entity_causal.py`
- `.harness/profiles/infra-semantic-entity-causal.json`

That slice proves semantic snapshot construction, inheritance/conflict denial,
selector filtering, event-derived dossiers, append-only causal-parent queries,
checkpoint-tail replay equivalence, and rejected-write zero-write behavior for
the bounded contract.

It does not prove generic effect/state lifecycle execution, full meta-rule
runtime closure, broad cross-domain settlement, package-authoring activation,
or production transport/privacy closure. INF-1R remains one narrow
production-finish mapping; INF-1X has one-shot production, four explicit
Survival scheduled-expiry owner rows, one Construction maintenance row, one
closed Economy wage-obligation row, one closed Ecology frost semantic
adapter, and INF-1AA's seventh finite `effect:drought -> state:drought@1`
row sourced from committed drought-process evidence, including immutable
matrix admission and the fixed Ecology frost dispel/exact-obligation-cancel
action, not a generic owner matrix.

## Success boundary

`INF-1` is complete only when its own design, plan, owner-scoped code, focused
tests, focused Harness profile, and reviewed evidence all exist and all claims
in the formal design are backed by fresh proof. Contract-sample evidence alone
does not upgrade future INF-2, SOC-1, GAME-1, CREATOR-1, or P6/P7 scopes to
complete.

## INF-1AG Current Row Status

## 2026-08-20 Descriptor/Binding Admission Approval (Historical Gate)

The exact descriptor and immutable Construction catalog row from the
[admission packet](2026-08-19-inf-1ag-construction-owner-operation-descriptor-admission-packet.md)
were explicitly approved for admission work. The allowed scope was limited
to the existing `GameplayPatchRegistry` candidate/activation boundary:
candidate structural and digest validation, exact-one read-only descriptor
resolution, package/content/declaration/descriptor/active-set pin retention,
and full/checkpoint-tail replay. The catalog remains immutable/read-only.

Admission evidence did not create or invoke a Construction business event.
The later runtime approval is a separate gate and is recorded below.

The dedicated admission Harness was
`infra-construction-facility-descriptor-binding-admission`; its zero-write,
privacy, revision, idempotency, receipt, exact-one resolution, and replay
selectors cover only the frozen package binding and existing descriptor.

## 2026-08-20 Construction Runtime Approval

The exact frozen `oven -> kiln` row is implemented and verified through the
existing `ConstructionProductionAuthority`, using only the admitted descriptor,
`GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`,
and the existing replay/projection spine. The row-specific verifier binds the
committed project-visible `facility_acquired` event to `facility_ref` and
`project_ref`, pins package/declaration/descriptor and stream revisions, and
rejects unknown, inactive, digest-mismatched, ambiguous, stale, private,
conflicting, duplicate, or revision-conflicting inputs before any append.

Focused evidence is `12 passed`; the independent
`infra-construction-facility-package-transform` Harness is green. It proves
success, append-derived project receipt, exact/changed idempotency, package and
binding zero-write cases, privacy and binding fences, full replay,
checkpoint-tail replay, and v1 terminal/no-compensation behavior. This is one
implemented narrow vertical only; generic Construction transforms and all
other INF rows remain separately gated. August INF A-D remains `not complete`.

INF-1AI's committed operational-verification record is consumed read-only by
the separately owned INF-2AE commissioning-review exchange. That handoff does
not change Construction ownership or admit a cross-domain Construction write.

Verification caveat: the exact INF-1AG focused suite and both dedicated Harness
profiles are green. After repairing stale selector and predecessor evidence
references, a fresh all-INF inventory reran all 124 profiles and every profile
passed. Full pytest remains `3561 passed, 1 failed` because the host denies
writing the workspace-parent `.env`; this is an environment limitation, not an
INF-1AG code failure.

## INF-1AJ Facility Public-Use Enablement

`INF-1AJ` is an implemented narrow Construction vertical. One committed,
project-visible `facility_operationally_verified@1` event for an `oven` enables
the Construction-owned `public_use_status=enabled` projection and increments
the facility revision. The fixed project stream/event, owner-derived
idempotency, append-derived receipt, source/stream revision fence, terminal
no-disable/no-compensation rule, and full/checkpoint-tail replay are covered by
the independent `inf1aj-facility-public-use` Harness and focused tests.

The row does not imply licensing, technology, maintenance, weather immunity,
production output, inventory, payment, material, social, or generic
facility-kind availability. Other facility kinds remain zero-write for this
capability.

## INF-1AK Public-Project Step Completion

`INF-1AK` is an implemented narrow Construction extension. It consumes only
the committed Organization `work_order_fulfilled@1` event for the literal
`work-order:public-project:workshop-bench@1` and records one fixed
`project-step:public-project:workshop-bench@1` completion on the matching
Construction facility/project stream. Source/target heads, facility/project
binding, project privacy, owner-derived idempotency, append receipt,
zero-write rules, and full/checkpoint-tail replay are covered by the
independent `inf1ak-public-project-step-completion` Harness.

This row does not change facility kind, condition, public-use status, output,
inventory, material, payment, wage, permit, technology, weather, maintenance,
social, population, or generic task semantics.

Implementation plan: [INF-1AJ Facility Public-Use Enablement](../../../plans/world-character-siming-authority-mainline/inf-1/2026-08-27-inf-1aj-facility-public-use-plan.md).

## 2026-08-28 Current Lane Checkpoint

INF-1's approved Construction rows remain implemented and verified through
INF-1AM. Remaining shapes are `duplicate/closed` or `owner-contract blocked`
because no additional committed Construction source and exact outcome tuple
exists. No new Construction row is inferred from production, maintenance,
repair, transform, or output facts. Current verification is `1232 passed` for
the filename-scoped INF/INFRA collection, `1246 passed` for the keyword
selection, and `4004 passed` for the repository-root suite. Goal remains
active; August INF A-D remains not complete.

## INF-1AL Mill-Reinforced Public-Use Enablement

`INF-1AL` is an implemented narrow existing-row extension. A committed,
project-visible Construction `facility_operationally_verified@1` event for a
current active `mill_reinforced` facility is accepted only with exactly one
earlier frozen v2 `mill -> mill_reinforced` provenance event. Construction then
records one project-scoped `facility_public_use_enabled@1` fact. It changes
only `public_use_status` and facility revision; it does not imply output,
inventory, material, payment, permit, technology, weather, maintenance,
social, population, or generic facility availability.

The row has an independent descriptor/catalog partition,
owner-derived idempotency, append-derived receipt, zero-write rejection,
and full/checkpoint-tail replay evidence in the
[INF-1AL contract](2026-08-28-inf-1al-mill-reinforced-public-use-owner-admission-design.md),
[implementation plan](../../../plans/world-character-siming-authority-mainline/inf-1/2026-08-28-inf-1al-mill-reinforced-public-use-plan.md),
and `inf1al-mill-reinforced-public-use` Harness. INF-1AJ remains the separate
oven-only row; no generic public-use operation is admitted.

Current INF-1 verification is `1235 passed` in the filename-scoped INF/INFRA
collection, `1249 passed` in the keyword-selected collection, and `4007 passed`
for the repository-root suite. INF-1AM is the latest implemented
existing-row extension; all remaining unformed Construction shapes remain
duplicate/closed or owner-contract blocked.

## INF-1AM Reinforced Mill Flour Output Certification

`INF-1AM` is an implemented narrow Construction row. One committed,
project-visible acquisition, the exact frozen v2 `mill -> mill_reinforced`
provenance, and one completed run using
`recipe:industrial-facilities:mill-flour@1` with
`item:industrial-facilities:flour@1` produce one project-visible
`mill_flour_output_certified@1` fact with fixed quantity `10`.

The row is terminal per run and records only Construction certification. Its
owner-derived idempotency, append-derived project receipt,
full/checkpoint-tail replay, source/revision/privacy fences, and zero-write
boundaries are covered by the `inf1am-mill-flour-output-certification`
Harness. It does not create Inventory or Economy truth and is not a generic
production-output API.

## 2026-08-28 Next Construction Row Blocker

The post-INF-1AM audit found no second unclaimed Construction source/outcome
tuple in the existing committed evidence. Acquisition, repair, transform,
decommission, run completion, maintenance, operational verification,
public-use, project-step, and flour-output shapes are already closed by
existing Construction owner paths; production-completed work evidence has no
unclaimed Construction target semantic.

The only current new direction, Organization grain intake, lacks a committed
`facility_ref`/`project_ref` binding and an exact Construction-owned outcome,
so it cannot select a Construction stream or justify a caller-shaped action.
The precise missing fields and zero-write boundary are recorded in
[the next-row blocker](2026-08-28-inf-1-next-construction-row-blocker.md).
No RED tests, runtime, catalog, or Harness were added because no unique row
exists to implement without inventing facts or generic behavior.

## 2026-09-01 Continuation Status

The ordered recheck found no additional distinct committed Construction source
and exact target semantic. Existing rows remain implemented and verified;
unformed actions/transforms remain duplicate/closed or owner-contract blocked.

The separate Construction/Production generic-platform track now has approved
subsystem specs and a first headless typed-content/grid-occupancy slice. It is
owner-bound platform work and does not alter or generalize the existing INF-1
narrow rows.

2026-09-02: a consumed Economy `budget_reserved` source is rejected by
Construction start and replay before mutation. This closes one reservation
lifecycle evidence gate without adding a generic transform or authority.

2026-09-02: `run_failed@1` replay now rejects private events, wrong facility
streams, mismatched facility/recipe identities, and inconsistent source
revision vectors before projection mutation.

Maintenance obligation events now retain facility/project/revision/policy pins;
replay fails closed on tampering without changing legacy event interpretation.

Maintenance obligation requests reject changed duplicate idempotency keys.

Core facility/run lifecycle event schemas are explicitly registered and
idempotent in the existing registry.

Construction reservation requirements use exact-set validation; extra refs or
evidence keys fail closed before append.

Run-start replay also rejects non-canonical reservation refs or mismatched
reservation evidence keys.

ConstructionJob completion/failure replay now rejects wrong plot stream or
private scope before terminal status changes.

When a Facility projection exists, run-start replay also rejects wrong stream,
privacy or facility/revision identity before accepting the run.

Run-finish replay applies the same exact project/stream/facility source fence.

Acquisition replay applies the canonical project/facility stream fence and
requires non-empty facility/plot identity fields.

Transform replay applies the same project/privacy/facility-stream source fence.

Declared transform acquisition references are resolved and revision-checked
during replay.
Checkpoint-tail replay may use persisted acquisition identity for pre-tail
sources; full replay requires the committed source event.

Repair replay applies the same project/privacy/facility-stream source fence.

Repair replay enforces condition bounds and strict facility revision increments.

Maintenance-state application replay applies the materialized facility
project/privacy/stream fence.

Decommission replay applies the same project/privacy/facility-stream source
fence before terminal lifecycle mutation.

The v3 mill decommission row additionally resolves and verifies its exact
reinforcement source event; generic lifecycle rows remain acquisition-only.

Failure admission enforces run chronology and rejects any tick before the
committed ProductionRun start.

Failure events also inherit ProductionRun reservation refs/evidence and replay
rejects lineage tampering before status mutation.
