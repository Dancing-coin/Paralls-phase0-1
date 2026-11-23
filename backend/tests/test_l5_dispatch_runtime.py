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
