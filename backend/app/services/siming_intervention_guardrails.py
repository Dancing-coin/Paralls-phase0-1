from pydantic import BaseModel, ConfigDict, Field

from app.models.siming_event import FairnessStateSnapshot, InterventionCandidate
from app.models.siming_narrative import InterventionSeed


BLOCKED_RISK_TAGS = {
    "locked_truth_rewrite",
    "skip_role_autonomy",
    "skip_esm",
    "phase2_projection_required",
}
SEED_SOURCE_TO_CANDIDATE_SOURCE = {
    "narrative_core": "rule",
}


class GuardrailResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: InterventionSeed
    accepted: bool
    reasons: list[str] = Field(default_factory=list)

    def to_candidate(
        self,
        *,
        room_id: str,
        scene_id: str,
        zone_id: str,
        causation_id: str,
        correlation_id: str,
    ) -> InterventionCandidate:
        if not self.accepted:
            raise ValueError("rejected seed cannot be converted to candidate")
        target_actor_id = next((ref for ref in self.seed.target_refs if ref.startswith("char_")), None)
        target_environment_id = next((ref for ref in self.seed.target_refs if ref.startswith("env_")), None)
        target_object_id = next((ref for ref in self.seed.target_refs if ref.startswith("obj_")), None)
        return InterventionCandidate(
            candidate_id=f"candidate:{self.seed.seed_id}",
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            causation_id=causation_id,
            correlation_id=correlation_id,
            proposed_band=self.seed.suggested_band,
            target_actor_id=target_actor_id,
            target_object_id=target_object_id,
            target_environment_id=target_environment_id,
            established_fact_ids=list(self.seed.basis_obligation_refs),
            explanation=self.seed.explanation,
            confidence=0.75,
            reason_tags=["guardrail_checked", *self.reasons],
            source=SEED_SOURCE_TO_CANDIDATE_SOURCE.get(self.seed.source, self.seed.source),
        )


class SimingInterventionGuardrails:
    def evaluate_seed(self, seed: InterventionSeed, *, snapshot: FairnessStateSnapshot) -> GuardrailResult:
        reasons: list[str] = []
        for tag in seed.risk_tags:
            if tag in BLOCKED_RISK_TAGS:
                reasons.append(tag)
        unknown_refs = [ref for ref in seed.basis_obligation_refs if ref not in snapshot.known_fact_ids]
        if unknown_refs:
            reasons.append("unknown_fact_reference")
        target_actor_refs = [ref for ref in seed.target_refs if ref.startswith("char_")]
        for actor_ref in target_actor_refs:
            if actor_ref not in snapshot.eligible_actor_ids:
                reasons.append("actor_not_eligible")
        if seed.suggested_band == "environment_request" and "esm_validated_request" not in seed.risk_tags:
            reasons.append("environment_request_requires_esm_path")
        return GuardrailResult(seed=seed, accepted=not reasons, reasons=sorted(set(reasons)))
