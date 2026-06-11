# Character Agent Minimal Runtime Slice Design

## Problem

The repository has already stabilized the minimum `Phase 0` loop around:

- `System L1` structured facts
- `ESM` authoritative world settlement
- `L6` authority events
- minimal `Siming` catalyst output
- Godot-side dialogue, attention, and runtime-state presentation

What is still missing is a real character-agent runtime seam for `CharacterA` and `CharacterB`.

Right now, too much “the character seems to understand and react” behavior still accumulates in transition layers such as:

- `backend/app/services/character_service.py`
- `backend/app/services/conversation_relation_service.py`
- `scripts/phase0/MainDemoController.gd`
- `scripts/character/CharacterReplica.gd`

That is acceptable for a demo bootstrap, but it is the wrong place to keep growing subjective interpretation and actor-specific intent.

## Goal

Add a minimum character-agent runtime slice that explicitly implements the `CharacterAgent L1` perception layer for `CharacterA` and `CharacterB`, then uses that layer to form a minimal subjective interpretation, choose one minimal intent, and emit one minimal embodied response without bypassing `ESM`, `Siming`, or `System L1`.

This spec is intentionally not the full character-agent architecture. It only defines the smallest runtime slice that can be inserted into the already-running `L1 / L6 / Siming` foundation.

This slice must stay aligned with the main-project `CharacterAgent L1` design in:

- `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\角色智能体\01-角色智能体总纲.md`
- `D:\Projects\Paralls\docs\phase1\core\01-运行时核心\角色智能体\03-感知链路与角色私有世界模型设计.md`

## Scope

This slice covers only:

1. `CharacterA` and `CharacterB`
2. role-private structured inputs
3. an implemented `CharacterAgent L1` perception layer as a first-class deliverable
4. a minimal `L1 -> L2 -> L3 -> L4` character-agent chain
5. observable Godot-facing outputs for:
   - attention shift
   - brief dialogue response
   - micro reposition
   - role-state hint
   - physiology hint

This slice does not cover:

- expansion of `System L1` fact domains beyond what the current repo already proves
- full personality or memory systems
- long-horizon planning
- full autonomous dialogue loops
- full player/agent dual-control for `CharacterC`
- full `FACS/SACS/Binder/Canonical Rig` production-chain work
- character-owned authoritative world changes

## Source Inputs And Existing Anchors

The slice must be built on top of existing repository anchors rather than replacing them:

- `backend/app/services/character_perceived_input_service.py`
- `backend/app/services/character_runtime_state_service.py`
- `backend/app/services/conversation_relation_service.py`
- `backend/app/services/per_character_percept_filter.py`
- `backend/app/services/siming_runtime.py`
- `backend/app/main.py`
- `scripts/autoload/BackendBridge.gd`
- `scripts/autoload/LocalPresentationBus.gd`
- `scripts/character/CharacterReplica.gd`

Those pieces already prove that:

- role-private perceived events exist
- self-body perceived events exist
- runtime-state projection exists
- Godot can already render dialogue, attention, and state deltas

The missing work is to make a character-agent runtime consume those structured inputs as its true default boundary.

## Boundary Freeze

### `System L1` vs `CharacterAgent L1`

These are not the same thing.

`System L1` remains responsible for:

- raw fact production
- structured player input ingress
- deterministic `ESM` settlement
- public world/body/object/environment truth

`CharacterAgent L1` is only the character’s private intake layer. It must never become a hidden second world-truth engine.

### Allowed Upstream Inputs

The runtime slice may only consume:

1. `CharacterPerceivedEvent`
2. `SelfBodyPerceivedEvent`
3. `Siming` high-level catalyst outputs
4. structured world / constraint / conversation summaries that are already private or filtered for a given actor

It must not directly consume:

- raw global fact streams as its business input
- unfiltered authority bus truth
- Godot local camera / keyboard / mouse noise

### Allowed Downstream Outputs

The runtime slice may only emit:

- minimal character intent decisions
- presentation-oriented output commands
- future optional action requests that still route back through `ESM`

It must not directly decide:

- whether a world interaction succeeds
- whether a body change is authoritative
- whether an object/environment state really changes

## Slice Shape

The minimum slice has four internal layers.

### `CharacterAgent L1`: Perception Layer

`CharacterAgent L1` must be implemented in this slice as the character-agent perception layer.

It is not optional glue, and it is not only a passive data container. Its job is to:

- receive role-private structured inputs
- normalize them into actor-private perception state
- maintain the current private world snapshot
- expose the snapshot to downstream `L2`
- preserve the boundary between filtered character input and public world truth

This is an implementation requirement for this slice, not a future placeholder.
What stays out of scope is rebuilding `System L1` itself.

The main-project `L1` design defines the perception system as four linked parts:

1. `Raw Fact Producers`
2. `Perceptible Compilation Layer`
3. `Per-Character Perception Filter`
4. `Private World Snapshot`

For this repository, those parts map as follows:

1. `Raw Fact Producers`
   - already present in current `System L1`
   - not reimplemented in this slice
2. `Perceptible Compilation Layer`
   - already present through candidate-percept compilation
   - must be treated as upstream input to character-agent `L1`
3. `Per-Character Perception Filter`
   - already present in placeholder form
   - must be hardened so the character-agent slice receives true role-private inputs
4. `Private World Snapshot`
   - must be implemented inside this slice as the actor-private short-horizon perception state

So the current slice does not merely “store a snapshot”.
It must connect and formalize the latter two parts of the main-project `CharacterAgent L1` design inside this repo:

- role-private perception filtering as the enforced input boundary
- private world snapshot as the short-horizon perception state

Minimum snapshot state:

- `visible_entities`
- `audible_entities`
- `unresolved_signals`
- `active_anomalies`
- `attention_targets`
- `short_horizon_social_presence`
- `local_spatial_confidence_map`
- `recent_world_changes`
- `recent_constraint_results`
- `body_state_hints`
- `last_siming_catalyst`

The main-project design also freezes a perception-quality model. This slice must reserve the fields and tests for:

- `clarity_score`
- `certainty_score`
- partial / missed / distorted perception outcomes

The first implementation may keep some of those outcomes simple and deterministic, but it should not omit the data shape entirely.

The first implementation may keep `audible_entities` structurally present but sparsely populated because the current repo has not yet promoted auditory facts into the actor-private path.

Minimum `CharacterAgent L1` responsibilities for this implementation:

1. consume `CharacterPerceivedEvent`
2. consume `SelfBodyPerceivedEvent`
3. consume actor-targeted `Siming` catalyst input
4. consume true role-private filtered inputs rather than public world-truth objects
5. update one actor-private snapshot per supported character
6. maintain minimum perception-quality state
7. provide a stable read boundary for `L2`
8. emit debug-visible `L1` update traces

### `CharacterAgent L2`: Minimal Interpreter

`L2` converts the latest private input plus snapshot context into a minimal subjective interpretation.

Required output fields:

- `interpreted_summary`
- `interpretation_type`
- `salience_score`
- `ambiguity_level`
- `risk_level`
- `opportunity_level`
- `attention_target`
- `inner_prompt_candidate`

The first pass should remain deterministic and template-driven. It does not require an LLM or full memory system.

### `CharacterAgent L3`: Intent Selection

`L3` chooses a single dominant next intent from a small, frozen action set:

- `observe_target`
- `speak_brief_response`
- `inspect_object`
- `reposition`
- `stay_silent`

Selection keeps the main-project “three-filter” shape in lightweight form:

1. `Persona Filter`
2. `Logic Filter`
3. `Gain/Loss Filter`

The first slice only needs single-step selection, not multi-turn planning.

### `CharacterAgent L4`: Presentation Adapter

`L4` translates the selected intent into the current Godot-facing embodiment surface.

The slice must reuse existing presentation paths whenever possible:

- dialogue still lands as a dialogue-style payload
- attention still lands as a look/focus-style payload
- runtime-state hints can still land through the runtime-state surface

The only new outbound protocol added by this slice should be a minimal structured character-agent output envelope for commands that do not map cleanly onto existing message types, especially micro reposition and unified role/physiology hints.

## Runtime Objects To Introduce

The slice should introduce a small set of explicit runtime objects instead of overloading existing dictionaries:

### `CharacterPrivateWorldSnapshot`

Per-actor mutable runtime state for the character-agent chain.

### `CharacterInterpretation`

Frozen output from `L2` that explains what the actor thinks just happened.

### `CharacterIntentDecision`

Frozen output from `L3` that records the chosen minimal intent plus compact reasons.

### `CharacterPresentationCommand`

Frozen output from `L4` that the backend can emit to Godot as a structured presentation command.

These types should live in a dedicated backend model module so tests, debug output, and websocket integration share the same schema.

## Integration Design

### Backend Runtime Owner

Add a dedicated backend runtime owner:

- `backend/app/services/character_agent_runtime.py`

Responsibilities:

- own the character-agent `L1 -> L2 -> L3 -> L4` orchestration
- maintain per-actor private snapshots for `char_a` and `char_b`
- accept structured upstream events
- run `L2 -> L3 -> L4`
- return zero or more `CharacterPresentationCommand` objects

This service is the only place where the four-layer slice is orchestrated.

### Backend Subservices

Add focused subservices:

- `backend/app/services/character_agent_l2.py`
- `backend/app/services/character_agent_l3.py`
- `backend/app/services/character_agent_l4_adapter.py`

The first pass should keep them deterministic and small. No hidden model router, no new dependency, no speculative memory layer.

### WebSocket / Backend Wiring

`backend/app/main.py` becomes the integration seam.

It must feed the runtime when:

- filtered `CharacterPerceivedEvent` is created
- `SelfBodyPerceivedEvent` is created
- a `siming_output` targets `char_a` or `char_b`

The runtime then returns presentation commands that are appended to outbound websocket messages.

### Godot Wiring

The frontend side should stay thin:

- `scripts/autoload/BackendBridge.gd` parses the new output envelope
- `scripts/autoload/LocalPresentationBus.gd` exposes one new signal for character-agent outputs
- `scripts/character/CharacterReplica.gd` consumes those commands and maps them to existing local pose, look, speech, and move-target helpers

`MainDemoController.gd` should not absorb this logic unless a command truly needs scene-level coordination. Default posture: keep character-owned presentation inside `CharacterReplica.gd`.

## Outbound Envelope

Add one new websocket message type:

- `character_agent_output`

Minimum payload:

- `actor_id`
- `output_type`
- `producer_ts`
- `causation_id`
- `correlation_id`
- optional `target_actor_id`
- optional `target_object_id`
- optional `target_environment_id`
- optional `dialogue_text`
- optional `move_target`
- optional `role_state_hint`
- optional `physiology_hint`

Allowed `output_type` values for this slice:

- `attention_shift`
- `brief_dialogue_response`
- `reposition_step`
- `role_state_hint`
- `physiology_hint`

This envelope is presentation-only. It does not mean the character has acquired world authority.

## Observability And Audit

The slice must remain easy to verify.

Required debug stages:

- candidate received
- private filter applied
- snapshot updated
- interpretation produced
- intent selected
- presentation command emitted

Required audit rule:

- the character-agent runtime may only accept filtered/private inputs, never raw-fact or public authority event objects as its business interface

This boundary needs explicit tests because it is easy to violate accidentally during future cleanup.

## Acceptance

The slice is accepted when all of the following are true:

1. `CharacterAgent L1` is implemented as a dedicated perception layer rather than hidden inside transition glue.
2. The repo uses the main-project `L1` chain shape: candidate compilation -> private filter -> private world snapshot.
3. `CharacterA` and `CharacterB` can consume `CharacterPerceivedEvent` through `CharacterAgent L1`.
4. At least one path also consumes `SelfBodyPerceivedEvent` or `Siming` catalyst input through `CharacterAgent L1`.
5. `CharacterAgent L1` maintains a readable private snapshot for each supported actor.
6. `CharacterAgent L1` exposes minimum perception-quality state such as `clarity_score` and `certainty_score`.
7. `L2` consumes that snapshot boundary and produces a structured interpretation object.
8. `L3` selects one minimal intent from the frozen set.
9. `L4` emits at least one observable Godot-facing command.
10. Godot visibly reacts through at least one of:
   - attention shift
   - brief dialogue response
   - reposition micro-step
11. The slice does not subscribe directly to global raw-fact truth as its runtime business input.
12. The slice does not bypass `ESM` for authoritative world settlement.
13. Existing `Phase 0` verification remains green.

## Verification

Minimum required verification for implementation:

- backend unit tests for `CharacterAgent L1` perception ingestion, snapshot updates, interpretation, and intent selection
- backend websocket integration tests for runtime ingestion and outbound `character_agent_output`
- static or unit-level boundary audit proving no raw-fact/direct-authority bypass
- `python -m pytest -v`
- `python scripts/verification/harness.py --profile phase0`
- `python scripts/verification/harness.py --profile phase1-slice`

## Future Evolution

The correct follow-on order after this slice is:

1. promote auditory facts into actor-private perception
2. deepen `L2` interpretation quality
3. expand `L3` beyond single-step intent
4. connect optional actor-originated action requests back into `ESM`
5. only then expand memory, social inference, and player dual-control

## Summary

The point of this spec is not to “finish character agents”.

It is to insert one disciplined, testable character-agent runtime seam into the current demo so that `CharacterA` and `CharacterB` stop being only presentation shells and start becoming minimal actors with:

- private input
- subjective interpretation
- minimal intent
- minimal embodied response

while the project still preserves the already-proven `Phase 0` runtime loop and its world-truth boundaries.
