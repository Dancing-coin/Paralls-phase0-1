from __future__ import annotations

from collections.abc import Mapping

from .siming_contracts import PopulationReadSet
from .simulation_contracts import (
    ActionCandidatePayload, CharacterSimulationFrame, ContinuityDeltaPayload, ModuleDefinition,
    ModuleProposal, ParticipationResolution, UpgradeRequestPayload,
)


def build_simulation_frame(
    *, actor_ref: str, profile_ref: str, profile_revision: str,
    character_revision: int, tick_cursor: int, read_set: PopulationReadSet,
    module_states: Mapping[str, Mapping[str, object]], participation: ParticipationResolution,
    codebook_refs: tuple[str, ...], activation_lock_ref: str | None,
    module_definitions: tuple[ModuleDefinition, ...] = (),
) -> CharacterSimulationFrame:
    observed_tick = read_set.cadence.window_end
    if participation.status == "resolved" and (
        observed_tick >= participation.review_tick
        or ("B0" in participation.allowed_tiers and observed_tick >= participation.b0_expiry_tick)
    ):
        raise ValueError("frame_participation_stale")
    # 旧 read-set 仍可变；新帧只接受当前实际内容与原摘要相符的输入。
    current = PopulationReadSet.from_inputs(read_set.cadence, read_set.projections)
    if current.read_set_digest != read_set.read_set_digest:
        raise ValueError("frame_read_set_digest_invalid")
    revisions: dict[str, int] = {}
    for vector in (read_set.cadence.base_revision_vector, read_set.cadence.source_revision_vector,
                   *(projection.revision_vector for projection in current.projections)):
        for ref, revision in vector.items():
            if ref in revisions and revisions[ref] != revision:
                raise ValueError("frame_source_revision_conflict")
            revisions[ref] = revision
    definitions = {definition.module_ref: definition for definition in module_definitions}
    if len(definitions) != len(module_definitions):
        raise ValueError("frame_module_definition_duplicate")
    for module_ref, state in module_states.items():
        definition = definitions.get(module_ref)
        if definition is None:
            raise ValueError("frame_module_not_declared")
        if not set(state).issubset(definition.state_schema.shared_fields):
            raise ValueError("frame_module_field_not_declared")
    return CharacterSimulationFrame(
        actor_ref=actor_ref, profile_ref=profile_ref, profile_revision=profile_revision,
        character_core_revision=character_revision, simulation_tick_cursor=tick_cursor,
        source_revision_vector=revisions, module_states=module_states,
        domain_fact_refs=tuple(projection.ref for projection in current.projections),
        participation_resolution=participation, codebook_refs=codebook_refs,
        activation_lock_ref=activation_lock_ref, read_set_digest=current.read_set_digest,
    )


def validate_module_proposal(
    *, proposal: ModuleProposal, definition: ModuleDefinition, frame: CharacterSimulationFrame, tick: int,
) -> ModuleProposal:
    proposal = ModuleProposal.model_validate(proposal)
    if type(tick) is not int or tick < 0:
        raise ValueError("proposal_tick_invalid")
    if proposal.actor_ref != frame.actor_ref or proposal.cohort_ref is not None:
        raise ValueError("proposal_actor_mismatch")
    if proposal.frame_digest != frame.frame_digest:
        raise ValueError("proposal_frame_mismatch")
    if proposal.module_ref != definition.module_ref or proposal.definition_version != definition.definition_version:
        raise ValueError("proposal_definition_mismatch")
    if proposal.proposal_kind not in definition.proposal_kinds:
        raise ValueError("proposal_kind_not_declared")
    participation = frame.participation_resolution
    if participation.status != "resolved" or proposal.module_ref not in participation.allowed_modules:
        raise ValueError("proposal_module_denied")
    if proposal.required_fidelity not in participation.allowed_tiers or proposal.required_fidelity not in definition.supported_tiers:
        raise ValueError("proposal_fidelity_denied")
    if proposal.read_dependencies != frame.source_revision_vector:
        raise ValueError("proposal_read_dependencies_mismatch")
    if tick >= proposal.expiry_tick:
        raise ValueError("proposal_expired")
    deadline = participation.review_tick
    if proposal.required_fidelity == "B0":
        deadline = min(deadline, participation.b0_expiry_tick)
    if proposal.expiry_tick > deadline:
        raise ValueError("proposal_policy_deadline_exceeded")
    payload = proposal.typed_payload
    if isinstance(payload, ContinuityDeltaPayload):
        if not set(payload.state_delta).issubset(definition.state_schema.shared_fields):
            raise ValueError("proposal_module_field_not_declared")
        for field in payload.state_delta:
            if f"{definition.module_ref}.{field}" in participation.forbidden_dimensions:
                raise ValueError("proposal_dimension_denied")
            if definition.field_policy(field).group_summary_only:
                raise ValueError("proposal_individual_field_denied")
    elif isinstance(payload, ActionCandidatePayload):
        if payload.capability_ref not in definition.capability_refs:
            raise ValueError("proposal_capability_not_declared")
    elif isinstance(payload, UpgradeRequestPayload):
        if payload.target_fidelity != proposal.required_fidelity:
            raise ValueError("proposal_upgrade_fidelity_mismatch")
        if payload.trigger_ref not in (*definition.upgrade_triggers, *participation.upgrade_triggers):
            raise ValueError("proposal_trigger_not_declared")
    return proposal
