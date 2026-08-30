from __future__ import annotations

from .models import ActivationDecision


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
