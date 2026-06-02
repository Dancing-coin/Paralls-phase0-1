from app.models.runtime_state import CharacterRuntimeStateDelta, CharacterRuntimeStateSnapshot, ConversationCandidateEvent


class CharacterRuntimeStateService:
    MIRROR_VISUAL_FACT_DEDUP_WINDOW_MS = 160

    def __init__(self) -> None:
        self._state: dict[str, CharacterRuntimeStateSnapshot] = {}

    def get_snapshot(self, actor_id: str) -> CharacterRuntimeStateSnapshot | None:
        return self._state.get(actor_id)

    def get_or_create_snapshot(
        self,
        *,
        actor_id: str,
        room_id: str,
        scene_id: str,
        zone_id: str,
        producer_ts: int,
    ) -> CharacterRuntimeStateSnapshot:
        existing = self._state.get(actor_id)
        if existing is not None:
            return existing

        snapshot = CharacterRuntimeStateSnapshot(
            actor_id=actor_id,
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            revision_seq=1,
            producer_ts=producer_ts,
            updated_at=producer_ts,
        )
        self._state[actor_id] = snapshot
        return snapshot

    def apply_focus_state(
        self,
        *,
        actor_id: str,
        room_id: str,
        scene_id: str,
        zone_id: str,
        producer_ts: int,
        target_actor_id: str | None,
        target_object_id: str | None,
    ) -> CharacterRuntimeStateDelta | None:
        snapshot = self.get_or_create_snapshot(
            actor_id=actor_id,
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            producer_ts=producer_ts,
        )
        next_focus_target = target_actor_id or target_object_id or None
        next_attention_source = "focus_state"
        next_nearby_actor_refs = [target_actor_id] if target_actor_id else []
        next_nearby_object_refs = [target_object_id] if target_object_id else []
        if (
            snapshot.current_focus_target == next_focus_target
            and snapshot.current_attention_source == next_attention_source
            and snapshot.nearby_actor_refs == next_nearby_actor_refs
            and snapshot.nearby_object_refs == next_nearby_object_refs
        ):
            return None

        snapshot.revision_seq += 1
        snapshot.current_focus_target = next_focus_target
        snapshot.current_attention_source = next_attention_source
        snapshot.nearby_actor_refs = next_nearby_actor_refs
        snapshot.nearby_object_refs = next_nearby_object_refs
        snapshot.updated_at = producer_ts
        return CharacterRuntimeStateDelta(
            actor_id=actor_id,
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            revision_seq=snapshot.revision_seq,
            producer_ts=producer_ts,
            changed_fields=[
                "current_focus_target",
                "current_attention_source",
                "nearby_actor_refs",
                "nearby_object_refs",
            ],
            current_focus_target=snapshot.current_focus_target,
            current_attention_source=snapshot.current_attention_source,
            nearby_actor_refs=list(snapshot.nearby_actor_refs),
            nearby_object_refs=list(snapshot.nearby_object_refs),
            updated_at=producer_ts,
        )

    def apply_runtime_projection(
        self,
        *,
        actor_id: str,
        room_id: str,
        scene_id: str,
        zone_id: str,
        producer_ts: int,
        current_focus_target: str | None,
        current_attention_source: str,
        nearby_actor_refs: list[str],
        nearby_object_refs: list[str],
        nearby_environment_refs: list[str] | None = None,
        conversation_candidate_refs: list[str] | None = None,
        engagement_pressure: str | None = None,
        privacy_risk_hint: str | None = None,
    ) -> CharacterRuntimeStateDelta | None:
        snapshot = self.get_or_create_snapshot(
            actor_id=actor_id,
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            producer_ts=producer_ts,
        )
        next_focus_target = current_focus_target or None
        next_nearby_environment_refs = list(nearby_environment_refs or [])
        next_conversation_candidate_refs = list(conversation_candidate_refs or [])
        next_engagement_pressure = engagement_pressure if engagement_pressure not in {None, ""} else None
        next_privacy_risk_hint = privacy_risk_hint if privacy_risk_hint not in {None, ""} else None
        if (
            snapshot.current_focus_target == next_focus_target
            and snapshot.current_attention_source == current_attention_source
            and snapshot.nearby_actor_refs == nearby_actor_refs
            and snapshot.nearby_object_refs == nearby_object_refs
            and snapshot.nearby_environment_refs == next_nearby_environment_refs
            and snapshot.conversation_candidate_refs == next_conversation_candidate_refs
            and snapshot.engagement_pressure == next_engagement_pressure
            and snapshot.privacy_risk_hint == next_privacy_risk_hint
        ):
            return None

        changed_fields: list[str] = []
        if snapshot.current_focus_target != next_focus_target:
            changed_fields.append("current_focus_target")
        if snapshot.current_attention_source != current_attention_source:
            changed_fields.append("current_attention_source")
        if snapshot.nearby_actor_refs != nearby_actor_refs:
            changed_fields.append("nearby_actor_refs")
        if snapshot.nearby_object_refs != nearby_object_refs:
            changed_fields.append("nearby_object_refs")
        if snapshot.nearby_environment_refs != next_nearby_environment_refs:
            changed_fields.append("nearby_environment_refs")
        if snapshot.conversation_candidate_refs != next_conversation_candidate_refs:
            changed_fields.append("conversation_candidate_refs")
        if snapshot.engagement_pressure != next_engagement_pressure:
            changed_fields.append("engagement_pressure")
        if snapshot.privacy_risk_hint != next_privacy_risk_hint:
            changed_fields.append("privacy_risk_hint")

        snapshot.revision_seq += 1
        snapshot.current_focus_target = next_focus_target
        snapshot.current_attention_source = current_attention_source
        snapshot.nearby_actor_refs = list(nearby_actor_refs)
        snapshot.nearby_object_refs = list(nearby_object_refs)
        snapshot.nearby_environment_refs = next_nearby_environment_refs
        snapshot.conversation_candidate_refs = next_conversation_candidate_refs
        snapshot.engagement_pressure = next_engagement_pressure
        snapshot.privacy_risk_hint = next_privacy_risk_hint
        snapshot.updated_at = producer_ts
        return CharacterRuntimeStateDelta(
            actor_id=actor_id,
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            revision_seq=snapshot.revision_seq,
            producer_ts=producer_ts,
            changed_fields=changed_fields,
            current_focus_target=snapshot.current_focus_target,
            current_attention_source=snapshot.current_attention_source,
            nearby_actor_refs=list(snapshot.nearby_actor_refs),
            nearby_object_refs=list(snapshot.nearby_object_refs),
            nearby_environment_refs=list(snapshot.nearby_environment_refs),
            conversation_candidate_refs=list(snapshot.conversation_candidate_refs),
            engagement_pressure=snapshot.engagement_pressure,
            privacy_risk_hint=snapshot.privacy_risk_hint,
            updated_at=producer_ts,
        )

    def apply_visual_fact(
        self,
        *,
        actor_id: str,
        room_id: str,
        scene_id: str,
        zone_id: str,
        producer_ts: int,
        target_actor_id: str | None,
        target_object_id: str | None,
        relation_type: str,
    ) -> CharacterRuntimeStateDelta | None:
        snapshot = self.get_or_create_snapshot(
            actor_id=actor_id,
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            producer_ts=producer_ts,
        )
        if self._should_suppress_mirrored_visual_fact(
            snapshot=snapshot,
            producer_ts=producer_ts,
            relation_type=relation_type,
            target_actor_id=target_actor_id,
            target_object_id=target_object_id,
        ):
            return None

        next_focus_target = target_actor_id or target_object_id or None
        next_attention_source = "visual_fact"
        next_nearby_actor_refs = [target_actor_id] if target_actor_id else []
        next_nearby_object_refs = [target_object_id] if target_object_id else []
        if (
            snapshot.current_focus_target == next_focus_target
            and snapshot.current_attention_source == next_attention_source
            and snapshot.nearby_actor_refs == next_nearby_actor_refs
            and snapshot.nearby_object_refs == next_nearby_object_refs
        ):
            return None

        snapshot.revision_seq += 1
        snapshot.current_focus_target = next_focus_target
        snapshot.current_attention_source = next_attention_source
        snapshot.nearby_actor_refs = next_nearby_actor_refs
        snapshot.nearby_object_refs = next_nearby_object_refs
        snapshot.updated_at = producer_ts
        return CharacterRuntimeStateDelta(
            actor_id=actor_id,
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            revision_seq=snapshot.revision_seq,
            producer_ts=producer_ts,
            changed_fields=[
                "current_focus_target",
                "current_attention_source",
                "nearby_actor_refs",
                "nearby_object_refs",
            ],
            current_focus_target=snapshot.current_focus_target,
            current_attention_source=snapshot.current_attention_source,
            nearby_actor_refs=list(snapshot.nearby_actor_refs),
            nearby_object_refs=list(snapshot.nearby_object_refs),
            updated_at=producer_ts,
        )

    def apply_conversation_candidate(self, candidate: ConversationCandidateEvent) -> CharacterRuntimeStateDelta | None:
        snapshot = self.get_or_create_snapshot(
            actor_id=candidate.actor_id,
            room_id=candidate.room_id,
            scene_id=candidate.scene_id,
            zone_id=candidate.zone_id,
            producer_ts=candidate.producer_ts,
        )
        next_conversation_candidate_refs = [self._build_candidate_ref(candidate)]
        next_nearby_actor_refs = list(candidate.candidate_actor_ids)
        next_nearby_object_refs = list(candidate.candidate_object_ids)
        next_nearby_environment_refs = list(candidate.candidate_environment_ids)
        next_engagement_pressure = candidate.engagement_pressure
        next_privacy_risk_hint = candidate.privacy_risk_hint
        if (
            snapshot.conversation_candidate_refs == next_conversation_candidate_refs
            and snapshot.nearby_actor_refs == next_nearby_actor_refs
            and snapshot.nearby_object_refs == next_nearby_object_refs
            and snapshot.nearby_environment_refs == next_nearby_environment_refs
            and snapshot.engagement_pressure == next_engagement_pressure
            and snapshot.privacy_risk_hint == next_privacy_risk_hint
        ):
            return None

        snapshot.revision_seq += 1
        snapshot.conversation_candidate_refs = next_conversation_candidate_refs
        snapshot.nearby_actor_refs = next_nearby_actor_refs
        snapshot.nearby_object_refs = next_nearby_object_refs
        snapshot.nearby_environment_refs = next_nearby_environment_refs
        snapshot.engagement_pressure = next_engagement_pressure
        snapshot.privacy_risk_hint = next_privacy_risk_hint
        snapshot.updated_at = candidate.producer_ts
        return CharacterRuntimeStateDelta(
            actor_id=candidate.actor_id,
            room_id=candidate.room_id,
            scene_id=candidate.scene_id,
            zone_id=candidate.zone_id,
            revision_seq=snapshot.revision_seq,
            producer_ts=candidate.producer_ts,
            changed_fields=[
                "conversation_candidate_refs",
                "nearby_actor_refs",
                "nearby_object_refs",
                "nearby_environment_refs",
                "engagement_pressure",
                "privacy_risk_hint",
            ],
            nearby_actor_refs=list(snapshot.nearby_actor_refs),
            nearby_object_refs=list(snapshot.nearby_object_refs),
            nearby_environment_refs=list(snapshot.nearby_environment_refs),
            conversation_candidate_refs=list(snapshot.conversation_candidate_refs),
            engagement_pressure=snapshot.engagement_pressure,
            privacy_risk_hint=snapshot.privacy_risk_hint,
            updated_at=candidate.producer_ts,
        )

    def _build_candidate_ref(self, candidate: ConversationCandidateEvent) -> str:
        parts = ["cand"]
        if candidate.candidate_actor_ids:
            parts.append(candidate.candidate_actor_ids[0])
        if candidate.candidate_object_ids:
            parts.append(candidate.candidate_object_ids[0])
        if candidate.candidate_environment_ids:
            parts.append(candidate.candidate_environment_ids[0])
        return "_".join(parts)

    def _should_suppress_mirrored_visual_fact(
        self,
        *,
        snapshot: CharacterRuntimeStateSnapshot,
        producer_ts: int,
        relation_type: str,
        target_actor_id: str | None,
        target_object_id: str | None,
    ) -> bool:
        if relation_type not in {"actor_looks_at_actor", "actor_looks_at_object"}:
            return False
        if snapshot.current_attention_source != "focus_state":
            return False
        visual_target = target_actor_id or target_object_id or None
        if visual_target is None or snapshot.current_focus_target != visual_target:
            return False
        return abs(snapshot.updated_at - producer_ts) <= self.MIRROR_VISUAL_FACT_DEDUP_WINDOW_MS
