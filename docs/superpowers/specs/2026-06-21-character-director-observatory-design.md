# Character Director Observatory Design

Date: `2026-06-21`

## Purpose

This spec defines a full in-Godot observability system for the current role runtime so developers can watch:

- what each character perceives
- how each character interprets the current situation
- what each character intends to do
- how those intentions turn into execution and world results
- how `Siming` acts as director / playwright across the whole scene
- how multi-character interactions line up as a readable dramatic script

It exists because the repository already has a real character-agent runtime, a real `Siming` path, and a real `ESM` settlement path, but current observability is still split across:

- runtime logs
- narrow debug overlays
- backend traces
- isolated verification reports

That is enough for engineering verification, but not enough for intuitive real-machine testing where a developer wants to watch the full scene as a coherent dramatic system.

## Problem

The current repo can already produce:

- per-character private perception
- `L2` interpretation
- `L3` intent selection
- `L4` execution staging
- `Siming` catalyst output
- `ESM` settlement
- shared actor ingress into Godot

But during live Godot testing, these truths remain too fragmented.

Current pain points:

1. you can see that a character moved or spoke, but not clearly why
2. you can inspect backend state, but not as an in-scene developer observatory
3. `Siming` is present, but not visible as a real director seat across the whole story
4. multi-character interactions do not yet read like a script
5. world acceptance / rejection is not visually tied tightly enough to role intention and `Siming` intervention

The result is that the system can be verified, but the dramatic runtime cannot yet be watched as a full live authored scene.

## Goal

Build a developer-only in-Godot observatory that makes the role runtime legible as a dramatic system.

The full system must let a tester:

1. watch each role’s current behavior
2. inspect each role’s perception, memory, interpretation, intent, and execution summary
3. watch `Siming` as a distinct director / playwright seat
4. see role-to-role, role-to-object, role-to-environment, and `Siming` influence links in scene space
5. verify that role runtime, `Siming`, and `ESM` all line up into readable dramatic beats
6. review interactions and dialogue as something script-like rather than raw debug logs

## Non-Goals

This change does not:

- replace the current backend verification / harness system
- expose raw chain-of-thought text
- become a player-facing HUD
- change `ESM` authority boundaries
- change `Siming` domain authority
- rewrite the character-agent business logic

It is an observability and debugging system layered on top of current truth, not a replacement for runtime architecture.

## User-Approved Product Direction

The observatory design is frozen to these choices:

- dual-view system
- default follow mode plus switchable director monitor
- HUD + head tags + in-scene relationship lines
- `Siming` fully represented inside the director monitor and dramatic chain
- pure debug / developer-oriented posture
- developer-only by default

The visual direction is:

- hybrid
  - normal observation feels like a game HUD
  - director monitor feels like a stage / control-room / script workstation

## Core Design Decision

This should not be implemented as one enlarged debug overlay.

It must be implemented as a multi-surface observability system with:

1. in-scene actor tags
2. in-scene relationship / influence overlays
3. a focused single-character inspection panel
4. a global director monitor
5. a script timeline / script ledger
6. a `Siming`-specific director board
7. a world-outcome / settlement trace surface

This is required because each surface answers a different question:

- what is this actor doing right now
- why is this actor doing it
- what is the scene-wide dramatic state
- what is `Siming` pushing
- what did the world accept or reject
- how do all of these line up as dramatic beats

## System Surfaces

### 1. `ActorStateTags`

Per-role floating in-scene labels.

They show:

- actor id / name
- current intent
- current focus target
- current state
- one short “why now” summary
- whether `Siming` recently influenced the actor

Purpose:

- first-glance readability

### 2. `RelationshipOverlay`

In-scene lines and markers that show:

- attention links
- dialogue links
- action intent links
- blocked / constraint links
- `Siming` influence links
- current world-target markers

Purpose:

- first-glance dramatic geometry

### 3. `CharacterObserverPanel`

Single-role deep inspection panel.

It must show:

- perception summary
- internal state summary
- recent memory summary
- `L2` interpretation summary
- `L3` decision summary
- `L4` execution summary
- latest settlement / dialogue result
- latest `Siming` impact on that role

Purpose:

- answer “why is this actor behaving like this”

### 4. `DirectorMonitorPanel`

Global overview monitor.

It must contain:

- cast board for `char_a`, `char_b`, `char_c`
- scene-state board
- world-outcome / constraint board
- `SimingDirectorBoard`

Purpose:

- answer “what is the whole scene doing”

### 5. `SimingDirectorBoard`

Dedicated `Siming` director seat.

It must show:

- latest fairness snapshot summary
- latest intervention candidate
- latest intervention decision
- selected path
- intervention band
- target actor / object / environment
- reason
- downstream status
- no-action reason when relevant

Purpose:

- make `Siming` legible as director / playwright instead of a background service

### 6. `ScriptTimelinePanel`

Global beat timeline.

It must present:

- dramatic beats, not raw logs
- role actions
- role interpretations
- `Siming` interventions
- world settlements
- dialogue turns
- linked beat references

Purpose:

- answer “how did this scene happen”

### 7. `DialogueSceneLedger`

Cross-role interaction and dialogue ledger.

It must support:

- per-pair conversation review
- interpretation mismatch inspection
- “who thought what” alignment
- “what was said vs what was understood” comparison

Purpose:

- make multi-character dialogue look and read like a script

### 8. `WorldOutcomeTrace`

Settlement and dramatic acknowledgment surface.

It must show:

- action request
- settlement acceptance / rejection
- constraint results
- object / environment state changes
- dramatic consequence summaries

Purpose:

- answer “did the world actually accept the scene this actor tried to produce”

## Message Families

The observatory must not be driven only by free-form debug strings.

It needs structured backend-to-Godot message families:

- `character_agent_debug_snapshot`
- `character_agent_debug_event`
- `siming_debug_snapshot`
- `siming_debug_event`
- `world_outcome_trace`
- `script_beat_event`

Each message family must carry:

- `producer_ts`
- `causation_id`
- `correlation_id`

and enough participant information for cross-role beat reconstruction.

## Backend Projection Responsibilities

### Character Agent

Add a dedicated projection layer that converts current role runtime truth into observatory payloads.

Suggested module:

- `backend/app/services/character_agent_debug_projection.py`

Responsibilities:

- emit current actor dramatic state summary
- emit actor dramatic events after key runtime stages
- preserve references back to timeline events

### Siming

Add a dedicated projection layer for `Siming`.

Suggested module:

- `backend/app/services/siming_debug_projection.py`

Responsibilities:

- expose `Siming` director-seat summaries
- emit `Siming` dramatic events
- preserve selected path, band, target, and downstream effect

### World Outcome

Add a dedicated projection layer for settlement / constraint / world-change observability.

Suggested module:

- `backend/app/services/world_outcome_debug_projection.py`

Responsibilities:

- convert `ESM` / authority results into dramatic world-outcome summaries

### Script Beat Aggregation

Add a dedicated beat aggregation layer.

Suggested module:

- `backend/app/services/script_beat_projection.py`

Responsibilities:

- merge role, `Siming`, and world events into beat-oriented script summaries

## Godot State Aggregation

Godot should not let every UI surface parse backend payloads independently.

A single aggregation node should own cached observatory state.

Suggested module:

- `scripts/ui/CharacterDirectorState.gd`

Responsibilities:

- latest role dramatic state by actor
- recent role events by actor
- latest `Siming` dramatic state
- recent `Siming` events
- recent world-outcome events
- recent script beats

All observatory UI surfaces should consume this state center, not the websocket payloads directly.

## Interaction Model

The developer interaction model is fixed to:

- `F6` — observatory master toggle
- `F7` — follow mode / director monitor mode toggle
- `F8` — script mode toggle
- `Tab` / `Shift+Tab` — cycle observed actor
- click actor — lock observer target
- `Space` — freeze current observatory frame
- `Esc` — leave freeze mode

## Freeze Mode

The full observatory must support frozen inspection.

Purpose:

- hold a dramatic moment still
- inspect role, `Siming`, and world state alignment
- debug fast transitions that are hard to observe live

Freeze mode is not optional in the full system because the runtime now includes fast transitions across:

- perception
- interpretation
- execution
- `Siming` influence
- settlement

## Why `Siming` Must Appear In Multiple Layers

`Siming` is not just another event producer.

It functions as:

- fairness observer
- intervention chooser
- dramatic catalyst
- playwright-like scene shaper

So the observatory must surface `Siming` in all of:

- director monitor
- single-role observer traces
- relationship overlay
- script timeline
- world-outcome acknowledgment flow

If `Siming` appears only in a single debug panel, the observatory fails its core purpose.

## Data Presentation Rules

### Do Show

- short structured summaries
- recent memory summaries
- current risk / opportunity / ambiguity
- current selected intent
- current execution summary
- recent `Siming` reason and target
- recent world acceptance / rejection
- beat-level script summaries

### Do Not Show

- raw unrestricted chain-of-thought text
- unstable full raw memory dumps as primary UI
- uncontrolled per-frame noise

The full observatory is for human-readable dramatic debugging, not for dumping backend internals blindly.

## Full Build Requirement

This design is not an MVP-only sketch.

The implementation plan should target the full system architecture:

- backend projection layers
- Godot aggregation state center
- all major UI surfaces
- `Siming` director-seat treatment
- script-ledger treatment
- freeze mode

Implementation may still be sequenced, but the target architecture must remain the full observatory, not a single expanded debug overlay.

## Acceptance Criteria

The full observatory is complete when all are true:

1. a tester can watch current role intent, focus, state, and “why now” in-scene
2. a tester can inspect any role’s perception, memory, interpretation, decision, execution, and outcome
3. a tester can watch all three roles plus `Siming` in one global director monitor
4. `Siming` is legible as an active directing force rather than a hidden background service
5. role-to-role interactions can be reviewed in a script-like ledger
6. world settlement / rejection can be matched against role intention and `Siming` influence
7. the observatory data path is structured and state-centered, not string-log-only
8. the system is developer-only and hidden by default

## Summary

The repository already has enough real dramatic runtime truth that a simple debug overlay is no longer sufficient.

What it needs now is a full developer observatory that makes:

- role cognition
- `Siming` direction
- world authority
- multi-role dramatic interaction

visible together in Godot as one coherent scene-debugging system.
