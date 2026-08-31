from __future__ import annotations

from app.gameplay import organization_government_runtime
from app.gameplay.government_drought_advisory_presentation import GovernmentDroughtAdvisoryPresentationService
from app.gameplay.organization_government_runtime import GovernmentAuthority
from app.gameplay.ownership_runtime import OwnershipAuthorityService
from app.services.websocket_session_auth_service import WebSocketConnectionContext, WebSocketSessionBinding
from test_inf4u_municipal_drought_assessment_certificate import _intent_for, _setup_completed_assessment


def _request(store, certificate_event_id: str, advisory_event_id: str):
    certificate = store.get_event(certificate_event_id)
    advisory = store.get_event(advisory_event_id)
    values = {
        "certificate_event_id": certificate_event_id,
        "expected_certificate_revision": certificate.stream_revision,
        "expected_ownership_revision": store.get_stream_head("gameplay:ownership"),
        "expected_contract_revision": store.get_stream_head("gameplay:contracts"),
        "expected_advisory_revision": advisory.stream_revision,
        "expected_government_revision": store.get_stream_head(advisory.stream_id),
        "command_id": "command:municipal-drought-acknowledgment:1",
        "idempotency_key": "pending",
        "causation_id": certificate_event_id,
        "correlation_id": "corr:municipal-drought-acknowledgment:1",
        "submitted_at": "2026-08-27T00:00:00Z",
    }
    values["idempotency_key"] = (
        f"government:drought-assessment-acknowledgment:{certificate_event_id}:"
        f"{values['expected_certificate_revision']}:"
        f"{values['expected_contract_revision']}:"
        f"{values['expected_advisory_revision']}:"
        f"{values['expected_government_revision']}:v1"
    )
    intent_type = getattr(
        organization_government_runtime,
        "GovernmentDroughtAssessmentAcknowledgmentIntentV1",
        None,
    )
    assert intent_type is not None, "missing row-specific Government acknowledgment intent"
    return intent_type.model_validate(values)


def test_exact_municipal_certificate_acknowledges_only_authority_government_view() -> None:
    store, advisory_event_id = _setup_completed_assessment()
    certificate = OwnershipAuthorityService(store=store).grant_municipal_drought_assessment_certificate(
        _intent_for(store, advisory_event_id)
    )
    assert certificate.committed
    certificate_event_id = certificate.committed_event_ids[0]
    government = GovernmentAuthority(store=store)
    jurisdiction_ref = store.get_event(advisory_event_id).payload["jurisdiction_ref"]
    project_before = government.drought_advisory_view_for(jurisdiction_ref=jurisdiction_ref)

    result = government.acknowledge_municipal_drought_assessment_certificate(
        _request(store, certificate_event_id, advisory_event_id)
    )

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.government.drought_assessment_acknowledged"
    assert event.visibility_policy == "authority_only"
    authority_view = government.drought_assessment_acknowledgment_view_for(
        jurisdiction_ref=jurisdiction_ref,
        checkpoint_at=event.global_sequence - 1,
    )
    assert authority_view.acknowledgment_refs == (event.payload["acknowledgment_ref"],)
    assert authority_view.source_revision_vector == {
        "gameplay:ownership": 1,
        "gameplay:contracts": store.get_stream_head("gameplay:contracts"),
        store.get_event(advisory_event_id).stream_id: event.stream_revision,
    }
    assert project_before == government.drought_advisory_view_for(jurisdiction_ref=jurisdiction_ref)
    delivered: list[tuple[str, dict[str, object]]] = []
    presentation = GovernmentDroughtAdvisoryPresentationService(
        government=government,
        deliver=lambda session_ref, payload: delivered.append((session_ref, payload)),
    )
    context = WebSocketConnectionContext(
        remote_host="127.0.0.1",
        observed_at=1,
        connection_ref="connection:inf3u",
        binding=WebSocketSessionBinding(
            session_ref="session:inf3u",
            principal_ref="principal:inf3u",
            allowed_actor_refs=(),
            allowed_government_drought_advisory_jurisdiction_refs=(jurisdiction_ref,),
            connection_epoch=1,
            lease_expires_at=10,
        ),
    )
    presentation.subscribe(context=context, jurisdiction_ref=jurisdiction_ref)
    presentation.after_transaction_dispatched(store.read_transactions()[-1])
    assert store.read_transactions()[-1].outbox_entries == []
    assert delivered == []


def test_acknowledgment_duplicate_changed_and_forged_certificate_are_zero_write() -> None:
    store, advisory_event_id = _setup_completed_assessment()
    certificate = OwnershipAuthorityService(store=store).grant_municipal_drought_assessment_certificate(
        _intent_for(store, advisory_event_id)
    )
    assert certificate.committed
    request = _request(store, certificate.committed_event_ids[0], advisory_event_id)
    government = GovernmentAuthority(store=store)
    first = government.acknowledge_municipal_drought_assessment_certificate(request)
    before = store.export_snapshot()

    duplicate = government.acknowledge_municipal_drought_assessment_certificate(request)
    changed = government.acknowledge_municipal_drought_assessment_certificate(
        request.model_copy(update={"correlation_id": "corr:changed"})
    )
    forged = government.acknowledge_municipal_drought_assessment_certificate(
        request.model_copy(update={"certificate_event_id": "event:missing"})
    )

    assert first.committed
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed and changed.failure is not None
    assert not forged.committed and forged.failure is not None
    assert store.export_snapshot() == before


def test_acknowledgment_rejects_private_or_stale_certificate_before_append() -> None:
    store, advisory_event_id = _setup_completed_assessment()
    certificate = OwnershipAuthorityService(store=store).grant_municipal_drought_assessment_certificate(
        _intent_for(store, advisory_event_id)
    )
    assert certificate.committed
    certificate_event_id = certificate.committed_event_ids[0]
    original = store.get_event(certificate_event_id)
    store._events_by_id[certificate_event_id] = original.model_copy(
        update={"visibility_policy": "project"}, deep=True
    )
    before = store.export_snapshot()

    result = GovernmentAuthority(store=store).acknowledge_municipal_drought_assessment_certificate(
        _request(store, certificate_event_id, advisory_event_id)
    )

    assert not result.committed and result.failure is not None
    assert store.export_snapshot() == before


def test_acknowledgment_rejects_stale_government_head_before_append() -> None:
    store, advisory_event_id = _setup_completed_assessment()
    certificate = OwnershipAuthorityService(store=store).grant_municipal_drought_assessment_certificate(
        _intent_for(store, advisory_event_id)
    )
    assert certificate.committed
    request = _request(store, certificate.committed_event_ids[0], advisory_event_id)
    before = store.export_snapshot()

    result = GovernmentAuthority(store=store).acknowledge_municipal_drought_assessment_certificate(
        request.model_copy(update={"expected_government_revision": 2})
    )

    assert not result.committed and result.failure is not None
    assert store.export_snapshot() == before
