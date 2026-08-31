from __future__ import annotations

import pytest

from app.gameplay.ownership_runtime import MunicipalDroughtAssessmentCertificateIntentV1, OwnershipAuthorityService, OwnershipProjector
from app.gameplay.ownership_runtime import OwnershipRuntimeError
from test_inf3s_government_drought_assessment_contract import _contracts, _request
from test_inf3t_municipal_drought_assessment_fulfillment import _request as _fulfillment_request
from test_infra_weather_front_government_drought_advisory import JURISDICTION, _intent, _setup


def _setup_completed_assessment():
    store, _ecology, government, weather_event_id = _setup()
    advisory = government.issue_drought_advisory(_intent(store, weather_event_id))
    assert advisory.committed
    contracts = _contracts(store)
    contract = contracts.create_municipal_drought_assessment_from_advisory(
        _request(store, advisory.committed_event_ids[0])
    )
    assert contract.committed
    contract_event = store.get_event(contract.committed_event_ids[0])
    assert contracts.fulfill_municipal_drought_assessment_by_policy(
        _fulfillment_request(store, contract_event.event_id)
    ).committed
    return store, advisory.committed_event_ids[0]


def _intent_for(store, advisory_event_id: str, **updates: object) -> MunicipalDroughtAssessmentCertificateIntentV1:
    contract_revision = store.get_stream_head("gameplay:contracts")
    ownership_revision = store.get_stream_head("gameplay:ownership")
    values: dict[str, object] = {
        "advisory_event_id": advisory_event_id,
        "expected_contract_revision": contract_revision,
        "expected_ownership_revision": ownership_revision,
        "command_id": "command:municipal-drought-certificate:1",
        "idempotency_key": "pending",
        "causation_id": advisory_event_id,
        "correlation_id": "corr:municipal-drought-certificate:1",
        "submitted_at": "2026-08-26T00:00:00Z",
    }
    values.update(updates)
    contract_id = f"contract:municipal-drought-assessment:{JURISDICTION}:{advisory_event_id}"
    values["idempotency_key"] = f"ownership:municipal-drought-assessment-certificate:{contract_id}:{values['expected_contract_revision']}:{values['expected_ownership_revision']}:v1"
    return MunicipalDroughtAssessmentCertificateIntentV1.model_validate(values)


def test_completed_municipal_assessment_grants_one_fixed_certificate_title() -> None:
    store, advisory_event_id = _setup_completed_assessment()
    ownership = OwnershipAuthorityService(store=store)

    result = ownership.grant_municipal_drought_assessment_certificate(_intent_for(store, advisory_event_id))

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    contract_id = f"contract:municipal-drought-assessment:{JURISDICTION}:{advisory_event_id}"
    assert event.event_type == "gameplay.ownership.right_granted"
    assert event.visibility_policy == "authority_only"
    assert event.payload == {
        "right_id": f"right:municipal-drought-assessment-certificate:{contract_id}",
        "asset_ref": f"asset:municipal-drought-assessment-certificate:{contract_id}",
        "holder_ref": "organization:district-works",
        "contract_id": contract_id,
        "advisory_event_id": advisory_event_id,
    }
    assert OwnershipProjector().rebuild(store.read_events()) == OwnershipProjector().rebuild(
        store.read_events(), checkpoint_at=event.global_sequence
    )


def test_incomplete_or_changed_certificate_request_is_zero_write() -> None:
    store, advisory_event_id = _setup_completed_assessment()
    ownership = OwnershipAuthorityService(store=store)
    request = _intent_for(store, advisory_event_id)
    first = ownership.grant_municipal_drought_assessment_certificate(request)
    before = store.export_snapshot()

    stale = ownership.grant_municipal_drought_assessment_certificate(
        _intent_for(store, advisory_event_id, expected_contract_revision=1)
    )
    changed = ownership.grant_municipal_drought_assessment_certificate(
        request.model_copy(update={"correlation_id": "corr:changed"})
    )

    assert first.committed
    assert not stale.committed and stale.failure is not None
    assert not changed.committed and changed.failure is not None
    assert changed.failure.error_code == "idempotency_key_reused"
    assert store.export_snapshot() == before


def test_generic_initial_title_cannot_reserve_municipal_certificate_identity() -> None:
    store, advisory_event_id = _setup_completed_assessment()
    contract_id = f"contract:municipal-drought-assessment:{JURISDICTION}:{advisory_event_id}"
    asset_ref = f"asset:municipal-drought-assessment-certificate:{contract_id}"
    right_id = f"right:municipal-drought-assessment-certificate:{contract_id}"
    before = store.export_snapshot()

    with pytest.raises(OwnershipRuntimeError, match="municipal_certificate_row_required"):
        OwnershipAuthorityService(store=store).grant_initial_title(
            command_id="command:generic-municipal-certificate",
            asset_ref=asset_ref,
            holder_ref="organization:district-works",
            right_id=right_id,
            idempotency_key="generic-municipal-certificate",
            causation_id=advisory_event_id,
            correlation_id="corr:generic-municipal-certificate",
        )

    assert store.export_snapshot() == before


def test_generic_transfer_cannot_move_municipal_certificate_title() -> None:
    store, advisory_event_id = _setup_completed_assessment()
    ownership = OwnershipAuthorityService(store=store)
    certificate = ownership.grant_municipal_drought_assessment_certificate(
        _intent_for(store, advisory_event_id)
    )
    assert certificate.committed
    event = store.get_event(certificate.committed_event_ids[0])
    before = store.export_snapshot()

    with pytest.raises(OwnershipRuntimeError, match="municipal_certificate_title_transfer_forbidden"):
        ownership.transfer_title(
            command_id="command:generic-municipal-certificate-transfer",
            asset_ref=str(event.payload["asset_ref"]),
            right_id=str(event.payload["right_id"]),
            from_holder_ref="organization:district-works",
            to_holder_ref="organization:other",
            idempotency_key="generic-municipal-certificate-transfer",
            causation_id=event.event_id,
            correlation_id="corr:generic-municipal-certificate-transfer",
        )

    assert store.export_snapshot() == before


def test_package_exchange_fragment_cannot_transfer_municipal_certificate_title() -> None:
    store, advisory_event_id = _setup_completed_assessment()
    ownership = OwnershipAuthorityService(store=store)
    certificate = ownership.grant_municipal_drought_assessment_certificate(
        _intent_for(store, advisory_event_id)
    )
    assert certificate.committed
    event = store.get_event(certificate.committed_event_ids[0])
    before = store.export_snapshot()

    with pytest.raises(OwnershipRuntimeError, match="municipal_certificate_title_transfer_forbidden"):
        ownership.build_package_declared_negotiated_exchange_fragment(
            provider_holder_ref="organization:district-works",
            receiver_holder_ref="organization:other",
            source_ref=certificate.committed_event_ids[0],
            asset_ref=str(event.payload["asset_ref"]),
            outcome_ref="outcome:package-declared-negotiated-exchange@1",
            package_revision="package:other:v1",
            expected_revision=store.get_stream_head("gameplay:ownership"),
        )

    assert store.export_snapshot() == before
