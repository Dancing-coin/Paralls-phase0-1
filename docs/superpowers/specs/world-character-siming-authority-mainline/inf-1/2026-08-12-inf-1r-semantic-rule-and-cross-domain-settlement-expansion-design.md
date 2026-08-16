# INF-1R Semantic Rule And Cross-Domain Settlement Expansion Design

Status: `implemented and verified for the sole production-finish mapping; no generalized cross-domain rule authority`

Date: `2026-08-12`

## Purpose and dependency

INF-1R expands the verified semantic/entity/causal vertical into a governed,
closed rule vocabulary and repeatable cross-domain settlement mapping. It
depends on INF-1's immutable snapshots and INF-2's caller-driven receipt
contract. It does not turn a rule evaluator into a world owner.

## First executable vertical and owners

The first and only authorized INF-1R slice is a semantic-driven production
finish consequence. `SemanticSettlementAuthority` in
`backend/app/gameplay/semantic_authority.py` remains the proposal bridge; the
sole target owner is `ConstructionProductionAuthority.build_due_finish_fragment`
in `backend/app/gameplay/construction_production_runtime.py`. It builds an
`OwnerAuthorizedFragment` for stream
`gameplay:construction_production:{facility_ref}` and existing event
`gameplay.construction_production.run_finished`. The coordinator appends that
fragment through the existing event store.

Survival and economy are explicitly out of this first INF-1R mapping. Their
existing fragment builders are reusable evidence. Later INF-1 packages admit
only individually documented rows: the three Survival state-owner bridges and
INF-1J's exact Economy wage-obligation mapping. Neither changes this
production-finish slice into a general semantic-rule target router.

## Owners and boundaries

| Concern | Owner | Boundary |
| --- | --- | --- |
| definitions, selectors, trace | `gameplay/semantic_registry.py` | versioned read/evaluation surface only |
| rule evaluation and effect proposal | closed extension of `SemanticSettlementAuthority` | emits the typed production-finish proposal only |
| first settlement target | `ConstructionProductionAuthority.build_due_finish_fragment` | validates run/recipe/tick and builds the sole authorized fragment |
| other state, inventory, body, construction, economy changes | their existing domain authorities | out of scope until individually mapped |
| committed truth/outbox/replay | `GameplayEventStore` and existing replay | the sole production append spine |
| dossier and trace reads | `entity_causal_projection.py` | rebuildable, scope-filtered projection |

The only formal write path is:

```text
structured fact/intent -> frozen SemanticSnapshot -> closed rule evaluation
-> SettlementPlan -> ConstructionProductionAuthority fragment -> append_batch
-> outbox/replay -> scope-filtered projection
```

Godot, player clients, LLMs, Siming, creator tools, and MCP may submit facts,
intent, evidence, or drafts. They cannot install a production rule, invoke an
append, or write a target domain directly.

## Data and event contracts

`RuleSetRevision`, `EffectDefinition`, `ResistanceProfile`,
`StateLifecyclePolicy`, `RuleEvaluationEnvelope`, and `RuleEvaluationTrace`
are immutable, digested inputs. A plan pins active semantic, policy, domain,
and ruleset revisions; each effect carries `causal_chain_id`, parent refs,
stable target/component scope, idempotency key, and a declared owner.

New committed event payloads remain domain-owned and may carry only these
common correlation fields: `rule_set_revision`, `semantic_snapshot_digest`,
`effect_ref`, `causal_chain_id`, `trace_digest`, and `settlement_plan_ref`.
The evaluator must never emit generic `world.state_changed` events or a
parallel rule-event store. The first slice may emit only the existing
production-finish event with versioned correlation payload fields.

## Rule semantics

Rules execute in fixed phases: `normalize`, `eligibility`, `derive`,
`resolve`, `propagate`, and `settle`. Same-phase ordering is stable by declared
priority, specificity, then rule reference. Conflict policies are closed:
`exclusive`, `replace`, `additive`, `minimum`, `maximum`, `suppress`, and
`reject`. A rule graph must use fixed-precision values, deterministic seed
material, visited `(rule, entity, component)` tuples, maximum depth, and
per-chain/per-target budgets. Unsupported policy, ambiguous ownership,
conflict, cyclic re-entry, or budget exhaustion returns a structured result
without partial append.

Persistent state expiry and periodic effects become INF-2 obligations. A read
or projection must never expire, refresh, or stack state implicitly.

## Revision, idempotency, failure, and privacy

Every command pins snapshot, ruleset, policy, and expected owner revisions.
The command idempotency key returns the original scoped receipt only when the
same input digest is supplied; reuse with a different digest is rejected.
Stale revisions, unregistered definitions, an unauthorized target/view,
fragment overlap, or an owner decline produce zero writes. A coordinator may
assemble fragments but may not repair, replace, or authorize them.

Authority traces may expose authorized inputs and decisions. Actor, public,
and creator traces expose only explicitly allowed labels, digests, and
redacted reasons. Privacy filtering is applied before trace material leaves the
backend; redaction never changes settlement input or replay result.

## Replay, migration, and rollback

Full replay and checkpoint-tail replay must reproduce the same domain
projections, causal graph, trace digest, and scoped receipt for a fixed active
revision set. Rule revisions and event payload readers require explicit
versioned upcasters. Historical events are immutable. Rollback deactivates a
future rule revision, cancels a future obligation, or emits owner-specific
compensating events; it cannot delete effects already committed to history.

## Verified evidence

`SemanticProductionFinishCommand` is the closed proposal accepted by
`SemanticSettlementAuthority.settle_production_finish`. It validates the
frozen snapshot digest, facility target, privacy scope, and owner stream
revision before calling only
`ConstructionProductionAuthority.build_due_finish_fragment`. The bridge adds
correlation fields to the owner event and calls the existing fragment batch
adapter followed by `GameplayEventStore.append_batch()` once. It does not
write a semantic event or use the obligation coordinator as a second owner.

Focused evidence: `backend/tests/test_infra_semantic_cross_domain.py` proves
success/outbox, owner decline zero-write, duplicate idempotency, revision
conflict zero-write, private proposal zero-write, and full/checkpoint-tail
replay equivalence. The independent Harness profile is
`infra-semantic-cross-domain`; its current report is
`.harness/verification/infra-semantic-cross-domain-report.json`.

## Harness, non-goals, completion

`infra-semantic-cross-domain` independently proves the named production
fragment, owner-decline zero-write, idempotency, revision conflict zero-write,
private-proposal zero-write, and full/checkpoint-tail replay. Phase ordering,
broader conflict handling, migration reader compatibility, and owner-specific
compensating rollback remain INF-1X/INF-2X work and are not claimed here.

Non-goals: arbitrary user code, free-form expressions, direct creator
activation, transport auth closure, universal domain coverage, survival/economy
rule mapping, a scheduler, or P6/P7. Completion is limited to the named
production-finish mapping and matching focused tests.
