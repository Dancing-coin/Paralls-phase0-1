# Character Gameplay Foundation Spec Tree

Status: `partially-implemented; broader-closure-planned`

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

The foundation core is now executable: the Gameplay event store, replay,
committed outbox/authority-bus spine, and the minimum read-only
`CharacterGameRuntimeState` composition core have code and focused evidence.
This does not claim the complete gameplay facade, state-group lifecycle,
inventory/equipment/economy domains, persistence, or Godot mirror is finished.
The first inventory and equipment placement/activation authority slices have
focused backend evidence; their broader domain closures remain planned.
The economy slice now additionally proves account transfer, one fixed-offer
purchase, one zero-consideration item/title gift, and simple-debt
issue/repayment settlement. Credential links are also replayable evidence-only
records: their issue/supersede events retain the declared holder and pinned
inventory revision as issuance evidence, while a read-only item-presence/holder
presentation check remains current-state based. This is not generic commerce
closure. Account/debt privacy is currently backend-only query filtering,
including configured audience field redaction, not a Godot or transport privacy
closure. Registered `simple_service` contract
terms with a pinned completion evidence kind can atomically record matching
evidence and fulfill; arbitrary or cross-domain execution remains deferred.
The first governed patch-runtime slice now additionally proves immutable
trusted manifests, dependency/schema conflict rejection, deterministic
proposal-only rules, side-effect-free capability gates, and a minimal
authority-ledger install/enable/disable lifecycle slice, rule-only same-patch
upgrade/rollback, and fail-closed lifecycle replay. It does not yet
convert arbitrary proposals into domain settlement (only `resource.consume` is
currently revalidated and settled), persist handler artifacts,
or implement patch-owned data-transform lifecycle migration beyond the first
bounded resource-bounds upgrade and Godot delivery. That upgrade pins old/new
resource and state-group definitions, emits a typed resource fact plus a
state-group definition/source transition in the Patch cutover batch, requires
deterministic replay evidence, and explicitly rejects its lossy rollback. A
bounded explicit-actor Patch enable/disable can now atomically materialize or
disable its uniquely owned declared state groups with the active-set cutover;
compatible same-patch revisions can identity-rebind those groups during
explicit actor upgrade/rollback. It does not provide actor discovery,
domain-effect revocation, compensation, generic or additional data-transform
migration. Candidate manifests and
active-set identity have durable JSON snapshot recovery; this
does not constitute a production patch registry.

The shared durable-store recovery path also validates the full ledger/index
relationship before reopening: transaction-embedded events, append results,
idempotency records and outbox entries must agree with the canonical event
ledger. Corrupt or partial snapshots fail closed, protecting replay,
duplicate handling and append-derived receipt evidence for all owner rows.

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
2. [Gameplay Foundation Shared Contract Closure](2026-08-07-gameplay-foundation-shared-contract-closure-design.md) `approved` (first-phase P1A dependency; [matching plan](../../../plans/world-character-siming-authority-mainline/phase-one-gameplay/2026-08-07-gameplay-foundation-shared-contract-closure-implementation-plan.md))
3. [Foundation invariants and domain boundaries](2026-07-23-foundation-invariants-and-domain-boundaries-design.md)
4. [State-group registry and runtime facade](2026-07-23-state-group-registry-and-runtime-facade-design.md)
5. [Event sourcing and authority settlement](2026-07-23-event-sourcing-and-authority-settlement-design.md)
6. [Coupled event store and authority bus](2026-07-31-coupled-event-store-and-authority-bus-design.md)
7. [Resource, status, body, and effective stats](2026-07-23-resource-status-body-and-effective-stats-design.md)
8. [Inventory, container, and encumbrance](2026-07-23-inventory-container-and-encumbrance-design.md)
9. [Ownership, economy, and transactions](2026-07-23-ownership-economy-and-transaction-design.md)
10. [Equipment runtime](2026-07-23-equipment-runtime-design.md)
11. [Skill, ability graph, and affordance](2026-07-23-skill-ability-graph-and-affordance-design.md)
12. [Gameplay Patch Rule IR and capabilities](2026-07-23-gameplay-patch-rule-ir-and-capabilities-design.md)
13. [Godot runtime mirror and prediction](2026-07-23-godot-runtime-mirror-and-prediction-design.md)
14. [Relationship graph boundaries](2026-07-23-relationship-graph-boundaries-design.md)
15. [Siming Perspective/Knowledge Graph contract](2026-07-23-siming-perspective-knowledge-graph-contract-design.md)
16. [Persistence, replay, migration, and hot reload](2026-07-23-persistence-replay-migration-and-hot-reload-design.md)
17. [Gameplay-domain extension catalog](2026-07-23-gameplay-domain-extension-catalog-design.md)
18. [Package content and cross-domain binding matrix](2026-08-17-package-content-and-cross-domain-binding-matrix-design.md) `design baseline; no runtime implementation`
19. [Package contract closure and manifest adapter](2026-08-17-package-contract-closure-and-manifest-adapter-design.md) `design-only; implementation gated`
20. [Federated Gameplay Extension Platform](2026-08-18-federated-gameplay-extension-platform-design.md) `INF-P P1 binding sequencing implemented and verified; package and row gates remain separate`
21. [Federated Gameplay Extension Platform approval packet](2026-08-18-federated-gameplay-extension-platform-approval-packet.md) `platform contract approved; downstream implementation separately gated`
22. [Federated Gameplay Extension Platform approval-readiness audit](2026-08-18-federated-gameplay-extension-platform-approval-readiness-audit.md) `design approved; INF-P schema/P1 mechanics implemented and verified`
23. [Federated Gameplay Extension Platform schema decision design](2026-08-18-federated-gameplay-extension-platform-schema-decision-design.md) `historical design gate; superseded by verified INF-P implementation`
24. [Federated Gameplay Extension Platform schema mapping and migration errata](2026-08-18-federated-gameplay-extension-platform-schema-mapping-and-migration-errata-design.md) `approved mapping; INF-P mechanics implemented and verified`
25. [Federated Gameplay Extension Platform schema-closure addendum](2026-08-18-federated-gameplay-extension-platform-schema-closure-addendum.md) `approved closure; INF-P mechanics implemented and verified`
20. [adventure-basic reference package](2026-07-23-adventure-basic-reference-pack-design.md)
21. [Verification and acceptance matrix](2026-07-23-verification-and-acceptance-matrix-design.md)
22. [Specification and runtime baseline](2026-07-29-gameplay-foundation-spec-and-runtime-baseline.md)
23. [WebSocket session identity and mirror scope](2026-08-03-websocket-session-identity-and-mirror-scope-design.md)

## Phase One Gameplay Specs

The first-phase vertical and evidence specifications live in a dedicated child tree so that
domain closure is not mixed into the reusable foundation contract:

- [Phase One Gameplay Specification Tree](../phase-one-gameplay/README.md)
- [P1B Contract Verification And Evidence](../phase-one-gameplay/2026-08-07-p1b-contract-verification-and-evidence-design.md)
- [P1C Frost Farm Contract Sample](../phase-one-gameplay/2026-08-07-p1c-frost-farm-contract-sample-design.md)
- [P1D Econ-1 Bakery Reference Game](../phase-one-gameplay/2026-08-07-p1d-econ1-bakery-reference-game-design.md)
- [P1E Generalization Gate](../phase-one-gameplay/2026-08-07-p1e-generalization-gate-design.md)

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

This tree is partially implemented. It authorizes continued work on the
existing foundation core only when each change follows the plans, preserves the
listed boundaries, and adds focused evidence. Broader domain closure still
requires the relevant specification and plan gates; it must not be inferred
from the implemented core.

The dedicated draft implementation-plan tree is now available at:

- `docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/`

It is execution-active for the foundation core. Execute remaining work in
dependency order and end with fresh focused evidence plus the repository-wide
`all` profile when the environment permits it.
