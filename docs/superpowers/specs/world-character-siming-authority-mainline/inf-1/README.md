# INF-1 Specification Tree

Status: `approved INF-1 narrow verticals, including four Survival rows, two closed Survival state-action rows, one Construction maintenance-state row, one closed Economy wage-obligation row, one closed Ecology frost crop-state row, one closed Ecology drought state row, and two exact weather-front Survival edges, are verified; August INF-1 closure remains incomplete`

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

The exact frozen `oven -> kiln` row is implemented and verified through the
existing `ConstructionProductionAuthority`. Its typed proposal contains no
owner, stream, event, privacy, receipt, fragment, target, or package choice.
The authority resolves the active immutable binding, validates the committed
project-visible `facility_acquired` evidence and its facility/project/revision
pins, then appends one project-scoped `facility_transformed` event through
`GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`.

Focused evidence is `11 passed`; the independent
`infra-construction-facility-package-transform` Harness is green. It proves
success, append-derived receipt, exact/changed idempotency, inactive/unadmitted/
ambiguous/digest-conflicting package binding, private and project-conflicting
evidence, revision zero-write, full replay, checkpoint-tail replay, and v1
terminal/no-compensation behavior. The frozen manifest remains unchanged.
This does not admit a generic Construction transform, payment, material,
fanout, compensation, router, registry, writer, or second runtime. August INF
A-D remains `not complete`.
