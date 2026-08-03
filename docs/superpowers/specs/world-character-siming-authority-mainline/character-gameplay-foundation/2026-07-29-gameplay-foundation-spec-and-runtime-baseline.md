# Character Gameplay Foundation Specification And Runtime Baseline

Status: `current-code-audit; minimum-runtime-state-and-safe-mirror-foundations-implemented; broader-closure-planned`

Date: `2026-08-03`

## Purpose

This document records the boundary between the approved design target and the
repository implementation as inspected on 2026-08-01. It is a status record,
not a replacement design and not an implementation authorization.

The normative design remains this directory's existing 2026-07-23 documents.
`docs/kimi分析/2026-07-20-游戏角色与世界玩法底座需求分析.md` is an input analysis
only. It does not override this tree.

## Mainline Boundary

Character Gameplay Foundation is the authoritative, event-replayable gameplay
state substrate below gameplay packages and above Godot presentation. It adds
game-body, possession, rights, economy, equipment, and usable-action truth to
the completed character mind core.

It does not:

- replace CharacterAgent L1/L2/L3/L4 cognition, its memory stores, or its
  shadow mind-frame projections;
- move authority, event settlement, or world truth into Godot;
- give Siming raw character-private state or low-level actor control;
- replace the existing ESM/world-runtime authority path; or
- include current LLM, dialogue streaming, TTS, or presentation closure work.

## `CharacterGameRuntimeState` Definition Status

The facade remains fully specified by
`2026-07-23-state-group-registry-and-runtime-facade-design.md`. A minimal,
in-process, read-only core now exists in `backend/app/gameplay/runtime_state.py`:

- immutable `StateGroupDefinition` metadata;
- `StateGroupRegistry` duplicate/unknown dependency, dependency-cycle, and
  enabled-conflict rejection plus deterministic load order;
- `CharacterGameRuntimeStateBuilder`, which composes only enabled group
  payloads into immutable envelopes with source revision vectors and a stable
  checksum.

This is deliberately not the complete runtime façade. It has no actor/world/
patch eligibility policy, lifecycle event materialization, event-store replay
integration, live delta transport, persistence, or a connected Godot mirror.
Consumer-filtered authority/Mind/Godot/debug views and a safe Godot snapshot
envelope exist as reusable read-only foundations only. The current implementation therefore
does not authorize a claim that the complete `CharacterGameRuntimeState` or
`StateGroupRegistry` delivery is finished.

```text
identity, mental, resources, status_tags, body_runtime, inventory, ownership,
equipment, skills, ability_affordances, relationships, effective_stats,
enabled_state_groups, revision_vector
```

It is a versioned read facade over independently owned domain projections. It
is not an aggregate root, write API, replacement for `CharacterDynamicState`,
or a renamed `CharacterRuntimeStateService`.

The implemented core is a composition utility, not a new gameplay truth owner.
It accepts independently produced projections and exposes no write operation.

## Topic Status Matrix

| Topic | Formal specification | Reusable implementation foundation | Not started / deliberately absent |
| --- | --- | --- | --- |
| Foundation invariants and identifiers | Complete in foundation-invariants, event-sourcing, and master designs | Existing structured intent, authority events, and world-result projections | Gameplay-specific identities, command envelopes, event taxonomy, atomic batch API |
| Event sourcing and settlement | Complete | `gameplay/` now has an in-memory event store, atomic batches, committed outbox dispatcher, and replay evidence | Durable storage, production checkpointing/upcasts, and gameplay-domain projection rebuilding |
| State groups and runtime facade | Complete | `gameplay/runtime_state.py` provides immutable definitions, deterministic dependency/conflict validation, and a read-only composed snapshot; `state_group_views.py` provides consumer-filtered views | Eligibility, lifecycle/materialization, committed-event rebuild, live deltas, persistence, and connected Godot mirror delivery |
| Resource/status/body/effective stats | Complete | `NeedTensionState`, `CharacterDynamicState`, dossier embodiment seed, and L1 self-body hints are implemented for cognition | Gameplay health/stamina/fatigue, status tags, body-function runtime, modifiers, explained effective stats |
| Inventory/container/encumbrance | Complete | Interaction contracts name physical affordances only | Item identity, location/container projection, access/capacity policy, storage-ring propagation, encumbrance |
| Equipment | Complete | Mind-frame accepts an `equipment_affordance` summary; presentation has a lightweight `equipment_state` field | Slot runtime, grants, modifier lifecycle, unequip safety, equipment-to-Godot binding contract |
| Ownership/economy/transactions | Complete | Existing authority boundary and typed failure patterns can be reused | Rights, accounts, balances, offer/transaction ledger, debt/contract primitives, atomic cross-domain settlement |
| Stable skills, ability graph, and current affordance | Complete | `character_agent/skills/` contains typed definitions, a registry, initial states, evaluation, primitive expansion, and mind-safe summaries; dossier emits capability seed candidates | Persisted gameplay skill group, graph edges/evidence, body/resource/equipment/environment-aware affordance projection, authority-owned execution costs |
| Patch Rule IR and capabilities | Complete | Existing service boundaries are candidate capability-host locations | Manifest registry, deterministic Rule IR, bounded handlers, patch revision pinning, lifecycle/migration |
| Godot gameplay mirror and prediction | Complete | Policy-filtered Godot projection, backend-issued trusted-local session binding with explicit multi-actor scope, backend-published generic view repository, WebSocket bind/subscribe/snapshot/unsubscribe wiring, after-commit fanout preparation, and a presentation-only consumer reject authority/private/physics fields at every nesting depth | Production identity adapter, continuous after-commit WebSocket delivery, runtime probe, per-actor delta/revision lifecycle, prediction, rollback, and resync |
| Relationships and Siming knowledge | Complete with first-closure deferral | Social memory, dossier relationship seed candidates, and Siming read-model/state-tree work exist | Production relationship graph and Siming Perspective/Knowledge Graph runtime |
| Persistence, migration, hot reload | Complete | Existing dossier reload invalidation is explicitly non-mutating | Gameplay event persistence, checkpointing, event upcasts, state-group/patch migrations |
| `adventure-basic` reference pack and harness | Complete | Repository harness framework and focused backend tests exist | Package manifest/runtime, profiles, Godot probes, replay evidence, five end-to-end scenarios |

## Code Evidence Boundaries

- `backend/app/character_agent/profile/dossier_seed_projection.py` produces
  `candidate_only` relationship and capability initialization bundles; it does
  not persist graph, skill, or game-state truth.
- `backend/app/character_agent/skills/service.py` evaluates registered skill
  paths from supplied skill states. It does not read equipment, body, resource,
  inventory, ownership, or authoritative gameplay events.
- `backend/app/character_agent/mind/affordances.py` deliberately exposes
  summary cards and removes registry internals; it is not an ability graph.
- `backend/app/services/authority_event_bus.py` is an in-memory authority event
  notification surface, not an event store and not an atomic settlement log.
- `backend/app/gameplay/runtime_state.py` is an in-process read façade builder.
  It cannot enable a group, mutate a projection, or replace gameplay event
  settlement; completed event-store integration remains follow-on work.
- `backend/app/services/character_runtime_state_service.py` is current
  character-runtime/cognition plumbing. It must remain separate from the new
  `CharacterGameRuntimeState` facade.
- `backend/app/world_runtime/projection.py` projects existing world result
  deltas. It is not the future gameplay-projection rebuild system.

## Planning Consequence

The next plan increment connects the existing minimal registry/facade core to
committed lifecycle events and a small resource/status/body vertical slice
before adding inventory or economy. It must then rebuild a projection and
deliver a typed mirror delta. The current core alone is not that vertical slice.

The dedicated plan tree is:
`docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/`.
