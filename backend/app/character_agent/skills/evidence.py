from __future__ import annotations

from hashlib import sha1

from app.character_agent.skills.models import (
    ActionSettlementResult,
    SkillEvaluationResult,
    SkillEvidence,
    SkillLearningPolicy,
)


class SkillEvidenceExtractor:
    def extract(
        self,
        *,
        actor_id: str,
        selected_skill_path: dict[str, object],
        skill_evaluation_result: SkillEvaluationResult,
        settlement_result: ActionSettlementResult,
        learning_policy: SkillLearningPolicy,
        source_settlement_id: str,
    ) -> SkillEvidence | None:
        if not learning_policy.evidence_collection_enabled:
            return None

        skill_id = self._string_value(selected_skill_path.get("skill_id"))
        action_id = self._string_value(selected_skill_path.get("action_id")) or skill_evaluation_result.action_id
        binding_id = self._string_value(selected_skill_path.get("binding_id"))
        if skill_id == "" or action_id == "":
            return None

        if not self._policy_allows_path(selected_skill_path=selected_skill_path, learning_policy=learning_policy):
            return None

        learning_config = self._mapping(selected_skill_path.get("learning"))
        if settlement_result.outcome_band == "blocked" and not bool(learning_config.get("evidence_on_blocked", False)):
            return None
        if settlement_result.outcome_band != "blocked" and not bool(learning_config.get("evidence_on_attempt", True)):
            return None

        evidence_channels = self._build_evidence_channels(
            selected_skill_path=selected_skill_path,
            settlement_result=settlement_result,
            learning_config=learning_config,
        )

        return SkillEvidence(
            evidence_id=self._evidence_id(
                actor_id=actor_id,
                skill_id=skill_id,
                binding_id=binding_id,
                source_settlement_id=source_settlement_id,
            ),
            actor_id=actor_id,
            skill_id=skill_id,
            action_id=action_id,
            binding_id=binding_id,
            source_settlement_id=source_settlement_id,
            outcome_band=settlement_result.outcome_band,
            primary_failure_domain=settlement_result.primary_failure_domain,
            failure_domains=list(settlement_result.failure_domains),
            evidence_channels=evidence_channels,
            eligible_for_candidate=False,
            eligible_for_promotion=False,
        )

    def _policy_allows_path(
        self,
        *,
        selected_skill_path: dict[str, object],
        learning_policy: SkillLearningPolicy,
    ) -> bool:
        path_tags = self._string_list(selected_skill_path.get("skill_path_tags"))
        blocked_domains = set(learning_policy.blocked_domains)
        if blocked_domains.intersection(path_tags):
            return False
        if learning_policy.allowed_domains and not set(learning_policy.allowed_domains).intersection(path_tags):
            return False
        return True

    def _build_evidence_channels(
        self,
        *,
        selected_skill_path: dict[str, object],
        settlement_result: ActionSettlementResult,
        learning_config: dict[str, object],
    ) -> dict[str, object]:
        channel_names = self._string_list(learning_config.get("evidence_channels"))
        path_tags = self._string_list(selected_skill_path.get("skill_path_tags"))
        tools_used = self._string_list(selected_skill_path.get("tools_used"))

        channels: dict[str, object] = {}
        if "acquisition" in channel_names:
            channels["acquisition"] = 0.0
        if "improvement" in channel_names:
            channels["improvement"] = 0.12 if settlement_result.outcome_band != "blocked" else 0.0
        if "confidence" in channel_names:
            channels["confidence"] = 0.03 if settlement_result.outcome_band != "blocked" else 0.0
        if "specialization" in channel_names:
            channels["specialization"] = {tag: 0.08 for tag in path_tags}
        if "tool_familiarity" in channel_names:
            channels["tool_familiarity"] = {tool: 0.04 for tool in tools_used}
        if "maladaptive_pattern" in channel_names:
            maladaptive: dict[str, float] = {}
            if settlement_result.outcome_band == "blocked":
                maladaptive[settlement_result.primary_failure_domain] = 0.1
            channels["maladaptive_pattern"] = maladaptive

        channels["context"] = {
            "skill_path_id": settlement_result.skill_path_id,
            "skill_contributions": list(settlement_result.skill_contributions),
            "risk_tags": list(settlement_result.risk_tags),
            "missing_requirements": list(settlement_result.missing_requirements),
        }
        return channels

    def _evidence_id(
        self,
        *,
        actor_id: str,
        skill_id: str,
        binding_id: str,
        source_settlement_id: str,
    ) -> str:
        digest = sha1(f"{actor_id}|{skill_id}|{binding_id}|{source_settlement_id}".encode("utf-8")).hexdigest()[:12]
        return f"skill_evidence:{digest}"

    def _mapping(self, value: object) -> dict[str, object]:
        return dict(value) if isinstance(value, dict) else {}

    def _string_value(self, value: object) -> str:
        return str(value or "").strip()

    def _string_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        result: list[str] = []
        for item in value:
            text = self._string_value(item)
            if text and text not in result:
                result.append(text)
        return result
