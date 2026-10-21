from app.gameplay.event_store import GameplayEventStore
from app.gameplay.facility_repair_admission import (
    FacilityRepairCaller, FacilityRepairEvidence, FacilityRepairGrant,
    FacilityRepairAdmissionRequest,
)


def _request(**changes):
    values = dict(
        actor_ref="character:worker", organization_ref="org:bakery",
        designated_role_ref="role:maintenance", facility_ref="facility:bakery",
        facility_incarnation=2,
        owner_grant=FacilityRepairGrant(
            grant_ref="grant:repair:1", issuer_ref="owner-issuer:missing",
            owner_ref="org:bakery", grantee_ref="character:worker",
            facility_ref="facility:bakery", valid_from_world_tick=0,
        ),
        evidence=FacilityRepairEvidence(
            tool_refs=("tool:wrench",), material_refs=("material:steel",),
            completion_record_ref="completion:1", evidence_revision="evidence:v1",
        ),
        world_ref="world:bakery", timeline_ref="timeline:main", world_tick=4,
        expected_facility_revision=3, facility_source_revision="facility:v2",
        idempotency_key="repair:1",
    )
    values.update(changes)
    return FacilityRepairAdmissionRequest(**values)


def test_repair_admission_is_fail_closed_without_real_issuers_and_writes_nothing():
    store = GameplayEventStore()
    before = store.export_snapshot()
    result = FacilityRepairCaller(store=store).admit(_request())
    assert not result.admitted and result.status == "deferred"
    assert result.stop_reason == "facility_repair_sources_unavailable"
    assert result.zero_write
    assert store.export_snapshot() == before


def test_repair_admission_rejects_target_or_grant_mismatch_before_source_lookup():
    caller = FacilityRepairCaller(store=GameplayEventStore())
    result = caller.admit(_request(facility_ref="facility:other"))
    assert result.status == "rejected"
    assert result.stop_reason == "facility_grant_target_mismatch"
    result = caller.admit(_request(owner_grant=_request().owner_grant.model_copy(update={"grantee_ref": "character:other"})))
    assert result.stop_reason == "facility_grant_actor_mismatch"


def test_repair_admission_rejects_expired_or_revoked_grant():
    caller = FacilityRepairCaller(store=GameplayEventStore())
    grant = _request().owner_grant.model_copy(update={"valid_until_world_tick": 3})
    assert caller.admit(_request(owner_grant=grant)).stop_reason == "facility_grant_invalid"
    grant = _request().owner_grant.model_copy(update={"revoked": True})
    assert caller.admit(_request(owner_grant=grant)).stop_reason == "facility_grant_invalid"
