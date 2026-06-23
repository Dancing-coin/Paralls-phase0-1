# Character Agent Stage 2 Design

Date: `2026-06-24`

## Problem

The repository already has:

- a runnable `Phase 0` dramatic loop
- a real `CharacterAgentRuntime` backbone
- shared actor ingress into the Godot-side actor stack
- minimal memory/timeline/runtime truth
- working `Siming` authority/event paths

But it still does not provide a complete character-mind stage that supports:

- reusable character profiles for arbitrary roles
- memory structures strong enough to preserve subjective continuity
- explicit knowledge-state progression
- `L2 -> L3 -> L4` decisions grounded in profile, memory, and knowledge
- `Siming` influence over role mentality without replacing role agency
- visible basic embodied expression in the live 3D scene

The current repo is therefore still closer to a runnable character-agent skeleton than a reusable role-mind substrate.

## Goal

Define `Stage 2` of the character-agent system as a generalized role-mind substrate for arbitrary characters, not a special-case extension for `char_a / char_b / char_c`.

This stage must let a role in the live 3D scene:

- load a stable long-term character profile
- perceive the world through the current private-perception chain
- accumulate memory in structured pools
- evolve proposition-like knowledge states
- interpret current subjective reality in `L2`
- plan current intent in `L3`
- express that intent through a minimal but visible `L4`
- accept `Siming` as a legal mentality catalyst without surrendering final agency

## Non-Goals

This stage does not ship:

- database persistence
- full embodiment chain
- full `FACS`
- full `SACS/Binder` rollout
- full higher-order memory
- final production-grade asset adapter generalization

This stage may reserve interfaces for those future systems, but it does not attempt to complete them now.

## Scope Decision

This stage is explicitly a **mind-first, light-execution** stage.

Primary work:

- character profile system
- four-pool memory system
- knowledge-state model
- `L2` interpretation grounded in profile + memory + knowledge
- `L3` planning grounded in `L2`
- `Siming` mentality influence protocol
- basic `L4` execution visible in the 3D scene

Deferred work:

- persistent database schema realization
- full facial expression system
- complete embodiment binder chain
- higher-order cognition pool

## Architectural Summary

The Stage 2 runtime chain is:

```text
CharacterProfile
-> PrivateWorldSnapshot
-> Four-Pool Memory
-> KnowledgeState / SocialMemory
-> L2 Interpretation
-> L3 Planning
-> L4 Basic Execution
-> Shared Actor Ingress
-> CharacterRuntimeState / CharacterPresentationInput
-> Godot actor stack
```

This is not a separate player-only or NPC-only lane.

It must apply to arbitrary dramatic roles through one generalized runtime species with different control modes.

## Integration Constraints

Stage 2 must preserve current repository truths:

- `System L1 / ESM` remain world-truth settlement authority
- the character agent still consumes only role-legal business inputs
- `Siming` remains catalyst-level, not direct role replacement
- the Godot actor stack remains shared across human/agent/program control families

This stage must not create:

- a second agent-only embodiment path
- direct world-truth writes from character reasoning
- profile-specific hardcoded logic in runtime services

## Character Profile System

### Purpose

A role needs a stable long-term identity substrate that is separate from runtime state.

Stage 2 therefore formalizes a structured-file-first character-profile system.

### Source Strategy

Character profiles are defined in structured files first.

Code is responsible only for:

- default filling
- validation
- normalization
- runtime loading

### Core Rule

Profile data is long-lived identity truth.

It must not be mutated by:

- player control
- `Siming`
- runtime emotion
- current injury
- current conversation state

### Stage 2 Profile Structure

Profiles freeze the existing eight-layer structure:

1. `identity_core`
2. `origin_seed`
3. `life_memory_backbone`
4. `virtue_value_layer`
5. `trait_vector_layer`
6. `capability_constraint_layer`
7. `style_expression_bias_layer`
8. `conversation_personality_layer`

### Mandatory Stage 2 Runtime Fields

Stage 2 does not require every possible field to be fully authored, but it requires these fields to be real runtime inputs:

- identity:
  - `character_id`
  - `canonical_name`
  - `aliases`
  - `occupation_role`
- trait vector:
  - `courage`
  - `scheming`
  - `empathy`
  - `rationality`
  - `sociability`
- values and taboos:
  - value priorities
  - red lines
  - forbidden behaviors
- capability/constraint:
  - skills
  - knowledge domains
  - physical constraints
  - psychological constraints
  - social constraints
- style/expression:
  - speech style
  - silence pattern
  - gesture bias
  - posture bias
- conversation personality:
  - `social_openness`
  - `privacy_sensitivity`
  - `talk_initiative`
  - `deception_control`
  - `trust_threshold_for_private_talk`

### Runtime Object Model

`L2/L3/L4` should not read raw profile files directly.

Profiles are loaded into a runtime `CharacterProfile` object and exposed through narrower read-only views such as:

- `ProfileIdentityView`
- `ProfileValuesView`
- `ProfileCapabilitiesView`
- `ProfileConversationBiasView`

This decouples the runtime mind chain from raw storage schema drift.

### Role Runtime Identity

A role instance in Stage 2 is represented conceptually as:

```text
CharacterProfile
+ PrivateWorldSnapshot
+ MemoryState
+ KnowledgeState
+ DynamicState
+ ControlMode
```

Only the first element is long-lived profile truth.

## Four-Pool Memory System

### Scope

Stage 2 implements four memory pools:

1. `Event Memory`
2. `Observation Memory`
3. `Knowledge Memory`
4. `Social Memory`

`Higher-Order Memory` is deferred, but its interface may be reserved.

### Boundary With Snapshot

`PrivateWorldSnapshot` is current short-horizon subjective perception.

Memory is durable role-internal accumulation derived from:

- perceived events
- self-body events
- dialogue outcomes
- `ESM` settlement outcomes
- `Siming`-catalyzed attention shifts

The snapshot and the memory layer must not collapse into one object.

### Event Memory

Purpose:

- record what happened
- preserve source and timing
- remain valid even before the role fully interprets meaning

Minimum fields:

- `memory_id`
- `actor_id`
- `source_event_id`
- `world_ts`
- `event_type`
- `summary`
- `clarity_score`
- `certainty_score`
- `refs`

### Observation Memory

Purpose:

- preserve the role’s actually perceived version of details
- retain ambiguity, partial capture, and distortion

It stores what the role thinks it sensed, not world truth.

### Knowledge Memory

Purpose:

- store proposition-like believed content
- track confidence and status over time

Examples:

- “char_b is hiding something”
- “the letter matters”
- “the light change may be intentional”

### Social Memory

Purpose:

- store long-horizon relationship cognition toward other roles

Examples:

- trust baseline
- suspicion baseline
- intimacy
- dependency
- unresolved tension
- shared secret references

### Memory Deposition Chain

The memory chain in Stage 2 is:

```text
Perceived event / self-body event / dialogue result / ESM result / Siming-catalyzed attention
-> Event Memory
-> Observation Memory
-> L2 interpretation
-> Knowledge Memory and Social Memory updates
```

This prevents one-step over-flattening of role cognition.

### Stage 2 Persistence Posture

Implementation may remain in-process and session-scoped for now.

But every memory object must be shaped so that later persistence is straightforward.

## Knowledge State Model

### Purpose

Stage 2 introduces an explicit knowledge-state model so roles do not jump directly from “saw something” to “fully know it.”

### Knowledge States

Minimum state set:

- `noticed`
- `suspected`
- `tentatively_believed`
- `believed`
- `high_confidence_believed`
- `disputed`
- `abandoned`

### Semantic Rule

Knowledge state is not a separate memory pool.

It is the proposition-state machine attached to knowledge objects in `Knowledge Memory`.

### Stage 2 Planning Impact

Knowledge states must affect later planning through `L2 -> L3`.

Minimum influence rules:

- `suspected` / `tentatively_believed`
  - bias toward observe/probe/verify/caution
- `believed` / `high_confidence_believed`
  - bias toward stronger action commitment
- `disputed`
  - bias toward caution, hesitation, and re-check behavior
- `abandoned`
  - reduce planning weight while preserving lineage

Knowledge state is therefore part of the active mind chain, not just trace metadata.

## L2 Interpretation Layer

### Purpose

`L2` converts current role-private reality into structured subjective interpretation.

### Inputs

`L2` consumes:

- read-only profile views
- current private snapshot
- memory slices from all four pools
- active knowledge-state objects
- social-memory state
- current event
- current control mode
- recent settlement/dialogue writeback
- optional `Siming` catalyst input

### Outputs

Stage 2 freezes the minimum `L2` output family as:

- `interpreted_situation`
- `belief_deltas`
- `social_read`
- `perceived_risk`
- `perceived_opportunity`
- `attention_pressure`
- `inner_state_shift`
- `reasoning_trace_summary`

### Update Responsibilities

`L2` must be able to update:

- proposition-like understanding of the world
- relationship-like understanding of other roles

That means:

- `Knowledge Memory` changes
- `Social Memory` changes

### Why This Matters

Without this layer, memory stays archival and does not become active mentality.

## L3 Planning Layer

### Purpose

`L3` turns subjective reality into current action possibility space.

### Required Logical Stages

Stage 2 freezes the following planning stages as real behavior contracts:

1. `Goal Activator`
2. `Candidate Generator`
3. `Constraint Projector`
4. `Triple Filter Engine`
5. `Priority Ranker`
6. `Intent Selector`

Implementation may still evolve internally, but these behaviors must exist and be auditable.

### Stage 2 Candidate Intent Set

Minimum supported actions:

- `observe`
- `approach`
- `withdraw`
- `speak_public`
- `speak_private`
- `ask_probe`
- `withhold`
- `share_info`
- `inspect_object`
- `follow_target`
- `seek_private_distance`
- `break_contact`
- `self_protect`
- `pause`
- `defer`

`pause` and `defer` are required so roles can remain dramatically meaningful without always escalating.

### Triple Filter Requirements

#### Persona Filter

Must depend on profile truth.

Question:

“Is this the kind of action this role would plausibly take?”

#### Logic Filter

Must depend on perception/memory/knowledge-state context.

Question:

“Does this make sense in the role’s current subjective situation?”

#### Gain/Loss Filter

Must depend on:

- value priorities
- perceived risk/opportunity
- relationship pressure
- current stress

Question:

“Is this worth it for the role right now?”

## Siming Mentality Influence Protocol

### Purpose

Stage 2 treats `Siming` as a legal catalyst for role mentality, not as a role-replacement brain.

### Allowed Influence Surface

`Siming` may influence:

- attention target re-focusing
- `vigilance_level`
- `distraction_level`
- event salience
- memory retrieval priority
- `L2` pressure and risk interpretation
- `L3` candidate ranking bias

### Forbidden Influence Surface

`Siming` may not:

- inject hidden world truth the role never perceived
- skip `L2`
- skip `L3`
- override explicit player priority
- directly finalize world-truth outcomes
- directly command role embodiment as if it were the role’s own decision

### Stage 2 Siming Input Shape

Stage 2 should treat Siming influence as a structured catalyst packet with fields conceptually like:

- `target_ref`
- `catalyst_type`
- `presentation_hint`
- `pressure_hint`
- `salience_boost`
- `reason_scope`

Exact field naming may evolve, but the behavior contract must stay stable.

### Player Rule

For player-related roles, `Siming` may bias role inclination but may not defeat explicit player-driven high-priority intent.

## L4 Basic Execution

### Purpose

Stage 2 does not implement full embodiment, but it must establish a visible minimal expression loop in the live 3D scene.

### Channel Posture

The five-channel model remains architecturally true:

1. `Speech Channel`
2. `Face Channel`
3. `Body Channel`
4. `Social-Spatial Channel`
5. `Physiology Channel`

But Stage 2 only fully lands:

- `Speech`
- `Body`
- `Social-Spatial`
- minimal `Physiology`

`Face` and full `FACS/Binder` stay as reserved future seams.

### Stage 2 Visible Expression Set

Minimum visible action family:

- orient to target
- hold attention
- approach target
- withdraw
- follow
- break contact
- pause
- observe pose
- inspect pose
- self-protect pose
- public speech trigger
- private speech trigger

### Implementation Rule

These expressions may be realized through:

- existing animation clip switching
- AnimationTree parameter switching
- simple bone pose adjustments
- runtime state tags

The requirement is not richness.

The requirement is visible causality from mentality to expression.

### Physiology Minimum

Minimum physiology states:

- `stable`
- `elevated`
- `guarded`
- `hesitant`

These can initially appear through stance, timing, hesitation, distance preference, and posture contraction rather than a full physiological rig.

### Shared Actor Rule

Stage 2 must continue to route through the shared actor ingress family.

It must not create an agent-only body path.

## Control-Mode Rule

Stage 2 must stay generalized across arbitrary roles.

It must not rely on `char_a / char_b / char_c` special-case logic as the architecture truth.

The runtime remains one generalized role species with different control modes.

Player-related roles keep:

- explicit player priority
- automatic role completion layers
- automatic micro-level state continuity

AI-driven roles keep:

- full automatic `L3/L4` authority within the same runtime family

## Siming Branch Relationship

The active `feat/siming` branch is treated as an implementation input source for Stage 2, not as architecture truth by itself.

Stage 2 design assumes that Siming-related work may later merge to mainline, but this spec defines the role-mind contract independently of that branch’s exact file layout.

The contract that matters is:

- `Siming` can legally influence role mentality
- `Siming` cannot replace role agency
- `Siming` remains upstream of `L2/L3`, not a bypass around them

## Verification Targets

### Profile and Generalization

Must prove:

- arbitrary roles can load through one structured profile path
- runtime does not depend on fixed `A/B/C` role naming to function
- profile values reach `L2/L3`

### Memory and Knowledge

Must prove:

- events deposit into the four-pool chain
- knowledge states transition across multiple levels
- social memory changes later planning
- memory is not reduced to one undifferentiated history string

### Siming Influence

Must prove:

- `Siming` legally changes salience/attention/pressure
- `Siming` does not inject hidden truth
- `Siming` does not bypass `L2/L3`
- player priority is preserved

### Scene Execution

Must prove:

- planning outputs become visible basic expression in the 3D scene
- AI and player-related roles both use the shared actor ingress
- `ESM` remains settlement authority for world-relevant actions

### Minimum Required Verification Surfaces

- backend unit tests for profile loading/validation
- memory and knowledge-state tests
- `L2` interpretation tests
- `L3` filter/ranking tests
- `Siming` mentality influence tests
- runtime integration tests for basic visible expression
- existing `Phase 0` and character-agent execution verification paths where relevant

## Acceptance Criteria

Stage 2 is accepted when all are true:

1. Arbitrary roles can load a structured-file-first profile through one generalized loader path.
2. The runtime uses four real memory pools:
   - `Event`
   - `Observation`
   - `Knowledge`
   - `Social`
3. Knowledge objects progress through explicit knowledge states.
4. `L2` consumes profile + memory + knowledge as active reasoning inputs.
5. `L3` consumes `L2` outputs and applies real persona/logic/gain-loss filters.
6. `Siming` influences mentality legally through structured catalyst input.
7. `Siming` does not replace role agency or world settlement.
8. `L4` produces visible basic expression in the live 3D scene.
9. The shared actor ingress remains the only local embodiment path.
10. The design remains generalized for arbitrary roles rather than freezing `A/B/C` as architecture truth.

## Summary

Stage 2 turns the current character-agent skeleton into a generalized role-mind substrate.

It does so by adding:

- structured long-term profiles
- four-pool memory
- explicit knowledge-state progression
- profile/memory/knowledge-driven `L2 -> L3`
- legal `Siming` mentality influence
- visible basic `L4` expression

without prematurely expanding into:

- database persistence
- full `FACS`
- full embodiment-chain completion
- higher-order memory

This is the shortest architecture-correct path toward an actually continuous role experience inside the current 3D scene.
