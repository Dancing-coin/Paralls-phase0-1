from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.character_agent.profile.models import CharacterProfile


DossierVisibilityValue = Literal[
    "visible",
    "summarized",
    "partial",
    "belief_only",
    "constraint_only",
    "action_relevant_only",
    "hidden",
]

DossierScalar = Field(ge=0.0, le=1.0)


class StrictDossierModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DossierVisibilityPolicy(StrictDossierModel):
    author: DossierVisibilityValue = "visible"
    self: DossierVisibilityValue = "visible"
    other_actors: DossierVisibilityValue = "belief_only"
    player: DossierVisibilityValue = "summarized"
    l2: DossierVisibilityValue = "summarized"
    l3: DossierVisibilityValue = "summarized"
    l4: DossierVisibilityValue = "action_relevant_only"


class DossierLayerMetadata(StrictDossierModel):
    layer_id: str = ""
    layer_version: int = Field(default=1, ge=1)
    source: str = "authored"
    hot_reload_allowed: bool = True
    invalidates: list[str] = Field(default_factory=list)
    does_not_mutate: list[str] = Field(default_factory=list)


class DossierMetadata(StrictDossierModel):
    authoring_status: str = "draft"
    layer_versions: dict[str, int] = Field(default_factory=dict)
    layers: dict[str, DossierLayerMetadata] = Field(default_factory=dict)


class DemographicIdentity(StrictDossierModel):
    age_band: str | None = None
    gender_identity: str | None = None
    body_identity: str | None = None


class RoleIdentities(StrictDossierModel):
    occupational_role: str | None = None
    scene_role: str | None = None
    authority_role: str | None = None


class AffiliationIdentities(StrictDossierModel):
    organizations: list[str] = Field(default_factory=list)
    factions: list[str] = Field(default_factory=list)


class SocialIdentities(StrictDossierModel):
    social_rank: str | None = None
    reputation_tags: list[str] = Field(default_factory=list)


class IdentityProfile(StrictDossierModel):
    actor_id: str = ""
    canonical_name: str = ""
    aliases: list[str] = Field(default_factory=list)
    demographic_identity: DemographicIdentity = Field(default_factory=DemographicIdentity)
    role_identities: RoleIdentities = Field(default_factory=RoleIdentities)
    affiliation_identities: AffiliationIdentities = Field(default_factory=AffiliationIdentities)
    social_identities: SocialIdentities = Field(default_factory=SocialIdentities)
    family_identities: list[str] = Field(default_factory=list)
    legal_identities: list[str] = Field(default_factory=list)
    self_concept: list[str] = Field(default_factory=list)
    perceived_identities: dict[str, list[str]] = Field(default_factory=dict)
    hidden_identities: list[str] = Field(default_factory=list)
    default_visibility: DossierVisibilityPolicy = Field(default_factory=DossierVisibilityPolicy)


class BodySchema(StrictDossierModel):
    body_type: str | None = None
    height_band: str | None = None
    dominant_hand: str | None = None
    permanent_limitations: list[str] = Field(default_factory=list)


class SensoryBaseline(StrictDossierModel):
    vision: str | None = None
    hearing: str | None = None


class MotorBaseline(StrictDossierModel):
    sprint_capacity: str | None = None
    fine_motor_control: str | None = None
    load_bearing: str | None = None


class VoiceBaseline(StrictDossierModel):
    volume: str | None = None
    tone: str | None = None


class EmbodimentProfile(StrictDossierModel):
    body_schema: BodySchema = Field(default_factory=BodySchema)
    sensory_baseline: SensoryBaseline = Field(default_factory=SensoryBaseline)
    motor_baseline: MotorBaseline = Field(default_factory=MotorBaseline)
    chronic_conditions: list[str] = Field(default_factory=list)
    voice_baseline: VoiceBaseline = Field(default_factory=VoiceBaseline)
    visual_markers: list[str] = Field(default_factory=list)
    default_posture: str | None = None
    realization_hints: dict[str, list[str]] = Field(default_factory=dict)
    default_visibility: DossierVisibilityPolicy = Field(default_factory=DossierVisibilityPolicy)


class AuthorityProfile(StrictDossierModel):
    responsibilities: list[str] = Field(default_factory=list)
    allowed_actions: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    escalation_targets: list[str] = Field(default_factory=list)
    default_visibility: DossierVisibilityPolicy = Field(default_factory=DossierVisibilityPolicy)


class PrivateTruth(StrictDossierModel):
    truth_id: str
    content: str
    known_by: list[str] = Field(default_factory=list)
    unknown_to: list[str] = Field(default_factory=list)
    disclosure_threshold: dict[str, object] = Field(default_factory=dict)
    allowed_projection: dict[str, DossierVisibilityValue] = Field(default_factory=dict)


class PrivateTruthProfile(StrictDossierModel):
    secrets: list[PrivateTruth] = Field(default_factory=list)
    default_visibility: DossierVisibilityPolicy = Field(default_factory=DossierVisibilityPolicy)


class RelationshipEvidenceSeed(StrictDossierModel):
    event_id: str
    summary: str
    effect: dict[str, float] = Field(default_factory=dict)


class RelationshipSeed(StrictDossierModel):
    target_actor_id: str
    relation_tags: list[str] = Field(default_factory=list)
    initial_trust: float = DossierScalar
    initial_affinity: float = DossierScalar
    initial_obligation: float = DossierScalar
    initial_tension: float = DossierScalar
    evidence_seeds: list[RelationshipEvidenceSeed] = Field(default_factory=list)


class RelationshipSeedProfile(StrictDossierModel):
    relationships: list[RelationshipSeed] = Field(default_factory=list)
    default_visibility: DossierVisibilityPolicy = Field(default_factory=DossierVisibilityPolicy)


class SkillSeedSupport(StrictDossierModel):
    action_family: str


class SkillSeedRequirement(StrictDossierModel):
    condition: str


class CapabilitySeed(StrictDossierModel):
    skill_id: str
    source: str = "authored"
    rank: str = ""
    proficiency: float = DossierScalar
    confidence: float = DossierScalar
    supports: list[SkillSeedSupport] = Field(default_factory=list)
    requires: list[SkillSeedRequirement] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)


class CapabilitySeedProfile(StrictDossierModel):
    skill_seeds: list[CapabilitySeed] = Field(default_factory=list)
    knowledge_domains: list[str] = Field(default_factory=list)
    constraints: dict[str, list[str]] = Field(default_factory=dict)
    default_visibility: DossierVisibilityPolicy = Field(default_factory=DossierVisibilityPolicy)


class CharacterDossier(StrictDossierModel):
    dossier_id: str
    actor_id: str
    schema_version: Literal["character_dossier.v1"] = "character_dossier.v1"
    dossier_metadata: DossierMetadata = Field(default_factory=DossierMetadata)
    identity_profile: IdentityProfile = Field(default_factory=IdentityProfile)
    embodiment_profile: EmbodimentProfile = Field(default_factory=EmbodimentProfile)
    origin_profile: dict[str, object] | None = None
    life_history_profile: dict[str, object] | None = None
    value_profile: dict[str, object] | None = None
    personality_profile: dict[str, object] | None = None
    need_profile: dict[str, object] | None = None
    expression_profile: dict[str, object] | None = None
    relationship_seed_profile: RelationshipSeedProfile = Field(
        default_factory=RelationshipSeedProfile
    )
    capability_seed_profile: CapabilitySeedProfile = Field(default_factory=CapabilitySeedProfile)
    authority_profile: AuthorityProfile = Field(default_factory=AuthorityProfile)
    private_truth_profile: PrivateTruthProfile = Field(default_factory=PrivateTruthProfile)
    character_profile: CharacterProfile

    @model_validator(mode="after")
    def validate_actor_consistency(self) -> CharacterDossier:
        profile_actor_id = self.character_profile.identity_core.character_id
        if self.actor_id != profile_actor_id:
            raise ValueError(
                "actor_id must match character_profile.identity_core.character_id"
            )
        if self.identity_profile.actor_id and self.identity_profile.actor_id != self.actor_id:
            raise ValueError("identity_profile.actor_id must match actor_id")
        return self


__all__ = [
    "AuthorityProfile",
    "CapabilitySeedProfile",
    "CharacterDossier",
    "DemographicIdentity",
    "DossierLayerMetadata",
    "DossierMetadata",
    "DossierVisibilityPolicy",
    "EmbodimentProfile",
    "IdentityProfile",
    "PrivateTruthProfile",
    "RelationshipSeedProfile",
    "RoleIdentities",
    "AffiliationIdentities",
    "SocialIdentities",
]
