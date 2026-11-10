"""基于会话接入维护司命的有限阶知识状态。"""

from app.models.siming_knowledge_graph import (
    AccessResolution,
    AwarenessLevel,
    AwarenessRelation,
    AwarenessResolution,
    Conversation,
    ConversationBoundaryChange,
    InformationItem,
    KnowledgeClaim,
    KnowledgeResolution,
    MembershipResolution,
    MembershipState,
    PerceptionAccess,
    PrivacyRiskResolution,
)


class SimingKnowledgeGraph:
    """司命高阶知识图谱（v0.1，会话作用域内存态）。"""

    def __init__(self) -> None:
        self._conversations: dict[str, Conversation] = {}
        self._information_items: dict[str, InformationItem] = {}
        self._access_history: dict[tuple[str, str], list[PerceptionAccess]] = {}
        self._latest_access: dict[tuple[str, str], PerceptionAccess] = {}
        self._membership_states: dict[tuple[str, str], MembershipState] = {}
        self._knowledge_claims: dict[tuple[str, str], KnowledgeClaim] = {}
        self._higher_order_claims: dict[tuple[str, str, str], KnowledgeClaim] = {}
        self._awareness_relations: dict[tuple[str, str, str], AwarenessRelation] = {}

    def create_conversation(
        self,
        conversation_id: str,
        room_id: str,
        scene_id: str,
        started_at: int,
        boundary_type: str = "public",
    ) -> Conversation:
        conversation = Conversation(
            conversation_id=conversation_id,
            room_id=room_id,
            scene_id=scene_id,
            started_at=started_at,
            boundary_type=boundary_type,
        )
        if conversation_id in self._conversations:
            raise ValueError(f"conversation already exists: {conversation_id}")
        self._conversations[conversation_id] = conversation
        return conversation.model_copy(deep=True)

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        conversation = self._conversations.get(conversation_id)
        return None if conversation is None else conversation.model_copy(deep=True)

    def end_conversation(self, conversation_id: str, ended_at: int) -> None:
        conversation = self._require_conversation(conversation_id)
        if ended_at < conversation.started_at:
            raise ValueError("conversation cannot end before it starts")
        if conversation.ended_at is not None and ended_at != conversation.ended_at:
            raise ValueError("conversation end time is immutable")
        self._conversations[conversation_id] = conversation.model_copy(update={"ended_at": ended_at})

    def change_boundary(
        self, conversation_id: str, new_boundary: str, changed_at: int, trigger_reason: str = ""
    ) -> ConversationBoundaryChange:
        conversation = self._require_active_conversation(conversation_id, changed_at)
        change = ConversationBoundaryChange(
            conversation_id=conversation_id,
            old_boundary=conversation.boundary_type,
            new_boundary=new_boundary,
            changed_at=changed_at,
            trigger_reason=trigger_reason,
        )
        self._conversations[conversation_id] = conversation.model_copy(
            update={"boundary_type": new_boundary}
        )
        return change

    def evaluate_access(
        self,
        actor_id: str,
        conversation_id: str,
        current_tick: int,
        spatial_proximity: float = 1.0,
        acoustic_clarity: float = 1.0,
    ) -> AccessResolution:
        conversation = self._require_active_conversation(conversation_id, current_tick)
        if not actor_id:
            raise ValueError("actor_id must not be empty")
        self._validate_score(spatial_proximity, "spatial_proximity")
        self._validate_score(acoustic_clarity, "acoustic_clarity")
        if spatial_proximity >= 0.8 and acoustic_clarity >= 0.8:
            quality = "full"
        elif spatial_proximity >= 0.5 and acoustic_clarity >= 0.5:
            quality = "partial"
        elif spatial_proximity >= 0.3 or acoustic_clarity >= 0.3:
            quality = "minimal"
        else:
            quality = "none"

        access = PerceptionAccess(
            access_id=f"access:{actor_id}:{conversation_id}:{current_tick}",
            actor_id=actor_id,
            target_conversation_id=conversation_id,
            access_quality=quality,
            access_started_at=current_tick,
        )
        self._access_history.setdefault((actor_id, conversation_id), []).append(access)
        self._latest_access[(actor_id, conversation_id)] = access
        return AccessResolution(
            actor_id=actor_id,
            conversation_id=conversation_id,
            access_quality=quality,
            access_started_at=current_tick,
            reason=f"spatial={spatial_proximity:.2f}, acoustic={acoustic_clarity:.2f}",
        )

    def evaluate_awareness(
        self, observer_id: str, observed_id: str, conversation_id: str, current_tick: int
    ) -> AwarenessResolution:
        self._require_active_conversation(conversation_id, current_tick)
        observer_access = self._access_at(observer_id, conversation_id, current_tick)
        observed_access = self._access_at(observed_id, conversation_id, current_tick)
        if (observer_access is None or observer_access.access_quality == "none"
                or observed_access is None or observed_access.access_quality == "none"):
            level: AwarenessLevel = "unaware"
        elif (observer_access.access_quality in ("full", "partial")
              and observed_access.access_quality in ("full", "partial")):
            level = "aware_mutual"
        else:
            level = "aware_present"
        self._awareness_relations[(observer_id, observed_id, conversation_id)] = AwarenessRelation(
            observer_id=observer_id,
            observed_id=observed_id,
            conversation_id=conversation_id,
            awareness_level=level,
            updated_at=current_tick,
        )
        return AwarenessResolution(
            observer_id=observer_id,
            observed_id=observed_id,
            conversation_id=conversation_id,
            awareness_level=level,
            updated_at=current_tick,
        )

    def evaluate_membership(
        self,
        actor_id: str,
        conversation_id: str,
        current_tick: int,
        has_spoken: bool = False,
        explicitly_excluded: bool = False,
    ) -> MembershipResolution:
        conversation = self._require_active_conversation(conversation_id, current_tick)
        access = self._access_at(actor_id, conversation_id, current_tick)
        if explicitly_excluded:
            membership_type, reason = "excluded", "explicitly_excluded"
        elif access is None:
            membership_type, reason = "listener", "no_access_record"
        elif access.access_quality in ("none", "minimal"):
            membership_type, reason = "listener", f"access_quality={access.access_quality}"
        elif has_spoken:
            membership_type, reason = "active_member", "has_spoken"
        elif access.access_quality == "full" and self._is_known_by_member(actor_id, conversation_id):
            membership_type, reason = "silent_member", "known_by_member"
        else:
            membership_type, reason = "candidate", f"access_quality={access.access_quality}"

        joined_at = current_tick if membership_type in ("candidate", "silent_member", "active_member") else None
        previous = self._membership_states.get((actor_id, conversation_id))
        if joined_at is not None and previous is not None and previous.joined_at is not None:
            joined_at = previous.joined_at
        state = MembershipState(
            actor_id=actor_id,
            conversation_id=conversation_id,
            membership_type=membership_type,
            joined_at=joined_at,
        )
        self._membership_states[(actor_id, conversation_id)] = state
        members = set(conversation.participant_ids)
        listeners = set(conversation.listener_ids)
        if membership_type in ("candidate", "silent_member", "active_member"):
            members.add(actor_id)
            listeners.discard(actor_id)
        elif membership_type == "listener":
            listeners.add(actor_id)
            members.discard(actor_id)
        else:
            members.discard(actor_id)
            listeners.discard(actor_id)
        self._conversations[conversation_id] = conversation.model_copy(
            update={"participant_ids": sorted(members), "listener_ids": sorted(listeners)}
        )
        return MembershipResolution(
            actor_id=actor_id,
            conversation_id=conversation_id,
            membership_type=membership_type,
            joined_at=joined_at,
            reason=reason,
        )

    def register_information(
        self,
        info_id: str,
        content_type: str,
        source_actor_id: str | None,
        revealed_at: int,
        conversation_id: str | None = None,
        visibility_scope: str = "public",
    ) -> InformationItem:
        if conversation_id is not None:
            self._require_active_conversation(conversation_id, revealed_at)
        item = InformationItem(
            info_id=info_id,
            content_type=content_type,
            source_actor_id=source_actor_id,
            revealed_at=revealed_at,
            conversation_id=conversation_id,
            visibility_scope=visibility_scope,
        )
        existing = self._information_items.get(info_id)
        if existing is not None and existing != item:
            raise ValueError(f"information item already exists: {info_id}")
        self._information_items[info_id] = item
        return item.model_copy(deep=True)

    def evaluate_knowledge(
        self,
        actor_id: str,
        info_id: str,
        current_tick: int,
        source_conversation_id: str | None = None,
    ) -> KnowledgeResolution:
        if current_tick < 0:
            raise ValueError("current_tick must be non-negative")
        info = self._information_items.get(info_id)
        previous = self._knowledge_claims.get((actor_id, info_id))
        if previous is not None and previous.knowledge_state == "known" and current_tick >= previous.acquired_at:
            return KnowledgeResolution(**previous.model_dump())
        state, source = "unknown", None
        if info is not None and current_tick >= info.revealed_at:
            source_conversation_id = source_conversation_id or info.conversation_id
            if actor_id == info.source_actor_id:
                state, source = "known", "direct_observation"
            elif info.visibility_scope == "private":
                pass
            elif source_conversation_id is not None:
                self._require_conversation(source_conversation_id)
                access = self._access_at(actor_id, source_conversation_id, info.revealed_at)
                if info.conversation_id == source_conversation_id and access is not None:
                    if access.access_quality == "minimal":
                        state, source = "suspected", "eavesdrop"
                    elif access.access_quality in ("full", "partial"):
                        membership = self._membership_states.get((actor_id, source_conversation_id))
                        if membership is not None and membership.membership_type == "listener":
                            state, source = "known", "eavesdrop"
                        else:
                            state, source = "known", "conversation"
            elif info.visibility_scope == "public" or actor_id == info.source_actor_id:
                state, source = "known", "direct_observation"

        claim = KnowledgeClaim(
            actor_id=actor_id,
            info_id=info_id,
            knowledge_state=state,
            acquired_at=current_tick if state != "unknown" else None,
            source_type=source,
        )
        if (previous is not None and previous.knowledge_state == "suspected" and state == "unknown"
                and current_tick >= previous.acquired_at):
            return KnowledgeResolution(**previous.model_dump())
        if previous is None or previous.acquired_at is None or current_tick >= previous.acquired_at:
            self._knowledge_claims[(actor_id, info_id)] = claim
        return KnowledgeResolution(
            actor_id=actor_id,
            info_id=info_id,
            knowledge_state=state,
            source_type=source,
            acquired_at=claim.acquired_at,
        )

    def evaluate_privacy_risk(self, actor_id: str, conversation_id: str) -> PrivacyRiskResolution:
        conversation = self._require_conversation(conversation_id)
        eavesdroppers = sorted(
            member.actor_id
            for member in self._membership_states.values()
            if member.conversation_id == conversation_id
            and member.actor_id != actor_id
            and member.membership_type == "listener"
            and (access := self._latest_access.get((member.actor_id, conversation_id))) is not None
            and access.access_quality != "none"
        )
        count = len(eavesdroppers) if conversation.boundary_type != "public" else 0
        level = "critical" if count >= 3 else "high" if count == 2 else "medium" if count else "none"
        return PrivacyRiskResolution(
            actor_id=actor_id,
            conversation_id=conversation_id,
            risk_level=level,
            risk_factors=[f"eavesdropper_count={count}"],
            eavesdropper_ids=eavesdroppers if count else [],
        )

    def evaluate_higher_order_knowledge(
        self, observer_id: str, known_by_actor_id: str, info_id: str, current_tick: int
    ) -> KnowledgeResolution:
        if current_tick < 0:
            raise ValueError("current_tick must be non-negative")
        info = self._information_items.get(info_id)
        known_claim = self._knowledge_claims.get((observer_id, info_id))
        subject_claim = self._knowledge_claims.get((known_by_actor_id, info_id))
        claim_key = (observer_id, known_by_actor_id, info_id)
        previous = self._higher_order_claims.get(claim_key)
        if (previous is not None and previous.knowledge_state == "known"
                and current_tick >= previous.acquired_at):
            return KnowledgeResolution(**previous.model_dump())

        proven = (
            info is not None
            and current_tick >= info.revealed_at
            and observer_id != known_by_actor_id
            and known_claim is not None
            and known_claim.knowledge_state == "known"
            and known_claim.acquired_at <= current_tick
            and subject_claim is not None
            and subject_claim.knowledge_state == "known"
            and subject_claim.acquired_at <= current_tick
            and info.conversation_id is not None
            and (access := self._access_at(observer_id, info.conversation_id, info.revealed_at)) is not None
            and access.access_quality in ("full", "partial")
            and (subject_access := self._access_at(known_by_actor_id, info.conversation_id, info.revealed_at)) is not None
            and subject_access.access_quality in ("full", "partial")
            and (awareness := self._awareness_relations.get(
                (observer_id, known_by_actor_id, info.conversation_id)
            )) is not None
            and awareness.updated_at <= info.revealed_at
            and awareness.awareness_level in ("aware_present", "aware_mutual")
        )
        claim = KnowledgeClaim(
            actor_id=observer_id,
            known_by_actor_id=known_by_actor_id,
            info_id=info_id,
            knowledge_state="known" if proven else "unknown",
            acquired_at=current_tick if proven else None,
            source_type="inference" if proven else None,
        )
        if proven or previous is None:
            self._higher_order_claims[claim_key] = claim
        return KnowledgeResolution(**claim.model_dump())

    def who_knows_knows(self, info_id: str, known_by_actor_id: str) -> list[str]:
        return sorted(
            observer_id
            for (observer_id, subject_id, claimed_info), claim in self._higher_order_claims.items()
            if subject_id == known_by_actor_id
            and claimed_info == info_id
            and claim.knowledge_state == "known"
        )

    def who_knows(self, info_id: str) -> list[str]:
        return sorted(
            actor_id
            for (actor_id, claimed_info), claim in self._knowledge_claims.items()
            if claimed_info == info_id and claim.knowledge_state == "known"
        )

    def fairness_observations(self, actor_id: str, current_tick: int) -> tuple[int, int, list[str], int]:
        """Return known information, participation, access qualities and known evidence."""
        claims = [claim for (actor, _), claim in self._knowledge_claims.items()
                  if actor == actor_id and claim.knowledge_state == "known"
                  and claim.acquired_at is not None and claim.acquired_at <= current_tick]
        participation = sum(1 for (actor, _), membership in self._membership_states.items()
                            if actor == actor_id and membership.membership_type in ("active_member", "silent_member")
                            and membership.joined_at is not None and membership.joined_at <= current_tick)
        access = [record.access_quality for (actor, conversation), _ in self._access_history.items()
                  if actor == actor_id and (record := self._access_at(actor, conversation, current_tick)) is not None]
        evidence = sum(1 for claim in claims if self._information_items[claim.info_id].content_type == "evidence")
        return len(claims), participation, access, evidence

    def active_conversations(self, current_tick: int) -> list[Conversation]:
        return [conversation.model_copy(deep=True) for conversation in self._conversations.values()
                if conversation.started_at <= current_tick and (conversation.ended_at is None or current_tick <= conversation.ended_at)]

    def awareness_at(self, observer_id: str, observed_id: str, conversation_id: str, current_tick: int) -> AwarenessLevel:
        relation = self._awareness_relations.get((observer_id, observed_id, conversation_id))
        return relation.awareness_level if relation and relation.updated_at <= current_tick else "unaware"

    def has_secret(self, conversation_id: str, current_tick: int) -> bool:
        return any(item.conversation_id == conversation_id and item.content_type == "secret" and item.revealed_at <= current_tick for item in self._information_items.values())

    def who_is_in_conversation(self, conversation_id: str) -> list[str]:
        return sorted(
            actor_id
            for (actor_id, conv_id), member in self._membership_states.items()
            if conv_id == conversation_id
            and member.membership_type in ("candidate", "silent_member", "active_member")
        )

    def who_is_listening(self, conversation_id: str) -> list[str]:
        return sorted(
            actor_id
            for (actor_id, conv_id), member in self._membership_states.items()
            if conv_id == conversation_id and member.membership_type == "listener"
        )

    def _is_known_by_member(self, actor_id: str, conversation_id: str) -> bool:
        return any(
            relation.conversation_id == conversation_id
            and relation.observed_id == actor_id
            and relation.awareness_level in ("aware_present", "aware_mutual")
            and (membership := self._membership_states.get((relation.observer_id, conversation_id))) is not None
            and membership.membership_type in ("active_member", "silent_member")
            for relation in self._awareness_relations.values()
        )

    def _require_conversation(self, conversation_id: str) -> Conversation:
        conversation = self._conversations.get(conversation_id)
        if conversation is None:
            raise KeyError(f"unknown conversation: {conversation_id}")
        return conversation

    def _access_at(self, actor_id: str, conversation_id: str, at: int) -> PerceptionAccess | None:
        return max(
            (access for access in self._access_history.get((actor_id, conversation_id), [])
             if access.access_started_at <= at),
            key=lambda access: access.access_started_at,
            default=None,
        )

    def _require_active_conversation(self, conversation_id: str, at: int) -> Conversation:
        conversation = self._require_conversation(conversation_id)
        if at < conversation.started_at or (conversation.ended_at is not None and at > conversation.ended_at):
            raise ValueError("time is outside the active conversation interval")
        return conversation

    @staticmethod
    def _validate_score(score: float, name: str) -> None:
        if not isinstance(score, (int, float)) or not 0 <= score <= 1:
            raise ValueError(f"{name} must be between 0 and 1")


__all__ = ["SimingKnowledgeGraph"]
