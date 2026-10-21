from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

from app.character_agent.skills.learning import LearningProposal
from app.character_agent.skills.models import ActionSettlementResult, PrimitiveActionPlan, SkillEvaluationResult
from app.character_agent.skills.store import SkillEvidenceStore


class LearningSettlementReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    idempotency_key: str
    actor_id: str
    skill_id: str
    status: Literal["accepted", "rejected", "duplicate_replayed", "changed_duplicate"]
    revision: int = 0
    authority_event_id: str = ""
    reason: str = ""
    failure_refs: list[str] = Field(default_factory=list)


class SkillLearningSettlement:
    """The sole owner boundary for projecting learning progress to skill revision."""

    def __init__(self, *, store: SkillEvidenceStore | None = None) -> None:
        self._store = store or SkillEvidenceStore()
        self._receipts: dict[str, tuple[str, LearningSettlementReceipt]] = {}

    def settle(
        self,
        proposal: LearningProposal,
        *,
        authority_event_id: str,
        accepted: bool = True,
        reason: str = "",
    ) -> LearningSettlementReceipt:
        digest = self._digest(proposal)
        previous = self._receipts.get(proposal.idempotency_key)
        if previous is not None:
            previous_digest, receipt = previous
            if previous_digest == digest:
                return receipt.model_copy(deep=True, update={"status": "duplicate_replayed"})
            return receipt.model_copy(deep=True, update={"status": "changed_duplicate", "reason": "idempotency_payload_changed"})

        if not accepted:
            receipt = LearningSettlementReceipt(
                proposal_id=proposal.proposal_id,
                idempotency_key=proposal.idempotency_key,
                actor_id=proposal.actor_id,
                skill_id=proposal.skill_id,
                status="rejected",
                reason=reason or "owner_rejected",
                failure_refs=list(proposal.failure_refs),
            )
            self._store.record_failure_evidence(
                actor_id=proposal.actor_id,
                skill_id=proposal.skill_id,
                refs=proposal.failure_refs,
            )
            self._receipts[proposal.idempotency_key] = (digest, receipt)
            return receipt.model_copy(deep=True)

        if not authority_event_id:
            receipt = LearningSettlementReceipt(
                proposal_id=proposal.proposal_id,
                idempotency_key=proposal.idempotency_key,
                actor_id=proposal.actor_id,
                skill_id=proposal.skill_id,
                status="rejected",
                reason="authority_required",
                failure_refs=list(proposal.failure_refs),
            )
            self._store.record_failure_evidence(
                actor_id=proposal.actor_id,
                skill_id=proposal.skill_id,
                refs=proposal.failure_refs,
            )
            self._receipts[proposal.idempotency_key] = (digest, receipt)
            return receipt.model_copy(deep=True)

        revision = self._store.record_skill_revision(
            actor_id=proposal.actor_id,
            skill_id=proposal.skill_id,
        )
        receipt = LearningSettlementReceipt(
            proposal_id=proposal.proposal_id,
            idempotency_key=proposal.idempotency_key,
            actor_id=proposal.actor_id,
            skill_id=proposal.skill_id,
            status="accepted",
            revision=revision,
            authority_event_id=authority_event_id,
            failure_refs=list(proposal.failure_refs),
        )
        self._store.record_failure_evidence(
            actor_id=proposal.actor_id,
            skill_id=proposal.skill_id,
            refs=proposal.failure_refs,
        )
        self._receipts[proposal.idempotency_key] = (digest, receipt)
        return receipt.model_copy(deep=True)

    def _digest(self, proposal: LearningProposal) -> str:
        payload = json.dumps(proposal.model_dump(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def map_action_settlement_result(
    *,
    skill_evaluation_result: SkillEvaluationResult | None,
    primitive_action_plan: PrimitiveActionPlan | None,
    plan_policy: str,
    selected_channels: Sequence[str],
    channel_results: Sequence[Mapping[str, Any]],
    unified_result_family: Sequence[Mapping[str, Any]],
    orchestration_status: str,
) -> ActionSettlementResult | None:
    if skill_evaluation_result is None and primitive_action_plan is None:
        return None

    semantic_effects: list[str] = []
    physical_effects: list[str] = []
    costs = _collect_costs(skill_evaluation_result)
    realization_hints = _collect_realization_hints(primitive_action_plan)
    failure_domains: list[str] = []
    primary_failure_domain = "none"

    for result in unified_result_family:
        result_type = str(result.get("result_type", "") or "")
        if result_type == "action_resolution_result":
            stable_summary = str(result.get("stable_state_summary", "") or "")
            action_profile = str(result.get("action_profile", "") or "")
            if stable_summary:
                semantic_effects.append(stable_summary)
            if action_profile:
                semantic_effects.append(action_profile)
        elif result_type in {"object_state_result", "body_state_result", "environment_state_result"}:
            change_summary = str(result.get("change_summary", "") or "")
            current_state = str(result.get("current_state", "") or "")
            if change_summary:
                physical_effects.append(change_summary)
            elif current_state:
                physical_effects.append(current_state)

    has_missing_requirements = any(
        isinstance(path, Mapping) and path.get("missing_requirements")
        for path in (skill_evaluation_result.blocked_paths if skill_evaluation_result is not None else [])
    )
    selected_path_present = bool(skill_evaluation_result and skill_evaluation_result.selected_path)
    constraint_present = any(str(result.get("result_type", "") or "") == "constraint_state_result" for result in unified_result_family)
    physical_rejected = any(
        str(result.get("channel", "") or "") == "physical" and str(result.get("status", "") or "") == "rejected"
        for result in channel_results
    )
    semantic_accepted = any(
        str(result.get("channel", "") or "") == "semantic" and str(result.get("status", "") or "") in {"accepted", "applied"}
        for result in channel_results
    )

    if orchestration_status == "completed":
        outcome_band = "success_with_cost" if costs else "clean_success"
    else:
        if has_missing_requirements and not selected_path_present:
            primary_failure_domain = "missing_requirement"
        elif physical_rejected and semantic_accepted and "physical" in selected_channels:
            primary_failure_domain = "physical_failure"
        elif constraint_present or plan_policy in {
            "denied-by-constraint",
            "requires-active-perception",
            "requires-authority-confirmation",
        }:
            primary_failure_domain = "world_constraint"
        else:
            primary_failure_domain = "skill_failure"
        failure_domains.append(primary_failure_domain)
        if has_missing_requirements and primary_failure_domain != "missing_requirement":
            failure_domains.append("missing_requirement")
        outcome_band = "blocked" if primary_failure_domain in {"world_constraint", "missing_requirement"} else "failed"

    return ActionSettlementResult(
        outcome_band=outcome_band,
        failure_domains=failure_domains,
        primary_failure_domain=primary_failure_domain,
        semantic_effects=_unique(semantic_effects),
        physical_effects=_unique(physical_effects),
        social_effects=[],
        costs=costs,
        realization_hints=realization_hints,
    )


def _collect_costs(skill_evaluation_result: SkillEvaluationResult | None) -> list[str]:
    if skill_evaluation_result is None:
        return []
    costs = list(skill_evaluation_result.recommendation_reason)
    for blocked_path in skill_evaluation_result.blocked_paths:
        missing_requirements = blocked_path.get("missing_requirements")
        if isinstance(missing_requirements, list):
            for requirement in missing_requirements:
                if isinstance(requirement, str) and requirement:
                    costs.append(f"missing_requirement:{requirement}")
    return _unique(costs)


def _collect_realization_hints(primitive_action_plan: PrimitiveActionPlan | None) -> list[str]:
    if primitive_action_plan is None:
        return []
    hints = list(primitive_action_plan.realization_keys)
    hints.extend(
        f"primitive:{action_name}"
        for action_name in primitive_action_plan.primitive_actions
        if isinstance(action_name, str) and action_name
    )
    return _unique(hints)


def _unique(values: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
