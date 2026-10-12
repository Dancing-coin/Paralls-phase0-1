from __future__ import annotations

from .models import ActivationDecision
from .simulation_contracts import ParticipationPolicy, ParticipationResolution, simulation_digest


def resolve_participation(*, policies: tuple[ParticipationPolicy, ...], tick: int) -> ParticipationResolution:
    if type(tick) is not int or tick < 0:
        raise ValueError("participation_tick_invalid")
    ordered = tuple(sorted(policies, key=lambda policy: policy.policy_ref))
    if len({policy.policy_ref for policy in ordered}) != len(ordered):
        raise ValueError("participation_policy_duplicate")
    allowed = set(ordered[0].allowed_tiers) if ordered else set()
    modules = set(ordered[0].allowed_modules) if ordered else set()
    for policy in ordered[1:]:
        allowed.intersection_update(policy.allowed_tiers)
        modules.intersection_update(policy.allowed_modules)
    expiry = min((policy.b0_expiry_tick for policy in ordered), default=tick)
    review = min((policy.review_tick for policy in ordered), default=tick)
    if tick >= expiry:
        allowed.discard("B0")
    if tick >= review:
        allowed.clear()
    tiers = tuple(tier for tier in ("B0", "B1", "B2", "B3") if tier in allowed)
    return ParticipationResolution(
        allowed_tiers=tiers, recommended_tier=tiers[0] if tiers else None,
        allowed_modules=tuple(sorted(modules)),
        forbidden_dimensions=tuple(sorted({dimension for policy in ordered for dimension in policy.forbidden_dimensions})),
        upgrade_triggers=tuple(sorted({trigger for policy in ordered for trigger in policy.upgrade_triggers})),
        b0_expiry_tick=expiry, review_tick=review,
        policy_revision=simulation_digest([policy.model_dump(mode="json") for policy in ordered]),
        source_policy_pins={policy.policy_ref: policy.revision for policy in ordered},
        status="resolved" if tiers else "defer",
    )


class ActivationPolicy:
    def __init__(self, *, prewarm_distance_m: float = 12.0, policy_revision: str = "policy:activation:v1") -> None:
        self.prewarm_distance_m = prewarm_distance_m
        self.policy_revision = policy_revision

    def evaluate(
        self,
        *,
        actor_id: str,
        distance_m: float,
        focused: bool,
        interaction_type: str,
        pending_seed: bool,
        budget: int,
        supported_actor: bool = True,
        stale_revision: bool = False,
    ) -> ActivationDecision:
        if not supported_actor or stale_revision:
            return ActivationDecision(actor_id=actor_id, state="requeue", reason="unsupported_actor" if not supported_actor else "stale_revision", policy_revision=self.policy_revision)
        if budget <= 0:
            return ActivationDecision(actor_id=actor_id, state="requeue", reason="activation_budget_exhausted", policy_revision=self.policy_revision)
        if interaction_type in {"dialogue", "conflict", "consequential"} and focused:
            return ActivationDecision(actor_id=actor_id, state="active", reason="player_dialogue" if interaction_type == "dialogue" else f"player_{interaction_type}", requires_activation_lock=True, load_private_memory=True, policy_revision=self.policy_revision)
        if focused:
            return ActivationDecision(actor_id=actor_id, state="activation_candidate", reason="focused_player_input", requires_activation_lock=True, policy_revision=self.policy_revision)
        if distance_m <= self.prewarm_distance_m or pending_seed:
            return ActivationDecision(actor_id=actor_id, state="prewarm", reason="proximity_or_pending_seed", policy_revision=self.policy_revision)
        return ActivationDecision(actor_id=actor_id, state="dormant", reason="no_activation_signal", policy_revision=self.policy_revision)

    def evaluate_siming_delivery(self, *, actor_id, delivery, budget, supported_actor, stale_revision):
        """已提交的三类高层私有输入允许认知；来源证明仍由入站服务独立验证。"""
        from app.models.siming_character_bridge import SimingCharacterCompatibilityInput
        delivery = SimingCharacterCompatibilityInput.model_validate(delivery.model_dump(mode='json'))
        if actor_id != delivery.actor_id:
            return ActivationDecision(actor_id=actor_id, state='requeue', reason='siming_target_mismatch', policy_revision=self.policy_revision)
        decision = self.evaluate(actor_id=actor_id, distance_m=float('inf'), focused=False,
            interaction_type='none', pending_seed=False, budget=budget,
            supported_actor=supported_actor, stale_revision=stale_revision)
        if decision.state == 'requeue':
            return decision
        return ActivationDecision(actor_id=actor_id, state='active', reason='siming_high_level_input',
            requires_activation_lock=True, load_private_memory=True, policy_revision=self.policy_revision)

    def evaluate_scheduled_background(self, *, actor_id, eligible, budget, supported_actor):
        """原后台调度资格只唤醒自己的私有快照，不伪造玩家关注。"""
        decision = self.evaluate(actor_id=actor_id, distance_m=float('inf'), focused=False,
            interaction_type='none', pending_seed=False, budget=budget, supported_actor=supported_actor)
        if decision.state == 'requeue' or not eligible:
            return decision
        return ActivationDecision(actor_id=actor_id, state='active', reason='scheduled_background',
            requires_activation_lock=True, load_private_memory=True, policy_revision=self.policy_revision)
