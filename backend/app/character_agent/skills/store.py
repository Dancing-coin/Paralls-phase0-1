from __future__ import annotations

from app.character_agent.skills.models import SkillEvidence


class SkillEvidenceStore:
    def __init__(self) -> None:
        self._evidence_ids: set[str] = set()
        self._by_actor: dict[str, list[SkillEvidence]] = {}

    def append(self, evidence: SkillEvidence) -> None:
        if evidence.evidence_id in self._evidence_ids:
            return

        stored = evidence.model_copy(deep=True)
        self._evidence_ids.add(stored.evidence_id)
        self._by_actor.setdefault(stored.actor_id, []).append(stored)

    def query(
        self,
        *,
        actor_id: str,
        skill_id: str = "",
        action_id: str = "",
        binding_id: str = "",
        source_settlement_id: str = "",
    ) -> list[SkillEvidence]:
        matches: list[SkillEvidence] = []
        for evidence in self._by_actor.get(actor_id, []):
            if skill_id and evidence.skill_id != skill_id:
                continue
            if action_id and evidence.action_id != action_id:
                continue
            if binding_id and evidence.binding_id != binding_id:
                continue
            if source_settlement_id and evidence.source_settlement_id != source_settlement_id:
                continue
            matches.append(evidence.model_copy(deep=True))
        return matches


__all__ = ["SkillEvidenceStore"]
