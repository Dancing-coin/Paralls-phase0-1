# Gameplay Foundation Shared Contract Closure Design

Status: `approved; matching plan authorized by user on 2026-08-07`

Date: `2026-08-07`

## Purpose

将 `docs/8月分析/第一阶段推进/01-通用基础契约收口.md` 转换为可审阅的正式
Gameplay Foundation 子规格。本文冻结跨玩法必须稳定的契约和边界；在第一阶段中
承担 P1A，供 V0、Econ-1 以及第二个异质样板复用，后续玩法继续依赖它。

文件名中的 `shared` 明确表示：P1A 是第一阶段交付使用的共享底座收口，不是第一阶段
专属 runtime，也不是一个新的平行玩法运行时。

本文是现有 `world-character-Siming-authority unified runtime` 和
`Character Gameplay Foundation` 的增量规格，不建立新的 runtime、event store、
authority bus、全局 scheduler 或万能 coordinator。实现必须扩展现有 owner，并继续
通过 `GameplayEventStore.append_batch()` 形成唯一 Gameplay 事实链。

本规格获批前只授权设计审阅，不授权运行时代码实现。获批后必须创建 matching
implementation plan，完成计划审阅后才能进入 SDD 实现。

## Source Of Truth And Dependencies

设计优先级如下：

1. 当前线程的明确指令；
2. `docs/superpowers/specs/world-character-siming-authority-mainline/` 主线规格；
3. 本目录既有 Gameplay Foundation 规格与计划；
4. `docs/8月分析/第一阶段推进/` 作为本规格的增量输入；
5. 代码、focused tests 和 `.harness/verification/` 作为实现状态证据。

本规格直接依赖：

- foundation invariants and domain boundaries；
- event sourcing and authority settlement；
- state-group registry and runtime facade；
- resource/status/body/effective-stats；
- inventory/container/encumbrance；
- ownership/economy/transaction primitives；
- skill/ability/affordance；
- Patch Rule IR and capabilities；
- Godot mirror and verification matrix。

## Scope

### In scope

- stable identity and cross-domain references;
- Entity/Thing/Environment/Relationship/CausalEvent contract;
- tag, material, property, effect, resistance, meta-rule and semantic revision contract;
- `ActionPrimitive` registry, `ActionIntent`, `PhysicalFact`, `LogicalFact` and evidence envelope contract;
- selector/query and deterministic Rule IR input/output boundaries;
- typed effect proposal and effect application boundary;
- reservation/hold lifecycle shared by resources, inventory and future domains;
- `SettlementPlan` as an adapter to the existing authority settlement path;
- tick, obligation, calendar, retry, compensation, world profiles and revision pinning semantics;
- state-group/profile activation and `ActiveSemanticSet`/`ActiveWorldRevision` contract;
- standard Gameplay package/domain-extension manifest, compatibility and migration declaration contract;
- projection, permission, privacy and evidence-trace contract;
- creator authorization-decision input for `reader`/`editor`/`admin`, without implementing the
  Creator Control Plane product;
- replay, checkpoint, upcast, migration and rollback requirements;
- contract-level Harness gates used before V0 and Econ-1.

### Explicit non-goals

- no second event store, event bus, runtime or hidden scheduler;
- no generic economy, dynamic market, order book, auction or macro-price model;
- no construction, production, Survival, Organization or Government implementation in
  this shared contract spec;
- no population simulation, NPC materialization or hidden actor fixtures;
- no Creator Control Plane UI/CLI/MCP product implementation or arbitrary Python/GDScript execution;
- no replacement of CharacterAgent, ESM, Siming, Godot or `CharacterGameRuntimeState` owners;
- no sample-specific fields enter the core schema.

## Current Baseline And Incremental Work

| Capability | Current state | P1A action | Evidence/owner boundary |
| --- | --- | --- | --- |
| Atomic events, idempotency, revisions, replay, checkpoint, outbox | `implemented/reusable` | only add typed contract fixtures and evidence refs | `GameplayEventStore` and existing domain authorities |
| State groups, resources, body, status, effective stats | `implemented/reusable` | define optional group lifecycle and disabled semantics needed by later Survival profiles | existing gameplay state-group/resource owners |
| Inventory, containers, encumbrance, equipment | `implemented/reusable` | define lot/reference extension points without changing item truth ownership | inventory/equipment authorities |
| Ownership, account, fixed offer, gift, debt, typed contract | `implemented/reusable` | define cross-domain settlement inputs and obligations | ownership/economy/contract authorities |
| Skill, ability, affordance and Patch capability | `implemented/reusable` or `partial` | normalize proposal, capability, failure and revision metadata | skill/ability/Patch owners |
| ActionPrimitive/action/fact envelope | `partial/reusable` for embodied slices | freeze registry entries, `ActionIntent -> PhysicalFact/LogicalFact` and evidence mapping without replacing embodied authority | embodied interaction/ESM/Gameplay authority path |
| Resource reservation | `implemented/reusable` for resource state | generalize reserve/consume/release semantics as a shared value/lifecycle contract | resource reservation authority; future owners remain domain-specific |
| Godot snapshot/delta mirror | `implemented/reusable` for bounded scopes | freeze scope-filtered projection contract | mirror/projection owner |
| Identity/reference and world records | `planned` | freeze stable IDs, references and lifecycle contract; implementation owner is pinned in matching plan | existing world/ESM fact path, no new runtime |
| Semantic/effect/resistance registry | `planned` | freeze declarative revisioned registry and deterministic evaluation trace | status/Patch incremental path |
| Selector/query | `planned` | freeze read-only query input, result and privacy behavior | projection/query path |
| State-group/profile activation | `partial/reusable` | freeze `disabled/narrative/lightweight/simulation`, mode revision and no-hidden-effect semantics | state-group lifecycle authority |
| World profile and active revision set | `planned` | freeze game/simulation/inference profile, `ActiveSemanticSet`, `ActiveWorldRevision` and session pinning | existing session/patch/schema revision paths |
| Gameplay package/domain-extension manifest | `partial/reusable` for trusted Patch manifests | freeze domain maturity, owned aggregates, state groups, commands/events, dependencies, compatibility and migration declarations | Patch/package registry path |
| `SettlementPlan` adapter | `planned` | define pre-submit shape and exact `append_batch` mapping | authority settlement path |
| Reservation/Hold lifecycle | `partial/reusable` | freeze reserve/consume/release/expire/compensate, ownership and idempotency | resource/inventory/economy/domain authorities |
| Tick/obligation/calendar/revision pinning | `planned` | freeze command/lifecycle contract; do not create a global clock runtime | existing scheduling/continuity path plus domain owners |
| Permission/projection/evidence | `partial` | unify principal, privacy scope, redaction and trace references | authority envelope and mirror/projection path |

`planned` means the contract is being frozen here; it does not mean that the runtime exists.
The matching plan must name the exact existing modules and functions that will be extended.

## Normative Invariants

### One canonical owner

Every canonical field and lifecycle has exactly one authority owner. Other domains may keep
opaque references, pinned revisions or projections, but may not duplicate mutable truth.

Examples:

- currency balance belongs to the account/economy authority;
- item quantity and lot custody belong to inventory;
- facility progress belongs to construction/production when that domain is added;
- character needs and bodily consequences belong to the Survival state-group authority;
- permit and tax policy facts belong to Government authority;
- `CharacterGameRuntimeState` only composes read projections.

### Existing authority path only

All Gameplay writes follow:

```text
typed command
-> identity and permission validation
-> pinned revisions and read set
-> domain preconditions and Rule/Capability proposal
-> authority settlement
-> GameplayEventStore.append_batch()
-> committed outbox/projections
-> scoped facade, actor view or Godot mirror
```

`SettlementPlan` may prepare and validate a cross-domain batch, but it is not a second event
store, a coordinator with mutable state, or an alternate commit path.

The fast path used by an already-closed domain and the generalized semantic/settlement path
must produce the same typed result envelope, event lineage, revision metadata and replay result.
The generalized path is required for new cross-domain adapters, not as a reason to migrate
existing bounded authorities into a new coordinator. After commit, only eligible public
notifications may flow through System L6; L6 is not the Gameplay event ledger or a write owner.

### Action and fact boundary

Player, CharacterAgent, NPC and embodied adapters submit the same typed `ActionIntent` shape.
An `ActionPrimitiveDefinition` declares target kinds, required capabilities, observation needs,
fact kind, costs and failure policy. An adapter may provide a verified `PhysicalFact` or
`LogicalFact`, but neither fact is itself a world-state mutation. The owning authority validates
the fact, evaluates semantic/effect rules, and only then maps the result to domain events.

### Determinism and revision pinning

- Rules, semantic registries, policies and time inputs are pinned for each settlement.
- Randomness, external responses and clock reads must be explicit evidence/input values.
- A revision conflict produces a typed failure and zero committed domain events.
- Replaying the same event stream with the same pinned revisions produces the same result hash.

World consumption profiles may change tick granularity, batching and reporting, but they must
reuse the same canonical events, owners, revision semantics and settlement path. They are not
the same thing as Creator Workbench, Preview or Production environments. A session pins its
`ActiveWorldRevision` and its referenced `ActiveSemanticSet` before it accepts writes.

### Reservation and hold safety

- A reservation has one owning domain and an explicit lifecycle.
- `consume`, `release`, `expire` and compensation are append-only facts.
- A reservation cannot make another domain's balance, inventory or facility state appear
  committed before the owning authority accepts the corresponding event batch.
- Repeated lifecycle commands are idempotent; unknown, stale or already-final reservations fail
  closed without partial writes.

### Disable means no hidden effects

An optional state group that is disabled must not create implicit ticks, penalties, resource
consumption or background writes. A mode change is an explicit ruleset/state-group revision
transition and is itself replayable.

### Projection is not authority

Snapshots, checkpoints, `CharacterGameRuntimeState`, creator debug views, actor views and Godot
mirrors are rebuildable projections. Missing fields must retain an explicit reason such as
`disabled`, `not_materialized`, `not_authorized` or `unsupported`, never silently become zero.

## Shared Contract Models

The following are value/record contracts, not a universal aggregate:

```text
EntityRef
  entity_type, entity_id

SourceRef
  source_type, source_id, source_revision?

RevisionVector
  entries: map<AggregateRef, non_negative_integer>

EntityRecord
  entity_ref, entity_kind, lifecycle, location_ref, component_refs, source_refs, revision

ThingRecord | EnvironmentRecord
  entity_ref, type_refs, material_refs, property_refs, status_refs,
  ownership_ref?, domain_projection_refs, revision

RelationshipRecord
  relationship_ref, source_ref, target_ref, relation_kind, terms_ref?, visibility_scope,
  lifecycle, revision

CausalEventRecord
  event_ref, trigger_ref, causal_parent_refs, affected_entity_refs, observed_by,
  rule_revision_refs, evidence_refs, settlement_refs

SemanticDefinition
  semantic_id, semantic_version, tags, materials, properties, source_revision

SemanticSnapshot
  entity_ref, component_refs, resolved_tags, resolved_parameters, statuses,
  relation_refs, policy_context_ref, source_revision_vector, digest

ActionPrimitiveDefinition
  action_ref, action_version, target_kinds, required_capabilities,
  observation_requirements, physical_or_logical_fact_kind, cost_policy, failure_policy

EffectDefinition
  effect_id, effect_version, inputs, preconditions, outputs, trace_policy

ActionIntent
  intent_id, principal_ref, actor_ref, action_ref, target_refs, requested_at
  required_observation_scope, expected_revisions, evidence_refs

PhysicalFact | LogicalFact
  fact_id, fact_kind, source_ref, observed_at, subject_refs, payload
  confidence/verification_state, visibility_scope, evidence_refs

SelectorQuery
  query_id, query_version, principal_ref, selectors, expected_revisions, privacy_scope

EffectProposal
  proposal_id, effect_ref, target_refs, preconditions, cost_reservations,
  evidence_refs, source_rule_ref, pinned_revisions

Reservation
  reservation_ref, owner_ref, target_ref, quantity_or_amount, status
  created_revision, expires_at_tick, source_obligation_ref

SettlementPlan
  plan_id, command_id, expected_revision_vector, proposals, event_mapping,
  idempotency_key, causation_id, correlation_id

ScheduledObligation
  obligation_id, owner_ref, due_tick, policy_revision, status, retry_policy,
  compensation_policy, source_refs

WorldConsumptionProfile
  profile_ref, kind, tick_interval, batch_limit, catch_up_budget,
  reporting_projection_refs, active_revision_ref

ActiveSemanticSet
  world_ref, semantic_registry_revision, effect_registry_revision,
  active_rule_revisions, policy_context_refs, activated_at_tick, digest

ActiveWorldRevision
  world_ref, content_package_revisions, semantic_set_ref, schema_registry_revision,
  policy_revision_refs, core_compatibility_version, digest

GameplayPackageManifest
  package_id, package_revision, domain_id, maturity_level, required_core_version,
  owned_aggregates, state_groups, commands, events, projections, declared_schemas,
  dependencies, conflicts, capabilities, privacy_policies, mirror_bindings,
  compatibility_range, migration_refs, content_digest

ProjectionEnvelope
  schema_id, schema_version, projection_revision, source_revision_vector,
  privacy_scope, payload, evidence_refs

SettlementReceipt
  transaction_id, committed_event_ids, stream_revisions, projection_digests,
  rejected_effects, audit_refs, pinned_revisions

RevisionActivationRequest
  request_ref, project_ref, world_ref, candidate_revision_refs, expected_active_digest,
  activation_tick, migration_ref, lock_ref, status
```

领域扩展只能在自己的 package 中增加 schema、authority、projection、Rule IR 定义和
Harness profile。扩展必须声明依赖、冲突、启停、升级、upcaster 和失败码。

## Contract Owner Matrix

| Contract | Canonical owner boundary | Forbidden owner |
| --- | --- | --- |
| identity/reference/entity records | existing world/ESM fact path, extended in place | new world runtime or gameplay god object |
| semantic/tag/material/effect/resistance | status/Patch semantic path, extended in place | sample-local interpreter |
| ActionPrimitive/ActionIntent/PhysicalFact/LogicalFact | embodied interaction registry, ESM and owning Gameplay authority | Godot, VLA or model output as canonical fact |
| selector/query | read-only projection/query path | direct store mutation or private-state scan |
| Rule IR/capability | existing Patch runtime and registered handlers | arbitrary script execution |
| Reservation/Hold | resource/inventory/economy or the domain that owns the reserved fact | shared shadow balance/inventory or generic coordinator |
| SettlementPlan | existing authority settlement + `append_batch` | second ledger/store/coordinator |
| time/obligation/calendar/profile | existing scheduling/continuity helpers plus domain-owned obligations and session revisions | global hidden scheduler or creator environment |
| package/domain-extension manifest and compatibility | Patch/package registry path and closed migrator registry | content package executable handler |
| permission/projection/evidence | authority envelope, projection and mirror owners | Godot or creator direct writes |

The matching plan must replace each boundary-level owner with an exact module/function mapping
and add a regression test before implementation.

## Existing Implementation Binding

P1A must extend the following existing owners in place. These are binding starting points for
the matching plan, not permission to create wrapper runtimes around them:

| Contract | Existing implementation anchor | P1A extension rule |
| --- | --- | --- |
| event, batch, failure and checkpoint envelope | `backend/app/gameplay/models.py` | preserve strict models, append-only identity and zero-write failures |
| append, idempotency, stream revisions and outbox | `backend/app/gameplay/event_store.py` | all new adapters terminate at `GameplayEventStore.append_batch()` |
| event schema and historical upcast | `backend/app/gameplay/event_schema_registry.py`, `event_upcasters.py`, `replay.py` | register immutable schema digests and continuous trusted upcasters |
| state groups and composed read facade | `runtime_state.py`, `state_group_lifecycle_authority.py`, `state_group_views.py` | keep the facade read-only; lifecycle changes are authority events |
| resource/body/status/effective stats | `resource_body_runtime.py`, `status_tags.py`, `effective_stats.py` | add profile and semantic metadata without moving canonical state |
| inventory/equipment/rights/economy/contracts | `inventory_runtime.py`, `equipment_runtime.py`, `ownership_runtime.py`, `economy_runtime.py`, `debt_runtime.py`, `contract_runtime.py` | domain owners retain custody, balance, rights and obligation facts |
| Rule IR, capability and patch lifecycle | `patch_runtime.py`, `patch_rule_settlement.py`, `patch_lifecycle_authority.py` | proposal-only evaluation; no arbitrary package code or direct writes |
| embodied facts and evidence | `embodied_authority_settlement_service.py`, `embodied_evidence_ledger.py`, `esm_service.py` | adapters submit verified facts; they do not become canonical fact stores |
| world scheduling and continuity | `backend/app/world_runtime/scheduling.py`, `continuity.py` | expose explicit tick/obligation inputs; do not add a global clock owner |
| Godot mirror and after-commit delivery | `godot_mirror_projection.py`, `godot_mirror_delivery.py` | publish committed, scope-filtered projections only |

If an implementation plan cannot bind a contract to one of these owners or to a separately
approved domain owner, the contract is not ready for SDD.

## Semantic, Tag And Meta-Rule Contract

Tags and semantic definitions are namespaced, versioned declarations. A package may add a new
definition only under its own namespace and declared schema revision; it may not silently
redefine another package's tag, material, property or effect. Composition order and conflict
resolution are explicit, never dependent on dictionary/load order.

```text
MetaRuleDefinition
  rule_ref, rule_version, trigger_selectors, guard_expression,
  phase, priority, conflict_policy, evaluation_budget,
  proposal_templates, trace_policy, source_revision

RuleEvaluationInput
  trigger_ref, semantic_snapshot, causal_event_ref?,
  action_intent?, pinned_revisions, explicit_time_inputs, evidence_refs

RuleEvaluationTrace
  evaluation_id, rule_refs, matched_selectors, guard_results,
  conflict_decisions, budget_usage, proposal_digests,
  explanation_visibility, input_digest, output_digest
```

Evaluation is deterministic for the same input and pinned revisions. Unknown tags/effects,
ambiguous priorities, dependency cycles, depth/visit/proposal/output budget exhaustion and
privacy-ineligible inputs fail closed before settlement. A meta-rule can produce only a typed
`EffectProposal` or a typed rejection; it cannot append events, mutate a projection, read raw
private mind state or call an unregistered capability. The existing Patch Rule IR and registered
capability handlers remain the implementation owner for this contract.

## Command, Event And Evidence Envelopes

The existing `GameplayEvent` and `AtomicEventBatch` models are the canonical storage envelope.
The shared contract makes the boundary fields explicit so domain packages cannot invent a
second command/event shape:

```text
GameplayCommandEnvelope
  command_id, command_type, command_version,
  principal_ref, actor_ref?, project_ref?,
  transaction_id?, idempotency_key, expected_revisions,
  causation_id, correlation_id, source_ref, submitted_at,
  pinned_revisions, payload

GameplayEventEnvelope
  event_id, event_type, schema_version, stream_ref, stream_revision,
  global_sequence, transaction_id, command_id, causation_id,
  correlation_id, occurred_at, source_ref, visibility_policy,
  pinned_revisions, evidence_refs, payload

EvidenceEnvelope
  evidence_ref, evidence_kind, source_ref, observed_at,
  verification_state, payload_digest, visibility_scope, provenance_refs

AuthorizationDecision
  decision_id, principal_ref, project_scope, capability,
  data_classification, policy_revision, decision, reason_code,
  expires_at?, audit_ref
```

The adapter may enrich an existing model with these fields through a versioned schema, but it
must preserve the current batch identity checks, idempotency digest, stream revision check,
registered event schema requirement and outbox linkage. `AuthorizationDecision` is an input to
the owning authority, not a grant to call that authority directly.

Compatibility is explicit: `GameplayEventEnvelope.stream_ref` maps to the implemented
`GameplayEvent.stream_id`; `GameplayCommandEnvelope.expected_revisions` maps to
`AtomicEventBatch.expected_stream_revisions`; and `pinned_revisions` maps to the batch's existing
revision map. New `occurred_at`, source, evidence and policy metadata may be added only through a
registered event schema version and trusted upcaster. No adapter may maintain a parallel command
or event ledger while the existing model is being extended.

## Creator Capability Adapter

The three creator tiers are part of the permission input contract, while membership management,
UI, CLI and MCP remain owned by the separate Creator Control Plane spec:

| Tier | Foundation-visible capability | Never implied by the tier |
| --- | --- | --- |
| `reader` | read an authorized `creator_debug_view` or published authored projection | draft mutation, simulation write, Gameplay command or runtime-private access |
| `editor` | create/patch/validate scoped drafts and run resettable preview requests | publish, activate, retire, rollback, member management or event-store writes |
| `admin` | approve/publish/activate/retire/rollback requests within project scope and read audit projections | cross-project access, event deletion, arbitrary migrator/handler or core implementation access |

Every tier is still evaluated as `principal + project scope + resource + capability + data
classification + policy revision`. The foundation consumes the resulting
`AuthorizationDecision`, preserves it in audit/evidence references, and rejects missing or
expired decisions. UI, CLI and MCP must produce the same decision for the same request; none may
import internal dossier loaders, layer replacement functions or event-store methods.

## Settlement And Failure Contract

Each cross-domain command must include:

```text
command_id
command_type / command_version
principal_ref / actor_ref?
idempotency_key
expected_revisions
causation_id / correlation_id
source_ref
submitted_at
payload
```

The authority returns either a committed receipt containing transaction, event and projection
revisions, or a structured failure containing a stable failure code, blocked owner/scope,
source refs and zero-write guarantee.

At minimum the contract must distinguish:

- `invalid_schema`;
- `action_primitive_unavailable`;
- `fact_unverified`;
- `permission_denied`;
- `revision_conflict`;
- `idempotency_key_reused`;
- `precondition_failed`;
- `dependency_unavailable`;
- `policy_revision_unavailable`;
- `reservation_unknown_or_final`;
- `package_dependency_conflict`;
- `package_compatibility_failed`;
- `active_revision_lock_conflict`;
- `migration_required`;
- `settlement_write_failed`.

Repeated commands with the same principal and canonical payload return the original receipt.
The same idempotency key with a different payload is rejected and cannot partially settle.

## Time And Obligation Contract

P1A does not implement a global `SimulationClock`. It defines the data and command semantics
needed by later domains:

- domain time is an explicit `tick`/calendar value in commands and events;
- an obligation has an owner, due tick, policy revision, retry policy and status;
- repeated tick delivery is idempotent;
- overdue handling is an explicit domain command, not an in-memory callback;
- compensation or recovery writes new facts and never deletes history;
- a transaction pins its policy/rule revisions until settlement completes;
- disabled state groups produce no implicit obligation or penalty.

World consumption profiles are declared values attached to a session or simulation run. They
may choose different tick intervals, batch sizes, catch-up budgets and reporting projections,
but they do not change event ownership or settlement meaning. Creator Workbench, Preview and
Production are control-plane environments and are orthogonal to these world profiles.

## Reservation And Hold Contract

Resource reservation is already implemented for a bounded resource slice. P1A defines the
shared lifecycle needed by future inventory, construction, production, economy and Survival
domains without moving ownership into a new service:

```text
reserve -> consume/commit
        -> release | expire
        -> compensation fact when a domain policy requires recovery
```

Every reservation has an owner, target aggregate, amount or quantity, source obligation,
creation revision, optional expiry tick and explicit status. A reservation is not a committed
balance, inventory transfer or production result. Unknown, stale, already-final and repeated
lifecycle commands return stable failures or the original receipt and append no partial events.

## Package And Active Revision Contract

`GameplayPackageManifest` is a declaration boundary for schema, semantic, rule and capability
dependencies. It may reference a registered closed-core migrator, but cannot carry executable
Python/GDScript, an event deletion operation or an authority handler.

Before a session accepts writes, the active package revisions, semantic/rule revisions, policy
references, schema registry revision and core compatibility version are combined into an
`ActiveWorldRevision` digest. Its semantic subset is an `ActiveSemanticSet`. Both are pinned in
commands, events, receipts and replay fixtures. This is a runtime contract only; the external
Creator Control Plane and its UI/CLI/MCP product remain a separate spec.

Activation is an explicit lifecycle: candidate revision validation, dependency/conflict check,
activation lock, optional migration reference, scheduled activation, session pinning and
retirement/rollback compatibility. Pending activation cannot silently change an active session;
an activation conflict fails closed and records no production event.

The minimum package/revision state machine is:

```text
draft
  -> validated
  -> staged
  -> scheduled
  -> active
  -> retired

validated/staged/scheduled -> rejected
active -> rollback_requested -> validated -> scheduled
```

`publish`, `activate`, `retire` and `rollback` are append-only control-plane commands. A
rollback selects or creates a compatible new active revision and may add forward migration or
compensation facts; it never removes events from the retired revision. An active revision cannot
be replaced while an activation lock, migration, or pinned session precondition is unresolved.

## Replay, Checkpoint And Migration Contract

Replay restores facts from committed events and historical readers. It does not rerun current
Rule IR, current meta-rules, current capability handlers or current wall-clock values to decide
what happened in the past.

```text
ReplayContext
  stream_scope, from_checkpoint?, target_global_sequence?,
  event_schema_registry_revision, upcaster_chain_digests,
  active_world_revision_digest, projector_id, projector_version

ReplayEvidence
  replay_id, source_event_digest, checkpoint_digest?,
  resulting_projection_digest, applied_event_ids, reader_digests,
  success, failure?
```

Every checkpoint records its source revision vector, last global sequence, projector/schema
versions and projection hash. A restored store must validate event ordering, stream revisions,
schema registrations, transaction membership and idempotency records before becoming write-ready.
Upcasters are trusted, continuous `vN -> vN+1` transforms with registered input/output schema
digests and deterministic output. A migration candidate must pass shadow replay and before/after
fixture comparison before activation; a failed migration leaves the previous active revision and
event history untouched.

## Projection, Permission And Evidence

Every projection carries `schema_id`, `schema_version`, `projection_revision`, source revision
vector, privacy scope and evidence refs. The following views are distinct:

- authority view: complete fields needed by the owning authority;
- actor view: only the actor's permitted gameplay facts;
- creator/debug view: trace and explanations subject to creator scope, but no authority write;
- Godot mirror: presentation-safe committed result and bounded prediction metadata;
- public view: explicitly public fields only.

Creator/debug access never grants a write capability. A projection may redact or omit a field,
but consumers must not infer that absence means zero.

## P1B Verification Gates

P1B is the verification package for this spec, not a new runtime or authority.

### G1 Contract closure

Must prove:

  - stable IDs and references validate;
  - semantic/effect/meta-rule definitions are namespaced, revisioned and deterministic;
  - command, event, evidence and authorization envelopes preserve identity, scope and digest;
- `ActionPrimitiveDefinition` and `ActionIntent` map only to verified `PhysicalFact` or
  `LogicalFact` evidence;
- selector/query is read-only and privacy-filtered;
- Rule/Capability output is a typed proposal;
- reservation lifecycle rejects stale/unknown/duplicate operations without partial writes;
- `SettlementPlan` maps only to `append_batch`;
  - active world/semantic revisions, package/domain-extension compatibility and activation locks
    are pinned and fail closed;
  - package/revision lifecycle transitions and replay/migration preconditions are explicit;
- disabled state groups and world-profile changes produce no hidden writes;
- owner and forbidden-write checks are machine-checkable.

### G2 Contract generality

At least two structurally different contract fixtures must use the same identity, semantic,
causal, settlement, time and projection contracts. A fixture is not automatically a full V0
vertical slice. The recommended fixtures are an effect/resistance case and an object/ownership
interaction case; the exact V0 game sample is selected in P1C.

### G3 Reliability

Must prove successful settlement, structured rejection, permission failure, stale revision,
duplicate command, reservation lifecycle, package conflict, fast-path/general-path result
equivalence, full replay, checkpoint-plus-tail replay, projection rebuild and zero-write failure
behavior.

Evidence must be retained under `.harness/verification/` with a dedicated profile and report.
The matching plan must define the final profile name before implementation begins.

## V0 And Later Domain Boundary

P1C is expected to use the “frost farm” sample because it exercises environment effect,
resistance, state transition and optional survival projection with a small event surface. The
“fire oak door” interaction remains a valid alternative contract fixture or later heterogeneous
sample, but it does not enter implementation until its scope is named in a separate plan.

P1A does not authorize Construction/Production, Survival, Organization, Government, dynamic
market or Population Simulation implementation. Those domains require their own approved specs.

For the first Econ-1 spec, the permitted reference configuration is:

- one player/owner CharacterRecord;
- aggregate customer demand;
- fixed supplier quotes;
- parameterized public competitor profiles;
- no NPC canonical state;
- optional later integration with already existing CharacterRecords only through typed intent.

## SDD Entry Criteria

P1A may enter SDD implementation only after all of the following are true:

1. This spec is approved and its status is changed from `awaiting-user-review`.
2. A matching implementation plan exists under the corresponding plan tree.
3. The plan names exact existing owners/modules for every planned contract.
4. G1-G3 Harness profile names, focused tests and evidence paths are fixed.
5. Migration, rollback and compatibility boundaries are explicit.
6. No unresolved decision changes the ownership or scope model.

Until then, edits are limited to this spec, its review comments and non-authorizing analysis
documents. No implementation agent should create a second runtime, store, bus, scheduler,
shadow NPC state or sample-local settlement path.

## Acceptance Criteria

This spec is ready for planning when reviewers can answer “yes” to all of these questions:

- Can a new domain add only schema, authority, projection and package while reusing the existing
  event spine?
- Is every canonical field assigned one owner?
- Can player, CharacterAgent and embodied adapters use the same ActionPrimitive/ActionIntent/fact boundary?
- Are success, failure, duplicate and stale-revision outcomes deterministic and replayable?
- Are reservation/hold, package compatibility and active revision transitions explicit and
  replayable?
- Are meta-rule/tag conflicts, evaluation budgets and explanation visibility deterministic?
- Can a restored checkpoint validate its event schema/upcaster chain before writes resume?
- Do fast-path and generalized-path settlements produce equivalent typed results and replay?
- Can disabled state groups be proven to produce no hidden effects?
- Are game/simulation/inference profiles separate from Creator Workbench/Preview/Production?
- Can actor, creator/debug and Godot views be separated without granting writes?
- Do `reader`/`editor`/`admin` decisions remain project-scoped inputs rather than direct runtime
  privileges?
- Are V0 and Econ-1 explicitly consumers of this contract rather than new core owners?
- Is Population Simulation clearly outside this spec and separately gated?

## Review Questions

- Confirm “frost farm” as the P1C V0 vertical sample.
- Confirm that Econ-1 first implementation is `bakery-single-owner` and does not materialize
  NPC canonical state.
- Confirm the exact existing module owners to bind in the matching plan.
- Confirm that G2 contract fixtures are distinct from the one formal V0 vertical sample.
- Confirm that package/revision contracts are frozen here while Creator Control Plane UI/CLI/MCP
  remains a separate spec.
