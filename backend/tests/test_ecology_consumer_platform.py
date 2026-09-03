from __future__ import annotations

import pytest

from app.gameplay.ecology_consumer_platform import (
    ConsumerEdgePlatformError,
    admit_consumer_edge,
    consumer_edge_definitions,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog
from app.gameplay.settlement_plan import build_atomic_event_batch


ROW_CASES = (
    (
        "weather-front:survival:hydration@1",
        "inf:weather-front-survival-hydration@1",
        "ecology_consumer",
        "actor_gameplay.survival_domain",
        ("gameplay:survival:profile:c4",),
        ("gameplay.survival.state_applied", "gameplay.survival.obligation_opened"),
        "gameplay.ecology.weather_front.propagated",
        "policy:weather-front-survival-hydration@1",
        "revision:weather-front-survival-hydration-source@1",
        "recipe:ecology-consumer:weather-front-survival-hydration@1",
        "gameplay:ecology:region:c4",
    ),
    (
        "weather-front:construction:maintenance@1",
        "inf:weather-front-construction-maintenance@1",
        "ecology_consumer",
        "actor_gameplay.construction_production_domain",
        ("gameplay:construction_production:facility:c4",),
        ("gameplay.construction_production.maintenance_obligation_created",),
        "gameplay.ecology.weather_front.propagated",
        "policy:weather-front-construction-maintenance@1",
        "revision:weather-front-construction-maintenance-source@1",
        "recipe:ecology-consumer:weather-front-construction-maintenance@1",
        "gameplay:ecology:region:c4",
    ),
    (
        "inventory:grain-harvest-custody@1",
        "inf:inventory-grain-harvest-custody@1",
        "contract_admission",
        "actor_gameplay.inventory_domain",
        ("gameplay:inventory:actor:c4",),
        ("gameplay.inventory.grain_harvest_received@1",),
        "gameplay.ecology.grain_harvested",
        "policy:ecology-grain-harvest@1",
        "revision:ecology-grain-harvest-source@1",
        "recipe:ecology-consumer:inventory-grain-harvest-custody@1",
        "gameplay:ecology:region:c4",
    ),
    (
        "weather-front:economy:quote@1",
        "inf:weather-front-economy-quote@1",
        "ecology_consumer",
        "actor_gameplay.economy_domain",
        ("gameplay:economy",),
        ("gameplay.economy.dynamic_quote_published",),
        "gameplay.ecology.weather_front.propagated",
        "policy:weather-front-economy-quote@1",
        "revision:weather-front-economy-quote-source@1",
        "recipe:ecology-consumer:weather-front-economy-quote@1",
        "gameplay:ecology:region:c4",
    ),
    (
        "weather-front:organization:supply@1",
        "inf:weather-front-organization-supply@1",
        "ecology_consumer",
        "actor_gameplay.organization_domain",
        ("gameplay:organization:organization:c4",),
        ("gameplay.organization.commerce_commitment_accepted",),
        "gameplay.ecology.weather_front.propagated",
        "policy:weather-front-organization-supply@1",
        "revision:weather-front-organization-supply-source@1",
        "recipe:ecology-consumer:weather-front-organization-supply@1",
        "gameplay:ecology:region:c4",
    ),
    (
        "government:jurisdiction:drought-advisory@1",
        "inf:weather-front-government-drought-advisory@1",
        "ecology_consumer",
        "actor_gameplay.government_domain",
        ("gameplay:government:advisory:jurisdiction:c4",),
        ("gameplay.government.drought_advisory_issued",),
        "gameplay.ecology.weather_front.propagated",
        "policy:weather-front-government-drought-advisory@1",
        "revision:weather-front-government-drought-advisory-source@1",
        "recipe:ecology-consumer:weather-front-government-drought-advisory@1",
        "gameplay:ecology:region:c4",
    ),
)


def _seed_source_event(
    store: GameplayEventStore,
    *,
    source_event_type: str,
    source_stream_id: str,
    policy_revision: str,
    command_id: str,
    idempotency_key: str,
) -> object:
    result = store.append_batch(
        build_atomic_event_batch(
            command_id=command_id,
            principal_ref="authority:ecology",
            stream_id=source_stream_id,
            expected_revision=0,
            event_specs=((source_event_type, {"policy_revision": policy_revision}),),
            idempotency_key=idempotency_key,
            causation_id=f"cause:{command_id}",
            correlation_id=f"corr:{command_id}",
        )
    )
    assert result.committed
    return store.read_stream(source_stream_id)[0]


def _admission_kwargs(
    *,
    contract_ref: str,
    owner_ref: str,
    target_stream_id: str,
    target_event_types: tuple[str, ...],
    source_event,
    source_stream_id: str,
    source_revision: int,
    target_expected_revision: int,
    idempotency_key: str,
) -> dict[str, object]:
    return {
        "contract_ref": contract_ref,
        "target_owner_ref": owner_ref,
        "target_stream_ids": (target_stream_id,),
        "target_event_types": target_event_types,
        "projection_scope": "project",
        "source_event_id": source_event.event_id,
        "source_stream_id": source_stream_id,
        "source_revision": source_revision,
        "target_expected_revisions": {target_stream_id: target_expected_revision},
        "idempotency_key": idempotency_key,
    }


def test_consumer_edge_definitions_pin_six_exact_rows() -> None:
    definitions = consumer_edge_definitions()

    assert len(definitions) == 6
    assert [definition.contract_ref for definition in definitions] == [case[1] for case in ROW_CASES]
    for definition, case in zip(definitions, ROW_CASES, strict=True):
        edge_ref, contract_ref, contract_kind, owner_ref, target_stream_ids, target_event_types, source_event_type, policy_ref, revision_ref, recipe_ref, source_stream_id = case
        assert definition.edge_ref == edge_ref
        assert definition.contract_ref == contract_ref
        assert definition.contract_kind == contract_kind
        assert definition.target_owner_ref == owner_ref
        assert definition.target_stream_pattern
        assert definition.target_event_types == target_event_types
        assert definition.source_event_type == source_event_type
        assert definition.source_policy_ref == policy_ref
        assert definition.source_revision_ref == revision_ref
        assert definition.precompiled_recipe_ref == recipe_ref
        assert definition.source_stream_pattern == "gameplay:ecology:{region_ref}"
        admitted = GovernedAuthorityContractCatalog.require(contract_ref=contract_ref, contract_kind=contract_kind)
        assert admitted.owner_ref == owner_ref
        assert admitted.projection_scope == "project"


@pytest.mark.parametrize("case", ROW_CASES)
def test_consumer_edge_admission_projects_and_replays_exact_one_binding(case: tuple[str, ...]) -> None:
    edge_ref, contract_ref, contract_kind, owner_ref, target_stream_ids, target_event_types, source_event_type, policy_ref, revision_ref, recipe_ref, source_stream_id = case
    target_stream_id = target_stream_ids[0]
    store = GameplayEventStore()
    source_event = _seed_source_event(
        store,
        source_event_type=source_event_type,
        source_stream_id=source_stream_id,
        policy_revision=policy_ref,
        command_id=f"seed:{edge_ref}",
        idempotency_key=f"seed:{edge_ref}",
    )
    before = store.export_snapshot()

    admission = admit_consumer_edge(
        store=store,
        **_admission_kwargs(
            contract_ref=contract_ref,
            owner_ref=owner_ref,
            target_stream_id=target_stream_id,
            target_event_types=target_event_types,
            source_event=source_event,
            source_stream_id=source_stream_id,
            source_revision=1,
            target_expected_revision=0,
            idempotency_key=f"admit:{edge_ref}",
        ),
    )

    assert admission.accepted
    assert admission.error_code is None
    assert admission.binding_ref == f"binding:{edge_ref}"
    assert admission.projection_evidence is not None
    assert admission.replay_evidence is not None
    assert admission.projection_evidence.contract_ref == contract_ref
    assert admission.projection_evidence.precompiled_recipe_ref == recipe_ref
    assert admission.replay_evidence.request_digest == admission.request_digest
    assert admission.replay_evidence.source_revision_vector == {source_stream_id: 1, target_stream_id: 0}
    assert store.export_snapshot() == before


@pytest.mark.parametrize(
    ("mutator", "error_code"),
    (
        ("unknown", "consumer_edge_definition_unknown"),
        ("unadmitted", "consumer_edge_unadmitted"),
        ("multiple", "consumer_edge_definition_ambiguous"),
        ("stale", "consumer_edge_target_revision_conflict"),
        ("private", "consumer_edge_source_private"),
        ("revision", "consumer_edge_source_revision_conflict"),
    ),
)
def test_consumer_edge_admission_rejects_zero_write_conflict_modes(mutator: str, error_code: str) -> None:
    edge_ref, contract_ref, contract_kind, owner_ref, target_stream_ids, target_event_types, source_event_type, policy_ref, revision_ref, recipe_ref, source_stream_id = ROW_CASES[0]
    target_stream_id = target_stream_ids[0]
    store = GameplayEventStore()
    source_event = _seed_source_event(
        store,
        source_event_type=source_event_type,
        source_stream_id=source_stream_id,
        policy_revision=policy_ref,
        command_id=f"seed:{mutator}",
        idempotency_key=f"seed:{mutator}",
    )
    if mutator == "stale":
        assert store.append_batch(
            build_atomic_event_batch(
                command_id="seed:stale:target",
                principal_ref="actor_gameplay.survival_domain",
                stream_id=target_stream_id,
                expected_revision=0,
                event_specs=(("gameplay.survival.state_applied", {"state_ref": "state:hydrated"}),),
                idempotency_key="seed:stale:target",
                causation_id="cause:seed:stale:target",
                correlation_id="corr:seed:stale:target",
            )
        ).committed
    if mutator == "private":
        private = source_event.model_copy(update={"visibility_policy": "authority_only"}, deep=True)
        store._events[store._events.index(source_event)] = private
        store._events_by_id[source_event.event_id] = private
        source_event = private

    definitions = consumer_edge_definitions()
    if mutator == "unknown":
        kwargs = _admission_kwargs(
            contract_ref="inf:weather-front-not-admitted@1",
            owner_ref=owner_ref,
            target_stream_id=target_stream_id,
            target_event_types=target_event_types,
            source_event=source_event,
            source_stream_id=source_stream_id,
            source_revision=1,
            target_expected_revision=0,
            idempotency_key="admit:unknown",
        )
    elif mutator == "unadmitted":
        fake_definition = definitions[0].model_copy(update={"contract_ref": "inf:weather-front-survival-hydration-unadmitted@1"})
        definitions = (fake_definition,)
        kwargs = _admission_kwargs(
            contract_ref=fake_definition.contract_ref,
            owner_ref=owner_ref,
            target_stream_id=target_stream_id,
            target_event_types=target_event_types,
            source_event=source_event,
            source_stream_id=source_stream_id,
            source_revision=1,
            target_expected_revision=0,
            idempotency_key="admit:unadmitted",
        )
    elif mutator == "multiple":
        duplicated = definitions[0]
        definitions = (duplicated, duplicated.model_copy(deep=True))
        kwargs = _admission_kwargs(
            contract_ref=duplicated.contract_ref,
            owner_ref=owner_ref,
            target_stream_id=target_stream_id,
            target_event_types=target_event_types,
            source_event=source_event,
            source_stream_id=source_stream_id,
            source_revision=1,
            target_expected_revision=0,
            idempotency_key="admit:multiple",
        )
    elif mutator == "stale":
        kwargs = _admission_kwargs(
            contract_ref=contract_ref,
            owner_ref=owner_ref,
            target_stream_id=target_stream_id,
            target_event_types=target_event_types,
            source_event=source_event,
            source_stream_id=source_stream_id,
            source_revision=1,
            target_expected_revision=0,
            idempotency_key="admit:stale",
        )
    elif mutator == "private":
        kwargs = _admission_kwargs(
            contract_ref=contract_ref,
            owner_ref=owner_ref,
            target_stream_id=target_stream_id,
            target_event_types=target_event_types,
            source_event=source_event,
            source_stream_id=source_stream_id,
            source_revision=1,
            target_expected_revision=0,
            idempotency_key="admit:private",
        )
    else:
        kwargs = _admission_kwargs(
            contract_ref=contract_ref,
            owner_ref=owner_ref,
            target_stream_id=target_stream_id,
            target_event_types=target_event_types,
            source_event=source_event,
            source_stream_id=source_stream_id,
            source_revision=0,
            target_expected_revision=0,
            idempotency_key="admit:revision",
        )

    before = store.export_snapshot()
    admission = admit_consumer_edge(store=store, definitions=definitions, **kwargs)

    assert not admission.accepted
    assert admission.error_code == error_code
    assert store.export_snapshot() == before
