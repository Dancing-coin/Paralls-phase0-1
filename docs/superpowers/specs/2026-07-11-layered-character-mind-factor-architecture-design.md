# Layered Character Mind Factor Architecture Design

Status: `approved`

Date: `2026-07-11`

## Purpose

Define how the character mind model should organize the major factors that
shape a character's decisions:

- memory and currently activated cognitive anchors
- personality and authored profile truth
- needs
- goals
- skills
- emotion, pressure, energy, and body state
- social relationship network

This design does not replace the existing four-layer character mind runtime.
It formalizes how supporting mind factors should be layered, projected, consumed
by `L2/L3/L4`, and written back without blurring memory, cognition, runtime
state, skill evidence, or authored profile truth.

## Source Context

Current repository facts:

- `CharacterAgentRuntime` already orchestrates `L1`, `L2`, `L3`, `L4`, memory,
  dynamic state, need tension, goal state, unresolved tension, supervision, and
  long-term drift gates.
- `L1` is the character-private perception layer. `L1RuntimePerceptionBridge`
  is the runtime perception bridge for world/runtime facts entering the
  character side.
- `L2` is a real cognition update layer. It emits belief deltas, social deltas,
  higher-order deltas, dynamic-state deltas, goal hints, and reasoning trace
  summaries.
- `L3` is a real planning layer. It consumes profile, memory, dynamic state,
  need tension, current goal state, goal history, supervision, and unresolved
  tensions.
- `L4` already emits an execution contract across speech, face, body,
  social-spatial, physiology, actor control frames, presentation plans, and
  `action_request_bundle`.
- `CharacterProfile` already separates authored profile truth from runtime
  state and includes `need_hierarchy_layer`, `temperament_response_layer`, and
  `long_term_personality_drift_layer`.
- `CharacterDynamicState` already separates affect, tension, and motivation
  groups.
- `NeedTensionState` already exists independently from `CharacterDynamicState`.
- The memory system already has five typed pools: event, observation,
  knowledge, social, and higher-order memory.
- Social relationship data currently exists as social memory. It should remain
  memory-owned while gaining graph-backed projections later.
- The skill system master design defines `CharacterSkillSystem`,
  `SkillAffordanceSummary`, skill-action bindings, skill evidence, and
  long-term skill learning gates, but its runtime implementation is still
  future work.
- `System L6` remains the public authority event bridge.
- ESM and physical channels remain authority settlement surfaces. ESM does not
  own character cognition.

Related designs:

- `docs/superpowers/specs/2026-06-29-complete-character-mind-core-design.md`
- `docs/character/character-mind-core-status.md`
- `docs/superpowers/specs/2026-07-08-character-needs-personality-affect-runtime-design.md`
- `docs/superpowers/specs/2026-07-10-character-skill-system-master-design.md`

## Goals

1. Preserve the existing `L1 -> L2 -> L3 -> L4` mind runtime as the primary
   character decision pipeline.
2. Avoid flattening all mind factors into one same-level context object.
3. Define a layered factor architecture that respects different time scales:
   authored truth, memory evidence, runtime state, affordances, cognition, and
   writeback.
4. Define `CharacterMindFrame` as a per-turn read-only frame, not a giant
   mutable mind object.
5. Define `CognitionWorkspace` as the current active thought workspace, not
   long-term memory.
6. Define `MindDeltaLedger` as the typed output ledger for cognition,
   planning, learning, and writeback.
7. Make graph-backed memory projections possible without making the graph the
   direct owner of cognition.
8. Let future skill/action/relationship implementations plug into the same
   projection and writeback pattern.

## Non-Goals

- Do not replace the existing four-layer character mind runtime.
- Do not create a single monolithic `CharacterMentalContext` object that mixes
  all truth, state, memory, and cognition.
- Do not let short-term emotion, need pressure, or active goals rewrite
  authored profile truth.
- Do not move character cognition into ESM, System L6, Godot, Kimodo, or the
  action realization layer.
- Do not make graph-backed memory projections decide character cognition by
  themselves.
- Do not implement the skill system, knowledge graph, or relationship graph in
  this design.
- Do not treat current lightweight L4 action routing as the final action
  library.

## Core Principles

### Existing Four Layers Stay Primary

The character mind already has a real four-layer runtime:

```text
L1 private perception
-> L2 subjective interpretation and cognition update
-> L3 goal arbitration, planning, and intent selection
-> L4 execution contract and embodied presentation request
```

The new factor architecture supports these layers. It does not replace them.

### Factors Are Not Same-Level Objects

The major factors have different time scales and authority:

- personality is long-term authored truth plus conservative drift
- memory is evidence and stored cognition
- relationship network is graph-backed social memory projection
- needs are stable drive weights plus current pressure
- emotion, stress, energy, and body state are runtime state
- goals are persisted runtime intent state
- skills are capability and action-path affordances

They must not be placed into one flat list where each factor can directly
rewrite the others.

### Projection Is A Read Model

Each factor source keeps its own truth. Projectors produce read-only summaries
for the current turn:

```text
Factor Source / Store
-> Factor Projector
-> Layered projection packet
-> CharacterMindFrame
```

Projection is not a second truth source.

### Cognition Produces Deltas

`L2/L3/L4` do not directly mutate profile, memory, skill state, relationship
graph, or long-term drift. They produce typed deltas and proposals. Writeback
policies decide what persists.

### Memory And Cognition Stay Distinct

Memory is saved, traceable, and recallable evidence or belief. Cognition is the
current process of interpreting, updating, selecting, and planning.

```text
Memory does not think.
Cognition does not store raw history.
Projection connects them.
Writeback closes the loop.
```

### Social Relationship Network Is Memory-Owned

The social relationship network belongs under social memory. It may use a graph
store and graph projections, but it must remain actor-private, evidence-backed,
and traceable to memory events.

## Layered Architecture

The mind factors are organized into six layers.

### 1. Enduring Truth Layer

Answers:

```text
Who is this character over the long term?
```

Includes:

- authored `CharacterProfile`
- `identity_core`
- `origin_seed`
- `life_memory_backbone`
- `virtue_value_layer`
- `trait_vector_layer`
- `capability_constraint_layer`
- `style_expression_bias_layer`
- `conversation_personality_layer`
- `need_hierarchy_layer`
- `temperament_response_layer`
- `long_term_personality_drift_layer`
- authored red lines and forbidden behaviors

Projection examples:

- `EffectiveProfileSummary`
- `PersonalityBiasSummary`
- `AuthoredConstraintSummary`

Rules:

- Short-term runtime state cannot rewrite authored profile truth.
- Long-term drift remains a separate layer and enters effective profile
  resolution.
- Capability constraints are not a full skill system; they feed the skill
  overlay resolver later.

### 2. Memory Evidence Layer

Answers:

```text
What has this character experienced, observed, learned, believed, and inferred
about others?
```

Includes:

- Event Memory
- Observation Memory
- Knowledge Memory
- Social Memory
- Higher-Order Memory
- future knowledge graph projections
- future social relationship graph projections
- future higher-order belief graph projections

Projection examples:

- `MemoryActivationSummary`
- `CognitiveAnchorSummary`
- `KnowledgeContextSummary`
- `RelationshipContextSummary`
- `HigherOrderBeliefSummary`

Rules:

- Event memory remains the evidence timeline and should not be collapsed into a
  graph-only structure.
- Knowledge, social, higher-order, and stable observation memories are suitable
  for graph-backed projection.
- Relationship graph edges must keep actor-private subjectivity and evidence
  references.

### 3. Runtime State Layer

Answers:

```text
What state is this character currently in?
```

Includes:

- `NeedTensionState`
- `CharacterDynamicState`
- affect state
- tension state
- motivation state
- future energy, fatigue, pain, injury, arousal, and bodily load state
- current goal state
- goal history
- unresolved tensions
- background agenda
- supervision state

Projection examples:

- `NeedPressureSummary`
- `AffectiveBodyStateSummary`
- `GoalContextSummary`
- `UnresolvedTensionSummary`
- `SupervisionSummary`

Rules:

- Stress and pressure are not the same as emotion.
- Energy, fatigue, pain, and injury belong in body/runtime state, not authored
  profile truth.
- Goals are runtime intent state. They may persist across turns, but they are
  not authored personality.

### 4. Affordance Layer

Answers:

```text
What can this character do now, and which paths are viable or character-fit?
```

Includes:

- skill affordances
- action affordances
- relationship affordances
- environmental affordances
- equipment affordances
- physical/body feasibility summaries

Projection examples:

- `SkillAffordanceSummary`
- `ActionAffordanceSummary`
- `RelationshipAffordanceSummary`
- `EnvironmentAffordanceSummary`
- `PhysicalFeasibilitySummary`

Rules:

- Skills are not cognition; they shape available and preferred action paths.
- Action realization does not decide success.
- ESM and physical channels remain authority settlement surfaces.
- L3 should see summaries, not the full skill/action registry.

### 5. Cognition Process Layer

Answers:

```text
How does the character understand the situation, reorganize goals, and choose
what to do?
```

Includes:

- `L2` subjective interpretation
- `CognitionWorkspace`
- cognitive anchor activation
- belief update proposals
- social update proposals
- higher-order update proposals
- need/affect interpretation
- goal reappraisal
- `L3` planning and arbitration
- skill/action path selection
- `L4` execution proposal shaping

Rules:

- `CognitionWorkspace` is per-turn active thinking state, not memory truth.
- It may contain active anchors, active conflicts, dominant drivers, decision
  biases, candidate questions, and hard constraints.
- It should be inspectable and traceable but not treated as long-term memory.

### 6. Writeback And Learning Layer

Answers:

```text
What should be preserved, updated, learned, or considered for long-term drift
after this turn?
```

Includes:

- memory writeback
- dynamic-state writeback
- need-tension writeback
- goal-state writeback
- unresolved-tension writeback
- relationship graph update candidates
- skill evidence writeback
- skill candidate and promotion gates
- personality drift candidate accumulation
- drift promotion gates

Rules:

- Writeback policy owns persistence decisions.
- Evidence references must be retained where a stored belief, relationship,
  skill evidence, or drift candidate is created.
- Learned skills and personality drift never directly edit authored profile
  truth.

## CharacterMindFrame

`CharacterMindFrame` is the per-turn read-only input frame for character
cognition. It is not the complete mind and not a mutable global context.

Example:

```yaml
CharacterMindFrame:
  actor_id: char_a
  mind_turn_id: mind_turn:char_a:123
  producer_ts: 123
  trigger:
    event_id: event:456
    event_type: character_perceived_event
  enduring_truth:
    effective_profile_summary: ...
    authored_constraint_summary: ...
  memory_evidence:
    memory_activation_summary: ...
    cognitive_anchor_summary: ...
    relationship_context_summary: ...
    knowledge_context_summary: ...
    higher_order_belief_summary: ...
  runtime_state:
    need_pressure_summary: ...
    affective_body_state_summary: ...
    goal_context_summary: ...
    unresolved_tension_summary: ...
    supervision_summary: ...
  affordances:
    skill_affordance_summary: ...
    action_affordance_summary: ...
    environment_affordance_summary: ...
    physical_feasibility_summary: ...
  provenance:
    source_refs:
      - profile:char_a
      - memory:event:123
      - social_memory:char_a:char_b
      - goal_state:char_a:current
```

### Factor Projection Card

Each factor projection should expose a typed card shape.

```yaml
MentalFactorProjectionCard:
  factor_type: relationship
  scope: actor_private
  horizon: scene
  confidence: 0.82
  freshness: current
  summary: "A trusts B but carries unresolved tension from a past secret."
  source_refs:
    - social_memory:char_a:char_b
    - event_memory:secret_leak
  risk_notes:
    - ambiguous_behavior_may_be_interpreted_charitably
```

Cards should be compact, traceable, and layer-aware.

## CognitionWorkspace

`CognitionWorkspace` is the current active workspace derived from the frame.
It captures what actually matters for the current decision.

Example:

```yaml
CognitionWorkspace:
  active_anchors:
    - "B once saved A."
    - "B previously hid sensitive information."
  dominant_drivers:
    - preserve_order
    - protect_innocent_life
    - avoid_public_betrayal
  active_conflicts:
    - order_vs_loyalty
    - urgency_vs_truth
  decision_biases:
    - avoid_direct_deception
    - interpret_B_charitably_due_to_trust
  hard_constraints:
    - cannot_falsify_authority_report
  candidate_questions:
    - "Is the medical emergency real?"
```

Rules:

- Workspace state may be observed and logged.
- Workspace state may inform L2/L3 reasoning.
- Workspace state is not automatically memory.
- If a workspace element should persist, it must become a typed delta or
  writeback candidate.

## Layer Context Views

Different layers should consume different views. They should not all consume
the full mind frame.

### L2InterpretationView

Consumes:

- perception context
- effective profile summary
- memory activation summary
- cognitive anchor summary
- relationship context summary
- need pressure summary
- affective body summary
- current goal context
- unresolved tension summary
- supervision summary

Produces:

- `CharacterInterpretation`
- belief deltas
- social deltas
- higher-order deltas
- dynamic-state deltas
- goal hints
- reasoning trace summary
- workspace notes

### L3PlanningView

Consumes:

- L2 interpretation
- cognition workspace
- goal context
- need pressure summary
- affective body summary
- skill affordance summary
- action affordance summary
- relationship affordance summary
- hard constraints
- unresolved tensions
- supervision summary

Produces:

- active goal frame
- goal portfolio changes
- selected intent
- preserved and suppressed goals
- candidate ranking
- skill/action path preferences
- planning trace summary

### L4ExecutionView

Consumes:

- selected intent
- selected or proposed skill/action path
- target refs
- affective body summary
- presentation constraints
- realization hints
- physical feasibility summary

Produces:

- execution semantics
- presentation plan
- actor control frames
- composite action proposal
- action request bundle

### WritebackView

Consumes:

- L2 deltas
- L3 decision and goal frame
- L4 execution proposal
- settlement result
- dialogue or action outcome
- evidence refs

Produces:

- memory write candidates
- dynamic-state updates
- need-tension updates
- goal-state records
- relationship graph update candidates
- skill evidence records
- drift candidate records

## Decision Flow

Recommended turn flow:

```text
1. L1 receives or updates actor-private perception.
2. Enduring truth projectors resolve effective profile and authored constraints.
3. Memory projectors activate relevant memory, knowledge, relationship, and
   higher-order belief summaries.
4. Runtime state projectors summarize needs, affect, body state, goals,
   unresolved tensions, and supervision.
5. Affordance projectors summarize current skill, action, environment, and
   physical feasibility.
6. CharacterMindFrame is assembled.
7. L2InterpretationView is built from the frame.
8. L2 interprets the event and emits cognition deltas plus workspace notes.
9. CognitionWorkspace is updated for the turn.
10. L3PlanningView is built.
11. L3 arbitrates goals, ranks candidates, and selects intent.
12. Skill/action path selection refines viable action paths.
13. L4ExecutionView is built.
14. L4 emits execution contract and action proposal/request.
15. ESM/physical/interaction orchestration settles semantic and physical truth.
16. WritebackView is built from cognition, planning, execution, and settlement.
17. Writeback policies persist memory, state, goal, skill evidence, relationship
    updates, and drift candidates where allowed.
```

## Factor Influence Rules

Factors influence decisions through projections and deltas, not direct mutation.

### Personality

Influences:

- need weights
- emotional reactivity
- interpretation style
- goal preference
- skill path preference
- expression style

Does not:

- decide settlement truth
- directly overwrite runtime state
- get overwritten by short-term state

### Memory And Cognitive Anchors

Influence:

- current interpretation
- risk assessment
- relationship context
- target salience
- goal generation
- skill learning evidence

Does not:

- replace L2 cognition
- directly choose actions
- mutate profile truth

### Needs

Influence:

- attention bias
- emotion and tension deltas
- goal urgency
- strategy ranking

Does not:

- override authority settlement
- directly force actions
- bypass red lines or supervision

### Goals

Influence:

- attention selection
- memory retrieval priority
- skill/action demand
- planning and candidate ranking

Does not:

- own authored personality
- directly mutate memory evidence
- bypass skill/action feasibility

### Skills

Influence:

- viable action families
- expected quality
- risk/cost estimates
- preferred action paths
- settlement input and learning evidence

Does not:

- own cognition
- own world truth
- replace ESM or physical authority

### Emotion, Pressure, Energy, And Body State

Influence:

- interpretation bias
- urgency
- skill performance modifiers
- action presentation
- physical feasibility

Does not:

- become authored personality without drift gates
- directly rewrite relationships
- decide action success by itself

### Social Relationship Network

Influences:

- interpretation of other actors
- trust and suspicion
- belonging, safety, and esteem pressures
- social goals
- social action strategy

Does not:

- exist outside memory ownership
- become objective world truth
- directly mutate current goal state without L2/L3 deltas

## Example

Scenario:

```text
Character A is a cautious, order-valuing knight with high empathy. Character B
is an old friend who once saved A. B is caught taking a medicine kit and whispers
that a child will die without it.
```

Layered inputs:

```text
Enduring truth:
- A values order and direct responsibility.
- A has high empathy and low tolerance for deception.

Memory evidence:
- B once saved A.
- B usually does not steal without cause.
- B has previously hidden information under pressure.

Runtime state:
- safety pressure: medium
- esteem pressure: medium
- concern: high
- stress load: medium
- current goal: preserve order

Affordances:
- authority protocol: strong
- persuasion: moderate
- deception: weak
- emergency aid path: possible if facts are verified
```

`L2` interpretation:

```text
B's action violates order, but the motive may be urgent aid. The situation is
not simply theft; it is an order, loyalty, and rescue conflict.
```

Workspace:

```yaml
active_conflicts:
  - order_vs_loyalty
  - urgency_vs_truth
dominant_drivers:
  - preserve_order
  - verify_emergency
  - protect_life_if_true
decision_biases:
  - avoid_direct_deception
  - interpret_B_charitably_due_to_trust
```

`L3` arbitration:

```yaml
dominant_goal: preserve_order_while_verifying_emergency
preserved_goals:
  - protect_relationship_with_B
  - prevent_child_harm_if_true
suppressed_goals:
  - publicly_accuse_B_immediately
  - lie_to_guard_directly
```

Skill/action path:

```text
Rejected path: lie for B
- weak deception
- poor personality fit
- high authority risk

Rejected path: publicly accuse B
- high relationship damage
- may delay rescue

Selected path: authority-mediated emergency verification
- strong authority protocol
- moderate persuasion
- preserves order while allowing urgent aid
```

`L4` execution:

```text
Speak firmly but low, ask B for the child's location, and propose that the guard
escort them to verify the emergency instead of treating the act as resolved theft
on the spot.
```

Writeback after settlement:

- event memory records the medicine incident
- social memory updates trust or unresolved tension depending on outcome
- goal history records the arbitration
- dynamic state updates stress and relief depending on result
- skill evidence may record authority protocol or persuasion usage
- long-term drift is only a candidate if repeated evidence accumulates

## Relationship To Existing Specs

### Needs / Personality / Affect Runtime

This design keeps the existing needs/personality/affect separation:

- authored profile truth remains long-term truth
- `NeedTensionState` remains runtime need pressure
- `CharacterDynamicState` remains affect/tension/motivation state
- long-term drift remains a gated overlay

It adds the layered frame and projection pattern around those pieces.

### Character Skill System

The skill system remains independent. This design defines where its summaries
enter the mind architecture:

- `SkillAffordanceSummary` belongs in the affordance layer
- skill evidence belongs in writeback and learning
- skill/action path selection participates after L3 intent selection and before
  final settlement

### Graph-Backed Memory

Future knowledge graph work should be modeled as memory projections:

- knowledge graph projects from knowledge memory
- social relationship graph projects from social memory
- higher-order belief graph projects from higher-order memory
- event memory remains evidence and timeline

Graph projections feed `CharacterMindFrame`; they do not own cognition.

## Implementation Phasing

This design should be implemented after or alongside the skill binding
contract, but it does not require all downstream systems at once.

### Phase 1: Contract And Shadow Frame

- Define `CharacterMindFrame` schemas.
- Define projection card schemas.
- Build a shadow `CharacterMindFrameBuilder` from existing runtime inputs.
- Do not change L2/L3 behavior yet.

### Phase 2: L2/L3 View Builders

- Add `L2InterpretationView` and `L3PlanningView` builders.
- Feed views in shadow mode beside current context payloads.
- Add tests proving parity with existing inputs.

### Phase 3: Projection Services

- Add projectors for effective profile, memory activation, relationship
  context, need pressure, affective body state, goal context, and unresolved
  tensions.
- Keep graph-backed memory optional.

### Phase 4: Skill And Action Affordances

- Feed `SkillAffordanceSummary` and `ActionAffordanceSummary` into planning and
  execution views once the skill binding contract exists.

### Phase 5: Delta Ledger And Writeback Policies

- Introduce `MindDeltaLedger` as a unifying envelope around current cognition
  deltas, goal records, skill evidence, relationship updates, and drift
  candidates.
- Preserve existing store boundaries.

### Phase 6: Graph-Backed Memory Projections

- Migrate suitable knowledge, social, higher-order, and stable observation
  memory reads to graph-backed projections.
- Keep event memory as evidence timeline.

## Acceptance Criteria

- The design keeps `L1/L2/L3/L4` as the core runtime.
- The design does not flatten all mind factors into one same-level context.
- The design separates authored truth, memory evidence, runtime state,
  affordances, cognition process, and writeback.
- The design treats social relationship network as memory-owned and
  graph-projectable.
- The design preserves the difference between memory and cognition.
- The design gives L2/L3/L4 separate consumption views.
- The design supports future skill/action integration without moving skill state
  into ESM or L4.
- The design supports future graph-backed memory without making graph queries
  replace character cognition.
- The design keeps all long-term changes gated and evidence-backed.
- The design can start in shadow mode without breaking the current character
  mind core or smoke path.
