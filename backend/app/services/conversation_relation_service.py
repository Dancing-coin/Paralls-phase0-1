from app.models.runtime_state import ConversationCandidateEvent
from app.models.visual_fact import VisualFactEvent


class ConversationRelationService:
    MIRROR_DEDUP_WINDOW_MS = 160
    CANDIDATE_DEDUP_WINDOW_MS = 900

    def __init__(self) -> None:
        self._relation_by_actor: dict[str, dict[str, str]] = {}
        self._last_emitted_candidate_by_actor: dict[str, tuple[str, int]] = {}

    def apply_focus_state(
        self,
        *,
        actor_id: str,
        room_id: str,
        scene_id: str,
        zone_id: str,
        target_actor_id: str,
        target_object_id: str,
        producer_ts: int,
    ) -> None:
        state = self._get_or_create_relation_state(actor_id, room_id, scene_id, zone_id)
        state["focus_target_actor_id"] = target_actor_id
        state["focus_target_object_id"] = target_object_id
        state["focus_producer_ts"] = str(producer_ts)

    def apply_world_result(
        self,
        *,
        actor_id: str,
        room_id: str,
        scene_id: str,
        zone_id: str,
        target_object_id: str,
        result_type: str,
        producer_ts: int,
    ) -> None:
        if result_type != "action_resolution_result":
            return

        state = self._get_or_create_relation_state(actor_id, room_id, scene_id, zone_id)
        state["world_target_object_id"] = target_object_id
        state["world_producer_ts"] = str(producer_ts)

    def apply_visual_fact(self, event: VisualFactEvent) -> None:
        state = self._get_or_create_relation_state(
            event.actor_id,
            event.room_id,
            event.scene_id,
            event.zone_id,
        )
        state["visual_fact_type"] = event.fact_type
        state["visual_relation_type"] = event.relation_type
        state["visual_target_actor_id"] = event.target_actor_id or ""
        state["visual_target_object_id"] = event.target_object_id or ""
        state["visual_target_environment_id"] = event.target_environment_id or ""
        state["visual_producer_ts"] = str(event.producer_ts)

    def build_candidate_event(
        self,
        *,
        actor_id: str,
        causation_id: str,
        correlation_id: str,
    ) -> ConversationCandidateEvent | None:
        relation = self._relation_by_actor.get(actor_id, {})
        if not relation:
            return None

        use_focus = causation_id.startswith("focus:")
        use_world = causation_id.startswith("world:")
        use_visual_fact = causation_id.startswith("visual_fact:")
        room_id = relation.get("room_id", "")
        scene_id = relation.get("scene_id", "")
        zone_id = relation.get("zone_id", "")
        if not room_id or not scene_id or not zone_id:
            return None

        candidate_actor_ids = []
        if use_focus and relation.get("focus_target_actor_id"):
            candidate_actor_ids = [relation["focus_target_actor_id"]]
        elif (
            use_visual_fact
            and relation.get("visual_relation_type") == "actor_looks_at_actor"
            and relation.get("visual_target_actor_id")
        ):
            if self._is_mirrored_focus_visual_fact(relation, "actor"):
                return None
            candidate_actor_ids = [relation["visual_target_actor_id"]]
        candidate_object_ids: list[str] = []
        candidate_environment_ids: list[str] = []
        if use_focus and relation.get("focus_target_object_id"):
            candidate_object_ids.append(relation["focus_target_object_id"])
        elif (
            use_visual_fact
            and relation.get("visual_relation_type") == "actor_looks_at_object"
            and relation.get("visual_target_object_id")
        ):
            if self._is_mirrored_focus_visual_fact(relation, "object"):
                return None
            candidate_object_ids.append(relation["visual_target_object_id"])
        elif (
            use_visual_fact
            and relation.get("visual_relation_type") == "actor_near_object"
            and relation.get("visual_target_object_id")
        ):
            candidate_object_ids.append(relation["visual_target_object_id"])
        elif (
            use_visual_fact
            and relation.get("visual_relation_type") == "environment_light_drop"
            and relation.get("visual_target_environment_id")
        ):
            candidate_environment_ids.append(relation["visual_target_environment_id"])
        if (
            relation.get("world_target_object_id")
            and relation["world_target_object_id"] not in candidate_object_ids
            and not candidate_environment_ids
        ):
            candidate_object_ids.append(relation["world_target_object_id"])

        if candidate_environment_ids:
            candidate_object_ids = []

        if not candidate_actor_ids and not candidate_object_ids and not candidate_environment_ids:
            return None

        engagement_pressure = "elevated" if candidate_actor_ids else "present"
        privacy_risk_hint = "low"
        producer_ts = self._resolve_candidate_ts(relation, use_focus, use_world, use_visual_fact)
        return ConversationCandidateEvent(
            actor_id=actor_id,
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            producer_ts=producer_ts,
            candidate_actor_ids=candidate_actor_ids,
            candidate_object_ids=candidate_object_ids,
            candidate_environment_ids=candidate_environment_ids,
            engagement_pressure=engagement_pressure,
            privacy_risk_hint=privacy_risk_hint,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )

    def should_emit_candidate(self, candidate: ConversationCandidateEvent) -> bool:
        signature = self._candidate_signature(candidate)
        previous = self._last_emitted_candidate_by_actor.get(candidate.actor_id)
        if previous is not None:
            previous_signature, previous_ts = previous
            if previous_signature == signature and abs(candidate.producer_ts - previous_ts) <= self.CANDIDATE_DEDUP_WINDOW_MS:
                return False
        self._last_emitted_candidate_by_actor[candidate.actor_id] = (signature, candidate.producer_ts)
        return True

    def apply_candidate_summary(self, candidate: ConversationCandidateEvent) -> None:
        state = self._get_or_create_relation_state(
            candidate.actor_id,
            candidate.room_id,
            candidate.scene_id,
            candidate.zone_id,
        )
        state["candidate_ref"] = self._build_candidate_ref(candidate)
        state["candidate_actor_ids"] = ",".join(candidate.candidate_actor_ids)
        state["candidate_object_ids"] = ",".join(candidate.candidate_object_ids)
        state["candidate_environment_ids"] = ",".join(candidate.candidate_environment_ids)
        state["candidate_engagement_pressure"] = candidate.engagement_pressure
        state["candidate_privacy_risk_hint"] = candidate.privacy_risk_hint
        state["candidate_producer_ts"] = str(candidate.producer_ts)

    def get_relation_snapshot(self, actor_id: str) -> dict[str, str] | None:
        relation = self._relation_by_actor.get(actor_id)
        if relation is None:
            return None
        return dict(relation)

    def project_runtime_state(self, actor_id: str) -> dict[str, object] | None:
        relation = self._relation_by_actor.get(actor_id)
        if relation is None:
            return None

        focus_ts = int(relation.get("focus_producer_ts", "0") or "0")
        visual_ts = int(relation.get("visual_producer_ts", "0") or "0")
        world_ts = int(relation.get("world_producer_ts", "0") or "0")
        visual_is_mirrored_actor = relation.get("visual_relation_type") == "actor_looks_at_actor" and self._is_mirrored_focus_visual_fact(relation, "actor")
        visual_is_mirrored_object = relation.get("visual_relation_type") == "actor_looks_at_object" and self._is_mirrored_focus_visual_fact(relation, "object")
        if visual_is_mirrored_actor or visual_is_mirrored_object:
            visual_ts = -1

        current_attention_source = ""
        current_focus_target = ""
        nearby_actor_refs: list[str] = []
        nearby_object_refs: list[str] = []
        nearby_environment_refs: list[str] = []

        if visual_ts >= focus_ts and visual_ts >= world_ts and visual_ts > 0:
            current_attention_source = "visual_fact"
            if relation.get("visual_target_actor_id"):
                current_focus_target = relation["visual_target_actor_id"]
                nearby_actor_refs = [relation["visual_target_actor_id"]]
            elif relation.get("visual_target_object_id"):
                current_focus_target = relation["visual_target_object_id"]
                nearby_object_refs = [relation["visual_target_object_id"]]
            elif relation.get("visual_target_environment_id"):
                current_focus_target = relation["visual_target_environment_id"]
                nearby_environment_refs = [relation["visual_target_environment_id"]]
        elif focus_ts >= world_ts and focus_ts > 0:
            current_attention_source = "focus_state"
            if relation.get("focus_target_actor_id"):
                current_focus_target = relation["focus_target_actor_id"]
                nearby_actor_refs = [relation["focus_target_actor_id"]]
            elif relation.get("focus_target_object_id"):
                current_focus_target = relation["focus_target_object_id"]
                nearby_object_refs = [relation["focus_target_object_id"]]
        elif world_ts > 0 and relation.get("world_target_object_id"):
            current_attention_source = "world_result"
            current_focus_target = relation["world_target_object_id"]
            nearby_object_refs = [relation["world_target_object_id"]]

        world_target_object_id = relation.get("world_target_object_id", "")
        if world_target_object_id != "" and world_target_object_id not in nearby_object_refs:
            nearby_object_refs.append(world_target_object_id)

        candidate_ts = int(relation.get("candidate_producer_ts", "0") or "0")
        candidate_refs: list[str] = []
        if relation.get("candidate_ref", "") != "":
            candidate_refs = [relation["candidate_ref"]]
        engagement_pressure = relation.get("candidate_engagement_pressure", "")
        privacy_risk_hint = relation.get("candidate_privacy_risk_hint", "")

        return {
            "actor_id": actor_id,
            "room_id": relation.get("room_id", ""),
            "scene_id": relation.get("scene_id", ""),
            "zone_id": relation.get("zone_id", ""),
            "current_focus_target": current_focus_target,
            "current_attention_source": current_attention_source,
            "nearby_actor_refs": nearby_actor_refs,
            "nearby_object_refs": nearby_object_refs,
            "nearby_environment_refs": nearby_environment_refs,
            "conversation_candidate_refs": candidate_refs,
            "engagement_pressure": engagement_pressure,
            "privacy_risk_hint": privacy_risk_hint,
            "producer_ts": max(focus_ts, visual_ts, world_ts, candidate_ts),
        }

    def _get_or_create_relation_state(self, actor_id: str, room_id: str, scene_id: str, zone_id: str) -> dict[str, str]:
        existing = self._relation_by_actor.get(actor_id)
        if existing is not None:
            existing["room_id"] = room_id
            existing["scene_id"] = scene_id
            existing["zone_id"] = zone_id
            return existing

        state = {
            "room_id": room_id,
            "scene_id": scene_id,
            "zone_id": zone_id,
            "focus_target_actor_id": "",
            "focus_target_object_id": "",
            "focus_producer_ts": "0",
            "world_target_object_id": "",
            "world_producer_ts": "0",
            "visual_fact_type": "",
            "visual_relation_type": "",
            "visual_target_actor_id": "",
            "visual_target_object_id": "",
            "visual_target_environment_id": "",
            "visual_producer_ts": "0",
            "candidate_ref": "",
            "candidate_actor_ids": "",
            "candidate_object_ids": "",
            "candidate_engagement_pressure": "",
            "candidate_privacy_risk_hint": "",
            "candidate_producer_ts": "0",
        }
        self._relation_by_actor[actor_id] = state
        return state

    def _is_mirrored_focus_visual_fact(self, relation: dict[str, str], target_kind: str) -> bool:
        focus_target = relation.get("focus_target_actor_id", "") if target_kind == "actor" else relation.get("focus_target_object_id", "")
        visual_target = relation.get("visual_target_actor_id", "") if target_kind == "actor" else relation.get("visual_target_object_id", "")
        if focus_target == "" or visual_target == "":
            return False
        if focus_target != visual_target:
            return False
        focus_ts = int(relation.get("focus_producer_ts", "0") or "0")
        visual_ts = int(relation.get("visual_producer_ts", "0") or "0")
        return abs(focus_ts - visual_ts) <= self.MIRROR_DEDUP_WINDOW_MS

    def _resolve_candidate_ts(self, relation: dict[str, str], use_focus: bool, use_world: bool, use_visual_fact: bool) -> int:
        if use_focus:
            return int(relation.get("focus_producer_ts", "0") or "0")
        if use_world:
            return int(relation.get("world_producer_ts", "0") or "0")
        if use_visual_fact:
            return int(relation.get("visual_producer_ts", "0") or "0")
        return int(relation.get("focus_producer_ts", "0") or "0")

    def _build_candidate_ref(self, candidate: ConversationCandidateEvent) -> str:
        parts = ["cand"]
        if candidate.candidate_actor_ids:
            parts.append(candidate.candidate_actor_ids[0])
        if candidate.candidate_object_ids:
            parts.append(candidate.candidate_object_ids[0])
        if candidate.candidate_environment_ids:
            parts.append(candidate.candidate_environment_ids[0])
        return "_".join(parts)

    def _candidate_signature(self, candidate: ConversationCandidateEvent) -> str:
        actor_ids = ",".join(candidate.candidate_actor_ids)
        object_ids = ",".join(candidate.candidate_object_ids)
        environment_ids = ",".join(candidate.candidate_environment_ids)
        return "%s|%s|%s|%s|%s" % (
            actor_ids,
            object_ids,
            environment_ids,
            candidate.engagement_pressure,
            candidate.privacy_risk_hint,
        )
