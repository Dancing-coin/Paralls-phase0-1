from __future__ import annotations

import pytest

from app.gameplay.ecology_runtime import EcologyHazardAuthority
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog, GovernedAuthorityContractError
from app.gameplay.organization_government_runtime import OrganizationAuthority
from app.gameplay.replay import GameplayProjectionReplay
from app.gameplay.settlement_plan import build_atomic_event_batch


REGION = "region:weather-response"
ORGANIZATIONS = ("organization:weather-response-a", "organization:weather-response-b")


def _setup() -> tuple[GameplayEventStore, EcologyHazardAuthority, OrganizationAuthority]:
    store = GameplayEventStore()
    ecology = EcologyHazardAuthority(store=store)
    source_stream = ecology.ecology_stream_id(region_ref=REGION)
    assert store.append_batch(
        build_atomic_event_batch(
            command_id="command:weather-front",
            principal_ref="authority:ecology",
            stream_id=source_stream,
            expected_revision=0,
            event_specs=[
                (
                    "gameplay.ecology.weather_front.propagated",
                    {
                        "source_region_ref": "region:source",
                        "target_region_ref": REGION,
                        "weather_ref": "weather:storm",
                        "tick": 3,
                        "policy_ref": "policy:ecology_weather_front_step",
                        "policy_revision": "1",
                    },
                )
            ],
            idempotency_key="weather-front",
            causation_id="cause:weather-front",
            correlation_id="corr:weather-front",
        )
    ).committed
    organization = OrganizationAuthority(store=store)
    for organization_ref, suffix in zip(ORGANIZATIONS, ("a", "b"), strict=True):
        assert organization.grant_commerce_budget(
            command_id=f"command:grant:{suffix}",
            organization_ref=organization_ref,
            grant_ref=f"grant:weather-response-{suffix}",
            budget_reservation_ref=f"reservation:weather-response-{suffix}",
            amount_minor=100,
            policy_revision=f"policy:weather-response-{suffix}",
            idempotency_key=f"grant:weather-response-{suffix}",
            causation_id=f"cause:grant:{suffix}",
            correlation_id=f"corr:grant:{suffix}",
        ).committed
    return store, ecology, organization


def _target_specs() -> tuple[dict[str, object], dict[str, object]]:
    return (
        {
            "organization_ref": ORGANIZATIONS[1],
            "counterparty_organization_ref": "organization:supplier-b",
            "commitment_ref": "commitment:weather-response-b",
            "policy_revision": "policy:weather-response-b",
            "organization_grant_refs": ("grant:weather-response-b",),
            "budget_reservation_refs": ("reservation:weather-response-b",),
        },
        {
            "organization_ref": ORGANIZATIONS[0],
            "counterparty_organization_ref": "organization:supplier-a",
            "commitment_ref": "commitment:weather-response-a",
            "policy_revision": "policy:weather-response-a",
            "organization_grant_refs": ("grant:weather-response-a",),
            "budget_reservation_refs": ("reservation:weather-response-a",),
        },
    )


def _intent(ecology: EcologyHazardAuthority):
    intent, error = ecology.admit_weather_front_to_organization_supply_fanout(
        target_specs=_target_specs(),
        region_ref=REGION,
    )
    assert error is None and intent is not None
    return intent


def _settle(store, organization, intent, *, key="weather-response-fanout", revisions=None, privacy="project", admission=None):
    return organization.settle_canonical_weather_front_supply_fanout(
        command=intent.command,
        admission=intent.admission if admission is None else admission,
        expected_revisions=revisions
        if revisions is not None
        else {
            f"gameplay:organization:{ORGANIZATIONS[0]}": 1,
            f"gameplay:organization:{ORGANIZATIONS[1]}": 1,
        },
        idempotency_key=key,
        causation_id="cause:weather-response-fanout",
        correlation_id="corr:weather-response-fanout",
        privacy_scope=privacy,
    )


def test_weather_front_organization_supply_fanout_updates_two_existing_organizations_in_one_owner_batch() -> None:
    store, ecology, organization = _setup()
    intent = _intent(ecology)
    before_count = len(store.read_events())

    result = _settle(store, organization, intent)

    assert result.committed
    assert len(result.committed_event_ids) == 2
    assert len(store.read_events()) == before_count + 2
    assert {
        event.stream_id for event in store.read_events()[-2:]
    } == {
        f"gameplay:organization:{ORGANIZATIONS[0]}",
        f"gameplay:organization:{ORGANIZATIONS[1]}",
    }
    assert [event.event_type for event in store.read_events()[-2:]] == [
        "gameplay.organization.commerce_commitment_accepted",
        "gameplay.organization.commerce_commitment_accepted",
    ]


def test_weather_front_organization_supply_fanout_requires_exact_opaque_two_organization_admission() -> None:
    store, ecology, organization = _setup()
    intent = _intent(ecology)
    before = store.export_snapshot()

    forged = _settle(store, organization, intent, key="weather-fanout-forged", admission=object())
    assert not forged.committed
    assert forged.failure is not None
    assert forged.failure.error_code == "weather_front_organization_fanout_admission_required"
    assert store.export_snapshot() == before

    malformed_intent, malformed_error = ecology.admit_weather_front_to_organization_supply_fanout(
        target_specs=(_target_specs()[0],),
        region_ref=REGION,
    )
    assert malformed_intent is None
    assert malformed_error == "weather_front_organization_fanout_target_invalid"


def test_weather_front_organization_supply_fanout_rejects_catalog_mismatch_source_conflict_and_revision_zero_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, ecology, organization = _setup()
    intent = _intent(ecology)
    before = store.export_snapshot()

    def reject_contract(**_kwargs: object) -> None:
        raise GovernedAuthorityContractError("governed_authority_contract_stream_mismatch")

    monkeypatch.setattr(GovernedAuthorityContractCatalog, "require_operation", staticmethod(reject_contract))
    catalog = _settle(store, organization, intent, key="weather-fanout-catalog")
    assert not catalog.committed
    assert catalog.failure is not None
    assert catalog.failure.error_code == "governed_authority_contract_stream_mismatch"
    assert store.export_snapshot() == before

    monkeypatch.undo()
    assert store.append_batch(
        build_atomic_event_batch(
            command_id="command:weather-advance",
            principal_ref="authority:ecology",
            stream_id=ecology.ecology_stream_id(region_ref=REGION),
            expected_revision=1,
            event_specs=[
                (
                    "gameplay.ecology.environment.recorded",
                    {"record_ref": REGION, "record": {}, "source_revision": 1, "causal_parent_refs": []},
                )
            ],
            idempotency_key="weather-advance",
            causation_id="cause:advance",
            correlation_id="corr:advance",
        )
    ).committed
    after_source = store.export_snapshot()
    stale = _settle(store, organization, intent, key="weather-fanout-stale")
    assert not stale.committed
    assert stale.failure is not None
    assert stale.failure.error_code == "weather_front_organization_fanout_source_revision_conflict"
    assert store.export_snapshot() == after_source

    store, ecology, organization = _setup()
    intent = _intent(ecology)
    before = store.export_snapshot()
    wrong_revision = _settle(
        store,
        organization,
        intent,
        key="weather-fanout-revision",
        revisions={
            f"gameplay:organization:{ORGANIZATIONS[0]}": 1,
            f"gameplay:organization:{ORGANIZATIONS[1]}": 0,
        },
    )
    assert not wrong_revision.committed
    assert wrong_revision.failure is not None
    assert wrong_revision.failure.error_code == "weather_front_organization_fanout_revision_conflict"
    assert store.export_snapshot() == before


def test_weather_front_organization_supply_fanout_duplicate_privacy_and_replay_are_verified() -> None:
    store, ecology, organization = _setup()
    intent = _intent(ecology)
    first = _settle(store, organization, intent, key="weather-fanout-duplicate")
    before = store.export_snapshot()

    duplicate = _settle(store, organization, intent, key="weather-fanout-duplicate")
    assert first.committed
    assert duplicate.idempotency_status == "duplicate_replayed"
    assert store.export_snapshot() == before

    private = _settle(store, organization, intent, key="weather-fanout-private", privacy="authority_only")
    assert not private.committed
    assert private.failure is not None
    assert private.failure.error_code == "weather_front_organization_fanout_privacy_denied"
    assert store.export_snapshot() == before

    replay = GameplayProjectionReplay(projector_id="inf3o", projector_version="1")
    full = replay.full_replay(store.read_events())
    tail = replay.checkpoint_plus_tail_replay(replay.create_checkpoint(()), store.read_events())
    assert full.succeeded and tail.succeeded and full.projection_hash == tail.projection_hash
