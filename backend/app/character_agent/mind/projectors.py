from __future__ import annotations

from copy import deepcopy

from app.character_agent.models.mind_frame import MentalFactorProjectionCard


def _mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return deepcopy(value)


def _dict_list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [deepcopy(entry) for entry in value if isinstance(entry, dict)]


def _first_text(entries: list[dict[str, object]], *keys: str) -> str:
    for entry in entries:
        for key in keys:
            value = str(entry.get(key, "") or "")
            if value:
                return value
    return ""


def _memory_ref(prefix: str, entry: dict[str, object]) -> str:
    value = str(
        entry.get("memory_id", "")
        or entry.get("source_event_id", "")
        or entry.get("proposition_key", "")
        or ""
    )
    if not value:
        return ""
    return f"{prefix}:{value}"


class EffectiveProfileProjector:
    def project(
        self,
        *,
        actor_id: str,
        effective_profile: dict[str, object] | None = None,
    ) -> list[MentalFactorProjectionCard]:
        profile = _mapping(effective_profile)
        identity = _mapping(profile.get("identity_core"))
        values = _mapping(profile.get("virtue_value_layer"))
        trait_vector = _mapping(profile.get("trait_vector_layer"))
        conversation = _mapping(profile.get("conversation_personality_layer"))
        temperament = _mapping(profile.get("temperament_response_layer"))
        red_lines_raw = values.get("red_lines", [])
        red_lines = list(red_lines_raw) if isinstance(red_lines_raw, list) else []
        profile_ref = f"profile:{actor_id}"

        cards = [
            MentalFactorProjectionCard(
                factor_type="effective_profile",
                layer="enduring_truth",
                scope="actor_private",
                horizon="long_term",
                confidence=1.0,
                freshness="current",
                summary=str(identity.get("canonical_name", "") or actor_id),
                payload={
                    "identity_core": identity,
                    "trait_vector_keys": sorted(trait_vector),
                    "red_lines": red_lines,
                },
                source_refs=[profile_ref],
            )
        ]
        if values or red_lines:
            cards.append(
                MentalFactorProjectionCard(
                    factor_type="authored_constraint",
                    layer="enduring_truth",
                    scope="actor_private",
                    horizon="long_term",
                    confidence=1.0,
                    freshness="current",
                    summary=red_lines[0] if red_lines else "",
                    payload={"red_lines": red_lines},
                    source_refs=[f"profile:{actor_id}:virtue_value_layer"],
                )
            )
        if trait_vector or conversation or temperament:
            cards.append(
                MentalFactorProjectionCard(
                    factor_type="personality_bias",
                    layer="enduring_truth",
                    scope="actor_private",
                    horizon="long_term",
                    confidence=0.9,
                    freshness="current",
                    summary=str(conversation.get("tone", "") or ""),
                    payload={
                        "conversation_personality_layer": conversation,
                        "temperament_response_layer": temperament,
                    },
                    source_refs=[f"profile:{actor_id}:personality_layers"],
                )
            )
        return cards


class MemoryActivationProjector:
    def project(
        self,
        memory_bundle: dict[str, list[dict[str, object]]] | None = None,
    ) -> list[MentalFactorProjectionCard]:
        memory = _mapping(memory_bundle)
        event_memories = _dict_list(memory.get("event_memories"))
        observation_memories = _dict_list(memory.get("observation_memories"))
        knowledge_memories = _dict_list(memory.get("knowledge_memories"))
        higher_order_memories = _dict_list(memory.get("higher_order_memories"))
        anchor_memories = event_memories + observation_memories
        activation_refs = [
            ref
            for ref in (
                _memory_ref("memory", entry)
                for entry in anchor_memories + knowledge_memories + higher_order_memories
            )
            if ref
        ]
        knowledge_refs = [
            ref
            for ref in (_memory_ref("knowledge_memory", entry) for entry in knowledge_memories)
            if ref
        ]
        higher_order_refs = [
            ref
            for ref in (
                _memory_ref("higher_order_memory", entry) for entry in higher_order_memories
            )
            if ref
        ]

        return [
            MentalFactorProjectionCard(
                factor_type="memory_activation",
                layer="memory_evidence",
                scope="actor_private",
                horizon="scene",
                confidence=0.8,
                freshness="recent",
                summary=_first_text(
                    event_memories + observation_memories + knowledge_memories + higher_order_memories,
                    "summary",
                    "observation_summary",
                    "proposition",
                    "meta_belief",
                ),
                payload={
                    "event_memory_count": len(event_memories),
                    "observation_memory_count": len(observation_memories),
                    "knowledge_memory_count": len(knowledge_memories),
                    "higher_order_memory_count": len(higher_order_memories),
                },
                source_refs=activation_refs,
            ),
            MentalFactorProjectionCard(
                factor_type="cognitive_anchor",
                layer="memory_evidence",
                scope="actor_private",
                horizon="scene",
                confidence=0.75,
                freshness="recent",
                summary=_first_text(
                    anchor_memories,
                    "summary",
                    "observation_summary",
                    "proposition",
                ),
                payload={
                    "active_anchors": [
                        entry.get("summary", "")
                        for entry in event_memories
                        if entry.get("summary")
                    ]
                },
                source_refs=activation_refs,
            ),
            MentalFactorProjectionCard(
                factor_type="knowledge_context",
                layer="memory_evidence",
                scope="actor_private",
                horizon="scene",
                confidence=0.75,
                freshness="recent",
                summary=_first_text(knowledge_memories, "proposition", "summary"),
                payload={"knowledge_memory_count": len(knowledge_memories)},
                source_refs=knowledge_refs,
            ),
            MentalFactorProjectionCard(
                factor_type="higher_order_belief",
                layer="memory_evidence",
                scope="actor_private",
                horizon="scene",
                confidence=0.75,
                freshness="recent",
                summary=_first_text(higher_order_memories, "meta_belief", "summary"),
                payload={"higher_order_memory_count": len(higher_order_memories)},
                source_refs=higher_order_refs,
            ),
        ]


class RelationshipContextProjector:
    def project(
        self,
        *,
        actor_id: str,
        social_memories: list[dict[str, object]] | None = None,
    ) -> list[MentalFactorProjectionCard]:
        entries = _dict_list(social_memories)
        top_target = str(entries[0].get("entity_id", "") or "") if entries else ""
        source_refs = [
            f"social_memory:{actor_id}:{entity_id}"
            for entry in entries
            if (entity_id := str(entry.get("entity_id", "") or ""))
        ]
        summary = ""
        if entries:
            first = entries[0]
            summary = "target=%s trust=%s suspicion=%s" % (
                top_target,
                str(first.get("trust_baseline", "") or ""),
                str(first.get("suspicion_baseline", "") or ""),
            )
        return [
            MentalFactorProjectionCard(
                factor_type="relationship_context",
                layer="memory_evidence",
                scope="actor_private",
                horizon="scene",
                confidence=0.8,
                freshness="recent",
                summary=summary,
                payload={
                    "target_count": len(entries),
                    "top_target": top_target,
                },
                source_refs=source_refs,
            )
        ]


class NeedPressureProjector:
    def project(
        self,
        need_tension_state: dict[str, object] | None = None,
    ) -> list[MentalFactorProjectionCard]:
        payload = _mapping(need_tension_state)
        return [
            MentalFactorProjectionCard(
                factor_type="need_pressure",
                layer="runtime_state",
                summary=str(payload.get("dominant_need", "") or ""),
                payload=payload,
                source_refs=["need_tension_state:current"] if payload else [],
            )
        ]


class AffectiveBodyStateProjector:
    def project(
        self,
        dynamic_state: dict[str, object] | None = None,
    ) -> list[MentalFactorProjectionCard]:
        payload = _mapping(dynamic_state)
        return [
            MentalFactorProjectionCard(
                factor_type="affective_body_state",
                layer="runtime_state",
                summary=f"stress_load={payload.get('stress_load', 0.0)}",
                payload=payload,
                source_refs=["dynamic_state:current"] if payload else [],
            )
        ]


class GoalContextProjector:
    def project(
        self,
        *,
        current_goal_state: dict[str, object] | None = None,
        goal_state_history: list[dict[str, object]] | None = None,
    ) -> list[MentalFactorProjectionCard]:
        current = _mapping(current_goal_state)
        goal_history = _dict_list(goal_state_history)
        return [
            MentalFactorProjectionCard(
                factor_type="goal_context",
                layer="runtime_state",
                summary=str(current.get("primary_goal", "") or ""),
                payload={
                    "current_goal_state": current,
                    "goal_state_history_count": len(goal_history),
                },
                source_refs=["goal_state:current"] if current else [],
            )
        ]


class UnresolvedTensionProjector:
    def project(
        self,
        unresolved_tensions: list[dict[str, object]] | None = None,
    ) -> list[MentalFactorProjectionCard]:
        tensions = _dict_list(unresolved_tensions)
        return [
            MentalFactorProjectionCard(
                factor_type="unresolved_tension",
                layer="runtime_state",
                summary=_first_text(tensions, "summary"),
                payload={"unresolved_tension_count": len(tensions)},
                source_refs=["unresolved_tensions:current"] if tensions else [],
            )
        ]


class SupervisionProjector:
    def project(
        self,
        supervision_state: dict[str, object] | None = None,
    ) -> list[MentalFactorProjectionCard]:
        payload = _mapping(supervision_state)
        return [
            MentalFactorProjectionCard(
                factor_type="supervision",
                layer="runtime_state",
                summary=str(payload.get("authorization_level", "") or payload.get("mode", "") or ""),
                payload=payload,
                source_refs=["supervision_state:current"] if payload else [],
            )
        ]


__all__ = [
    "AffectiveBodyStateProjector",
    "EffectiveProfileProjector",
    "GoalContextProjector",
    "MemoryActivationProjector",
    "NeedPressureProjector",
    "RelationshipContextProjector",
    "SupervisionProjector",
    "UnresolvedTensionProjector",
]
