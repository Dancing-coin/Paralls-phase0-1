# INF-1 Semantic, Entity, And Causal Foundation Design

Status: `implemented-and-verified for the documented INF-1 vertical; broader cross-domain coverage planned`

Date: `2026-08-12`

## Purpose

Define the independent formal contract for `INF-1`, the first mainline
infrastructure package in the post-P5 capability foundation.

`INF-1` gives the repository one shared semantic and causal language over the
existing world-character-Siming-authority runtime. It fixes:

1. who owns semantic definitions versus semantic assignments;
2. how immutable semantic snapshots are derived and digested;
3. how committed events rebuild entity/thing/environment/relationship dossiers;
4. how causal ancestry is recorded append-only and queried deterministically;
5. how revision, idempotency, rejection, privacy, replay, and migration
   behavior are governed; and
6. how future rule proposals remain proposal-only until an existing authority
   commits accepted effects through `GameplayEventStore.append_batch()`.

## Scope

`INF-1` covers:

- tag definitions, assignments, specificity, selector constraints, and snapshot
  digest behavior;
- event-derived entity/thing/environment/relationship/causal dossier
  projections;
- proposal-only semantic/rule outputs and explanation references;
- deterministic replay and checkpoint-tail equivalence for the bounded slice;
- permission/privacy scope rules for authority, actor, and debug reads; and
- migration/rollback rules for semantic and causal readers.

## Existing owner and write path

`INF-1` must reuse existing owners and write paths only.

| Surface | Existing owner | Write authority |
| --- | --- | --- |
| Semantic definition and snapshot resolution | `backend/app/gameplay/semantic_registry.py` | semantic registry code path only |
| Shared types and semantic snapshot schema | `backend/app/gameplay/shared_contracts.py` | typed backend contract only |
| Event truth | `backend/app/gameplay/event_store.py` | existing domain authority via `GameplayEventStore.append_batch()` |
| Replay | `backend/app/gameplay/replay.py` | read-only recovery/rebuild |
| Entity and causal dossiers | `backend/app/gameplay/entity_causal_projection.py` | derived from committed events only |
| Infrastructure proof gate | `.harness/profiles/infra-semantic-entity-causal.json` | Harness only |

The formal write path is:

```text
intent/fact/proposal
  -> existing authority validation
  -> typed event batch
  -> GameplayEventStore.append_batch()
  -> replay / entity-causal projection / filtered reads
```

No semantic registry, projection, Godot mirror, creator tool, model, or Siming
surface may append world-truth events directly.

## Read/write boundary

### Write boundary

- `INF-1` definitions are registry-owned and versioned.
- Tag assignments and domain-state facts remain owned by their domain
  authority.
- Entity and causal dossiers are append-only projections from committed events;
  they are never authoritative mutable stores.
- Rule evaluation is proposal-only. It may produce typed owner fragments or
  references, but it may not settle by itself.

### Read boundary

Three read classes are allowed:

| View | Allowed contents | Forbidden contents |
| --- | --- | --- |
| `authority_evaluation_view` | full snapshot fields and causal references required for settlement | bypassing owner validation |
| `actor_perception_view` | filtered entity/relationship/causal facts allowed by perception/privacy scope | hidden authority-only or creator-only details |
| `creator_debug_view` | filtered digest/trace/debug data authorized by scope | raw private facts, direct writer access, handler internals |

No read surface may convert itself into a write capability.

## Data model

The bounded `INF-1` contract consists of the following conceptual records.

### Semantic definitions and assignments

```text
TagDefinition
  tag_ref
  category
  parent_refs
  parameter_schema
  merge_policy
  allowed_entity_kinds
  visibility
  specificity
  version

TagAssignment
  entity_ref
  component_ref?
  tag_ref
  parameter_values
  source_ref
  revision
```

### Immutable semantic view

```text
SemanticSnapshot
  entity_ref
  entity_kind
  component_refs
  tag_refs
  parameters
  status_refs
  relation_refs
  source_revision_vector
  digest
```

### Event-derived dossiers

```text
EntityRecord
  entity_ref
  entity_kind
  status_refs
  component_refs
  last_event_ref

ThingRecord / EnvironmentRecord
  entity_ref
  property_refs
  ownership_ref?
  domain_projection_refs

RelationshipRecord
  relationship_ref
  source_ref
  target_ref
  relation_kind
  visibility_scope

CausalEventRecord
  event_ref
  causation_id
  causal_parent_refs
  affected_entity_refs
  evidence_refs
  settlement_refs
```

The authoritative truth for dossiers is still the committed event history. The
projection is rebuildable and disposable.

## Event types and projection inputs

`INF-1` does not introduce a second event store or a parallel event family.
Instead, it consumes existing committed `GameplayEvent` history and relies on
typed payload shapes that carry semantic/entity/causal fields when the owner
domain chooses to emit them.

Required committed-event input fields for the bounded slice are:

```text
entity_ref
entity_kind
component_refs?
status_refs?
relationship?
causal_parent_refs?
affected_entity_refs?
evidence_refs?
settlement_refs?
```

The bounded verified projection already proves:

- entity and relationship dossier extraction from committed events;
- causal parent lookup from append-only `causal_parent_refs`; and
- full replay versus checkpoint-plus-tail replay equivalence.

Future generic effect/state/meta-rule outputs must remain explicit follow-up
event families or payload extensions owned by existing authorities.

## Revision, identity, and idempotency contract

`INF-1` must be deterministic under fixed input revisions.

### Revision rules

- Definitions are immutable by published version.
- Snapshot construction pins the active semantic input revision and emits a
  stable digest.
- Rebuilds and readers must report the exact source revision vector they used.
- Stale or incompatible revisions fail closed rather than silently merging.

### Identity rules

- `tag_ref`, `entity_ref`, `relationship_ref`, and `event_ref` are stable
  identities, not per-reader aliases.
- Causal ancestry is recorded by immutable event references only.

### Idempotency rules

- Repeated committed event history must rebuild the same dossiers and causal
  graph.
- Duplicate command or transaction handling remains governed by the existing
  append path and stored idempotency outcome in the event-store contract.
- Same semantic inputs must yield the same snapshot digest and filtered
  explanation trace.

## Failure semantics and zero-write invariant

`INF-1` fails closed.

### Required failures

At minimum, the bounded contract must reject:

- unknown tag definitions or assignments;
- inheritance loops;
- unknown parameters;
- equal-priority semantic conflicts without an allowed merge rule;
- stale revision mismatches;
- causal reader attempts to treat uncommitted or malformed data as committed
  truth; and
- unauthorized proposal paths that try to bypass the event-store authority.

### Zero-write invariant

Any rejection in the settlement path must produce zero committed world-truth
writes. Failed semantic normalization, stale revision, unauthorized proposal,
or conflict rejection must not leave partial event, dossier, or projection
state behind.

Projection rebuild failure after a successful commit must preserve committed
event truth and mark the derived surface unhealthy or blocked; it may not
rewrite history to hide the failure.

## Permissions and privacy

`INF-1` privacy is scope-filtered, not transport-auth complete.

Required rules:

1. event truth retains its original privacy classification;
2. authority evaluation may read full data needed for deterministic settlement;
3. actor perception reads are filtered by allowed visibility scope;
4. creator/debug reads are filtered by explicit debug scope and must not expose
   private raw facts or internal handler details;
5. replay/checkpoint/debug evidence must not widen the privacy scope of stored
   facts; and
6. redacted or filtered views never count as authority truth.

The current repository boundary is still backend-centric. `INF-1` does not
claim production transport authn/authz, Godot delivery privacy closure, or
generic creator publication controls.

## Replay and determinism

`INF-1` must support deterministic rebuild from committed history.

Required replay invariants:

1. full replay and checkpoint-plus-tail replay produce the same canonical
   entity/relationship/causal result;
2. parent/child causal queries are derived from append-only parent refs, not
   mutable child lists;
3. replay never depends on wall clock, external services, or nondeterministic
   iteration order;
4. source revision vectors and digests are reportable in evidence; and
5. rejected requests produce no additional committed events.

Focused proof for this package is the independently named Harness profile:

- `python scripts/verification/harness.py --profile infra-semantic-entity-causal`

## Migration and rollback

`INF-1` migration applies to readers, definitions, and projections. It does not
rewrite historical events.

### Allowed migration

- add new semantic definitions under new versions or revisions;
- add reader/projection support that can still interpret retained history;
- rebuild dossiers from history under compatible reader changes; and
- publish explicit follow-up events when domain truth must materially change.

### Forbidden migration

- mutate or delete historical committed events to fit a new semantic model;
- treat a projection snapshot as new authority truth; or
- roll back by pretending later events never happened.

### Rollback rule

Rollback must activate a compatible prior reader/definition set or a forward
fix. If a prior reader cannot interpret already committed history, rollback is
refused and the package remains on the current compatible path until a forward
fix or compatible reader exists.

## Focused Harness profile and evidence

The named focused profile for this package is:

- `infra-semantic-entity-causal`

The profile and its focused tests must prove, at minimum:

1. selector acceptance and rejection;
2. inheritance and conflict denial;
3. stable semantic snapshot digest under same inputs;
4. event-derived dossier rebuild;
5. causal-parent query correctness;
6. full replay versus checkpoint-tail equivalence;
7. duplicate/idempotent rebuild determinism; and
8. zero committed writes on rejected requests.

## Explicit non-goals

`INF-1` does not include:

- a general-purpose meta-rule executor closure;
- full effect/resistance lifecycle ownership;
- a second scheduler or world loop;
- a new social truth store;
- direct Godot, model, Siming, or creator world writes;
- generic ecology/disaster, population, or civilization runtime;
- complete creator package activation or rollback control plane; or
- transport-complete production privacy/auth closure.

## Completion conditions

`INF-1` may be called `implemented-and-verified` only when all of the following
are true:

1. this independent formal design and its matching plan are approved;
2. owner-scoped code remains on the existing append/replay path;
3. focused tests cover happy path, replay, idempotency, revision rejection,
   privacy scope, and zero-write failure;
4. the focused Harness profile passes and produces fresh evidence;
5. the evidence report names the actual code and proof paths; and
6. remaining planned gaps are explicitly listed instead of being silently
   upgraded to complete.

## Current verified slice and remaining gaps

### Verified bounded slice

- semantic tag definition/assignment resolution;
- immutable semantic snapshot digest and constrained selector behavior;
- inheritance/parameter conflict rejection;
- event-derived entity/thing/environment/relationship dossiers;
- append-only causal-parent query and child derivation;
- full versus checkpoint-tail replay equivalence; and
- focused Harness coverage under `infra-semantic-entity-causal`.
- effect/resistance/state lifecycle resolution with scheduled-expiry proposal;
- phase/conflict/chain-budget evaluation and scope-filtered rule trace; and
- authority -> `SettlementPlan` -> event-store/outbox -> scoped causal projection,
  including idempotency, revision conflict, privacy, and replay evidence.

### Remaining gaps

- broad cross-domain `SettlementPlan` authoring and settlement mapping;
- richer privacy classes and transport-delivered filtered views;
- package/revision activation integration beyond the bounded slice; and
- independent migration/rollback evidence specific to future generic semantic
  event-family expansion.
