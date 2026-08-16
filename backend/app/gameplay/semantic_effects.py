from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field

from app.gameplay.models import StrictGameplayModel


class EffectApplication(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    effect_ref: str = Field(min_length=1)
    target_component_ref: str = Field(min_length=1)
    magnitude: int = Field(ge=0)
    stack_key: str = Field(min_length=1)
    expires_at_tick: int | None = Field(default=None, ge=0)
    causal_chain_id: str = Field(min_length=1)


class ResistanceProfile(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    effect_ref: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    modifier_basis_points: int = Field(ge=0, le=10_000)
    revision: int = Field(ge=0)


class StateDefinition(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    state_ref: str = Field(min_length=1)
    stack_policy: Literal["add", "replace", "refresh", "reject"]
    stack_limit: int = Field(ge=1)
    expiry_policy: Literal["none", "scheduled"]
    dispel_allowed: bool = True
    transform_targets: tuple[str, ...] = ()


class EffectResolution(StrictGameplayModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    effective_magnitude: int = Field(ge=0)
    next_stacks: int = Field(ge=0)
    error_code: str | None = None
    expiry_obligation: dict[str, object] | None = None


class StateActionResolution(StrictGameplayModel):
    """Pure, closed lifecycle action decision; an owner still performs writes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    next_stacks: int = Field(ge=0)
    next_state_ref: str | None = None
    error_code: str | None = None


class StateTransitionPlan(StrictGameplayModel):
    """Pure owner proposal shared by registered state adapters.

    This is deliberately a data-only decision. It cannot append events, select
    an owner, or construct a cross-domain settlement batch.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    operation: Literal["add", "replace", "refresh", "reject", "dispel", "transform"]
    effect_ref: str | None = None
    state_ref: str
    target_component_ref: str | None = None
    existing_stacks: int = Field(ge=0)
    next_stacks: int = Field(ge=0)
    effective_magnitude: int = Field(default=0, ge=0)
    next_state_ref: str | None = None
    error_code: str | None = None
    expiry_obligation: dict[str, object] | None = None


class EffectLifecycleEvaluator:
    """Pure fixed-point effect resolver; lifecycle writes remain owner proposals."""

    def resolve(
        self,
        application: EffectApplication,
        *,
        resistance: ResistanceProfile,
        state: StateDefinition,
        existing_stacks: int,
    ) -> EffectResolution:
        if resistance.effect_ref != application.effect_ref:
            return EffectResolution(accepted=False, effective_magnitude=0, next_stacks=existing_stacks, error_code="resistance_effect_mismatch")
        if existing_stacks < 0:
            return EffectResolution(accepted=False, effective_magnitude=0, next_stacks=existing_stacks, error_code="state_stack_invalid")
        if state.stack_policy == "reject" and existing_stacks >= state.stack_limit:
            return EffectResolution(accepted=False, effective_magnitude=0, next_stacks=existing_stacks, error_code="state_stack_limit")
        if state.stack_policy == "replace":
            next_stacks = 1
        elif state.stack_policy == "refresh":
            next_stacks = max(1, existing_stacks)
        else:
            next_stacks = existing_stacks + 1
        if next_stacks > state.stack_limit:
            return EffectResolution(accepted=False, effective_magnitude=0, next_stacks=existing_stacks, error_code="state_stack_limit")
        magnitude = application.magnitude * (10_000 - resistance.modifier_basis_points) // 10_000
        expiry = None
        if state.expiry_policy == "scheduled" and application.expires_at_tick is not None:
            expiry = {
                "obligation_kind": "semantic.effect.expire",
                "effect_ref": application.effect_ref,
                "state_ref": state.state_ref,
                "target_component_ref": application.target_component_ref,
                "due_tick": application.expires_at_tick,
                "causal_chain_id": application.causal_chain_id,
            }
        return EffectResolution(accepted=True, effective_magnitude=magnitude, next_stacks=next_stacks, expiry_obligation=expiry)

    def plan_apply(
        self,
        application: EffectApplication,
        *,
        resistance: ResistanceProfile,
        state: StateDefinition,
        existing_stacks: int,
    ) -> StateTransitionPlan:
        """Return a pure add/replace/refresh/reject proposal for an owner."""
        resolution = self.resolve(
            application,
            resistance=resistance,
            state=state,
            existing_stacks=existing_stacks,
        )
        operation = state.stack_policy if resolution.accepted else "reject"
        return StateTransitionPlan(
            accepted=resolution.accepted,
            operation=operation,
            effect_ref=application.effect_ref,
            state_ref=state.state_ref,
            target_component_ref=application.target_component_ref,
            existing_stacks=max(existing_stacks, 0),
            next_stacks=max(resolution.next_stacks, 0),
            effective_magnitude=resolution.effective_magnitude,
            error_code=resolution.error_code,
            expiry_obligation=resolution.expiry_obligation,
        )

    def resolve_dispel(self, *, state: StateDefinition, existing_stacks: int) -> StateActionResolution:
        if existing_stacks <= 0:
            return StateActionResolution(
                accepted=False,
                next_stacks=max(existing_stacks, 0),
                error_code="state_action_source_inactive",
            )
        if not state.dispel_allowed:
            return StateActionResolution(
                accepted=False,
                next_stacks=existing_stacks,
                error_code="state_dispel_not_allowed",
            )
        return StateActionResolution(accepted=True, next_stacks=0)

    def plan_dispel(self, *, state: StateDefinition, existing_stacks: int) -> StateTransitionPlan:
        """Return a pure dispel proposal for the existing owner adapter."""
        resolution = self.resolve_dispel(state=state, existing_stacks=existing_stacks)
        return StateTransitionPlan(
            accepted=resolution.accepted,
            operation="dispel" if resolution.accepted else "reject",
            state_ref=state.state_ref,
            existing_stacks=max(existing_stacks, 0),
            next_stacks=max(resolution.next_stacks, 0),
            error_code=resolution.error_code,
        )

    def resolve_transform(
        self,
        *,
        state: StateDefinition,
        existing_stacks: int,
        target_state_ref: str,
    ) -> StateActionResolution:
        if existing_stacks <= 0:
            return StateActionResolution(
                accepted=False,
                next_stacks=max(existing_stacks, 0),
                error_code="state_action_source_inactive",
            )
        if target_state_ref not in state.transform_targets:
            return StateActionResolution(
                accepted=False,
                next_stacks=existing_stacks,
                error_code="state_transform_target_unregistered",
            )
        return StateActionResolution(accepted=True, next_stacks=1, next_state_ref=target_state_ref)

    def plan_transform(
        self,
        *,
        state: StateDefinition,
        existing_stacks: int,
        target_state_ref: str,
    ) -> StateTransitionPlan:
        """Return a pure transform proposal for the existing owner adapter."""
        resolution = self.resolve_transform(
            state=state,
            existing_stacks=existing_stacks,
            target_state_ref=target_state_ref,
        )
        return StateTransitionPlan(
            accepted=resolution.accepted,
            operation="transform" if resolution.accepted else "reject",
            state_ref=state.state_ref,
            existing_stacks=max(existing_stacks, 0),
            next_stacks=max(resolution.next_stacks, 0),
            next_state_ref=resolution.next_state_ref,
            error_code=resolution.error_code,
        )


__all__ = [
    "EffectApplication",
    "EffectLifecycleEvaluator",
    "EffectResolution",
    "ResistanceProfile",
    "StateActionResolution",
    "StateDefinition",
    "StateTransitionPlan",
]
