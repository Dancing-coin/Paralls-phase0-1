# 2026-06-24 Observatory UI Lightweight Debug Layout Design

## Status

Draft for review.

## Purpose

The current `Character Director Observatory` UI is useful for debugging, but the default layout overloads the playfield with multiple overlapping fixed panels. This makes it hard to read the most important information while actively moving and observing characters in Godot.

This design defines a lightweight developer-facing default layout that:

- reduces overlap and screen obstruction
- restores information hierarchy
- keeps character-bound information near the character
- preserves deeper audit surfaces for dedicated debug review

This is explicitly a debugging and test-support interface. It is not a player-facing product UI.

## Hard Constraints

- Developer-only
- Hidden by default
- Not part of the player-facing shipping UX
- Must remain test-oriented and observability-oriented
- Must not change gameplay authority boundaries
- Must not add business-logic coupling from UI back into runtime decisions
- Must preserve existing observatory data sources and message families
- Must continue supporting director-mode and script-mode deep inspection

## Problem Summary

Current default observatory presentation has two major issues:

1. Information density is too high in the default state.
2. Multiple fixed panels overlap visually and compete for attention.

Specific symptoms:

- left-side and right-side blocks compete with focus hints and scene observation
- bottom information competes with character observation and world inspection
- character-specific information is detached from the character and must be mentally remapped
- too much detail is shown at once during “play while observing”

## Design Goal

Split the observatory into three information layers:

1. Character-local layer: concise information attached to the character
2. Current-selection layer: deeper detail for the currently observed actor
3. Global-event layer: a very thin rolling summary of the latest cross-system events

The default state should optimize for “play while observing”.

Dedicated heavy inspection should still exist, but only behind explicit mode switches.

## Default Layout

### 1. Overhead Character Cards

Each observable actor gets a compact head-follow card.

Base card:

- line 1: `Actor Name | Current State`
- line 2: `Current Intent -> Current Target`

For the currently observed actor only:

- line 3: one short summary line for “why now”

Behavior rules:

- current observed actor is visually highlighted
- non-selected actors are lower emphasis
- distant actors degrade to a single-line form
- if actors cluster visually, only the selected actor keeps the full card; others degrade to abbreviated form

What moves here from the old layout:

- core summary from `ActorStateTags`
- the most immediate “what is this actor doing now” signals

What does not move here:

- long thought summaries
- world outcome history
- full script ledger content

### 2. Right-Side Fixed Detail Rail

Only the currently observed actor gets a full detail panel.

Position:

- fixed on the right side of the screen

Content sections:

1. What was perceived
2. How it was interpreted
3. What the actor is preparing / executing
4. World / Siming feedback

Display rules:

- each section is limited to 1 to 2 lines in default mode
- empty sections are hidden entirely
- panel height is capped
- long strings are summarized rather than dumped raw

What this absorbs:

- most of `CharacterObserverPanel`

### 3. Bottom Thin Event Strip

A thin, always-on bottom strip stays visible in developer mode.

It shows only the latest 3 items across:

- world outcomes
- Siming actions
- script beats

Each row contains:

- a short type tag: `世界`, `司命`, `节拍`
- one short white-language summary

Behavior rules:

- newest row appears first
- only 3 rows are retained in default display
- no expanded payloads in the default strip

What this absorbs:

- lightweight summary role from `WorldOutcomeTrace`
- selected latest-event role from script and director surfaces

## Expanded Modes

The heavy panels are not deleted. They are moved behind explicit developer modes.

### Director Mode

Used for stationary inspection of cast-wide and Siming-wide state.

Expanded surfaces:

- `DirectorMonitorPanel`
- `SimingDirectorBoard`

### Script Mode

Used for beat replay, dialogue reconciliation, and ledger review.

Expanded surfaces:

- `ScriptTimelinePanel`
- `DialogueSceneLedger`

These are no longer part of the lightweight default composition.

## Visibility Model

Default observatory state:

- lightweight debug layout only
- overhead cards + right rail + bottom strip

Expanded director state:

- lightweight default remains the base
- director surfaces appear on top as explicit inspection tools

Expanded script state:

- lightweight default remains the base
- script replay / ledger surfaces appear on top as explicit inspection tools

## Information Hierarchy

Priority order in default mode:

1. Current observed actor
2. Character-local state around actors
3. Latest cross-system events
4. Deep inspection panels only when explicitly requested

This means the UI should help answer these questions quickly:

- Who is this actor?
- What are they doing right now?
- What are they looking at?
- Why are they doing it?
- What just happened in the world?

Without forcing the user to read multiple large blocks simultaneously.

## Component Mapping

### Components to refactor into the lightweight default

- `ActorStateTags` -> source data for overhead cards
- `CharacterObserverPanel` -> right-side detail rail
- `WorldOutcomeTrace` -> bottom thin event strip

### Components to keep as explicit expanded debug surfaces

- `DirectorMonitorPanel`
- `SimingDirectorBoard`
- `ScriptTimelinePanel`
- `DialogueSceneLedger`

### Components likely unchanged in role, but visually adjusted

- `RelationshipOverlay`
- `ObservatoryInputController`

## Interaction Expectations

- `Tab` still changes the currently observed actor
- current observed actor drives:
  - right-side detail rail
  - selected overhead expansion line
  - visual emphasis treatment
- `F6`, `F7`, `F9`, `F10`, `F11` remain developer controls
- no player-facing discoverability or onboarding is needed

## Implementation Strategy

Recommended order:

1. Introduce the lightweight default composition
2. Refactor existing panel responsibilities into the new layout
3. Collapse heavy panels behind explicit mode gating
4. Tune overlap behavior for clustered actors

## Verification Expectations

Minimum verification after implementation:

- default observatory no longer presents overlapping large blocks
- selected actor remains readable during active movement
- overhead cards remain attached and readable
- right-side rail only reflects the currently observed actor
- bottom strip shows only the latest 3 entries
- director mode still exposes cast / Siming inspection
- script mode still exposes beat / ledger inspection
- observatory remains developer-only and hidden-by-default

## Non-Goals

- No player-facing accessibility pass for this debug UI
- No redesign of backend observatory payloads
- No gameplay logic changes
- No authority changes
- No production HUD redesign

