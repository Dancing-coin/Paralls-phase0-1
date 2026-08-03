# Character Gameplay Foundation Master Design

Status: `partially-implemented; broader-closure-planned`

Date: `2026-07-23`

## Purpose

Define the complete target architecture and the first executable closure for
upgrading the current character agent from a cognition-capable actor into an
authoritative, extensible game character.

The design preserves the completed mind core and supplies the missing game
body: resources, bodily condition, possessions, equipment, ownership,
transactional economy, actionable abilities, rule extension, persistence, and
Godot projection.

The target architecture is no longer purely aspirational. The Gameplay event
store/replay/outbox spine, minimum runtime-state composition core, first
state-group/resource/inventory/equipment/ownership/economy/patch slices, and
the safe Godot-mirror foundation now have focused evidence. This document
still does not claim `adventure-basic` or full gameplay-domain closure.

## Input Analysis

This design consolidates requirements from:

- `docs/kimi分析/2026-07-20-游戏角色与世界玩法底座需求分析.md`
- `docs/上下文不够用/对话2.md`
- `docs/上下文不够用/对话3.md`

Those files are analysis inputs, not implementation truth. Statements in them
about current code completion are not adopted unless consistent with the
active mainline documents and repository evidence.

## Source-Of-Truth Position

This design is an incremental child of:

- `world-character-Siming-authority-mainline/README.md`
- `2026-06-29-world-character-siming-authority-mainline-master-design.md`
- the completed character mind-core design and status documents

It does not redefine Godot as world authority, move cognition into ESM, give
Siming low-level actor control, or replace L1/L2/L3/L4.

## Problem Statement

The repository has a strong character cognition and authority loop, but the
target gameplay foundation also needs to answer:

- What resources and bodily constraints does the actor have now?
- What physical items, abstract balances, rights, debts, and contracts exist?
- Which equipment is active, and what does it grant or modify?
- Which abilities are stable knowledge, and which are usable in this moment?
- How can new gameplay register state, rules, effects, AI projections, Godot
  presentation, persistence, and verification without editing every core
  module?
- How is every change replayable, explainable, authoritative, and mirrored?

## Architecture

```text
Authored Profile / Dossier Seeds
  -> Domain Materializers
  -> Domain Event Streams
  -> Domain Projections And Stores
  -> CharacterGameRuntimeState Facade
  -> Mind-Safe Views / Godot-Safe Views / Debug Views

Structured Intent
  -> Preconditions
  -> Cost Reservation
  -> Skill / Ability / Modifier Evaluation
  -> Authority Settlement
  -> Atomic Event Batch
  -> Projection Update
  -> Snapshot / Delta / Evidence
```

### Truth categories

- Authored truth: profile and dossier facts that define the actor baseline.
- Event truth: immutable accepted changes in domain streams.
- Projection truth: rebuildable current state derived from events.
- Advisory output: cognition, skill, VLA, and rule proposals awaiting authority.
- Presentation state: Godot-local rendering and reversible prediction.

No projection, advisory result, or presentation state may silently promote
itself into event truth.

## Character Runtime Composition

`CharacterGameRuntimeState` is a read facade over enabled domain projections:

```text
identity
mental
resources
status_tags
body_runtime
inventory
ownership
equipment
skills
ability_affordances
relationships
effective_stats
enabled_state_groups
revision_vector
```

The facade does not own domain writes. Each state group declares its schema,
commands, events, projections, permissions, persistence, synchronization,
visibility, prediction, and migration policies.

## Gameplay Extension Model

The extension model combines data-driven safety with an escape hatch for
complex trusted behavior:

1. A versioned `GameplayPatchManifest` declares state, data, rules,
   capabilities, Godot bindings, migrations, and verification.
2. Deterministic Rule IR represents triggers, typed conditions, reservations,
   typed effects, and modifier policies.
3. A rule may call only a registered capability handler named in the manifest.
4. The handler receives schema-validated input, runs under bounded execution,
   and returns proposals rather than direct writes.
5. Authority settlement validates proposals and appends accepted event batches.

The first closure trusts repository-owned authors. A future sandbox may adapt
the same capability boundary without changing domain truth contracts.

## Possession And Ownership Boundary

- Inventory answers where a physical item is.
- Containers answer how items may be stored and accessed.
- Ownership answers which economic or legal rights a subject holds.
- Equipment answers how an item currently affects an actor.
- A proof item may reference a right, but destroying the item does not
  implicitly destroy the right.
- Actors remain actors. Employment, guardianship, command, lease, and similar
  relations are modeled as rights or contracts, not `ItemInstance` ownership.

## Ability Boundary

The stable ability graph records learned or granted skills, actions,
prerequisites, costs, and evidence. The current affordance projection combines
that graph with body, resources, equipment, inventory, environment,
relationship permissions, and authority policy.

Skill and cognition layers may rank paths. Settlement decides whether a path
succeeds and which events result.

## Relationship And Siming Boundary

- Objective social/legal relationships are authority facts.
- Trust, fear, hostility, secrets, and misunderstandings are actor-private
  relationship beliefs.
- Siming may consume public facts, authority evidence, and explicit actor
  perspective facades.
- Siming cannot consume raw actor-private memory or write world truth.
- Relationship, ability, and Siming graphs share evidence and governance value
  objects, not one universal graph store or ontology.

## Godot Boundary

Godot contains:

- a global connection and routing bridge
- one runtime mirror component per actor
- consumer APIs for UI, movement, animation, effects, equipment presentation,
  audio, and debugging
- reversible predictions correlated by `prediction_id`

The backend confirms or rejects every authoritative mutation. Revision gaps,
unknown schemas, or rejected predictions trigger rollback or full resync.

## First Executable Closure

The `adventure-basic` package proves the foundation through five connected
scenarios:

1. purchase and equip a sword
2. block a known sword action because of injury or insufficient stamina
3. activate a storage-ring container while preserving correct carried weight
4. keep a land ownership right independent from its physical deed document
5. execute a minimal gift, debt, and contract lifecycle without introducing a
   dynamic market simulator

The package includes transactional economy primitives but excludes dynamic
market simulation. Cultivation receives a complete extension contract but no
first-closure implementation.

## Failure Model

All failures are typed and contain the failed stage, revision context, source
references, retry semantics, and recovery action. Precondition, handler,
transaction, event-upcast, projection, and Godot synchronization failures may
not leave partial authoritative state.

## Non-goals

- implementing every gameplay genre
- a universal graph database
- a full market simulator
- a full cultivation game
- arbitrary in-process third-party scripts
- moving world truth or settlement into Godot
- flattening mental, body, item, economic, and graph state into one model
- replacing current character cognition or authority architecture

## Acceptance Criteria

- Every child spec has explicit dependencies, authority rules, failure
  semantics, acceptance criteria, and planned harness evidence.
- The first closure can rebuild all authoritative projections from events.
- Cross-domain economic and equipment operations are atomic and idempotent.
- Godot can mirror, predict, confirm, reject, roll back, and resynchronize.
- Ability knowledge remains stable when temporary conditions block execution.
- Physical items and abstract rights remain separate but traceably linked.
- Gameplay packages cannot write domain stores or world truth directly.
- Actor-private relationship and memory information does not leak to Siming or
  unrelated Godot consumers.
- The `adventure-basic` scenarios pass focused profiles and the planned
  aggregate profile.

## Harness Mapping

- `gameplay-foundation-contract`
- `gameplay-event-replay`
- `gameplay-state-groups`
- `gameplay-possession-equipment`
- `gameplay-economy-authority`
- `gameplay-patch-runtime`
- `godot-gameplay-mirror`
- `adventure-basic`
- aggregate: `gameplay-foundation-all`
