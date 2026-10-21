"""Fail-closed admission boundary for the Phase 3 facility repair policy.

The existing ConstructionProductionAuthority repair method is a direct owner
API. This module is the newly designed caller contract; it deliberately does
not invoke that API until authoritative grants, target incarnation, evidence,
and world-time sources are available.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, StrictInt

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import StrictGameplayModel


class FacilityRepairEvidence(StrictGameplayModel):
    tool_refs: tuple[str, ...] = Field(min_length=1)
    material_refs: tuple[str, ...] = Field(min_length=1)
    completion_record_ref: str = Field(min_length=1)
    evidence_revision: str = Field(min_length=1)
    material_quantities: dict[str, StrictInt] = Field(default_factory=dict)
    material_policy_revision: str | None = None


class FacilityRepairGrant(StrictGameplayModel):
    grant_ref: str = Field(min_length=1)
    issuer_ref: str = Field(min_length=1)
    owner_ref: str = Field(min_length=1)
    grantee_ref: str = Field(min_length=1)
    facility_ref: str = Field(min_length=1)
    facility_incarnation: StrictInt | None = Field(default=None, ge=1)
    world_ref: str | None = None
    timeline_ref: str | None = None
    grant_revision: str | None = None
    receipt_ref: str | None = None
    valid_from_world_tick: StrictInt = Field(ge=0)
    valid_until_world_tick: StrictInt | None = Field(default=None, ge=0)
    revoked: bool = False


class FacilityRepairAdmissionRequest(StrictGameplayModel):
    actor_ref: str = Field(min_length=1)
    organization_ref: str | None = None
    designated_role_ref: str | None = None
    facility_ref: str = Field(min_length=1)
    facility_incarnation: StrictInt = Field(ge=1)
    owner_grant: FacilityRepairGrant
    evidence: FacilityRepairEvidence
    world_ref: str = Field(min_length=1)
    timeline_ref: str = Field(min_length=1)
    world_tick: StrictInt = Field(ge=0)
    expected_facility_revision: StrictInt = Field(ge=0)
    facility_source_revision: str = Field(min_length=1)
    membership_source_ref: str | None = None
    read_stream_revisions: dict[str, StrictInt] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=1)


class FacilityRepairAdmissionReceipt(StrictGameplayModel):
    admitted: bool
    status: Literal["deferred", "rejected"]
    zero_write: bool = True
    stop_reason: str
    request_digest: str


class FacilityRepairCaller:
    """Newly designed caller. It records no event while source owners are absent."""

    def __init__(self, *, store: GameplayEventStore):
        self.store = store

    def admit(self, request: FacilityRepairAdmissionRequest) -> FacilityRepairAdmissionReceipt:
        import hashlib
        import json

        digest = "sha256:" + hashlib.sha256(
            json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        grant = request.owner_grant
        if grant.facility_ref != request.facility_ref:
            return FacilityRepairAdmissionReceipt(admitted=False, status="rejected", stop_reason="facility_grant_target_mismatch", request_digest=digest)
        if grant.facility_incarnation is not None and grant.facility_incarnation != request.facility_incarnation:
            return FacilityRepairAdmissionReceipt(admitted=False, status="rejected", stop_reason="facility_incarnation_mismatch", request_digest=digest)
        if (grant.world_ref is not None and grant.world_ref != request.world_ref
                or grant.timeline_ref is not None and grant.timeline_ref != request.timeline_ref):
            return FacilityRepairAdmissionReceipt(admitted=False, status="rejected", stop_reason="facility_grant_scope_mismatch", request_digest=digest)
        if grant.grantee_ref != request.actor_ref:
            return FacilityRepairAdmissionReceipt(admitted=False, status="rejected", stop_reason="facility_grant_actor_mismatch", request_digest=digest)
        if grant.revoked or request.world_tick < grant.valid_from_world_tick or (
            grant.valid_until_world_tick is not None and request.world_tick > grant.valid_until_world_tick
        ):
            return FacilityRepairAdmissionReceipt(admitted=False, status="rejected", stop_reason="facility_grant_invalid", request_digest=digest)
        # Product policy is now explicit, but no real grant/evidence issuer is
        # registered in this repository. Keep the execution gate deferred.
        return FacilityRepairAdmissionReceipt(
            admitted=False, status="deferred", stop_reason="facility_repair_sources_unavailable",
            request_digest=digest,
        )


__all__ = [
    "FacilityRepairEvidence", "FacilityRepairGrant",
    "FacilityRepairAdmissionRequest", "FacilityRepairAdmissionReceipt", "FacilityRepairCaller",
]
