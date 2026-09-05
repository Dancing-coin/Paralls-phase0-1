"""Read-side case context and owner-bound intent validation.

This adapter never appends another owner's facts. It builds filtered contexts
and turns validated requests into source-bound proposals for Quest, Social,
Inventory and the case authority.
"""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field

from app.gameplay.models import StrictGameplayModel
from app.gameplay.p5.scripted_mystery_case_runtime import CaseProjection
from app.gameplay.p5.scripted_mystery_content import ScriptedMysteryCaseContent


class CaseTurnContext(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    recipient_ref: str = Field(pattern=r"^character:")
    public_fact_refs: tuple[str, ...] = ()
    private_fact_refs: tuple[str, ...] = ()
    visible_clue_refs: tuple[str, ...] = ()
    phase_ref: str | None = None
    source_revision_vector: dict[str, int] = {}


class StatementIntent(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    statement_ref: str
    speaker_ref: str = Field(pattern=r"^character:")
    target_ref: str
    mode: Literal["reveal", "withhold", "mislead", "deny"]
    expected_case_revision: int = Field(ge=0)
    command_id: str


class EvidenceDiscoveryIntent(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    clue_ref: str
    discoverer_ref: str = Field(pattern=r"^character:")
    expected_case_revision: int = Field(ge=0)
    collect_to_custody: bool
    command_id: str


class AccusationIntent(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accuser_ref: str = Field(pattern=r"^character:")
    target_ref: str = Field(pattern=r"^character:")
    evidence_refs: tuple[str, ...] = Field(min_length=1)
    expected_case_revision: int = Field(ge=0)
    command_id: str


class CaseEvidenceProjection(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_refs: tuple[str, ...] = ()
    statement_refs: tuple[str, ...] = ()
    accusation_refs: tuple[str, ...] = ()


class ScriptedMysteryEvidenceAdapter:
    def __init__(self, *, content: ScriptedMysteryCaseContent) -> None:
        self._content = content

    def build_turn_context(self, case_projection: CaseProjection, recipient_ref: str) -> CaseTurnContext:
        if recipient_ref not in self._content.actor_refs:
            raise ValueError("stormnight_recipient_unknown")
        knowledge = next(item for item in self._content.private_knowledge_sets if item.actor_ref == recipient_ref)
        public = tuple(sorted(fact.fact_ref for fact in self._content.truth_facts if fact.visibility == "project"))
        visible = tuple(sorted(clue.clue_ref for clue in self._content.clue_definitions if clue.clue_ref in case_projection.committed_clue_refs))
        return CaseTurnContext(recipient_ref=recipient_ref, public_fact_refs=public, private_fact_refs=knowledge.fact_refs, visible_clue_refs=visible, phase_ref=case_projection.phase_ref, source_revision_vector=case_projection.source_revision_vector)

    def validate_statement(self, intent: StatementIntent, context: CaseTurnContext) -> str | None:
        statement = next((item for item in self._content.statement_definitions if item.statement_ref == intent.statement_ref), None)
        if statement is None or statement.speaker_ref != intent.speaker_ref or intent.speaker_ref != context.recipient_ref:
            return "stormnight_statement_unadmitted"
        if intent.mode not in statement.allowed_modes:
            return "stormnight_statement_mode_unadmitted"
        if statement.visibility == "actor_private" and intent.target_ref != statement.target_ref:
            return "stormnight_statement_private_leak"
        return None

    def validate_discovery(self, intent: EvidenceDiscoveryIntent, context: CaseTurnContext) -> str | None:
        clue = next((item for item in self._content.clue_definitions if item.clue_ref == intent.clue_ref), None)
        if clue is None or intent.discoverer_ref != context.recipient_ref:
            return "stormnight_clue_unadmitted"
        if not clue.discovery_predicate_refs:
            return "stormnight_clue_predicate_missing"
        return None

    def validate_accusation(self, intent: AccusationIntent, context: CaseTurnContext) -> str | None:
        if intent.accuser_ref != context.recipient_ref or intent.target_ref not in self._content.actor_refs:
            return "stormnight_accusation_subject_invalid"
        if len(set(intent.evidence_refs)) != len(intent.evidence_refs) or tuple(intent.evidence_refs) != tuple(sorted(intent.evidence_refs)):
            return "stormnight_accusation_evidence_not_canonical"
        known = set(context.public_fact_refs) | set(context.private_fact_refs) | set(context.visible_clue_refs)
        if not set(intent.evidence_refs).issubset(known):
            return "stormnight_accusation_evidence_private_or_missing"
        if len(intent.evidence_refs) < 2:
            return "stormnight_accusation_evidence_insufficient"
        return None


__all__ = ["AccusationIntent", "CaseEvidenceProjection", "CaseTurnContext", "EvidenceDiscoveryIntent", "ScriptedMysteryEvidenceAdapter", "StatementIntent"]
