"""Non-authoritative Character Agent proposals for a scripted-mystery turn."""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field

from app.gameplay.models import StrictGameplayModel
from app.gameplay.p5.scripted_mystery_evidence import CaseTurnContext


class CaseAgentContext(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    turn_id: str
    actor_ref: str = Field(pattern=r"^character:")
    case_ref: str
    phase_ref: str | None = None
    public_fact_refs: tuple[str, ...] = ()
    private_fact_refs: tuple[str, ...] = ()
    visible_clue_refs: tuple[str, ...] = ()
    source_revision_vector: dict[str, int] = {}


class CaseTurnProposal(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    turn_id: str
    actor_ref: str = Field(pattern=r"^character:")
    proposal_kind: Literal["investigate", "question", "hide", "pursue"]
    target_ref: str | None = None
    clue_ref: str | None = None
    statement_ref: str | None = None
    source_revision_vector: dict[str, int] = {}
    owner_route: Literal["quest", "social", "action"]
    policy_revision: str


class CaseTurnDecision(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    proposal: CaseTurnProposal | None = None
    error_code: str | None = None


class ScriptedMysteryAgentTurnService:
    def propose_turn(self, context: CaseTurnContext, *, case_ref: str, turn_id: str, policy: Literal["investigator", "guardian"]) -> CaseTurnDecision:
        if not context.recipient_ref or not case_ref or not turn_id:
            return CaseTurnDecision(accepted=False, error_code="stormnight_agent_context_invalid")
        if policy == "investigator":
            clue = context.visible_clue_refs[0] if context.visible_clue_refs else None
            kind = "investigate" if clue else "question"
            proposal = CaseTurnProposal(turn_id=turn_id, actor_ref=context.recipient_ref, proposal_kind=kind, clue_ref=clue, owner_route="quest" if clue else "social", source_revision_vector=context.source_revision_vector, policy_revision="policy:stormnight:investigator@1")
        else:
            kind = "pursue" if context.visible_clue_refs else "hide"
            proposal = CaseTurnProposal(turn_id=turn_id, actor_ref=context.recipient_ref, proposal_kind=kind, target_ref=context.recipient_ref if kind == "pursue" else None, owner_route="action", source_revision_vector=context.source_revision_vector, policy_revision="policy:stormnight:guardian@1")
        return CaseTurnDecision(accepted=True, proposal=proposal)

    def propose_turn_from_character_runtime(self, runtime, event, *, context: CaseTurnContext, case_ref: str, turn_id: str, policy: Literal["investigator", "guardian"]) -> CaseTurnDecision:
        """Feed one committed perception through the existing Character runtime.

        The returned goal commands are normalized to a non-canonical proposal;
        this method never appends case or world facts.
        """
        if event.actor_id != context.recipient_ref:
            return CaseTurnDecision(accepted=False, error_code="stormnight_agent_actor_mismatch")
        commands = runtime.ingest_character_perceived_event(event)
        base = self.propose_turn(context, case_ref=case_ref, turn_id=turn_id, policy=policy)
        if not base.accepted or base.proposal is None:
            return base
        if commands:
            command = commands[0]
            proposal = base.proposal.model_copy(update={"target_ref": command.target_actor_id or command.target_object_id or command.target_environment_id}, deep=True)
            return CaseTurnDecision(accepted=True, proposal=proposal)
        return base


__all__ = ["CaseAgentContext", "CaseTurnDecision", "CaseTurnProposal", "ScriptedMysteryAgentTurnService"]
