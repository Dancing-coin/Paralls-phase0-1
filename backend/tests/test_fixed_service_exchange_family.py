from __future__ import annotations

import pytest

from app.gameplay.closed_generic_gameplay_families import FixedServiceExchangeIntent
from test_inf2ad_municipal_drought_assessment_exchange import (
    OUTCOME as MUNICIPAL_OUTCOME,
    PROVIDER as MUNICIPAL_PROVIDER,
    RECEIVER as MUNICIPAL_RECEIVER,
    _setup as _municipal_setup,
)
from test_inf2ag_public_workshop_service_exchange import (
    OUTCOME as WORKSHOP_OUTCOME,
    PROVIDER as WORKSHOP_PROVIDER,
    _setup as _workshop_setup,
)


def _intent() -> FixedServiceExchangeIntent:
    return FixedServiceExchangeIntent(
        proposal_digest="proposal:fixed-service-family:1",
        command_id="command:fixed-service-family",
        causation_id="cause:fixed-service-family",
        correlation_id="corr:fixed-service-family",
    )


def _prepared_setup(setup):
    prepared = setup()
    if len(prepared) == 2:
        store, economy = prepared
        return store, economy
    store, economy, _completed = prepared
    return store, economy


@pytest.mark.parametrize(
    ("setup", "expected_package_revision", "expected_outcome_ref", "expected_provider_ref", "expected_receiver_ref"),
    [
        (
            _workshop_setup,
            "package:industrial-facilities:v5",
            WORKSHOP_OUTCOME,
            WORKSHOP_PROVIDER,
            "organization:mill",
        ),
        (
            _municipal_setup,
            "package:municipal-drought-services:v1",
            MUNICIPAL_OUTCOME,
            MUNICIPAL_PROVIDER,
            MUNICIPAL_RECEIVER,
        ),
    ],
)
def test_fixed_service_exchange_uses_same_adapter_for_distinct_completed_service_packages(
    setup,
    expected_package_revision: str,
    expected_outcome_ref: str,
    expected_provider_ref: str,
    expected_receiver_ref: str,
) -> None:
    store, economy = _prepared_setup(setup)

    intent = _intent().model_copy(
        update={
            "proposal_digest": f"proposal:{expected_package_revision}",
            "command_id": f"command:{expected_package_revision}",
            "causation_id": f"cause:{expected_package_revision}",
            "correlation_id": f"corr:{expected_package_revision}",
        }
    )
    result = economy.settle_fixed_service_exchange(intent=intent)

    assert result.committed
    events = [store.get_event(event_id) for event_id in result.committed_event_ids]
    assert events[-1].event_type == "gameplay.economy.package_declared_negotiated_exchange_settled"
    assert events[-1].payload["family_ref"] == "fixed_service_exchange@1"
    assert events[-1].payload["package_revision_id"] == expected_package_revision
    assert events[-1].payload["outcome_ref"] == expected_outcome_ref
    assert events[-1].payload["provider_ref"] == expected_provider_ref
    assert events[-1].payload["receiver_ref"] == expected_receiver_ref
    assert events[-1].payload["amount_minor"] == 12


def test_fixed_service_exchange_rejects_caller_party_price_and_authority_coordinates() -> None:
    with pytest.raises(Exception):
        FixedServiceExchangeIntent.model_validate(
            {
                "proposal_digest": "proposal:fixed-service-family:1",
                "command_id": "command:fixed-service-family",
                "causation_id": "cause:fixed-service-family",
                "correlation_id": "corr:fixed-service-family",
                "provider_ref": "caller-provider",
                "receiver_ref": "caller-receiver",
                "amount_minor": 99,
                "currency_ref": "currency:caller",
            }
        )


def test_fixed_service_exchange_replays_duplicate_and_rejects_changed_duplicate() -> None:
    store, economy = _prepared_setup(_workshop_setup)
    intent = _intent()
    first = economy.settle_fixed_service_exchange(intent=intent)
    before = tuple(store.read_events())

    duplicate = economy.settle_fixed_service_exchange(intent=intent)
    changed = economy.settle_fixed_service_exchange(
        intent=intent.model_copy(update={"correlation_id": "corr:fixed-service:changed"})
    )
    full = economy.package_declared_negotiated_exchange_projection(scope="authority")
    tail = economy.package_declared_negotiated_exchange_projection(scope="authority", checkpoint_at=store.read_events()[-1].global_sequence)

    assert duplicate.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert not changed.committed
    assert changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert tuple(store.read_events()) == before
    assert full == tail
