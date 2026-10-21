"""Explicit capability intersection; no engine capabilities are inferred here."""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal


Determinism = Literal["best_effort", "replay_deterministic", "rollback_deterministic"]
_DETERMINISM = {"best_effort": 0, "replay_deterministic": 1, "rollback_deterministic": 2}


@dataclass(frozen=True)
class AdapterDescriptor:
    adapter_ref: str
    revision: str
    clock_mapping_refs: tuple[str, ...]
    evidence_types: tuple[str, ...]
    snapshot_scope: tuple[str, ...]
    determinism: Determinism
    max_lateness: int
    replay_supported: bool
    entity_binding_ref: str
    rollback_horizon: int
    invalidation_policy_ref: str

    def __post_init__(self) -> None:
        if (not all((self.adapter_ref, self.revision, self.entity_binding_ref))
                or self.determinism not in _DETERMINISM or self.max_lateness < 0
                or self.rollback_horizon < 0 or self.invalidation_policy_ref != "stop_confirmation"):
            raise ValueError("adapter_descriptor_not_admitted")


@dataclass(frozen=True)
class AdapterRequirement:
    clock_mapping_refs: tuple[str, ...]
    evidence_types: tuple[str, ...]
    snapshot_scope: tuple[str, ...]
    determinism: Determinism
    max_lateness: int
    replay_required: bool
    rollback_horizon: int

    def __post_init__(self) -> None:
        if (self.determinism not in _DETERMINISM or self.max_lateness < 0 or self.rollback_horizon < 0):
            raise ValueError("adapter_requirement_invalid")


@dataclass(frozen=True)
class AdapterAdmission:
    admitted: bool
    descriptors: tuple[AdapterDescriptor, ...]
    diagnostics: tuple[str, ...]
    faulted_adapter_refs: tuple[str, ...] = ()

    def can_confirm(self, current: tuple[AdapterDescriptor, ...]) -> bool:
        return self.admitted and not self.faulted_adapter_refs and (
            {d.adapter_ref: d for d in current} == {d.adapter_ref: d for d in self.descriptors}
            and len(current) == len(self.descriptors))

    def invalidate(self, *, adapter_ref: str, reason: str) -> AdapterAdmission:
        if adapter_ref not in {d.adapter_ref for d in self.descriptors} or not reason:
            raise ValueError("adapter_fault_identity_invalid")
        return replace(self, admitted=False, diagnostics=self.diagnostics + (reason,),
                       faulted_adapter_refs=tuple(sorted(set(self.faulted_adapter_refs) | {adapter_ref})))

    def recover(self, current: tuple[AdapterDescriptor, ...], *, requirement: AdapterRequirement) -> AdapterAdmission:
        old = {d.adapter_ref: d for d in self.descriptors}
        new = {d.adapter_ref: d for d in current}
        if any(ref not in new or new[ref].revision == old[ref].revision
               or new[ref].clock_mapping_refs == old[ref].clock_mapping_refs
               for ref in self.faulted_adapter_refs):
            return replace(self, diagnostics=self.diagnostics + ("adapter_recovery_new_revision_mapping_required",))
        return admit_adapters(current, requirement=requirement)


def admit_adapters(descriptors: tuple[AdapterDescriptor, ...], *, requirement: AdapterRequirement) -> AdapterAdmission:
    diagnostics: list[str] = []
    if not descriptors or len({d.adapter_ref for d in descriptors}) != len(descriptors):
        diagnostics.append("adapter_participants_invalid")
    for descriptor in descriptors:
        for required, supported, error in (
            (requirement.clock_mapping_refs, descriptor.clock_mapping_refs, "adapter_clock_mapping_missing"),
            (requirement.evidence_types, descriptor.evidence_types, "adapter_evidence_missing"),
            (requirement.snapshot_scope, descriptor.snapshot_scope, "adapter_snapshot_scope_missing"),
        ):
            if not set(required).issubset(supported):
                diagnostics.append(error)
        if _DETERMINISM[descriptor.determinism] < _DETERMINISM[requirement.determinism]:
            diagnostics.append("adapter_determinism_unsupported")
        if descriptor.max_lateness < requirement.max_lateness:
            diagnostics.append("adapter_lateness_unsupported")
        if requirement.replay_required and not descriptor.replay_supported:
            diagnostics.append("adapter_replay_unsupported")
        if descriptor.rollback_horizon < requirement.rollback_horizon:
            diagnostics.append("adapter_rollback_horizon_unsupported")
    return AdapterAdmission(not diagnostics, descriptors, tuple(dict.fromkeys(diagnostics)))
