# Character Personality Trait Vector Refactor Design

Status: `proposed`

Date: `2026-07-13`

## Purpose

Refactor the character personality model so that personality can support a
standard Big Five foundation without double-counting the existing custom
`trait_vector_layer` fields.

The current flat fields (`courage`, `scheming`, `empathy`, `rationality`, and
`sociability`) are useful for authoring, but they overlap heavily with Big Five
dimensions. This design replaces them as raw behavior inputs with a cleaner
model:

```text
Big Five + facets
+ values
+ temperament
+ conversation style
+ capability context
        ↓
PersonalityProjectionResolver
        ↓
deduplicated personality_projection
        ↓
needs / affect / L2 / L3 / L4
```

The goal is not to add more personality labels. The goal is to give the runtime
one canonical, deduplicated personality projection surface for decision making.

## Source Context

Current repository facts:

- `CharacterProfile.trait_vector_layer` is currently a flat Pydantic model with
  `courage`, `scheming`, `empathy`, `rationality`, and `sociability`.
- `CharacterProfile` already has separate layers for values, conversation
  style, temperament response, capabilities, needs, and long-term drift.
- `NeedTensionEngine` uses `need_hierarchy_layer` and `effective_profile` to
  derive runtime need pressure.
- `AffectEngine` uses `temperament_response_layer.baseline_temperament` and
  need pressure to derive runtime dynamic state.
- `L2` and `L3` already receive profile/effective-profile context.
- `CharacterMindFrame` already has an `effective_profile` card and a
  `personality_bias` card type in the enduring-truth layer.
- Current behavior should not be changed accidentally while restructuring the
  profile schema.

Related documents:

- `docs/superpowers/specs/2026-07-08-character-needs-personality-affect-runtime-design.md`
- `docs/superpowers/specs/2026-07-11-layered-character-mind-factor-architecture-design.md`
- `docs/架构/运行时/模块/角色智能体.md`
- `docs/character/character-mind-core-status.md`

## Problem

The current flat `trait_vector_layer` mixes several kinds of concepts:

| Current field | Actual meaning | Big Five overlap |
| --- | --- | --- |
| `courage` | pressure-resistant action tendency | low neuroticism, assertiveness, persistence, value commitment |
| `scheming` | ambiguous mix of planning, strategy, manipulation | conscientiousness, openness, low agreeableness, dominance |
| `empathy` | empathic attunement | agreeableness / compassion |
| `rationality` | analytic control and deliberation | conscientiousness, openness, low volatility |
| `sociability` | social approach tendency | extraversion, warmth, agreeableness |

Adding Big Five next to these fields as another peer set would create duplicate
behavior weights. For example, `agreeableness`, `empathy`, and
`mediation_tendency` would all try to bias de-escalation. `extraversion`,
`sociability`, and `talk_initiative` would all try to bias social approach.

The runtime needs correlated authoring fields, but behavior scoring needs a
single deduplicated projection.

## Goals

1. Make Big Five the standard low-level personality foundation.
2. Preserve project-specific role expressiveness without using overlapping
   custom traits as raw behavior inputs.
3. Split ambiguous traits such as `scheming` into clearer runtime projections.
4. Introduce `personality_projection` as the only behavior-facing personality
   signal surface.
5. Keep authored profile truth separate from runtime state and drift.
6. Preserve backward compatibility for existing profiles during migration.
7. Start in shadow mode so profile refactoring does not silently change current
   L2/L3/L4 behavior.

## Non-Goals

- Do not implement MBTI as a numeric runtime layer.
- Do not let Big Five directly choose actions.
- Do not let `personality_projection` replace need pressure, dynamic state,
  goals, memory, skills, or authority settlement.
- Do not rewrite all existing L2/L3 scoring in the schema migration phase.
- Do not remove current profile YAML compatibility in the first implementation
  pass.
- Do not treat short-term emotion as a personality trait.

## Design Decision

The long-term profile model should stop treating the flat `trait_vector_layer`
fields as personality atoms.

Target structure:

```yaml
personality_layer:
  big_five:
    openness: 0.62
    conscientiousness: 0.81
    extraversion: 0.46
    agreeableness: 0.78
    neuroticism: 0.34

  facets:
    openness:
      curiosity: 0.58
      imagination: 0.44
      ambiguity_tolerance: 0.61
      novelty_seeking: 0.36
    conscientiousness:
      orderliness: 0.86
      dutifulness: 0.82
      deliberation: 0.79
      persistence: 0.68
    extraversion:
      social_energy: 0.43
      assertiveness: 0.35
      warmth: 0.62
      activity_level: 0.48
    agreeableness:
      compassion: 0.84
      trust: 0.56
      cooperativeness: 0.78
      conflict_softening: 0.82
    neuroticism:
      anxiety: 0.36
      shame_sensitivity: 0.42
      volatility: 0.24
      vulnerability: 0.38

personality_projection:
  social_approach_bias: 0.52
  empathic_attunement: 0.81
  analytical_control: 0.76
  courage_bias: 0.61
  strategic_planning: 0.68
  manipulative_tendency: 0.18
  conflict_deescalation_bias: 0.83
  procedural_discipline: 0.84
  public_assertion_bias: 0.39
  avoidance_bias: 0.44
  trust_repair_bias: 0.72
  privacy_guard_bias: 0.69
  stress_vulnerability: 0.31
```

Implementation may store `personality_projection` as a generated read model
rather than authored YAML. The important rule is that L2/L3/L4 consume the
projection, not overlapping raw fields.

## Big Five Foundation

The five top-level Big Five scores are broad summary dimensions:

- `openness`: curiosity, imagination, ambiguity tolerance, willingness to
  update interpretations.
- `conscientiousness`: orderliness, duty, deliberation, persistence, procedural
  discipline.
- `extraversion`: social energy, assertion, warmth, public approach.
- `agreeableness`: compassion, trust, cooperation, conflict softening.
- `neuroticism`: anxiety, shame sensitivity, volatility, vulnerability to
  stress.

Facets are preferred over top-level scores for projection formulas because they
make behavior influences more explainable.

## Legacy Trait Migration

Existing flat fields should be treated as legacy authoring inputs or derived
concepts, not behavior atoms:

### `empathy`

Maps primarily to `agreeableness.compassion` and the projection
`empathic_attunement`.

Do not independently add `empathy` and `agreeableness` to de-escalation scores.

### `sociability`

Maps primarily to `extraversion.social_energy`, `extraversion.warmth`, and the
projection `social_approach_bias`.

### `rationality`

Maps to `analytical_control`, not a raw Big Five field. It combines
deliberation, orderliness, ambiguity tolerance, and low volatility.

### `courage`

Maps to `courage_bias`. Courage is not a primitive personality atom; it is the
runtime tendency to act despite pressure.

### `scheming`

Must be split. It is too ambiguous as a single trait.

Use two projections:

- `strategic_planning`: careful strategy and anticipation.
- `manipulative_tendency`: willingness to manipulate or deceive.

This prevents a capable planner from being accidentally modeled as morally
deceptive.

## Personality Projection

`PersonalityProjectionResolver` should generate a normalized projection from:

- `personality_layer.big_five`
- `personality_layer.facets`
- `virtue_value_layer`
- `temperament_response_layer`
- `conversation_personality_layer`
- `capability_constraint_layer`
- legacy `trait_vector_layer` fields, only during migration

Projection values are clamped to `[0.0, 1.0]` and include provenance/debug data
in tests or optional diagnostics.

Recommended projection formulas:

```text
empathic_attunement =
  0.55 * agreeableness.compassion
+ 0.20 * agreeableness.cooperativeness
+ 0.15 * openness.ambiguity_tolerance
+ 0.10 * legacy_empathy_or_default
```

```text
social_approach_bias =
  0.40 * extraversion.social_energy
+ 0.25 * extraversion.warmth
+ 0.20 * conversation.social_openness
+ 0.15 * agreeableness.trust
```

```text
analytical_control =
  0.40 * conscientiousness.deliberation
+ 0.25 * conscientiousness.orderliness
+ 0.20 * openness.ambiguity_tolerance
+ 0.15 * (1 - neuroticism.volatility)
```

```text
courage_bias =
  0.35 * (1 - neuroticism.anxiety)
+ 0.25 * extraversion.assertiveness
+ 0.20 * conscientiousness.persistence
+ 0.20 * value_commitment_strength
```

```text
strategic_planning =
  0.35 * conscientiousness.deliberation
+ 0.25 * openness.ambiguity_tolerance
+ 0.20 * analytical_control
+ 0.20 * temperament.impulse_control
```

```text
manipulative_tendency =
  0.35 * (1 - agreeableness.cooperativeness)
+ 0.25 * (1 - agreeableness.compassion)
+ 0.20 * temperament.dominance
+ 0.20 * (1 - conversation.deception_control)
```

```text
conflict_deescalation_bias =
  0.35 * agreeableness.cooperativeness
+ 0.30 * agreeableness.compassion
+ 0.15 * temperament.conflict_style.mediation_tendency
+ 0.10 * temperament.impulse_control
+ 0.10 * conversation.deception_control
```

```text
procedural_discipline =
  0.40 * conscientiousness.orderliness
+ 0.25 * conscientiousness.dutifulness
+ 0.20 * conscientiousness.deliberation
+ 0.15 * procedural_training_modifier
```

```text
stress_vulnerability =
  0.45 * neuroticism.anxiety
+ 0.25 * neuroticism.vulnerability
+ 0.20 * temperament.emotional_reactivity
+ 0.10 * (1 - temperament.recovery_speed)
```

```text
public_assertion_bias =
  0.35 * extraversion.assertiveness
+ 0.25 * temperament.dominance
+ 0.20 * courage_bias
+ 0.20 * (1 - conversation.privacy_sensitivity)
```

```text
avoidance_bias =
  0.35 * neuroticism.anxiety
+ 0.25 * temperament.conflict_style.avoidance_tendency
+ 0.20 * conversation.privacy_sensitivity
+ 0.20 * (1 - courage_bias)
```

```text
trust_repair_bias =
  0.30 * agreeableness.compassion
+ 0.25 * agreeableness.trust
+ 0.20 * temperament.trust_dynamics.forgiveness_threshold
+ 0.15 * temperament.attachment
+ 0.10 * empathic_attunement
```

```text
privacy_guard_bias =
  0.40 * conversation.privacy_sensitivity
+ 0.25 * conscientiousness.dutifulness
+ 0.20 * virtue_value_privacy_strength
+ 0.15 * temperament.facial_control_or_expression_control
```

## Duplicate Weight Guard

The overlap problem is solved by a consumption rule, not by pretending the raw
dimensions are statistically independent.

Rules:

1. Raw Big Five, facets, and legacy role traits may be correlated.
2. Behavior layers must not consume overlapping raw fields directly.
3. L2/L3/L4 should consume `personality_projection` entries.
4. A behavior score should use one projection per psychological meaning.
5. Tests should fail if L3 scoring starts using both a raw field and its
   projection for the same bias.

Example:

```text
Correct:
  conflict_deescalation_bias -> de-escalation score

Incorrect:
  agreeableness + empathy + mediation_tendency -> de-escalation score
```

## Relationship To Existing Mind Factors

This design only refactors personality. It does not change the seven-factor
architecture.

- Personality remains authored truth plus conservative drift.
- Needs continue to use `need_hierarchy_layer` and `NeedTensionState`.
- Emotion/body state remains runtime `CharacterDynamicState`.
- Memory and relationship remain memory-owned evidence/projections.
- Goals remain runtime intent state.
- Skills remain capability/action affordances until the full skill system lands.

`personality_projection` should influence these surfaces gradually:

- `NeedTensionEngine`: optional future modifiers for sensitivity and pressure
  interpretation.
- `AffectEngine`: optional future modifiers for stress vulnerability and
  recovery behavior.
- `L2`: clearer profile summaries and interpretation style hints.
- `L3`: deduplicated strategy biases.
- `L4`: expression/presentation hints.

## Compatibility And Migration

Migration should be staged:

1. Add new models while accepting current flat `trait_vector_layer` YAML.
2. Generate `personality_projection` in shadow mode.
3. Add projection cards to `CharacterMindFrame` without changing L2/L3 behavior.
4. Migrate character YAML files to `personality_layer`.
5. Update L2 prompt summaries to include projection summaries.
6. Update L3 scoring to consume projections and stop reading overlapping raw
   traits.
7. Deprecate the old flat trait vector after all profiles and tests migrate.

## Acceptance Criteria

- Existing profiles load unchanged during the first implementation phase.
- New profiles can define `personality_layer.big_five` and facets.
- Legacy `courage`, `scheming`, `empathy`, `rationality`, and `sociability`
  can be normalized into projection inputs during migration.
- `PersonalityProjectionResolver` emits stable, clamped projection values.
- `CharacterMindFrame` exposes personality projections as authored/enduring
  read-model evidence.
- No initial shadow-mode task changes command output, L2 decisions, or L3
  selected intents.
- Later behavior-consuming phases include regression tests proving duplicate
  raw/projection scoring does not occur.
- Documentation explains that MBTI is not the numeric runtime basis.

