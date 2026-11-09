"""司命高阶知识图谱的 v0.1 会话与知识状态模型。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


BoundaryType = Literal["public", "semi_private", "private"]
AccessQuality = Literal["full", "partial", "minimal", "none"]
MembershipType = Literal["candidate", "silent_member", "active_member", "excluded", "listener"]
KnowledgeState = Literal["known", "suspected", "misunderstood", "forgotten", "unknown"]
KnowledgeSource = Literal["direct_observation", "conversation", "eavesdrop", "inference", "told_by_other"]
AwarenessLevel = Literal["unaware", "aware_present", "aware_mutual"]


class KnowledgeGraphModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Conversation(KnowledgeGraphModel):
    conversation_id: str = Field(min_length=1)
    room_id: str = Field(min_length=1)
    scene_id: str = Field(min_length=1)
    started_at: int = Field(ge=0)
    ended_at: int | None = Field(default=None, ge=0)
    boundary_type: BoundaryType = "public"
    participant_ids: list[str] = Field(default_factory=list)
    listener_ids: list[str] = Field(default_factory=list)


class InformationItem(KnowledgeGraphModel):
    info_id: str = Field(min_length=1)
    content_type: Literal["statement", "action", "evidence", "secret"]
    source_actor_id: str | None = None
    revealed_at: int = Field(ge=0)
    conversation_id: str | None = None
    visibility_scope: Literal["public", "conversation", "private"] = "public"


class PerceptionAccess(KnowledgeGraphModel):
    access_id: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    target_conversation_id: str | None = None
    target_info_id: str | None = None
    access_quality: AccessQuality = "none"
    access_started_at: int = Field(ge=0)
    access_ended_at: int | None = Field(default=None, ge=0)


class MembershipState(KnowledgeGraphModel):
    actor_id: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    membership_type: MembershipType
    joined_at: int | None = Field(default=None, ge=0)
    left_at: int | None = Field(default=None, ge=0)


class KnowledgeClaim(KnowledgeGraphModel):
    actor_id: str = Field(min_length=1)
    info_id: str = Field(min_length=1)
    knowledge_state: KnowledgeState = "unknown"
    acquired_at: int | None = Field(default=None, ge=0)
    source_type: KnowledgeSource | None = None


class AwarenessRelation(KnowledgeGraphModel):
    observer_id: str = Field(min_length=1)
    observed_id: str = Field(min_length=1)
    conversation_id: str = Field(min_length=1)
    awareness_level: AwarenessLevel = "unaware"
    updated_at: int = Field(ge=0)


class MembershipResolution(KnowledgeGraphModel):
    actor_id: str
    conversation_id: str
    membership_type: MembershipType
    joined_at: int | None = None
    reason: str = ""


class AccessResolution(KnowledgeGraphModel):
    actor_id: str
    conversation_id: str
    access_quality: AccessQuality
    access_started_at: int = Field(ge=0)
    reason: str = ""


class KnowledgeResolution(KnowledgeGraphModel):
    actor_id: str
    info_id: str
    knowledge_state: KnowledgeState
    source_type: KnowledgeSource | None = None
    acquired_at: int | None = None


class AwarenessResolution(KnowledgeGraphModel):
    observer_id: str
    observed_id: str
    conversation_id: str
    awareness_level: AwarenessLevel
    updated_at: int = Field(ge=0)


class PrivacyRiskResolution(KnowledgeGraphModel):
    actor_id: str
    conversation_id: str
    risk_level: Literal["none", "low", "medium", "high", "critical"] = "none"
    risk_factors: list[str] = Field(default_factory=list)
    eavesdropper_ids: list[str] = Field(default_factory=list)


class ConversationBoundaryChange(KnowledgeGraphModel):
    conversation_id: str
    old_boundary: BoundaryType
    new_boundary: BoundaryType
    changed_at: int = Field(ge=0)
    trigger_reason: str = ""


__all__ = [
    "AccessResolution", "AwarenessRelation", "AwarenessResolution", "Conversation",
    "ConversationBoundaryChange", "InformationItem", "KnowledgeClaim",
    "KnowledgeResolution", "MembershipResolution", "MembershipState",
    "PerceptionAccess", "PrivacyRiskResolution",
]
