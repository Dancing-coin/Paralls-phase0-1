from __future__ import annotations

from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.population_continuity.domain_projection_sources import production_work_population_projections
from app.population_continuity.models import BatchIntentCandidate
from app.population_continuity.owner_adapters import OrganizationProductionWorkContributionOwnerExecutor
from app.population_continuity.siming_contracts import PopulationCadenceInput, PopulationProjection, PopulationReadSet
from app.services.siming_population_capability import PopulationSimulationCapability


def _event(**payload: object) -> AuthorityEvent:
    return AuthorityEvent(
        event_id="event:evidence:1", event_type="gameplay.construction_production.work_completion_evidence_recorded",
        producer_ts=100, room_id="room:bakery", scene_id="scene:bakery", zone_id="zone:bakery",
        source=AuthorityEventSource(layer="gameplay", system="production"),
        routing=AuthorityEventRouting(audience_mode="actor", routing_mode="event_type"),
        priority="p1", durability="replayable", causation_id="cause:1", correlation_id="corr:1",
        payload={
            "committed": True, "stream_ref": "gameplay:construction_production:facility:oven",
            "stream_revision": 1, "visibility_policy": "actor:character:worker",
            "evidence_kind": "production-completed", "outcome": "completed", "verification_state": "verified",
            "organization_ref": "org:bakery", "actor_ref": "character:worker",
            "assignment_ref": "assignment:1", "work_order_ref": "work-order:1", "facility_ref": "facility:oven",
            "observed_at": "2026-08-27T12:00:00Z", **payload,
        },
    )


def _organization_projection() -> dict[str, object]:
    return {
        "scope": "organization:summary", "organization_ref": "org:bakery",
        "source_revision_vector": {"gameplay:organization:org:bakery": 2},
        "schedule_event_id": "event:schedule:1", "schedule_event_revision": 2,
        "schedule": {"recipient_ref": "character:worker", "assignment_ref": "assignment:1", "work_order_ref": "work-order:1"},
    }


def _cadence() -> PopulationCadenceInput:
    return PopulationCadenceInput(
        cadence_id="cadence:production:1", world_ref="world:bakery", world_mode_ref="mode:bakery",
        world_mode_revision="mode:v1", cadence_source_ref="world:bakery", cadence_source_revision=1,
        window_start=100, window_end=101, base_checkpoint_ref="checkpoint:1", base_checkpoint_digest="sha256:cp",
        base_revision_vector={"world:bakery": 1}, policy_revision="policy:population:v1",
        selector_revision="selector:population:v1", ruleset_revision="rules:population:v1", deterministic_seed="seed:1",
        catch_up_limit=1, budget=1, report_scope="organization:summary",
    )


def test_committed_production_evidence_becomes_scoped_population_candidate() -> None:
    projections = production_work_population_projections(
        committed_events=(_event(),), organization_projection=_organization_projection(), scope="organization:summary"
    )
    assert len(projections) == 1
    assert projections[0].payload["candidate_kind"] == "organization_production_work_contribution"
    assert projections[0].revision_vector["gameplay:organization:org:bakery"] == 2


def test_selected_production_candidate_reaches_organization_owner() -> None:
    class Owner:
        def submit(self, intent, *, read_set):
            from app.population_continuity.siming_contracts import PopulationOwnerReceipt
            return PopulationOwnerReceipt(receipt_ref="receipt:1", owner_ref="actor_gameplay.organization_domain", event_family="gameplay.organization.production_work_contribution_accepted", committed=True, revision_vector={"gameplay:organization:org:bakery": 3}, zero_write=False)

    projection = production_work_population_projections(committed_events=(_event(),), organization_projection=_organization_projection(), scope="organization:summary")[0]
    read_set = PopulationReadSet.from_inputs(_cadence(), (projection,))
    result = PopulationSimulationCapability(owner_executors={"population:organization-production-work-contribution:v1": Owner()}).run_default_decision_cycle(read_set.cadence, read_set)
    assert result.status == "accepted"
    assert result.owner_receipts[0].event_family == "gameplay.organization.production_work_contribution_accepted"


def test_missing_or_stale_production_evidence_is_zero_write() -> None:
    assert production_work_population_projections(committed_events=(), organization_projection=_organization_projection(), scope="organization:summary") == ()
    assert production_work_population_projections(committed_events=(_event(committed=False),), organization_projection=_organization_projection(), scope="organization:summary") == ()


def test_duplicate_production_owner_intent_replays_receipt_without_append() -> None:
    class Authority:
        def accept_production_work_contribution(self, **kwargs):
            from types import SimpleNamespace
            return SimpleNamespace(committed=True, committed_event_ids=["event:accepted:1"], resulting_stream_revisions={"gameplay:organization:org:bakery": 3}, idempotency_status="duplicate_replayed")

    projection = production_work_population_projections(committed_events=(_event(),), organization_projection=_organization_projection(), scope="organization:summary")[0]
    read_set = PopulationReadSet.from_inputs(_cadence(), (projection,))
    receipt = OrganizationProductionWorkContributionOwnerExecutor(authority=Authority()).submit(
        BatchIntentCandidate(intent_ref="candidate:1", profile_ref="character:worker", intent_kind="organization_production_work_contribution", payload=projection.payload, expected_revisions=projection.revision_vector, policy_revision="policy:population:v1", package_revision="population:organization-production-work-contribution:v1", idempotency_key="caller-key", correlation_id="cadence:production:1", source_ref=projection.ref, privacy_scope="organization:summary"), read_set=read_set
    )
    assert receipt.committed and receipt.idempotency_status == "duplicate_replayed" and receipt.zero_write


def test_owner_rejection_stops_character_continuity_command() -> None:
    class RejectingOwner:
        def submit(self, intent, *, read_set):
            from app.population_continuity.siming_contracts import PopulationOwnerReceipt
            return PopulationOwnerReceipt(receipt_ref="rejected:1", owner_ref="actor_gameplay.organization_domain", event_family="gameplay.organization.production_work_contribution_accepted", committed=False, revision_vector={}, zero_write=True)

    projection = production_work_population_projections(committed_events=(_event(),), organization_projection=_organization_projection(), scope="organization:summary")[0]
    result = PopulationSimulationCapability(owner_executors={"population:organization-production-work-contribution:v1": RejectingOwner()}).run_default_decision_cycle(_cadence(), PopulationReadSet.from_inputs(_cadence(), (projection,)))
    assert result.status == "requeue"
    assert result.continuity_receipts == ()
