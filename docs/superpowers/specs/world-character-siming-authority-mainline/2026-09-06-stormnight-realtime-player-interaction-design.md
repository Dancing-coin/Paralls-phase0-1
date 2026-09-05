# Stormnight Realtime Player Interaction Design

## Purpose

Turn the completed Stormnight reference case into a separately runnable,
real-time player vertical without merging it with the knight church/Throne Hall
scenes. The vertical reuses the main application's shared
`GameplayEventStore`, WebSocket bridge, PlayerShell, Character Agent runtime,
ActionWindow and existing owners.

## Player loop

```text
Godot PlayerShell input
→ finite Stormnight player intent
→ Stormnight session adapter on the shared event store
→ Case / P5 / Quest / Social / Inventory owner validation
→ append-derived receipt + filtered projection
→ WebSocket response
→ Godot UI, actors and object state update
```

The client can request only `start`, `advance`, `inspect`, `question`, `hide`,
`pursue`, and `accuse`. It cannot select a stream, owner, event family,
revision, action graph, spatial snapshot, outcome or arbitrary event vector.
The local reference session fixes its player identity to
`character:stormnight-investigator@1`; an incoming actor identity is rejected.

## Backend adapter

`StormnightRealtimeSessionService` is an additive adapter over the application
shared event store. It does not own a second store or runtime. It creates the
existing `ScriptedMysteryCaseAuthority`, `QuestEvidenceAuthority`,
`SocialFactAuthority`, `InventoryAuthorityService`, `StormnightOwnerHandoffService`
and P5 `InvestigationConflictAuthority` over that same store.

The adapter offers one strict `StormnightPlayerIntent` model. Each allowed
intent resolves through a package-defined fixed mapping:

- `start`: open the admitted case;
- `advance`: advance only to the next declared phase;
- `inspect`: admit one declared clue, record Quest evidence and Inventory
  custody through their owners;
- `question`: record only the declared target statement through Case and
  Social owners;
- `hide` / `pursue`: use a fixed ActionWindow fixture and committed source
  snapshot; the caller supplies neither coordinates nor revisions;
- `accuse`: use admitted, visible evidence refs and the current case revision.

After an accepted intent the service creates filtered player context and asks
the existing Character Agent runtime for non-canonical NPC proposals. The
proposal is returned as presentation advice only; it cannot directly append.

## Godot presentation

`StormnightRealtimePlayable.tscn` is an independent scene. It instances the
existing PlayerShell, four primitive Stormnight actors, and a player HUD. It
does not instance `ThroneHall*`, `KnightRoleSkin.tscn`, the church glTF, or the
knight glb.

The scene maps keyboard actions to finite commands and sends a WebSocket
`stormnight_player_intent` envelope only after it has a backend connection.
Responses update only committed state. A pending interaction may animate a
local highlight, but rejection clears it and restores the last projection.

The HUD shows phase, evidence, last outcome, action feedback and NPC proposal
summary. It never renders another actor's private knowledge.

## Completion evidence

- Direct service tests cover start, inspect/custody, statement, action,
  accusation, duplicate/changed duplicate, private/stale/unknown rejection and
  zero-write.
- WebSocket handler tests prove a caller cannot choose another actor or owner.
- Godot static and headless probes prove PlayerShell, HUD, four actors and
  response rollback without church/knight references.
- A local backend-to-Godot smoke harness opens a case, sends player intents,
  receives committed projections and verifies visible state changes.
- Existing Stormnight replay and all four outcomes remain green.

## Explicit non-goals

This vertical is one local-player reference session, not authenticated public
multiplayer, arbitrary free-text truth creation, a generic new scheduler, or a
replacement for the existing mirror/session systems. Online account binding,
voice synthesis and live LLM provider operations remain follow-on work.
