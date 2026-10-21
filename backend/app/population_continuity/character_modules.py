"""固定农民模块只生成候选，所有实际状态仍由原 Owner/Core 接纳。"""
from app.gameplay.runtime_state import StateGroupDefinition
import math

from .continuous import advance_b0_row
from .simulation_contracts import (
    ActionCandidatePayload, ActivityCandidatePayload, CharacterSimulationFrame, ContinuityDeltaPayload,
    ModuleDefinition, ModuleFieldPolicy, ModuleProposal, UpgradeRequestPayload, simulation_digest,
)
from .simulation_frame import validate_module_proposal


_FIELDS = {
    "identity": ("profile_ref", "protected_refs"),
    "needs": ("fatigue", "need_pressure", "revision"),
    "schedule": ("routine_allowed", "confirmed_refs"),
    "household": ("care_obligation", "protected_refs"),
    "supply": ("shortage",), "situation": ("road_risk",),
    "affect": ("public_pressure",), "behavior": ("routine_allowed",),
}


def farmer_module_definitions() -> tuple[ModuleDefinition, ...]:
    result = []
    for category, fields in _FIELDS.items():
        public = fields if category in {"needs", "situation", "affect"} else ()
        result.append(ModuleDefinition(module_ref=category, category=category, definition_version="1",
            input_selectors=tuple(f"{category}.{name}" for name in fields),
            state_schema=StateGroupDefinition(group_id=category, definition_version="1",
                projection_schema_version=1, shared_fields=fields, population_allowed_fields=public),
            supported_tiers=("B0", "B1", "B2", "B3"),
            proposal_kinds=("continuity_delta", "activity_candidate", "action_candidate", "upgrade_request", "decision_conflict"),
            aggregation_policy="public_fields_only" if public else "none",
            upgrade_triggers=("care_obligation", "road_review"),
            capability_refs=("population:schedule-gated-supply:v1",) if category == "supply" else (),
            field_policies={name: ModuleFieldPolicy(aggregatable=True, individual_only=False) for name in public},
        ))
    return tuple(result)


def evaluate_modules(frame: CharacterSimulationFrame, *, to_tick: int) -> tuple[ModuleProposal, ...]:
    try:
        frame = CharacterSimulationFrame.model_validate(frame)
    except ValueError as exc:
        raise ValueError("module_frame_invalid") from exc
    if type(to_tick) is not int or to_tick <= frame.simulation_tick_cursor:
        raise ValueError("module_window_invalid")
    participation = frame.participation_resolution
    tier = participation.recommended_tier
    if participation.status != "resolved" or to_tick >= participation.review_tick:
        raise ValueError("module_participation_stale")
    states = frame.module_states
    if set(states) != set(participation.allowed_modules):
        raise ValueError("module_context_insufficient")
    needs = states.get("needs", {})
    for field in ("fatigue", "need_pressure"):
        value = needs.get(field)
        if type(value) not in {int, float} or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError("module_needs_context_insufficient")
    revision = needs.get("revision")
    if type(revision) is not int or revision < 0:
        raise ValueError("module_needs_context_insufficient")
    definitions = {item.module_ref: item for item in farmer_module_definitions()}
    proposals = []

    def propose(module, payload, fidelity=tier):
        deadline = participation.review_tick
        if fidelity == "B0":
            deadline = min(deadline, participation.b0_expiry_tick)
        identity = simulation_digest((frame.frame_digest, module, payload.model_dump(mode="json"), to_tick))
        proposal = ModuleProposal(proposal_ref=f"module:{identity}", actor_ref=frame.actor_ref,
            module_ref=module, definition_version="1", frame_digest=frame.frame_digest,
            proposal_kind=payload.kind, typed_payload=payload, read_dependencies=frame.source_revision_vector,
            required_fidelity=fidelity, expiry_tick=deadline, source_ref="rules:farmer@1",
            idempotency_key=f"module:{identity}")
        proposals.append(validate_module_proposal(proposal=proposal, definition=definitions[module],
            frame=frame, tick=to_tick))

    advanced = advance_b0_row(actor_id=frame.actor_ref, row={**dict(needs),
        "last_update_tick": frame.simulation_tick_cursor},
        window_start=frame.simulation_tick_cursor, window_end=to_tick)
    propose("needs", ContinuityDeltaPayload(expected_group_revision=revision,
        state_delta={field: advanced.values[field] for field in ("fatigue", "need_pressure")}))
    care = states["household"].get("care_obligation")
    shortage = states["supply"].get("shortage")
    routine = states["schedule"].get("routine_allowed")
    if any(type(value) is not bool for value in (care, shortage, routine)):
        raise ValueError("module_context_insufficient")
    if care:
        target = next((item for item in ("B2", "B3") if item in participation.allowed_tiers), None)
        if target is None:
            raise ValueError("module_protected_conflict")
        propose("household", UpgradeRequestPayload(trigger_ref="care_obligation", target_fidelity=target), target)
    elif routine:
        propose("behavior", ActivityCandidatePayload(activity_ref=advanced.values["activity_phase"]))
    if shortage:
        propose("supply", ActionCandidatePayload(intent_ref=f"intent:supply:{frame.actor_ref}:{to_tick}",
            capability_ref="population:schedule-gated-supply:v1"))
    return tuple(sorted(proposals, key=lambda item: item.proposal_ref))
