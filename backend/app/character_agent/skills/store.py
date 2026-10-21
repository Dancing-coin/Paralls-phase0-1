from __future__ import annotations

from app.character_agent.skills.models import SkillEvidence


class SkillEvidenceStore:
    def __init__(self) -> None:
        self._evidence_by_id: dict[str, SkillEvidence] = {}
        self._skill_revisions: dict[tuple[str, str], int] = {}
        self._failure_evidence: dict[tuple[str, str], list[str]] = {}

    def append(self, evidence: SkillEvidence) -> SkillEvidence:
        if evidence.evidence_id not in self._evidence_by_id:
            self._evidence_by_id[evidence.evidence_id] = evidence.model_copy(deep=True)
        return self._evidence_by_id[evidence.evidence_id].model_copy(deep=True)

    def contains(self, evidence_id: str) -> bool:
        return str(evidence_id or "") in self._evidence_by_id

    def query(
        self,
        *,
        actor_id: str,
        skill_id: str | None = None,
        action_id: str | None = None,
        binding_id: str | None = None,
        source_settlement_id: str | None = None,
    ) -> list[SkillEvidence]:
        records: list[SkillEvidence] = []
        for evidence in self._evidence_by_id.values():
            if evidence.actor_id != actor_id:
                continue
            if skill_id is not None and evidence.skill_id != skill_id:
                continue
            if action_id is not None and evidence.action_id != action_id:
                continue
            if binding_id is not None and evidence.binding_id != binding_id:
                continue
            if source_settlement_id is not None and evidence.source_settlement_id != source_settlement_id:
                continue
            records.append(evidence.model_copy(deep=True))
        return records

    def all(self) -> list[SkillEvidence]:
        return [evidence.model_copy(deep=True) for evidence in self._evidence_by_id.values()]

    def record_skill_revision(self, *, actor_id: str, skill_id: str) -> int:
        key = (actor_id, skill_id)
        revision = self._skill_revisions.get(key, 0) + 1
        self._skill_revisions[key] = revision
        return revision

    def skill_revision(self, *, actor_id: str, skill_id: str) -> int:
        return self._skill_revisions.get((actor_id, skill_id), 0)

    def record_failure_evidence(self, *, actor_id: str, skill_id: str, refs: list[str]) -> None:
        if not refs:
            return
        key = (actor_id, skill_id)
        current = self._failure_evidence.setdefault(key, [])
        for ref in refs:
            if ref and ref not in current:
                current.append(ref)

    def failure_evidence(self, *, actor_id: str, skill_id: str) -> list[str]:
        return list(self._failure_evidence.get((actor_id, skill_id), []))
