from __future__ import annotations

from app.gameplay.ecology_runtime import EcologyHazardAuthority
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, GovernedAuthorityContractError
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.gameplay.settlement_plan import build_atomic_event_batch


ORGANIZATION = "organization:weather-response"
REGION = "region:weather-response"


def _setup() -> tuple[GameplayEventStore, EcologyHazardAuthority, OrganizationAuthority]:
    store = GameplayEventStore()
    ecology = EcologyHazardAuthority(store=store)
    source_stream = ecology.ecology_stream_id(region_ref=REGION)
    assert store.append_batch(build_atomic_event_batch(
        command_id="command:weather-front", principal_ref="authority:ecology", stream_id=source_stream,
        expected_revision=0, event_specs=[("gameplay.ecology.weather_front.propagated", {
            "source_region_ref": "region:source", "target_region_ref": REGION,
            "weather_ref": "weather:storm", "tick": 3, "policy_ref": "policy:ecology_weather_front_step", "policy_revision": "1",
        })], idempotency_key="weather-front", causation_id="cause:weather-front", correlation_id="corr:weather-front",
    )).committed
    organization = OrganizationAuthority(store=store)
    assert organization.grant_commerce_budget(
        command_id="command:grant", organization_ref=ORGANIZATION, grant_ref="grant:weather-response",
        budget_reservation_ref="reservation:weather-response", amount_minor=100, policy_revision="policy:weather-response",
        idempotency_key="grant:weather-response", causation_id="cause:grant", correlation_id="corr:grant",
    ).committed
    return store, ecology, organization


def _intent(ecology: EcologyHazardAuthority):
    intent, error = ecology.admit_weather_front_to_organization_supply(
        organization_ref=ORGANIZATION, counterparty_organization_ref="organization:supplier",
        commitment_ref="commitment:weather-response", policy_revision="policy:weather-response",
        organization_grant_refs=("grant:weather-response",), budget_reservation_refs=("reservation:weather-response",), region_ref=REGION,
    )
    assert error is None and intent is not None
    return intent


def _settle(store, organization, intent, *, key="weather-response", revision=1, privacy="project", admission=None):
    return organization.settle_canonical_weather_front_supply(
        command=intent.command, admission=intent.admission if admission is None else admission,
        expected_revision=revision, idempotency_key=key, causation_id="cause:weather-response",
        correlation_id="corr:weather-response", privacy_scope=privacy,
    )


def test_weather_front_organization_supply_edge_uses_existing_organization_fragment_and_one_append() -> None:
    store, ecology, organization = _setup()
    result = _settle(store, organization, _intent(ecology))
    assert result.committed and store.get_stream_head(f"gameplay:organization:{ORGANIZATION}") == 2
    event = store.read_stream(f"gameplay:organization:{ORGANIZATION}")[-1]
    assert event.event_type == "gameplay.organization.commerce_commitment_accepted"
    assert event.payload["edge_ref"] == "ecology-weather:front-to-organization-supply:v1"
    assert event.payload["weather_event_id"] == store.read_stream(ecology.ecology_stream_id(region_ref=REGION))[0].event_id
    assert store.list_outbox()[-1].payload_projection == {"organization_ref": ORGANIZATION, "commitment_ref": "commitment:weather-response", "event_type": event.event_type}


def test_weather_front_organization_catalog_mismatch_rejects_before_append(monkeypatch) -> None:
    store, ecology, organization = _setup()
    intent = _intent(ecology)
    before = store.export_snapshot()

    def reject_contract(**_kwargs):
        raise GovernedAuthorityContractError("governed_authority_contract_owner_mismatch")

    monkeypatch.setattr(GovernedAuthorityContractCatalog, "require_operation", reject_contract)
    result = _settle(store, organization, intent)

    assert not result.committed
    assert result.failure is not None
    assert result.failure.error_code == "governed_authority_contract_owner_mismatch"
    assert store.export_snapshot() == before


def test_weather_front_organization_supply_edge_replays_exact_duplicate_and_rejects_changed_duplicate() -> None:
    store, ecology, organization = _setup()
    intent = _intent(ecology)
    assert _settle(store, organization, intent).committed
    duplicate = _settle(store, organization, intent)
    changed = _settle(store, organization, intent, key="weather-response", revision=2)
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert not changed.committed and changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert store.get_stream_head(f"gameplay:organization:{ORGANIZATION}") == 2


def test_weather_front_organization_supply_edge_rejects_forged_privacy_and_stale_source_without_writes() -> None:
    store, ecology, organization = _setup()
    intent = _intent(ecology)
    forged = _settle(store, organization, intent, admission=object())
    private = _settle(store, organization, intent, key="weather-private", privacy="authority_only")
    source_stream = ecology.ecology_stream_id(region_ref=REGION)
    assert store.append_batch(build_atomic_event_batch(
        command_id="command:weather-advance", principal_ref="authority:ecology", stream_id=source_stream,
        expected_revision=1, event_specs=[("gameplay.ecology.environment.recorded", {"record_ref": REGION, "record": {}, "source_revision": 1, "causal_parent_refs": []})],
        idempotency_key="weather-advance", causation_id="cause:advance", correlation_id="corr:advance",
    )).committed
    stale = _settle(store, organization, intent, key="weather-stale")
    assert forged.failure and forged.failure.error_code == "weather_front_organization_admission_required"
    assert private.failure and private.failure.error_code == "weather_front_organization_privacy_denied"
    assert stale.failure and stale.failure.error_code == "weather_front_organization_source_revision_conflict"
    assert store.get_stream_head(f"gameplay:organization:{ORGANIZATION}") == 1


def test_weather_front_organization_supply_edge_replays_full_and_checkpoint_tail() -> None:
    store, ecology, organization = _setup()
    assert _settle(store, organization, _intent(ecology)).committed
    assert organization.commerce_commitment_projection(organization_ref=ORGANIZATION)["projection_hash"] == organization.commerce_commitment_projection(organization_ref=ORGANIZATION, checkpoint_at=1)["projection_hash"]
