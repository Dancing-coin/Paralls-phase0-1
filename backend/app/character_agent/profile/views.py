from __future__ import annotations

from dataclasses import dataclass

from app.character_agent.profile.models import CharacterProfile


@dataclass(frozen=True, slots=True)
class ProfileIdentityView:
    actor_id: str
    canonical_name: str
    aliases: tuple[str, ...]
    occupation_role: str

    @classmethod
    def from_profile(cls, profile: CharacterProfile) -> "ProfileIdentityView":
        return cls(
            actor_id=profile.identity_core.character_id,
            canonical_name=profile.identity_core.canonical_name,
            aliases=tuple(profile.identity_core.aliases),
            occupation_role=profile.identity_core.occupation_role,
        )


@dataclass(frozen=True, slots=True)
class ProfileValuesView:
    value_priorities: tuple[str, ...]
    red_lines: tuple[str, ...]
    forbidden_behaviors: tuple[str, ...]

    @classmethod
    def from_profile(cls, profile: CharacterProfile) -> "ProfileValuesView":
        return cls(
            value_priorities=tuple(profile.virtue_value_layer.value_priorities),
            red_lines=tuple(profile.virtue_value_layer.red_lines),
            forbidden_behaviors=tuple(profile.virtue_value_layer.forbidden_behaviors),
        )


@dataclass(frozen=True, slots=True)
class ProfileCapabilitiesView:
    skills: tuple[str, ...]
    knowledge_domains: tuple[str, ...]
    physical_constraints: tuple[str, ...]
    psychological_constraints: tuple[str, ...]
    social_constraints: tuple[str, ...]

    @classmethod
    def from_profile(cls, profile: CharacterProfile) -> "ProfileCapabilitiesView":
        return cls(
            skills=tuple(profile.capability_constraint_layer.skills),
            knowledge_domains=tuple(profile.capability_constraint_layer.knowledge_domains),
            physical_constraints=tuple(profile.capability_constraint_layer.physical_constraints),
            psychological_constraints=tuple(profile.capability_constraint_layer.psychological_constraints),
            social_constraints=tuple(profile.capability_constraint_layer.social_constraints),
        )


@dataclass(frozen=True, slots=True)
class ProfileConversationBiasView:
    social_openness: float
    privacy_sensitivity: float
    talk_initiative: float
    deception_control: float
    trust_threshold_for_private_talk: float

    @classmethod
    def from_profile(cls, profile: CharacterProfile) -> "ProfileConversationBiasView":
        return cls(
            social_openness=profile.conversation_personality_layer.social_openness,
            privacy_sensitivity=profile.conversation_personality_layer.privacy_sensitivity,
            talk_initiative=profile.conversation_personality_layer.talk_initiative,
            deception_control=profile.conversation_personality_layer.deception_control,
            trust_threshold_for_private_talk=profile.conversation_personality_layer.trust_threshold_for_private_talk,
        )
