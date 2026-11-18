"""生成需经司命干预策略审核的机会候选。"""

from itertools import combinations
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.siming_knowledge_graph import SimingKnowledgeGraph
from app.models.siming_event import FairnessStateSnapshot, InterventionCandidate
from app.services.siming_policy import SimingInterventionPolicy


class OpportunityCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    opportunity_id: str
    opportunity_type: Literal["confrontation", "secret_exposure", "isolation"]
    actor_ids: list[str]
    motivation_check: bool
    knowledge_check: bool
    physical_check: bool
    narrative_value: float = Field(ge=0, le=1)
    feasible: bool
    reason: str


class SimingConflictGenerator:
    def __init__(self, knowledge_graph: SimingKnowledgeGraph) -> None:
        self._knowledge_graph = knowledge_graph

    def approve_candidate(self, opportunity: OpportunityCandidate, *, snapshot: FairnessStateSnapshot, policy: SimingInterventionPolicy) -> InterventionCandidate | None:
        if not (opportunity.feasible and opportunity.motivation_check
                and opportunity.knowledge_check and opportunity.physical_check) or not opportunity.actor_ids:
            return None
        for actor in opportunity.actor_ids:
            candidate = InterventionCandidate(candidate_id=f"{opportunity.opportunity_id}:{actor}", room_id=snapshot.room_id, scene_id=snapshot.scene_id, zone_id=snapshot.zone_id, causation_id=snapshot.causation_id, correlation_id=snapshot.correlation_id, proposed_band="opportunity", target_actor_id=actor, explanation=opportunity.reason, confidence=opportunity.narrative_value)
            if not policy.evaluate(candidate, snapshot=snapshot).accepted:
                return None
        return candidate

    def generate_opportunities(self, actor_ids: list[str], current_tick: int, *, motivations: set[str] | None = None, physical_presence: set[str] | None = None, isolated_actors: set[str] | None = None) -> list[OpportunityCandidate]:
        if current_tick < 0 or len(actor_ids) != len(set(actor_ids)):
            raise ValueError("invalid tick or duplicate actors")
        actors = set(actor_ids)
        motivated, present, isolated = motivations or set(), physical_presence or set(), isolated_actors or set()
        candidates = []

        def add(kind: str, key: str, participants: list[str], knowledge: bool, physical: bool, value: float) -> None:
            motivation = bool(set(participants) & motivated)
            candidates.append(OpportunityCandidate(opportunity_id=f"{kind}:{key}:{current_tick}", opportunity_type=kind, actor_ids=participants, motivation_check=motivation, knowledge_check=knowledge, physical_check=physical, narrative_value=value, feasible=motivation and knowledge and physical, reason=key))

        for conversation in self._knowledge_graph.active_conversations(current_tick):
            cid = conversation.conversation_id
            members = sorted(actors.intersection(self._knowledge_graph.who_is_in_conversation(cid, current_tick)))
            listeners = sorted(actors.intersection(self._knowledge_graph.who_is_listening(cid, current_tick)))
            for first, second in combinations(members, 2):
                aware = any(self._knowledge_graph.awareness_at(a, b, cid, current_tick) != "unaware" for a, b in ((first, second), (second, first)))
                add("confrontation", f"{cid}:{first}:{second}", [first, second], aware, {first, second} <= present, .7)
            if members and listeners and self._knowledge_graph.has_secret(cid, current_tick):
                for listener in listeners:
                    hidden = all(self._knowledge_graph.awareness_at(member, listener, cid, current_tick) == "unaware" for member in members)
                    can_hear = self._knowledge_graph.access_quality_at(listener, cid, current_tick) != "none"
                    add("secret_exposure", f"{cid}:{listener}", members + [listener], hidden and can_hear, set(members + [listener]) <= present, .8)
        for actor in sorted(actors & isolated):
            add("isolation", actor, [actor], True, actor in present, .4)
        return candidates
