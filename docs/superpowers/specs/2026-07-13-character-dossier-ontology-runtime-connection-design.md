# Character Dossier Ontology Runtime Connection Design

Status: `proposed`

Date: `2026-07-13`

## Purpose

Define the next layer above the current `CharacterProfile`: a full
`CharacterDossier` that represents editable authored character truth while
remaining safely separated from runtime state, memory, relationship graphs,
ability graphs, skill evaluation, and authority settlement.

This design is not only a naming cleanup. It defines the program boundary
between:

- static or semi-static authored dossier data
- runtime state that participates in action and world computation
- subjective belief and visibility-filtered knowledge
- relationship and ability graph read models
- `CharacterMindFrame` projections consumed by `L2`, `L3`, and `L4`

The first target is runtime-connected dossier ontology. The full chain is
identified and split into follow-up specs so this document does not absorb the
entire relationship graph, ability graph, body runtime, authoring tool, and
skill-system rollout at once.

## Source Context

Current repository facts:

- `CharacterProfile` already defines identity, origin, life-memory backbone,
  values, personality, needs, capability constraints, expression style,
  temperament response, long-term drift, and runtime defaults.
- `identity_core` currently covers only `character_id`, `canonical_name`,
  `aliases`, and `occupation_role`.
- `capability_constraint_layer` is currently a lightweight list of skills,
  knowledge domains, and constraints, not the full skill system.
- `CharacterMindFrame` already separates enduring truth, memory evidence,
  runtime state, affordances, and cognition workspace.
- `NeedTensionState`, `CharacterDynamicState`, `CharacterGoalStateRecord`,
  `CharacterMemoryRecordBundle`, and the five memory pools already exist.
- Relationship information currently exists through social memory and
  relationship projections, not a full relationship graph.
- The skill-system master design defines `CharacterSkillSystem`,
  `CharacterSkillState`, `SkillAffordanceSummary`, skill-action bindings, and
  skill evidence as the target architecture.
- A personality refactor design already introduces Big Five based
  `personality_layer` and behavior-facing `personality_projection`.

Related documents:

- `docs/superpowers/specs/2026-07-11-layered-character-mind-factor-architecture-design.md`
- `docs/superpowers/specs/2026-07-10-character-skill-system-master-design.md`
- `docs/superpowers/specs/2026-07-13-character-personality-trait-vector-refactor-design.md`
- `docs/superpowers/specs/2026-07-08-character-needs-personality-affect-runtime-design.md`
- `docs/架构/运行时/模块/角色智能体.md`

## Problem

The current profile model has grown beyond a simple personality profile, but it
still lacks a formal outer dossier boundary.

The main problems are:

1. `CharacterProfile` is doing two jobs: stable psychology baseline and full
   character dossier.
2. Identity is too thin for a character who exists in a social world.
3. Embodiment is only implied through physical constraints and expression
   fields, but body data must be separated into static authored baseline and
   dynamic runtime state.
4. Capability is currently a list of labels, not a structured seed for the
   ability graph and skill system.
5. Relationship seeds are missing; initial relationships have no evidence
   backed way to enter social memory.
6. Private truth, hidden truth, player visibility, self-knowledge, and
   author-only facts are not governed by one visibility model.
7. Static authored edits and hot reloads need a layer-level boundary that does
   not overwrite runtime state.
8. `L2`, `L3`, and `L4` must consume filtered projections and summaries, not
   raw full dossier truth.

Without this boundary, the system risks two failures:

- authored dossier edits accidentally overwrite lived runtime state
- model prompts become effectively omniscient because private or author-only
  facts are exposed directly

## Goals

1. Introduce `CharacterDossier` as the editable authored truth package above
   `CharacterProfile`.
2. Preserve the current `CharacterProfile` as the long-term psychological and
   behavior baseline inside the dossier.
3. Add explicit dossier layers for identity, embodiment, authority, private
   truth, relationship seeds, and capability seeds.
4. Define a layer-level visibility model with field-level overrides for
   sensitive facts.
5. Define the static/dynamic boundary for body and embodiment data.
6. Define layer-level dossier hot reload without mutating runtime state.
7. Define how dossier layers project into `CharacterMindFrame` and downstream
   `L2/L3/L4` views.
8. Define how relationship seeds initialize social memory and later
   relationship graph projections.
9. Define how capability seeds initialize skill state and later ability graph
   projections.
10. Identify follow-up specs needed for the full chain.

## Non-Goals

- Do not replace the existing `CharacterProfile` model in the first phase.
- Do not implement a full relationship graph in this design.
- Do not implement a full ability graph in this design.
- Do not implement full body simulation in this design.
- Do not let dossier hot reload overwrite `NeedTensionState`,
  `CharacterDynamicState`, `BodyRuntimeState`, current goals, memory, skill
  state, or relationship state.
- Do not expose author-only facts directly to `L2`, `L3`, `L4`, other actors,
  or the player.
- Do not move skill evaluation into the dossier.
- Do not move world-truth authority into the dossier, relationship graph, or
  ability graph.

## Core Design

Use:

```text
CharacterDossier
  -> DossierResolver
  -> VisibilityFilter
  -> ProjectionBuilder
  -> CharacterMindFrame
  -> L2 / L3 / L4
```

The governing rule is:

```text
Dossier owns authored truth.
Runtime stores own lived state.
Graphs own evidence-backed read models.
CharacterSkillSystem owns skill evaluation.
CharacterMindFrame owns the per-turn cognition input snapshot.
```

## CharacterDossier

`CharacterDossier` is the authoring and editing entry point for a character. It
wraps the existing `CharacterProfile` and adds dossier layers that are not
purely psychological.

Target shape:

```yaml
character_dossier:
  dossier_id: dossier:char_a
  actor_id: char_a
  schema_version: character_dossier.v1

  dossier_metadata:
    authoring_status: approved
    layer_versions:
      identity_profile: 1
      embodiment_profile: 1
      capability_seed_profile: 1

  identity_profile: {}
  embodiment_profile: {}
  origin_profile: {}
  life_history_profile: {}
  value_profile: {}
  personality_profile: {}
  need_profile: {}
  relationship_seed_profile: {}
  capability_seed_profile: {}
  authority_profile: {}
  private_truth_profile: {}
  expression_profile: {}

  character_profile:
    # compatibility wrapper around the current CharacterProfile
```

In the first implementation phase, existing YAML profiles may continue to load
as `CharacterProfile`. The dossier loader should also accept the new wrapped
shape. Compatibility must be explicit, tested, and temporary.

## Dossier Layers

### Identity Profile

`identity_profile` represents multiple meanings of identity, not only the
display name.

It should support:

- system identity
- canonical name, aliases, and forms of address
- age band
- gender and body identity where relevant to the world
- occupational identity
- organization identity
- faction identity
- social class or rank
- family identity
- legal identity
- self-concept
- public perceived identity
- hidden identity
- scene role
- authority identity

Example:

```yaml
identity_profile:
  actor_id: char_a
  canonical_name: Lin Yue
  aliases:
    - Yue
    - Archivist Lin
  demographic_identity:
    age_band: young_adult
    gender_identity: female
  role_identities:
    occupational_role: archive_attendant
    scene_role: grounded_social_anchor
    authority_role: archive_procedure_keeper
  affiliation_identities:
    organizations:
      - south_archive_household
    factions: []
  social_identities:
    social_rank: modest_staff
    reputation_tags:
      - discreet
      - reliable
  family_identities: []
  legal_identities: []
  self_concept:
    - careful_steward
    - trusted_keeper
  perceived_identities:
    public:
      - quiet_archive_attendant
      - reliable_mediator
  hidden_identities: []
```

Projection rule:

```text
IdentityProfile -> IdentityProjection -> enduring_truth cards
```

`L2` may receive self-concept and relevant perceived identity. `L3` should
receive only planning-relevant identity constraints and social role summaries.

### Embodiment Profile

`embodiment_profile` is a complete static or semi-static body entry point. It
is not the live body state.

It may include:

- body structure
- body-part availability and permanent limitations
- sensory baselines
- locomotion and motion ability ranges
- chronic injury or permanent constraints
- load-bearing baseline
- recovery baseline
- pain sensitivity baseline
- voice baseline
- visual markers
- default posture
- motion habits
- gesture tendencies
- asset and realization hints

Example:

```yaml
embodiment_profile:
  body_schema:
    body_type: slight
    height_band: average
    dominant_hand: right
    permanent_limitations: []
  sensory_baseline:
    vision: normal
    hearing: attentive
  motor_baseline:
    sprint_capacity: low
    fine_motor_control: high
    load_bearing: low
  chronic_conditions: []
  voice_baseline:
    volume: low
    tone: soft
  visual_markers:
    - archive_uniform
    - restrained_hand_motion
  default_posture: reserved_upright
  realization_hints:
    motion_style_tags:
      - contained
      - careful
```

Static/dynamic rule:

```text
EmbodimentProfile is editable authored baseline.
BodyRuntimeState is mutable runtime state.
Embodiment hot reload must not overwrite BodyRuntimeState.
```

Future `BodyRuntimeState` should own:

- current fatigue
- current pain
- current injury state
- current load
- current dizziness or impairment
- hunger, thirst, sleep debt, and other live physiological load
- action cooldowns
- balance and posture instability
- contact state
- temporary buffs or impairments

World, physical, interaction, and action settlement update
`BodyRuntimeState`. Dossier edits do not.

### Authority Profile

`authority_profile` describes duties, permissions, prohibitions, escalation
routes, and role-based authority constraints.

Example:

```yaml
authority_profile:
  responsibilities:
    - maintain_archive_order
    - protect_private_records
  allowed_actions:
    - explain_public_procedure
    - mediate_low_risk_disputes
  forbidden_actions:
    - grant_sealed_access_alone
  escalation_targets:
    - senior_archivist
```

Projection rule:

```text
AuthorityProfile -> authored_constraint card -> L2/L3/L4 constraints
```

Authority profile does not decide world truth. ESM and other authority
settlement surfaces remain authoritative for actual success or failure.

### Private Truth Profile

`private_truth_profile` stores authored private or hidden truths with explicit
knowledge holders and projection limits.

Example:

```yaml
private_truth_profile:
  secrets:
    - truth_id: secret:char_a:omission_fear
      content: fears one hidden omission could collapse trust
      known_by:
        - author
        - char_a
      unknown_to:
        - public
      disclosure_threshold:
        trust: high
        context:
          - private_conversation
      allowed_projection:
        l2: summarized
        l3: constraint_only
        player: hidden
```

Rules:

- `author_only` truth must not enter character subjective cognition.
- `self_known` truth may enter `L2` after visibility filtering.
- `L3` should receive only planning-relevant constraints or summaries.
- Player-facing projections may be hidden, summarized, or revealed only through
  explicit narrative or UI policy.
- Other actors should receive beliefs about the truth only through evidence,
  observation, or social memory, not direct dossier access.

### Relationship Seed Profile

`relationship_seed_profile` initializes relationship evidence. It does not own
live relationship state after initialization.

Example:

```yaml
relationship_seed_profile:
  relationships:
    - target_actor_id: char_b
      relation_tags:
        - trusted_colleague
      initial_trust: 0.68
      initial_affinity: 0.56
      initial_obligation: 0.34
      initial_tension: 0.18
      evidence_seeds:
        - event_id: rel_seed:char_a:char_b:kept_confidence
          summary: char_b once kept a sensitive archive matter private
          effect:
            trust: 0.18
            affinity: 0.08
```

Runtime boundary:

```text
RelationshipSeedProfile initializes SocialMemory.
SocialMemory and relationship evidence own later relationship change.
RelationshipGraph is an evidence-backed read model.
RelationshipReadModel feeds CharacterMindFrame.
```

The dossier should not keep updating live trust values after initialization.

### Capability Seed Profile

`capability_seed_profile` initializes authored ability and skill seeds with
lightweight ability relationships. It is not the full skill system and not the
full ability graph.

Example:

```yaml
capability_seed_profile:
  default_visibility:
    self: visible
    player: summarized
    other_actors: belief_only
  skill_seeds:
    - skill_id: social.mediation
      source: authored
      rank: trained
      proficiency: 0.74
      confidence: 0.81
      supports:
        - action_family: social_deescalation
      requires:
        - condition: has_speaking_turn
      blocked_by:
        - public_humiliation
        - extreme_fear
  knowledge_domains:
    - archive_routine
    - room_etiquette
  constraints:
    physical:
      - low_sprint_stamina
    social:
      - cannot_authorize_sealed_record_access_alone
```

Runtime boundary:

```text
CapabilitySeedProfile initializes CharacterSkillState.
AbilityGraph is a read model over skill state, registries, bindings, evidence,
equipment, body state, and runtime modifiers.
CharacterSkillService evaluates skill paths.
L3 sees SkillAffordanceSummary, not the full AbilityGraph.
```

This preserves the skill-system design rule that capability labels do not
directly become action success.

## Visibility Policy

Use layer-level default visibility with field-level overrides.

Recommended visibility dimensions:

```yaml
default_visibility:
  author: visible
  self: visible
  other_actors: belief_only
  player: summarized
  l2: summarized
  l3: summarized
  l4: action_relevant_only
```

Allowed values should include:

- `visible`
- `summarized`
- `partial`
- `belief_only`
- `constraint_only`
- `action_relevant_only`
- `hidden`

Projection views:

- `AuthoringView`
- `SelfBeliefSeedView`
- `PlayerFacingView`
- `L2DossierView`
- `L3PlanningSummary`
- `L4ExecutionConstraintView`

Rule:

```text
Raw dossier layers are never passed directly to L2, L3, or L4.
All consumers receive filtered projections or summaries.
```

## Layer Hot Reload

Static and semi-static dossier layers may be edited and hot reloaded at layer
granularity.

Example:

```yaml
layer_metadata:
  layer_id: embodiment_profile
  layer_version: 3
  source: authored
  hot_reload_policy:
    allowed: true
    invalidates:
      - embodiment_projection
      - physical_feasibility_projection
      - skill_affordance_projection
    does_not_mutate:
      - body_runtime_state
      - current_goal_state
      - memory_store
      - relationship_graph
```

Rules:

1. Hot reload may invalidate projections.
2. Hot reload may cause future skill, action, embodiment, or expression
   summaries to change.
3. Hot reload must not overwrite runtime stores.
4. Hot reload must not erase memory evidence.
5. Hot reload must not silently promote or remove learned skills.
6. Hot reload must be versioned and traceable.

## Runtime Connection

### Projection Flow

```text
CharacterDossier
-> DossierResolver
-> VisibilityFilter
-> IdentityProjection
-> EmbodimentProjection
-> AuthorityProjection
-> PrivateTruthProjection
-> CapabilitySeedProjection
-> RelationshipSeedProjection
-> CharacterMindFrame cards
```

Layer mapping:

```text
identity/value/personality/need baseline -> enduring_truth
private self-known constraints -> enduring_truth or memory_evidence
relationship evidence -> memory_evidence
body runtime/need tension/affect/goal -> runtime_state
skill/action/body feasibility -> affordance
```

### L2

`L2` may receive:

- identity self-concept
- relevant origin/life-history anchors
- values and red lines
- personality projection summaries
- self-known private truth summaries
- relationship context projections
- need and body state summaries

`L2` must not receive:

- author-only truths
- raw hidden identities not self-known
- full relationship graph
- full ability graph
- full skill registry

### L3

`L3` may receive:

- planning-relevant identity and authority constraints
- current goal context
- need pressure
- affective/body state
- relationship affordance summary
- skill affordance summary
- action affordance summary
- hard constraints

`L3` must not receive:

- raw dossier secrets
- full authoring dossier
- full ability graph
- full skill/action registry

### L4

`L4` may receive:

- selected intent
- selected skill path
- target refs
- affective/body summary
- embodiment presentation constraints
- realization hints
- physical feasibility summary
- action-relevant authority constraints

`L4` must not decide:

- whether a world state change is true
- whether an authority-gated action succeeds
- whether a learned skill is promoted

## Full Chain Expansion Path

This spec intentionally covers the runtime-connected dossier ontology, not
every downstream system in full. Follow-up specs should expand:

1. `CharacterDossier` schema, loader, and compatibility migration.
2. `VisibilityPolicy` and subjective belief projection.
3. `EmbodimentProfile` and `BodyRuntimeState`.
4. `RelationshipSeedProfile`, `SocialMemory` initialization, and
   `RelationshipGraph`.
5. `CapabilitySeedProfile`, `AbilityGraph`, and `CharacterSkillSystem`
   integration.
6. Dossier layer hot reload, versioning, invalidation, and tooling.
7. Authoring validation, profile migration, and editor/UI support.

Recommended implementation order:

```text
1. Dossier schema wrapper and compatibility loader
2. Visibility filter and projection contracts
3. Identity/authority/private-truth projections
4. Embodiment static/dynamic split contract
5. Relationship seed initialization
6. Capability seed to skill-state initialization
7. AbilityGraph and RelationshipGraph read models
8. Hot reload tooling and authoring validation
```

## Deferred Follow-Up Spec Boundaries

The matching implementation plan for this spec should cover the dossier
ontology, compatibility loader, visibility-filtered projections, shadow
`CharacterMindFrame` integration, seed initialization contracts, and hot reload
invalidation contract.

The following areas are deliberately not complete in that plan. They require
separate specs because each one has its own runtime authority, storage,
verification, and failure-mode surface.

### BodyRuntimeState And Physical Body Runtime

The current spec defines the boundary between static `EmbodimentProfile` and
future `BodyRuntimeState`. A follow-up body-runtime spec should define:

- `BodyRuntimeState` schema and store
- fatigue, pain, injury, load, hunger, sleep debt, balance, contact state, and
  temporary impairment fields
- how physical settlement, action execution, treatment, rest, and environment
  events update body state
- how body state modifies skill evaluation, action feasibility, and L4
  realization hints
- how static `EmbodimentProfile` hot reload affects future projections without
  clearing current injury, fatigue, or pain

That follow-up must not let authored dossier edits directly overwrite live body
state.

### RelationshipGraph Runtime

This spec defines `RelationshipSeedProfile` and its evidence-backed
initialization contract. A follow-up relationship-graph spec should define:

- social memory initialization from relationship seed candidates
- relationship edge schema and graph/read-model storage
- actor-private subjectivity, confidence, freshness, and evidence refs
- trust, suspicion, affinity, obligation, dependency, tension, shared secrets,
  and social-risk projection rules
- relationship update candidates from L2/writeback and settlement outcomes
- how `RelationshipReadModel` enters `CharacterMindFrame`

The relationship graph must remain memory-owned and evidence-backed. It must
not become objective world truth or directly mutate goals without L2/L3 deltas.

### AbilityGraph And CharacterSkillSystem Integration

This spec defines `CapabilitySeedProfile` and seed candidates. A follow-up
ability-graph / skill-integration spec should define:

- conversion from capability seeds to `CharacterSkillState`
- effective skill state resolution from authored seeds, learned overlays,
  equipment, evidence, and runtime modifiers
- ability graph node and edge types for skills, actions, tools, constraints,
  knowledge domains, body requirements, authority requirements, and evidence
- how `CharacterSkillService` queries the graph and binding registry
- how `SkillAffordanceSummary` is compressed for L3
- how `SkillEvaluationResult` feeds L4, ESM, physical settlement, realization,
  and `SkillEvidence`

The ability graph must not replace `CharacterSkillService`, and L3 must not
consume the raw graph or full skill/action registry.

### Runtime Hot Reload Service And Authoring Tools

This spec defines layer-level hot reload semantics and invalidation contracts.
A follow-up hot-reload/tooling spec should define:

- file watching or editor-triggered layer replacement
- layer version persistence
- projection cache invalidation
- runtime safety checks for active scenes
- authoring validation reports
- migration tooling from legacy profile YAML to dossier YAML
- player/debug UI visibility for dossier layers

The tooling spec must preserve the rule that hot reload invalidates projections
but does not mutate runtime stores.

### Subjective Belief And Knowledge Visibility

This spec defines layer visibility and private-truth knowledge holders. A
follow-up subjective-belief spec should define:

- conversion from self-known dossier facts into belief or memory seeds
- author-only truth filtering
- public knowledge versus private knowledge versus hidden truth
- other-actor belief models about the subject
- disclosure thresholds and event-driven reveal policies
- player-facing reveal and summary rules

That follow-up must ensure the character does not become omniscient by reading
author-only dossier truth.

### Authoring Validation And Migration

This spec identifies dossier schema direction. A follow-up authoring/migration
spec should define:

- validation profiles for minimal, narrative, runtime-ready, and production
  dossiers
- required versus optional layer policies
- schema version migration rules
- canonical examples for `char_a`, `char_b`, and `char_c`
- docs and editor guidance for authors
- harness checks proving all bundled dossiers load and project cleanly

This is separate from the first implementation plan because it changes the
authoring workflow rather than only adding runtime-compatible contracts.

## Compatibility And Migration

First implementation phase should support both:

```text
legacy CharacterProfile YAML
new CharacterDossier YAML with nested character_profile
```

Migration should be additive:

1. Load legacy profiles unchanged.
2. Add `CharacterDossier` models and loader.
3. Allow a dossier to wrap an existing profile payload.
4. Generate filtered projections in shadow mode.
5. Add `CharacterMindFrame` dossier cards without changing behavior.
6. Migrate character YAML files to dossier format after tests prove parity.
7. Deprecate direct profile-only authoring only after downstream readers are
   moved to dossier projections.

## Acceptance Criteria

- Existing character profiles continue to load.
- New `CharacterDossier` files can wrap the current `CharacterProfile` shape.
- `CharacterDossier` clearly separates authored truth from runtime state.
- Dossier layer hot reload invalidates projections but does not overwrite
  runtime stores.
- `identity_profile` supports full multi-identity representation.
- `embodiment_profile` supports complete static embodiment baseline while
  runtime body state remains separate.
- `private_truth_profile` uses knowledge holders and projection limits.
- `relationship_seed_profile` carries evidence seeds and initializes social
  memory rather than owning live relationships.
- `capability_seed_profile` carries skill seeds and lightweight relations
  without replacing the skill system.
- `L2`, `L3`, and `L4` receive filtered projections/summaries, not raw dossier
  truth.
- The design preserves ESM, physical channel, and interaction orchestration as
  settlement authorities.
- Follow-up full-chain specs are explicitly identified.
