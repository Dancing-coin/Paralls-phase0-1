from __future__ import annotations

from app.character_agent.skills.models import ActionDefinition, SkillActionBinding, SkillDefinition
from app.character_agent.skills.registry import CharacterSkillRegistry


def create_core_skill_registry() -> CharacterSkillRegistry:
    return CharacterSkillRegistry(
        skills=[
            SkillDefinition(
                skill_id="observation",
                display_name="Observation",
                settlement_categories=["cognitive"],
                domains=["observation"],
                role_tags=["perception"],
            ),
            SkillDefinition(
                skill_id="mediation",
                display_name="Mediation",
                settlement_categories=["social"],
                domains=["social"],
                role_tags=["de-escalation"],
            ),
            SkillDefinition(
                skill_id="procedural recall",
                display_name="Procedural Recall",
                settlement_categories=["cognitive", "tool"],
                domains=["procedure"],
                role_tags=["routine"],
            ),
            SkillDefinition(
                skill_id="threat assessment",
                display_name="Threat Assessment",
                settlement_categories=["cognitive", "authority"],
                domains=["safety_assessment", "threat_assessment"],
                role_tags=["security", "risk"],
            ),
            SkillDefinition(
                skill_id="command presence",
                display_name="Command Presence",
                settlement_categories=["social", "authority"],
                domains=["boundary_enforcement"],
                role_tags=["security", "assertion"],
            ),
            SkillDefinition(
                skill_id="perimeter discipline",
                display_name="Perimeter Discipline",
                settlement_categories=["authority", "physical"],
                domains=["access_control", "procedure"],
                role_tags=["security", "routine"],
            ),
        ],
        actions=[
            ActionDefinition(
                action_id="survey_scene",
                kind="composite",
                target_types=["room", "object", "actor"],
                settlement_categories=["cognitive"],
                primitive_sequence_templates={
                    "observation_to_survey_scene": ["orient_to_space", "scan_visible_changes", "note_relevant_details"],
                },
                realization_keys=["look_at_target", "focus_attention"],
            ),
            ActionDefinition(
                action_id="defuse_social_tension",
                kind="composite",
                target_types=["actor", "group"],
                settlement_categories=["social"],
                primitive_sequence_templates={
                    "mediation_to_defuse_social_tension": [
                        "approach_calmly",
                        "acknowledge_concerns",
                        "offer_face_saving_path",
                    ],
                },
                realization_keys=["open_palms", "steady_voice"],
            ),
            ActionDefinition(
                action_id="follow_room_protocol",
                kind="composite",
                target_types=["room", "object"],
                settlement_categories=["cognitive", "tool"],
                primitive_sequence_templates={
                    "procedural_recall_to_follow_room_protocol": [
                        "recall_required_steps",
                        "apply_access_sequence",
                        "confirm_completion_state",
                    ],
                },
                realization_keys=["refer_to_routine", "perform_ordered_steps"],
            ),
            ActionDefinition(
                action_id="assess_visible_threat",
                kind="composite",
                target_types=["room", "object", "actor"],
                settlement_categories=["cognitive", "authority"],
                primitive_sequence_templates={
                    "threat_assessment_to_assess_visible_threat": [
                        "scan_boundary",
                        "compare_against_access_rules",
                        "mark_risk_level",
                    ],
                },
                realization_keys=["focused_scan", "guarded_attention"],
            ),
            ActionDefinition(
                action_id="enforce_access_boundary",
                kind="composite",
                target_types=["actor", "object", "zone"],
                settlement_categories=["social", "authority"],
                primitive_sequence_templates={
                    "command_presence_to_enforce_access_boundary": [
                        "step_into_boundary_line",
                        "state_denial_clearly",
                        "request_protocol_confirmation",
                    ],
                },
                realization_keys=["firm_voice", "boundary_gesture"],
            ),
            ActionDefinition(
                action_id="secure_perimeter",
                kind="composite",
                target_types=["zone", "object"],
                settlement_categories=["authority", "physical"],
                primitive_sequence_templates={
                    "perimeter_discipline_to_secure_perimeter": [
                        "hold_guard_position",
                        "watch_entry_points",
                        "confirm_boundary_state",
                    ],
                },
                realization_keys=["guarded_stance", "perimeter_watch"],
            ),
        ],
        bindings=[
            SkillActionBinding(
                binding_id="observation_to_survey_scene",
                skill_id="observation",
                action_id="survey_scene",
                skill_path_tags=["observation", "baseline"],
                eligibility={"required_rank": "basic"},
            ),
            SkillActionBinding(
                binding_id="mediation_to_defuse_social_tension",
                skill_id="mediation",
                action_id="defuse_social_tension",
                skill_path_tags=["social", "de-escalation"],
                eligibility={"required_rank": "basic"},
            ),
            SkillActionBinding(
                binding_id="procedural_recall_to_follow_room_protocol",
                skill_id="procedural recall",
                action_id="follow_room_protocol",
                skill_path_tags=["procedure", "routine"],
                eligibility={"required_rank": "basic"},
            ),
            SkillActionBinding(
                binding_id="threat_assessment_to_assess_visible_threat",
                skill_id="threat assessment",
                action_id="assess_visible_threat",
                skill_path_tags=["security", "risk", "observation"],
                eligibility={"required_rank": "basic"},
            ),
            SkillActionBinding(
                binding_id="command_presence_to_enforce_access_boundary",
                skill_id="command presence",
                action_id="enforce_access_boundary",
                skill_path_tags=["security", "boundary", "authority"],
                eligibility={"required_rank": "basic"},
            ),
            SkillActionBinding(
                binding_id="perimeter_discipline_to_secure_perimeter",
                skill_id="perimeter discipline",
                action_id="secure_perimeter",
                skill_path_tags=["security", "perimeter", "routine"],
                eligibility={"required_rank": "basic"},
            ),
        ],
    )


def create_runtime_skill_registry(*overlays: CharacterSkillRegistry) -> CharacterSkillRegistry:
    return CharacterSkillRegistry.compose(create_core_skill_registry(), *overlays)
