from app.character_agent.profile.loader import CharacterProfileLoader


def test_character_profile_loader_accepts_needs_temperament_and_drift_layers(tmp_path):
    profile_path = tmp_path / "char_test.yaml"
    profile_path.write_text(
        """
identity_core:
  character_id: char_test
  canonical_name: Test Person
  aliases: []
  occupation_role: witness
origin_seed:
  homeland: low district
  formative_context: careful upbringing
  current_scene_function: observer
life_memory_backbone:
  defining_memories: []
  unresolved_knots: []
virtue_value_layer:
  value_priorities: [care]
  red_lines: [betray trust]
  forbidden_behaviors: [fabricate authority]
trait_vector_layer:
  courage: 0.4
  scheming: 0.2
  empathy: 0.8
  rationality: 0.7
  sociability: 0.5
capability_constraint_layer:
  skills: []
  knowledge_domains: []
  physical_constraints: []
  psychological_constraints: []
  social_constraints: []
style_expression_bias_layer:
  speech_style: measured
  silence_pattern: guarded
  gesture_bias: contained
  posture_bias: upright
conversation_personality_layer:
  social_openness: 0.5
  privacy_sensitivity: 0.6
  talk_initiative: 0.4
  deception_control: 0.8
  trust_threshold_for_private_talk: 0.7
need_hierarchy_layer:
  base_weights:
    physiological: 0.2
    safety: 0.8
    belonging: 0.6
    esteem: 0.5
    self_actualization: 0.4
  deprivation_sensitivity:
    physiological: 0.2
    safety: 0.8
    belonging: 0.6
    esteem: 0.5
    self_actualization: 0.4
  satisfaction_sensitivity:
    physiological: 0.2
    safety: 0.7
    belonging: 0.7
    esteem: 0.6
    self_actualization: 0.3
  dominant_drives: [preserve_order]
  satisfaction_channels:
    physiological: []
    safety: [predictable_routine]
    belonging: []
    esteem: []
    self_actualization: []
  frustration_channels:
    physiological: []
    safety: [spatial_uncertainty]
    belonging: []
    esteem: []
    self_actualization: []
temperament_response_layer:
  baseline_temperament:
    caution: 0.7
    dominance: 0.3
    attachment: 0.6
    emotional_reactivity: 0.5
    recovery_speed: 0.5
    impulse_control: 0.8
  conflict_style:
    confrontation_tendency: 0.2
    avoidance_tendency: 0.7
    mediation_tendency: 0.8
    escalation_threshold: 0.7
  defense_patterns:
    under_pressure: [procedural_control]
    under_shame: [silence]
    under_threat: [vigilance]
    under_loss: [withdrawal]
  trust_dynamics:
    initial_trust_bias: 0.4
    betrayal_memory_weight: 0.8
    forgiveness_threshold: 0.3
    loyalty_lock_in: 0.6
  expression_bias:
    outward_warmth: 0.4
    emotional_transparency: 0.3
    facial_control: 0.8
    verbal_indirection: 0.7
long_term_personality_drift_layer:
  stable_shifts: []
  reinforced_patterns: []
  weakened_patterns: []
  need_reweights: {}
  trust_reweights: {}
  expression_reweights: {}
  drift_policy:
    minimum_cross_scene_count: 3
    minimum_confirming_events: 8
    minimum_time_span: long_arc
    require_non_transient_evidence: true
runtime_defaults:
  default_control_mode: agent_full_auto
""",
        encoding="utf-8",
    )

    loader = CharacterProfileLoader(tmp_path)
    profile = loader.load("char_test")

    assert profile.need_hierarchy_layer.base_weights.safety == 0.8
    assert profile.temperament_response_layer.defense_patterns.under_shame == ["silence"]
    assert (
        profile.long_term_personality_drift_layer.drift_policy.minimum_confirming_events == 8
    )
