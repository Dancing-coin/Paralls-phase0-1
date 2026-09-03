from __future__ import annotations

import pytest

from app.gameplay.closed_generic_gameplay_families import FixedServiceExchangeIntent
from app.gameplay.patch_runtime import GameplayPatchManifest, GameplayPatchRegistry
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


def test_fixed_service_exchange_bounded_price_without_amount_fails_closed() -> None:
    store, economy = _prepared_setup(_workshop_setup)
    registry = economy._package_registry
    assert registry is not None
    revision = "package:industrial-facilities:v5"
    manifest = registry.candidate(revision)
    outcome = manifest.economic_outcomes[0]
    bounded_policy = outcome.price_policy.model_copy(
        update={"fixed_amount": None, "minimum_amount": 1, "maximum_amount": 2},
        deep=True,
    )
    bounded_manifest = manifest.model_copy(
        update={
            "economic_outcomes": (outcome.model_copy(update={"price_policy": bounded_policy}, deep=True),),
        },
        deep=True,
    )
    bounded_manifest = bounded_manifest.model_copy(
        update={"content_digest": bounded_manifest.expected_content_digest()}, deep=True
    )
    registry._candidates[revision] = bounded_manifest
    before = store.export_snapshot()

    result = economy.settle_fixed_service_exchange(
        intent=_intent().model_copy(
            update={
                "proposal_digest": f"proposal:{revision}:bounded",
                "command_id": "command:bounded-fixed-service",
                "correlation_id": "corr:bounded-fixed-service",
            }
        )
    )

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "fixed_service_exchange_source_invalid"
    assert store.export_snapshot() == before


def test_fixed_service_exchange_ignores_proposal_package_substring_and_uses_contract_service() -> None:
    store, economy = _prepared_setup(_workshop_setup)
    municipal_manifest_path = (
        __import__("pathlib").Path(__file__).resolve().parents[2]
        / "docs"
        / "superpowers"
        / "specs"
        / "world-character-siming-authority-mainline"
        / "inf-2"
        / "package-municipal-drought-services-v1.manifest.json"
    )
    registry = economy._package_registry
    assert registry is not None
    municipal_manifest = GameplayPatchManifest.model_validate_json(
        municipal_manifest_path.read_text(encoding="utf-8")
    )
    registry.install(municipal_manifest)
    registry.activate(tuple(registry._candidates.keys()))
    before = store.export_snapshot()

    result = economy.settle_fixed_service_exchange(
        intent=_intent().model_copy(
            update={
                "proposal_digest": "proposal:package:municipal-drought-services:v1",
                "command_id": "command:fixed-service-contract-selected",
                "correlation_id": "corr:fixed-service-contract-selected",
            }
        )
    )

    assert result.committed, result.failure
    settlement = store.get_event(result.committed_event_ids[-1])
    assert settlement.payload["package_revision_id"] == "package:industrial-facilities:v5"
    assert settlement.payload["outcome_ref"] == "outcome:industrial-facility-public-workshop-session-settlement@1"
    assert len(store.read_events()) > len(before["events"])


def test_fixed_service_exchange_retains_immutable_package_and_declaration_pins() -> None:
    store, economy = _prepared_setup(_workshop_setup)
    result = economy.settle_fixed_service_exchange(intent=_intent())
    assert result.committed
    settlement = store.get_event(result.committed_event_ids[-1])
    for key in ("package_revision", "content_digest", "declaration_ref", "declaration_digest", "active_patch_set_revision"):
        assert settlement.payload[key]
    forged = settlement.model_copy(
        update={"payload": {**settlement.payload, "content_digest": "sha256:forged"}},
        deep=True,
    )
    store._events_by_id[settlement.event_id] = forged
    store._events = [forged if event.event_id == settlement.event_id else event for event in store._events]

    with pytest.raises(Exception, match="package_exchange_replay_invalid"):
        economy.package_declared_negotiated_exchange_projection(scope="authority")


def test_fixed_service_exchange_replay_rejects_outcome_and_price_pin_tampering() -> None:
    store, economy = _prepared_setup(_workshop_setup)
    result = economy.settle_fixed_service_exchange(intent=_intent())
    assert result.committed
    settlement = store.get_event(result.committed_event_ids[-1])
    forged = settlement.model_copy(
        update={
            "payload": {
                **settlement.payload,
                "outcome_ref": "outcome:forged@1",
                "currency_ref": "currency:forged",
                "amount_minor": 999,
            }
        },
        deep=True,
    )
    store._events_by_id[settlement.event_id] = forged
    store._events = [forged if event.event_id == settlement.event_id else event for event in store._events]

    with pytest.raises(Exception, match="package_exchange_replay_invalid"):
        economy.package_declared_negotiated_exchange_projection(scope="authority")
