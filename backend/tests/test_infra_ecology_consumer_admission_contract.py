from __future__ import annotations

import pytest

from app.gameplay.ecology_consumer_admission import EcologyConsumerAdmissionCheck
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.settlement_plan import build_atomic_event_batch


def _weather_front(store: GameplayEventStore, *, region_ref: str = "region:c4"):
    stream_id = f"gameplay:ecology:{region_ref}"
    result = store.append_batch(
        build_atomic_event_batch(
            command_id=f"command:c4:{region_ref}",
            principal_ref="authority:ecology",
            stream_id=stream_id,
            expected_revision=0,
            event_specs=(
                (
                    "gameplay.ecology.weather_front.propagated",
                    {
                        "source_region_ref": "region:source",
                        "target_region_ref": region_ref,
                        "weather_ref": "weather:storm",
                        "tick": 1,
                    },
                ),
            ),
            idempotency_key=f"c4:{region_ref}",
            causation_id="cause:c4",
            correlation_id="corr:c4",
        )
    )
    assert result.committed
    return store.read_stream(stream_id)[-1]


@pytest.mark.parametrize(
    ("contract_ref", "owner_ref", "target_stream", "event_type"),
    (
        (
            "inf:weather-front-construction-maintenance@1",
            "actor_gameplay.construction_production_domain",
            "gameplay:construction_production:facility:c4",
            "gameplay.construction_production.maintenance_obligation_created",
        ),
        (
            "inf:weather-front-organization-supply@1",
            "actor_gameplay.organization_domain",
            "gameplay:organization:organization:c4",
            "gameplay.organization.commerce_commitment_accepted",
        ),
    ),
)
def test_c4_reuses_finite_weather_front_contract_for_two_existing_target_owners(
    contract_ref: str,
    owner_ref: str,
    target_stream: str,
    event_type: str,
) -> None:
    store = GameplayEventStore()
    source = _weather_front(store)

    check = EcologyConsumerAdmissionCheck.verify(
        store=store,
        contract_ref=contract_ref,
        target_owner_ref=owner_ref,
        target_stream_ids=(target_stream,),
        target_event_types=(event_type,),
        projection_scope="project",
        source_event_id=source.event_id,
        source_stream_id=source.stream_id,
        source_revision=source.stream_revision,
        target_expected_revisions={target_stream: 0},
        idempotency_key=f"c4:{contract_ref}",
    )

    assert check.accepted
    assert check.receipt_reader_ref == "GameplayEventStore.append_batch"
    assert check.replay_reader_ref
    assert check.request_digest == EcologyConsumerAdmissionCheck.verify(
        store=store,
        contract_ref=contract_ref,
        target_owner_ref=owner_ref,
        target_stream_ids=(target_stream,),
        target_event_types=(event_type,),
        projection_scope="project",
        source_event_id=source.event_id,
        source_stream_id=source.stream_id,
        source_revision=source.stream_revision,
        target_expected_revisions={target_stream: 0},
        idempotency_key=f"c4:{contract_ref}",
    ).request_digest
    assert store.read_events() == [source]


@pytest.mark.parametrize(
    "override",
    (
        {"contract_ref": "inf:weather-front-unregistered@1"},
        {"target_owner_ref": "authority:forged"},
        {"target_stream_ids": ("gameplay:economy",)},
        {"projection_scope": "authority_only"},
        {"source_revision": 0},
        {"idempotency_key": ""},
    ),
)
def test_c4_rejects_bad_admission_inputs_without_target_write(override: dict[str, object]) -> None:
    store = GameplayEventStore()
    source = _weather_front(store)
    kwargs: dict[str, object] = {
        "store": store,
        "contract_ref": "inf:weather-front-construction-maintenance@1",
        "target_owner_ref": "actor_gameplay.construction_production_domain",
        "target_stream_ids": ("gameplay:construction_production:facility:c4",),
        "target_event_types": ("gameplay.construction_production.maintenance_obligation_created",),
        "projection_scope": "project",
        "source_event_id": source.event_id,
        "source_stream_id": source.stream_id,
        "source_revision": source.stream_revision,
        "target_expected_revisions": {"gameplay:construction_production:facility:c4": 0},
        "idempotency_key": "c4:reject",
    }
    kwargs.update(override)

    check = EcologyConsumerAdmissionCheck.verify(**kwargs)

    assert not check.accepted
    assert check.error_code
    assert store.read_events() == [source]


def test_c4_rejects_stale_target_revision_without_writes() -> None:
    store = GameplayEventStore()
    source = _weather_front(store)
    target_stream = "gameplay:organization:organization:c4"
    assert store.append_batch(
        build_atomic_event_batch(
            command_id="command:c4:advance",
            principal_ref="actor_gameplay.organization_domain",
            stream_id=target_stream,
            expected_revision=0,
            event_specs=(("gameplay.organization.commerce_commitment_accepted", {"organization_ref": "organization:c4"}),),
            idempotency_key="c4:advance",
            causation_id="cause:c4:advance",
            correlation_id="corr:c4:advance",
        )
    ).committed
    before = store.export_snapshot()

    check = EcologyConsumerAdmissionCheck.verify(
        store=store,
        contract_ref="inf:weather-front-organization-supply@1",
        target_owner_ref="actor_gameplay.organization_domain",
        target_stream_ids=(target_stream,),
        target_event_types=("gameplay.organization.commerce_commitment_accepted",),
        projection_scope="project",
        source_event_id=source.event_id,
        source_stream_id=source.stream_id,
        source_revision=source.stream_revision,
        target_expected_revisions={target_stream: 0},
        idempotency_key="c4:stale",
    )

    assert not check.accepted
    assert check.error_code == "ecology_consumer_target_revision_conflict"
    assert store.export_snapshot() == before
