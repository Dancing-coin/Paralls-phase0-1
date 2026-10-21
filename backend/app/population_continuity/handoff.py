from __future__ import annotations

from .member_ledger import PopulationMemberLedger, pending_member_results
from .models import ActivationLock
from .simulation_contracts import CharacterSimulationFrame, IntersectionPacket, simulation_digest


def prepare_intersection(*, frame: CharacterSimulationFrame, ledger: PopulationMemberLedger,
                         trigger_kind: str, target_fidelity: str, lock: ActivationLock) -> IntersectionPacket:
    """纯交接上下文；真实锁、Core 和来源 read-set 由原 Owner 在接纳点重验。"""
    frame = CharacterSimulationFrame.model_validate(frame)
    ledger = PopulationMemberLedger.model_validate(ledger)
    if (type(lock.held_revision) is not int or lock.held_revision < 0 or lock.status != "active"
            or lock.profile_ref != frame.actor_ref or lock.lock_ref != frame.activation_lock_ref
            or lock.lock_ref != f"lock:{lock.world_ref}:{frame.actor_ref}"):
        raise ValueError("handoff_lock_stale")
    member = next((entry for entry in ledger.member_entries if entry.actor_ref == frame.actor_ref), None)
    if member is None or member.lifecycle != "active":
        raise ValueError("handoff_member_not_active")
    participation = frame.participation_resolution
    if (participation.status != "resolved" or target_fidelity not in {"B1", "B2", "B3"}
            or target_fidelity not in participation.allowed_tiers
            or frame.simulation_tick_cursor >= participation.review_tick
            or participation.source_policy_pins != member.participation_policy_pins):
        raise ValueError("handoff_participation_denied")
    own_results = tuple(item for item in ledger.confirmed_results if item.actor_ref == frame.actor_ref)
    if frame.character_core_revision < max(member.entry_character_revision,
            max((item.consumed_core_revision or 0 for item in own_results), default=0)):
        raise ValueError("handoff_core_frame_stale")
    pending = pending_member_results(ledger, actor_ref=frame.actor_ref)
    constraints = tuple(sorted(set(member.protected_field_refs) | set(participation.forbidden_dimensions)))
    codes = tuple(sorted(set(member.protected_code_refs) | set(frame.codebook_refs)))
    identity = simulation_digest(dict(frame_digest=frame.frame_digest, member=member.model_dump(mode="json"),
        pending=pending, cohort_ref=ledger.cohort_ref, trigger_kind=trigger_kind,
        target_fidelity=target_fidelity, lock_ref=lock.lock_ref, lock_revision=lock.held_revision))
    return IntersectionPacket(intersection_ref=f"intersection:{identity}", actor_ref=frame.actor_ref,
        trigger_kind=trigger_kind, group_ref=ledger.cohort_ref,
        last_confirmed_tick=frame.simulation_tick_cursor, continuity_revision=frame.character_core_revision,
        source_revision_vector=frame.source_revision_vector, hard_constraints=constraints, unresolved_proposals=pending,
        required_code_refs=codes, target_fidelity=target_fidelity,
        lock_ref=lock.lock_ref, lock_revision=lock.held_revision)
