from __future__ import annotations

from app.gameplay.construction_production_runtime import (
    ConstructionProductionAuthority,
    MillFlourOutputCertificationIntentV1,
    Recipe,
)
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog
from app.gameplay.event_store import GameplayEventStore
from test_infra_construction_mill_reinforcement import _intent, _setup


FACILITY = "facility:mill-reinforcement:1"
STREAM = f"gameplay:construction_production:{FACILITY}"
RECIPE = "recipe:industrial-facilities:mill-flour@1"
ITEM = "item:industrial-facilities:flour@1"
POLICY = "policy:industrial-facilities:reinforced-mill-flour-output@1"


def _completed_case():
    store, authority, _registry, acquisition_id = _setup()
    reinforcement = authority.reinforce_mill_from_package(_intent(acquisition_id))
    assert reinforcement.committed
    facility = authority.projector().facilities[FACILITY]
    recipe = Recipe(
        recipe_ref=RECIPE,
        inputs={"item:industrial-facilities:grain@1": 20},
        output_item=ITEM,
        duration_ticks=1,
        failure_policy_mode="terminal",
        failure_policy_revision="policy:failure:terminal@1",
    )
    assert authority.settle_start_run(
        facility=facility,
        recipe=recipe,
        run_ref="run:industrial-facilities:mill-flour:1",
        tick=10,
        command_id="run:industrial-facilities:mill-flour:1:start",
        idempotency_key="run:industrial-facilities:mill-flour:1:start",
        causation_id="cause:industrial-facilities:mill-flour:1:start",
        correlation_id="corr:industrial-facilities:mill-flour:1",
    ).committed
    run = authority.projector().runs["run:industrial-facilities:mill-flour:1"]
    assert authority.settle_finish_run(
        run,
        tick=11,
        recipe=recipe,
        command_id="run:industrial-facilities:mill-flour:1:finish",
        idempotency_key="run:industrial-facilities:mill-flour:1:finish",
        causation_id="cause:industrial-facilities:mill-flour:1:finish",
        correlation_id="corr:industrial-facilities:mill-flour:1",
    ).committed
    events = store.read_stream(STREAM)
    return store, authority, events[-2], events[-1]


def _intent_for(finished, *, stream_revision: int = 4, **updates: object) -> MillFlourOutputCertificationIntentV1:
    values: dict[str, object] = {
        "run_finished_event_id": finished.event_id,
        "expected_run_finished_revision": finished.stream_revision,
        "expected_run_started_revision": finished.stream_revision - 1,
        "expected_facility_revision": 1,
        "expected_stream_revision": stream_revision,
        "command_id": "certify:industrial-facilities:mill-flour:1",
        "idempotency_key": (
            f"construction:mill-flour-output-certification:{finished.event_id}:"
            f"{finished.stream_revision}:1:{stream_revision}:{POLICY}"
        ),
        "causation_id": finished.event_id,
        "correlation_id": "corr:industrial-facilities:mill-flour:1",
        "submitted_at": "2026-08-28T00:00:00Z",
    }
    values.update(updates)
    return MillFlourOutputCertificationIntentV1.model_validate(values)


def _zero_write(store: GameplayEventStore):
    snapshot = store.export_snapshot()
    return {key: snapshot[key] for key in ("events", "outbox", "idempotency")}


def test_inf1am_certifies_exact_reinforced_mill_flour_output_as_project_fact() -> None:
    store, authority, _started, finished = _completed_case()

    result = authority.certify_mill_flour_output(_intent_for(finished))

    assert result.committed, result.failure
    event = store.get_event(result.committed_event_ids[0])
    assert event.event_type == "gameplay.construction_production.mill_flour_output_certified@1"
    assert event.visibility_policy == "project"
    assert event.payload["facility_ref"] == FACILITY
    assert event.payload["project_ref"] == "plot:mill-reinforcement:1"
    assert event.payload["recipe_ref"] == RECIPE
    assert event.payload["output_item"] == ITEM
    assert event.payload["quantity"] == 10
    assert event.payload["source_run_finished_event_id"] == finished.event_id
    assert authority.projector().mill_flour_output_certifications["run:industrial-facilities:mill-flour:1"].quantity == 10
    receipt = authority.mill_flour_output_certification_receipt_for(result=result, scope="project")
    assert receipt.committed_event_ids == tuple(result.committed_event_ids)
    assert all(not item.event_type.startswith("gameplay.inventory.") for item in store.read_events())
    assert all(not item.event_type.startswith("gameplay.economy.") for item in store.read_events())
    assert not hasattr(authority, "record_output_receipt")
    assert not hasattr(authority, "settle_output_delivery")


def test_inf1am_duplicate_changed_duplicate_and_checkpoint_tail_replay_are_bounded() -> None:
    store, authority, _started, finished = _completed_case()
    first = authority.certify_mill_flour_output(_intent_for(finished))
    assert first.committed
    before = _zero_write(store)

    duplicate = authority.certify_mill_flour_output(_intent_for(finished))
    changed = authority.certify_mill_flour_output(_intent_for(finished, correlation_id="corr:changed"))
    full = authority.projector()
    tail = authority.projector(checkpoint_at=4)

    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert duplicate.committed_event_ids == first.committed_event_ids
    assert not changed.committed
    assert changed.failure is not None and changed.failure.error_code == "idempotency_key_reused"
    assert _zero_write(store) == before
    assert full.mill_flour_output_certifications == tail.mill_flour_output_certifications


def test_inf1am_rejects_stale_source_and_wrong_run_partition_without_write() -> None:
    store, authority, started, finished = _completed_case()
    before = _zero_write(store)

    stale = authority.certify_mill_flour_output(
        _intent_for(finished, expected_stream_revision=3)
    )
    assert not stale.committed
    assert stale.failure is not None
    assert _zero_write(store) == before

    store, authority, started, finished = _completed_case()
    source = store.get_event(finished.event_id)
    store._events_by_id[source.event_id] = source.model_copy(
        update={"payload": {**source.payload, "output_item": "item:wrong"}},
        deep=True,
    )
    before = _zero_write(store)
    wrong = authority.certify_mill_flour_output(_intent_for(finished))
    assert not wrong.committed
    assert wrong.failure is not None
    assert _zero_write(store) == before

    store, authority, started, finished = _completed_case()
    source = store.get_event(finished.event_id)
    store._events_by_id[source.event_id] = source.model_copy(
        update={"visibility_policy": "authority_only"},
        deep=True,
    )
    before = _zero_write(store)
    private = authority.certify_mill_flour_output(_intent_for(finished))
    assert not private.committed
    assert private.failure is not None
    assert _zero_write(store) == before


def test_inf1am_catalog_is_immutable_and_project_scoped() -> None:
    contract = GovernedAuthorityContractCatalog.require(
        contract_ref="inf:construction-reinforced-mill-flour-output-certification@1",
        contract_kind="lifecycle",
    )
    assert contract.owner_ref == "actor_gameplay.construction_production_domain"
    assert contract.stream_patterns == ("gameplay:construction_production:{facility_ref}",)
    assert contract.event_types == (
        "gameplay.construction_production.mill_flour_output_certified@1",
    )
    assert contract.projection_scope == "project"
    descriptor = next(
        item
        for item in GovernedAuthorityContractCatalog.descriptors()
        if item.descriptor_ref
        == "descriptor:construction-reinforced-mill-flour-output-certification@1"
    )
    assert descriptor.capability_ref == "capability:construction-reinforced-mill-flour-output-certification@1"
    assert descriptor.outcome_family_ref == "outcome:construction-reinforced-mill-flour-output-certified@1"
    assert descriptor.allowed_predicate_family_refs == (
        "predicate:construction-reinforced-mill-flour-output-certifiable@1",
    )
    assert descriptor.allowed_proposal_effect_types == (
        "effect:construction-reinforced-mill-flour-output-certification@1",
    )
