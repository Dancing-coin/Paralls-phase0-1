# INF-1X General Semantic Rule Closure Design

Status: `implemented and verified for the production one-shot row, three Survival state rows, one Construction maintenance row, and one closed Economy wage-obligation row; generic lifecycle and unmapped domains remain blocked`

## Purpose and inherited baseline

INF-1X closes the reusable semantic language that the verified INF-1 and the
narrow INF-1R production-finish mapping deliberately do not generalize. It
adds a closed `RuleSet`/effect/resistance contract, state lifecycle mapping,
and a declared cross-domain owner matrix. It inherits `TagDefinition`,
`TagAssignment`, immutable `SemanticSnapshot`, selector evaluation,
entity/causal projections, `SemanticSettlementAuthority`, and the canonical
event/outbox/replay spine. None of those foundations prove universal rules.

## Owners and write boundary

`semantic_registry.py` owns definitions, selector compilation, snapshot and
trace evaluation; it is never entity, balance, body, inventory, construction,
or policy truth owner. `SemanticSettlementAuthority` may make a typed proposal.
Each target must be an existing named authority with an exact owner builder,
stream, event family and scoped reader. The original one-shot mapping is
`ConstructionProductionAuthority.build_due_finish_fragment` for
`gameplay.construction_production.run_finished`. INF-1J additionally records
the closed `EconomyAuthority.open_wage_obligation` mapping for
`effect:wage_accrual_due`. Survival state rows are separately admitted through
their closed state-owner routes. Ecology, social, civilization and every other
Economy mapping remain rejected.

### 2026-08-12 admission result

INF-1R supplies only one admitted matrix row:

| Effect | Owner fragment | Stream | Event | Scoped projection | Lifecycle status |
| --- | --- | --- | --- | --- | --- |
| `effect:production_due_finish` | `ConstructionProductionAuthority.build_due_finish_fragment` | `gameplay:construction_production:{facility_ref}` | `gameplay.construction_production.run_finished` | construction production project scope | one-shot only |
| `effect:wage_accrual_due` | `EconomyAuthority.open_wage_obligation` | `gameplay:economy:wage:{worker_ref}` | `gameplay.economy.wage_obligation_opened` | Economy project scope | existing obligation lifecycle only |

Three registered durable rows now exist: `state:cold@1` / `effect:cold_exposure`,
`state:overheated@1` / `effect:heat_exposure`, and `state:dehydrated@1` /
`effect:dehydration_exposure` are owned by
`SurvivalAuthority` on `gameplay:survival:{actor_ref}`, with explicit opened,
settled and cancelled event types and
`SurvivalAuthority.build_state_expiry_fragment`. All other durable application,
refresh, expiry, retry, cancellation, transformation and compensation rows
remain unregistered. This package must not infer further rows from existing
economy, ecology, social, or civilization code.

## Verified closed vocabulary

`semantic_registry.py` now exposes immutable `RuleSetRevision`,
`ClosedRuleDefinition`, `ClosedEffectDefinition`, `OwnerMapping`, and
`StateLifecyclePolicy` contracts. The registry admits the one-shot production
row, the exact INF-1J Economy wage row and the three explicit Survival
scheduled lifecycles. Only `handler:production_due_finish` is admitted to the
one-shot closed rule evaluator; the Economy row has its own closed proposal
adapter and is not a generic rule handler.
It evaluates fixed phase/priority/specificity ordering, all closed conflict
policies, fixed-point resistance attenuation, and scope-filtered traces without
an event-store dependency. Guard evaluation accepts only fixed snapshot
tag/status/numeric predicates and rejects arbitrary expressions. Scheduled
lifecycle registration is rejected as `semantic_lifecycle_owner_unregistered`
except for the explicit Survival row above.

`SemanticSettlementAuthority.settle_closed_production_finish` validates the
closed ruleset/rule/owner row before delegating to the production owner
fragment. It detects idempotency-key reuse with changed command input before
the append path. It does not authorize `settle_lifecycle` as an INF-1X owner
mapping and does not add a generic writer.

INF-1B/INF-1D separately admit two scheduled state bridges:
`authority:semantic -> effect:cold_exposure -> state:cold@1 -> SurvivalAuthority`
and `authority:semantic -> effect:heat_exposure -> state:overheated@1 ->
SurvivalAuthority`. Each delegates to the existing Survival owner, which alone
appends state and obligation-opened events. They do not add a registry
`OwnerMapping` for a generic effect or widen any other lifecycle row.

Focused evidence is `backend/tests/test_infra_general_semantic_rule.py`.
Independent evidence is `infra-general-semantic-rule` at
`.harness/verification/infra-general-semantic-rule-report.json`, with distinct
assertions for each enabled capability and the durable/unmapped zero-write
fence.

```text
authority evaluation view -> frozen SemanticSnapshot -> closed RuleSet
-> SettlementPlan -> named OwnerAuthorizedFragment -> append_batch
-> outbox/replay -> scope-filtered projection
```

Godot, player clients, LLMs, Siming, creator/MCP tools submit evidence,
intent, drafts or preview requests only. They cannot register active rules,
execute a handler, append events, or change a domain projection directly.

## Data and event contract

`RuleSetRevision(rule_set_ref, revision, active_semantic_set_digest,
phase_order, rules, digest)`, `EffectDefinition(effect_ref, input_schema,
stack_policy, version)`, `ResistanceProfile(source_ref, effect_ref,
modifier_policy, revision)`, `StateLifecyclePolicy(state_ref, apply,
refresh, expire, dispel, transform policies)`, and `RuleEvaluationEnvelope`
are immutable and versioned. A rule has fixed phase, priority, selector,
typed handler reference, declared target-owner mapping, conflict policy,
chain budget and explanation template. Effects carry component scope,
`causal_chain_id`, parent refs, stable stack/idempotency key and target
expected revision.

Committed events stay domain-owned. They may carry common correlation fields
`rule_set_revision`, `semantic_snapshot_digest`, `effect_ref`,
`causal_chain_id`, `trace_digest`, and `settlement_plan_ref`; there is no
generic semantic event stream or parallel rule store. One-shot effects create
a named owner fragment. Durable application, refresh, expiry, periodic damage,
recovery and transformation require a named owner event plus an INF-2X
obligation; projections never mutate a lifecycle implicitly.

## Determinism, rejection, privacy and replay

Execution phases are `normalize`, `eligibility`, `derive`, `resolve`,
`propagate`, `settle`; same-phase ordering is priority, specificity, stable
rule ref. The closed conflicts are `exclusive`, `replace`, `additive`,
`minimum`, `maximum`, `suppress`, `reject`. Fixed-point numeric values,
recorded seed material, visited `(rule, entity, component)` tuples, depth and
per-chain/per-target budgets are mandatory. Unknown schemas/policies, rule
cycles, ambiguous target ownership, target overlap, stale revision, altered
idempotency reuse or any owner refusal reject before `append_batch`, with zero
writes and an auditable reason.

Authorities can read required evidence; actor/public/creator traces are
filtered before leaving backend and retain only allowed labels, digests and
redacted decisions. A viewer never gains settlement authority. Full and
checkpoint-tail replay must reproduce domain event/projection hashes, causal
ancestry, trace digest and scoped receipt under the pinned revisions. Readers
are versioned/upcast explicitly; rollback retires a future rule, cancels future
obligation, or emits a named owner compensation event, never deletes history.

## Harness, exclusions and completion

Profile `infra-general-semantic-rule` makes distinct assertions for phase
order, every conflict family, selector/snapshot revision pinning, resistance
attenuation, chain cycle/budget truncation, named owner mapping, zero-write
reject, duplicate idempotency, privacy trace filtering, full replay,
checkpoint-tail replay and reader migration. It must not use one pytest result
as several capabilities.

Non-goals: free-form code/formulas, creator activation, generic world writer,
all-domain coverage, a scheduler, transport authorization closure, P6/P7.
Completion means the declared closed vocabulary and every matrix row that is
actually implemented has its own owner-specific evidence; the current single
row does not claim that unmapped domains support semantic effects.
