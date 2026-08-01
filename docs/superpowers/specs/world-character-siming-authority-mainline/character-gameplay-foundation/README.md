# Character Gameplay Foundation Spec Tree

Status: `awaiting-user-review`

Date: `2026-07-23`

## Purpose

This folder defines the incremental specification tree that turns the completed
character mind core and the existing world-character-Siming-authority runtime
into an extensible game-character foundation.

It is a child of the active mainline spec tree. It does not replace:

- the world-character-Siming-authority mainline
- the completed character mind core
- existing L1/L2/L3/L4 cognition boundaries
- backend authority and settlement ownership
- the preserved Phase 0 smoke-compatibility surface

The target is a character that can participate in resources, bodily state,
inventory, equipment, ownership, economy, skills, relationships, and future
gameplay domains while new gameplay is added through versioned rule packages
rather than ad hoc cross-module writes.

## Approved Design Decisions

- Backend authority owns gameplay truth; Godot mirrors, presents, predicts, and
  submits requests.
- `CharacterGameRuntimeState` is a versioned composition facade, not a mutable
  god object.
- State groups are registered and instantiated dynamically per world, actor,
  and enabled gameplay package.
- Durable gameplay truth uses event sourcing. Checkpoint snapshots are caches,
  not independent truth.
- Cross-domain settlement appends one atomic event batch.
- Gameplay packages use declarative Rule IR by default and may call only
  registered, trusted capability handlers.
- The first delivery supports internal and trusted authors. Untrusted
  third-party code execution is outside the first closure.
- Objective relationship facts and actor-private relationship beliefs are
  separate.
- Stable ability knowledge and momentary affordance are separate.
- Relationship, ability, and Siming graphs share governance value objects, not
  one universal graph runtime.
- The Siming Perspective/Knowledge Graph is specified here but is not part of
  the first implementation closure.
- `adventure-basic` is the first executable reference package and includes a
  transactional economy foundation.

## Reading Order

1. [Master design](2026-07-23-character-gameplay-foundation-master-design.md)
2. [Foundation invariants and domain boundaries](2026-07-23-foundation-invariants-and-domain-boundaries-design.md)
3. [State-group registry and runtime facade](2026-07-23-state-group-registry-and-runtime-facade-design.md)
4. [Event sourcing and authority settlement](2026-07-23-event-sourcing-and-authority-settlement-design.md)
5. [Coupled event store and authority bus](2026-07-31-coupled-event-store-and-authority-bus-design.md)
6. [Resource, status, body, and effective stats](2026-07-23-resource-status-body-and-effective-stats-design.md)
7. [Inventory, container, and encumbrance](2026-07-23-inventory-container-and-encumbrance-design.md)
8. [Ownership, economy, and transactions](2026-07-23-ownership-economy-and-transaction-design.md)
9. [Equipment runtime](2026-07-23-equipment-runtime-design.md)
10. [Skill, ability graph, and affordance](2026-07-23-skill-ability-graph-and-affordance-design.md)
11. [Gameplay Patch Rule IR and capabilities](2026-07-23-gameplay-patch-rule-ir-and-capabilities-design.md)
12. [Godot runtime mirror and prediction](2026-07-23-godot-runtime-mirror-and-prediction-design.md)
13. [Relationship graph boundaries](2026-07-23-relationship-graph-boundaries-design.md)
14. [Siming Perspective/Knowledge Graph contract](2026-07-23-siming-perspective-knowledge-graph-contract-design.md)
15. [Persistence, replay, migration, and hot reload](2026-07-23-persistence-replay-migration-and-hot-reload-design.md)
16. [Gameplay-domain extension catalog](2026-07-23-gameplay-domain-extension-catalog-design.md)
17. [adventure-basic reference package](2026-07-23-adventure-basic-reference-pack-design.md)
18. [Verification and acceptance matrix](2026-07-23-verification-and-acceptance-matrix-design.md)
19. [Specification and runtime baseline](2026-07-29-gameplay-foundation-spec-and-runtime-baseline.md)

## Dependency Layers

```text
Existing Mainline And Character Mind Core
  -> Foundation Invariants
  -> Identity / Event / Evidence / Authority Contracts
  -> State Groups And Runtime Facade
  -> Core State + Possession + Economy + Equipment + Ability
  -> Rule IR And Settlement
  -> Godot Mirror + Persistence + Verification
  -> adventure-basic Reference Closure
  -> Deferred Domain Implementations
```

Dependencies point downward only. A domain spec may consume a lower-layer
contract, but lower layers must not import domain-specific combat, cultivation,
market, or Siming policy.

## Delivery Boundary

### First implementation closure

- foundation invariants and identifiers
- event store, atomic event batches, replay, and projection rebuilding
- state-group registry and runtime facade
- resource, status-tag, body, and effective-stat state
- item, inventory, container, storage-ring, equipment, and encumbrance state
- currency, transaction, ownership-right, debt, and contract primitives
- stable skill/ability state plus current affordance projection
- declarative gameplay patch registration and trusted capability handlers
- Godot snapshot/delta mirror, prediction confirmation, rollback, and resync
- `adventure-basic` reference scenarios and harness evidence

### Fully specified but deferred from the first closure

- cultivation runtime implementation
- dynamic market simulation
- production relationship graph implementation
- Siming Perspective/Knowledge Graph implementation
- untrusted third-party script sandbox
- large production skill/action/content libraries

These topics have explicit contracts and extension points. Deferred means they
are not first-closure implementation work; it does not mean their boundaries
are undefined.

## Review And Planning Gate

This tree remains `awaiting-user-review` until the user approves the written
files. No implementation plan should treat it as approved before that review.

The dedicated draft implementation-plan tree is now available at:

- `docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/`

It remains `drafted-for-spec-review` and does not authorize implementation.
After approval, execute it in dependency order and end with fresh evidence from
the planned `gameplay-foundation-all` harness aggregate plus the repository-wide
`all` profile.
