import pytest

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.l5_reaction import compile_reactions
from app.gameplay.l5_dispatch_runtime import (
    L5ReactionDispatcher,
    TrustedGameplayCommandGateway,
)
from app.gameplay.settlement_plan import build_atomic_event_batch


def test_committed_life_transition_is_submitted_once_through_trusted_command_gateway():
    store = GameplayEventStore()
    commit = store.append_batch(build_atomic_event_batch(
        command_id="life:death:1",
        principal_ref="authority:character:life-state",
        stream_id="gameplay:character:life:character:defender-1",
        expected_revision=0,
        event_specs=(("gameplay.character.life_state_changed", {
            "actor_ref": "character:defender-1",
            "from_state": "alive",
            "to_state": "dead",
        }),),
        idempotency_key="life:death:1",
        causation_id="combat:death:1",
        correlation_id="siege:east",
    ))
    event = store.get_event(commit.committed_event_ids[0])
    transaction = store.get_transaction(commit.transaction_id)
    submitted = []

    outputs = {"morale.refold": {"fact:unit:garrison-east:morale"}}
    gateway = TrustedGameplayCommandGateway(
        handlers={"morale.refold": submitted.append},
        command_fact_outputs=outputs,
    )
    reactions = compile_reactions([{
        "reaction_id": "casualty_to_morale",
        "on": {
            "fact_type_pattern": "fact:character:*:lifestate",
            "transition_to": "dead",
        },
        "emit": {"command_type": "morale.refold"},
    }], command_fact_outputs=gateway.command_fact_outputs)
    dispatcher = L5ReactionDispatcher(
        reactions=reactions,
        gateway=gateway,
        fact_type_for=lambda item: f"fact:character:{item.payload['actor_ref']}:lifestate",
    )

    results = dispatcher.after_transaction_dispatched(transaction)
    replayed = dispatcher.after_transaction_dispatched(transaction)

    assert len(results) == 1
    assert len(replayed) == 1
    assert len(submitted) == 2
    command = submitted[0]
    assert command.command_type == "morale.refold"
    assert command.command_id == f"l5:casualty_to_morale:{event.event_id}"
    assert command.idempotency_key == command.command_id
    assert command.causation_id == event.event_id
    assert command.trigger_event == event
    assert submitted[1].command_id == command.command_id

    unrelated = store.append_batch(build_atomic_event_batch(
        command_id="life:alive:2",
        principal_ref="authority:character:life-state:presence-admission",
        stream_id=event.stream_id,
        expected_revision=1,
        event_specs=(("gameplay.character.life_state_changed", {
            "actor_ref": "character:defender-1",
            "from_state": "dead",
            "to_state": "alive",
        }),),
        idempotency_key="life:alive:2",
        causation_id="combat:revival:1",
        correlation_id="siege:east",
    ))
    assert dispatcher.after_transaction_dispatched(
        store.get_transaction(unrelated.transaction_id)
    ) == ()
    assert len(submitted) == 2


def test_gateway_requires_a_trusted_output_mapping_for_each_handler():
    with pytest.raises(ValueError, match="^l5_command_registration_invalid$"):
        TrustedGameplayCommandGateway(
            handlers={"morale.refold": lambda _command: None},
            command_fact_outputs={},
        )

    with pytest.raises(ValueError, match="^l5_command_outputs_invalid$"):
        TrustedGameplayCommandGateway(
            handlers={"morale.refold": lambda _command: None},
            command_fact_outputs={"morale.refold": {"fact:unit:*:morale"}},
        )


def test_gateway_accepts_exact_place_machine_output_type():
    gateway = TrustedGameplayCommandGateway(
        handlers={"presence.reevaluate": lambda _command: None},
        command_fact_outputs={
            "presence.reevaluate": {"place:gate-03:passability"},
        },
    )

    assert gateway.command_fact_outputs["presence.reevaluate"] == frozenset(
        {"place:gate-03:passability"}
    )


def test_committed_gate_breach_dispatches_presence_machine_output():
    store = GameplayEventStore()
    commit = store.append_batch(build_atomic_event_batch(
        command_id="gate:breach:1",
        principal_ref="actor_gameplay.construction_production_domain",
        stream_id="fact:facility:gate-03:integrity",
        expected_revision=0,
        event_specs=(("gameplay.pool.threshold_crossed", {
            "fact_type": "fact:facility:gate-03:integrity",
            "threshold_ref": "breach",
            "direction": "enter",
            "value": "39",
        }),),
        idempotency_key="gate:breach:1",
        causation_id="impact:gate:1",
        correlation_id="siege:east",
    ))
    submitted = []
    output_type = "place:gate-03:passability"
    gateway = TrustedGameplayCommandGateway(
        handlers={"presence.reevaluate": submitted.append},
        command_fact_outputs={"presence.reevaluate": {output_type}},
    )
    reactions = compile_reactions([{
        "reaction_id": "gate_breach_to_presence_reeval",
        "on": {
            "fact_type_pattern": "fact:facility:gate-*:integrity",
            "event_type": "gameplay.pool.threshold_crossed",
        },
        "emit": {"command_type": "presence.reevaluate"},
    }], command_fact_outputs=gateway.command_fact_outputs)
    dispatcher = L5ReactionDispatcher(
        reactions=reactions,
        gateway=gateway,
        fact_type_for=lambda event: event.payload.get("fact_type"),
    )

    results = dispatcher.after_transaction_dispatched(
        store.get_transaction(commit.transaction_id)
    )

    assert len(results) == 1
    assert submitted[0].trigger_event.event_type == "gameplay.pool.threshold_crossed"
    assert gateway.command_fact_outputs["presence.reevaluate"] == frozenset({output_type})


def test_reaction_dispatch_rejects_an_unregistered_condition():
    gateway = TrustedGameplayCommandGateway(
        handlers={"morale.refold": lambda _command: None},
        command_fact_outputs={"morale.refold": {"fact:unit:garrison-east:morale"}},
    )
    reactions = compile_reactions([{
        "reaction_id": "casualty_to_morale",
        "on": {
            "fact_type_pattern": "fact:character:*:lifestate",
            "transition_to": "dead",
        },
        "when": {"condition_ref": "morale_relevant@1"},
        "emit": {"command_type": "morale.refold"},
    }], command_fact_outputs=gateway.command_fact_outputs)

    with pytest.raises(ValueError, match="^l5_condition_unknown$"):
        L5ReactionDispatcher(
            reactions=reactions,
            gateway=gateway,
            fact_type_for=lambda _event: None,
        )
