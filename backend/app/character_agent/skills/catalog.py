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
        ],
    )


def create_runtime_skill_registry(*overlays: CharacterSkillRegistry) -> CharacterSkillRegistry:
    return CharacterSkillRegistry.compose(create_core_skill_registry(), *overlays)
