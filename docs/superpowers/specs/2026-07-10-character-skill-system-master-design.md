# Character Skill System Master Design

Status: `approved-phase1-binding-contract; runtime-completion-implemented-and-verified`

Date: `2026-07-10`

## Purpose

Define the full character skill system for the world-character-Siming-authority
runtime. The system connects authored character capability, structured skills,
action definitions, semantic settlement, physical settlement, and realization
through Godot assets or Kimodo-style generated motion.

This is a master design. It defines the complete target architecture plus
phased adoption boundaries. The first implementation phase must not claim full
skill learning, full action-library replacement, or live Kimodo integration.

## Source Context

Current repository facts:

- `CharacterProfile.capability_constraint_layer` already records authored
  skills, knowledge domains, physical constraints, psychological constraints,
  and social constraints.
- `CharacterAgentL3Service` already selects intents and scores candidates.
- `CharacterAgentL4Executor` already emits execution semantics, presentation
  plans, actor control frames, and `action_request_bundle`.
- `CharacterEmbodimentAssetRegistry.gd` already provides an asset-registry
  seam for semantic motion keys, fallback asset refs, and missing semantic keys.
- `KimodoActionRequest` and `KimodoRealizationPlan` already define the Kimodo
  adapter contract.
- Interaction orchestration, ESM, and the physical channel already own
  semantic/physical authority settlement boundaries.
- `CharacterDynamicState` and `NeedTensionState` already provide runtime
  affect, tension, motivation, and need-pressure state.

Hermes Agent influence:

- Hermes skills are treated as on-demand procedural knowledge artifacts, not as
  one monolithic runtime subsystem.
- Hermes-style learning is useful as a long-term model for governed skill
  evolution, but Paralls must add world, role, settlement, physical, visibility,
  and authored-profile constraints.
- Reference repositories:
  - `https://github.com/NousResearch/hermes-agent`
  - `https://github.com/NousResearch/hermes-agent-self-evolution`

## Goals

1. Turn authored capabilities into checkable skill state without mutating the
   authored profile.
2. Connect skills to actions through a reusable binding layer.
3. Let actions participate in semantic settlement and physical settlement.
4. Let action realization consume settlement truth without becoming authority.
5. Support long-term skill learning as an evidence-based, policy-gated future
   capability.
6. Preserve existing boundaries:
   - ESM does not own character cognition.
   - CharacterAgent does not own world truth authority.
   - Godot does not fake settlement success.
   - Kimodo does not decide whether an action succeeded.

## Non-Goals

- Do not replace the entire existing L4 executor in the first phase.
- Do not implement automatic skill promotion in the first phase.
- Do not let learned skills directly edit `capability_constraint_layer`.
- Do not make L3 consume the full skill/action registry.
- Do not move skill state or skill learning into ESM.
- Do not make Kimodo or asset realization decide world truth.
- Do not build a large production action library as part of the contract phase.

## Core Principles

1. The system is named `CharacterSkillSystem`, not `SkillRuntime`.
2. `SkillDefinition`, `ActionDefinition`, and `SkillActionBinding` are separate.
3. `ActionDefinition` supports both `CompositeAction` and `PrimitiveAction`.
4. Realization decides presentation, not success.
5. Skill learning is evidence-based and policy-gated.
6. Skill and action loading uses:
   - Core Registry
   - Scenario Registry
   - Character Overlay
   - Equipment Overlay
   - Runtime Modifiers
7. `CharacterSkillService` is independent from L4, ESM, and the Action Library.
8. Composite actions are evaluated by skill path before primitive expansion.
9. Skill path selection is character-aware, not only success-maximizing.
10. Settlement results separate `outcome_band` from `failure_domain`.
11. `SkillEvidence` is directional, typed, and context-specific.
12. `SkillEvidence` has a dedicated store and references settlement/memory
    events.
13. `SkillPromotionGate` is conservative and explainable.
14. L3 sees `SkillAffordanceSummary`, not the full skill/action registry.
15. Skill-affordance visibility is layered.
16. `ObservedSkillBelief` is reserved for other actors' beliefs about a
    subject's skills.
17. Realization consumes selected skill path and settlement result to choose
    presentation variants.
18. Action variants are rule-selected from action id, selected skill path, and
    settlement outcome.
19. Personality, needs, affect, and body state are skill modifiers and strategy
    biases, not skill definitions.
20. Skill checks are advisory/pre-settlement inputs; ESM and physical channels
    remain authoritative for world truth.

## Architecture

The selected architecture is:

```text
Independent CharacterSkillService + Binding Registry
```

Runtime flow:

```text
L2
-> updates perception, memory, need tension, affect, dynamic state

CharacterSkillService
-> builds SkillAffordanceSummary for L3

L3
-> selects intent / goal / broad action direction

L4
-> creates CompositeActionProposal plus strategy preferences

CharacterSkillService
-> evaluates skill paths
-> outputs SkillEvaluationResult
-> selects/recommends a skill path

ActionLibrary
-> expands PrimitiveActionPlan for selected skill path

InteractionOrchestration / ESM
-> semantic authority settlement

Physical Channel
-> embodied/spatial/contact/object feasibility settlement

Realization Layer
-> Asset Registry / Kimodo / Godot fallback presentation

SkillEvidenceExtractor
-> records policy-gated SkillEvidence
```

Boundary rules:

- `CharacterSkillService` does not decide world truth.
- ESM does not own character skill state or skill learning.
- Physical channel does not own skill state.
- Realization does not change settlement truth.
- L3 reads summaries only.

## Registry And Overlay Model

Effective skill/action space is composed from layered sources:

```text
Core Registry
+ Scenario Registry
+ Character Overlay
+ Equipment Overlay
+ Runtime Modifiers
= EffectiveSkillActionSpace
```

### Core Registry

Platform-level reusable skills and actions, such as:

- observe
- listen
- persuasion
- deception
- first_aid
- stealth
- tool_use
- approach_target
- inspect_object
- speak_private
- carry_object

### Scenario Registry

World, scenario, room, or gameplay-mode extensions, such as:

- ritual_detection
- noble_etiquette
- faction_protocol
- supernatural_disguise
- special world-rule actions

### Character Overlay

Per-character skill state, learned skill overlays, restrictions, and visibility.

### Equipment Overlay

Temporary grants and modifiers from tools, equipment, props, or asset state.
Equipment grants do not mean the character has permanently learned a skill.

### Runtime Modifiers

Need pressure, affect, tension, body state, injury, fatigue, environment, and
relationship state modify path preference, confidence, quality, risk, and cost.
They do not define skills.

## Core Data Models

### SkillDefinition

Defines a skill type, not whether a character owns it.

```yaml
SkillDefinition:
  skill_id: first_aid
  display_name: First Aid
  settlement_categories:
    - cognitive
    - tool
    - social
  domains:
    - medical
    - emergency_response
  role_tags:
    - doctor
    - field_medic
  learnability: trained
  risk_tags:
    - infection_risk
    - pain_increase_risk
  visibility_default:
    player_visible: true
```

### ActionDefinition

Defines an action type. Actions can be composite or primitive.

```yaml
ActionDefinition:
  action_id: stabilize_injured_actor
  kind: composite
  target_types:
    - actor
  settlement_categories:
    - cognitive
    - physical
    - social
    - tool
  primitive_sequence_templates:
    first_aid_path:
      - approach_target
      - kneel_near_target
      - inspect_wound
      - apply_pressure
      - speak_reassurance
  variant_rules:
    - when:
        outcome_band: clean_success
      presentation_tags:
        - focused_care
        - steady_breath
    - when:
        outcome_band: failed
      presentation_tags:
        - uncertain_hands
        - anxious_recheck
  realization_keys:
    - medical_stabilize
    - kneel_inspect
```

### SkillActionBinding

Defines how a skill supports an action.

```yaml
SkillActionBinding:
  binding_id: first_aid_to_stabilize_injured_actor
  skill_id: first_aid
  action_id: stabilize_injured_actor
  skill_path_tags:
    - medical
    - nonviolent
    - urgent_care
  eligibility:
    required_rank: basic
    required_world_affordances:
      - target.injured
    optional_tools:
      - bandage
      - clean_cloth
  quality:
    primary_weight: 0.7
    supporting_skills:
      triage: 0.2
      emotional_regulation: 0.1
    runtime_modifiers:
      stress_load: -0.15
      calm: 0.08
  learning:
    evidence_on_attempt: true
    evidence_on_blocked: false
    evidence_channels:
      - improvement
      - specialization
      - confidence
```

### CharacterSkillState

Defines a specific character's skill state.

```yaml
CharacterSkillState:
  actor_id: char_a
  skill_id: first_aid
  source: authored
  rank: trained
  proficiency: 0.65
  confidence: 0.7
  familiarity:
    bleeding_control: 0.4
    medical_kit: 0.5
  restrictions: []
  evidence_refs: []
  visibility:
    player_visible: true
    visible_to_actors:
      - char_self
```

### SkillAffordanceSummary

Compressed view for L3.

```yaml
SkillAffordanceSummary:
  actor_id: char_a
  available_action_families:
    medical_help:
      level: trained
      confidence: medium
      examples:
        - stabilize_injured_actor
        - diagnose_wound
    social_deescalation:
      level: moderate
      confidence: high
    physical_force:
      level: weak
      confidence: low
      constraints:
        - old_shoulder_injury
  blocked_action_families:
    ritual_magic:
      reason: no_skill_source
  notable_constraints:
    - refuses_lethal_force
```

### CompositeActionProposal

L4 proposal before skill-path evaluation.

```yaml
CompositeActionProposal:
  proposal_id: action_prop:char_a:123
  actor_id: char_a
  source_intent: stabilize_target
  action_id: stabilize_injured_actor
  target_refs:
    actor: char_b
  preferred_strategy_tags:
    - nonviolent
    - urgent_care
  forbidden_strategy_tags:
    - lethal
  desired_outcomes:
    - target_stabilized
    - panic_reduced
```

### SkillEvaluationResult

CharacterSkillService output.

```yaml
SkillEvaluationResult:
  actor_id: char_a
  action_id: stabilize_injured_actor
  selected_path:
    binding_id: first_aid_to_stabilize_injured_actor
    skill_id: first_aid
  viable_paths:
    - binding_id: first_aid_to_stabilize_injured_actor
      eligibility_status: eligible
      objective_feasibility: 0.72
      character_fit: 0.84
      expected_quality: success_with_cost
      risk_estimate:
        infection_risk: medium
  blocked_paths:
    - binding_id: healing_magic_to_stabilize
      missing_requirements:
        - healing_magic.basic
  recommendation_reason:
    - matches_nonviolent_strategy
    - medical_skill_available
  learning_policy_snapshot:
    promotion_enabled: false
```

### PrimitiveActionPlan

Expanded after selected skill path.

```yaml
PrimitiveActionPlan:
  composite_action_id: stabilize_injured_actor
  skill_path_id: first_aid_to_stabilize
  primitive_actions:
    - approach_target
    - kneel_near_target
    - inspect_wound
    - apply_pressure
    - speak_reassurance
  realization_keys:
    - approach_careful
    - kneel_inspect
    - apply_pressure
    - calm_voice
```

### ActionSettlementResult

Separates result degree from failure cause.

```yaml
ActionSettlementResult:
  outcome_band: success_with_cost
  failure_domains:
    - tool_failure
  primary_failure_domain: tool_failure
  semantic_effects:
    - bleeding_reduced
  physical_effects:
    - actor_near_target
  social_effects:
    - target_trust_increased
  costs:
    - clean_cloth_contaminated
  realization_hints:
    - focused_care
    - urgent_low_voice
```

Outcome bands:

- blocked
- failed
- partial
- success_with_cost
- clean_success
- misfire

Failure domains:

- skill_failure
- missing_requirement
- world_constraint
- physical_failure
- authority_policy_failure
- social_resistance
- state_interference
- tool_failure
- knowledge_mismatch
- realization_failure

### SkillEvidence

Dedicated skill evidence; not undifferentiated memory.

```yaml
SkillEvidence:
  evidence_id: skill_evidence:...
  actor_id: char_a
  skill_id: first_aid
  action_id: stabilize_injured_actor
  binding_id: first_aid_to_stabilize_injured_actor
  source_settlement_id: settlement:123
  outcome_band: partial
  primary_failure_domain: skill_failure
  failure_domains:
    - skill_failure
    - state_interference
  evidence_channels:
    acquisition: 0.0
    improvement: 0.12
    confidence: 0.03
    specialization:
      bleeding_control: 0.08
    tool_familiarity:
      clean_cloth: 0.04
    maladaptive_pattern: {}
  eligible_for_candidate: false
  eligible_for_promotion: false
```

## Skill Learning

Learning is future-facing and gated. First-phase implementation may include
schema and recording only.

Pipeline:

```text
ActionSettlementResult
-> SkillEvidenceExtractor
-> SkillEvidenceStore
-> SkillCandidateStore
-> SkillPromotionGate
-> LearnedSkillLayer
-> EffectiveSkillStateResolver
```

Policy:

```yaml
SkillLearningPolicy:
  evidence_collection_enabled: true
  candidate_generation_enabled: true
  promotion_enabled: false
  auto_promotion_enabled: false
  allowed_domains:
    - social
    - investigation
    - medical
  blocked_domains:
    - authority
    - special
```

Promotion checks:

- policy permission
- learnability permission
- authored-profile compatibility
- sufficient evidence
- required external conditions
- fairness/safety
- explainable evidence refs

Learnability classes:

- natural
- trained
- granted
- locked

Authority and special skills are never auto-promoted unless explicitly granted.

## Visibility And Observed Skill Beliefs

The system distinguishes:

```text
ActualSkillState
InternalSkillAffordanceSummary
PlayerFacingCapabilityHint
ObservedSkillBelief
```

Example:

```yaml
ObservedSkillBelief:
  observer_actor_id: char_b
  subject_actor_id: char_a
  skill_id: deception
  belief_state: suspected
  confidence: 0.42
  evidence_refs:
    - saw_inconsistent_story
```

First phase may define schemas but should not implement complex inference.

## Realization And Kimodo

Realization consumes:

- selected skill path
- primitive action plan
- settlement outcome
- presentation tags
- body and affect state
- fallback policy
- Kimodo allowed flag

Realization may choose:

- local asset
- Kimodo generated motion
- fallback presentation

Realization must not change settlement truth.

## Phased Adoption

### Phase 1: Binding Contract

Implement schemas and a minimal service interface. Keep behavior compatible.

Suggested modules:

```text
backend/app/character_agent/skills/
  models.py
  registry.py
  service.py
  affordance.py
  evidence.py
```

Phase 1 includes:

- SkillDefinition
- ActionDefinition
- SkillActionBinding
- CharacterSkillState
- SkillAffordanceSummary
- CompositeActionProposal
- SkillEvaluationRequest
- SkillEvaluationResult
- PrimitiveActionPlan
- SkillLearningPolicy
- SkillEvidence schema

Phase 1 does not include:

- automatic promotion
- full candidate store
- ESM hard gating
- full action library replacement
- live Kimodo integration

### Phase 2: L3/L4 Integration

- Feed SkillAffordanceSummary into L3.
- Let L4 emit CompositeActionProposal.
- Run CharacterSkillService evaluation.
- Preserve old L4 fallback.

### Phase 3: Settlement Integration

- Feed SkillEvaluationResult into settlement request.
- Feed PrimitiveActionPlan into physical channel.
- Structure outcome band and failure domain.
- Extract SkillEvidence from settlement result.

### Phase 4: Learning / Visibility / Long-Term

- SkillCandidateStore
- SkillPromotionGate
- LearnedSkillLayer
- ObservedSkillBeliefStore
- PlayerFacingCapabilityHint
- Hermes-inspired skill-evolution review flow

## Acceptance Criteria

- The design keeps authored profile truth, runtime skill state, and learned skill
  overlay separate.
- The design keeps ESM as semantic authority and physical channel as embodied
  authority.
- The design keeps realization/Kimodo presentation-only.
- The design supports hybrid skill checks: rank/tag eligibility plus numeric
  quality/risk.
- The design supports multiple skill paths per action and multiple actions per
  skill.
- The design supports disabled skill learning and promotion-off-by-default.
- The design provides a phased path that can start in shadow mode without
  replacing existing L4 behavior.
