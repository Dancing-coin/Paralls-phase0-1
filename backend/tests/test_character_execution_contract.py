import warnings

import pytest
from pydantic import ValidationError

from app.character_agent.execution.l4_adapter import CharacterAgentL4Adapter
from app.character_agent.execution.l4_executor import CharacterAgentL4Executor
from app.character_agent.models.turn_context import CharacterTurnContext
from app.models.character_agent_runtime import (
    CharacterGoalCommand,
    CharacterIntentDecision,
    CharacterInterpretation,
    CharacterPrivateWorldSnapshot,
)
from app.character_agent.models.character_execution import (
    CharacterExecutionContract,
)


def _turn() -> CharacterTurnContext:
    return CharacterTurnContext.begin(
        actor_id="char_b",
        source_event_ref="event:perception:1",
        producer_ts=10,
        causation_id="cause:1",
        correlation_id="corr:1",
        input_revision_vector={"session:char_b": 3},
        memory_revision_vector={"memory:char_b": 4},
        policy_revision="policy:char_b:1",
        snapshot_revision=5,
        branch_id="branch:main",
    )


def _valid_contract(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "turn_id": "turn:char_b:event:perception:1",
        "actor_ref": "character:char_b",
        "source_ref": "event:perception:1",
        "producer_ts": 10,
        "target_refs": ("character:char_a",),
        "semantic_intent_id": "speak_public",
        "semantic_action_id": "open_close",
        "allowed_realization_hints": {"gesture": "present"},
        "expected_revision_vector": {"session:char_b": 3},
        "idempotency_key": "execution:turn:char_b:event:perception:1",
        "causation_id": "cause:1",
        "correlation_id": "corr:1",
        "privacy_scope": "actor_private:char_b",
        "authority_scope": "world:default",
        "expected_observation": {"semantic_effect": "door_state_changed"},
    }
    payload.update(overrides)
    return payload


def _snapshot() -> CharacterPrivateWorldSnapshot:
    return CharacterPrivateWorldSnapshot(
        actor_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=10,
        updated_at=10,
        attention_targets=["char_a"],
    )


def _interpretation() -> CharacterInterpretation:
    return CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="char_a is speaking nearby",
        interpretation_type="social_signal",
        salience_score=0.8,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="medium",
        attention_target="char_a",
    )


def _decision() -> CharacterIntentDecision:
    return CharacterIntentDecision(
        actor_id="char_b",
        selected_intent="speak_public",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="respond",
    )


def _legacy_command() -> CharacterGoalCommand:
    return CharacterGoalCommand(
        actor_id="char_b",
        command_type="speak",
        ttl_ms=1000,
        causation_id="cause:1",
        correlation_id="corr:1",
        producer_ts=10,
        target_actor_id="char_a",
        dialogue_text="Hello.",
    )


def test_execution_contract_requires_turn_and_rejects_body_or_world_writes() -> None:
    contract = CharacterExecutionContract.model_validate(
        _valid_contract(semantic_action_id="open_close")
    )
    assert contract.semantic_action_id == "open_close"

    with pytest.raises(ValidationError, match="forbidden execution field"):
        CharacterExecutionContract.model_validate(
            _valid_contract(global_position=[1, 0, 1])
        )

    with pytest.raises(ValidationError, match="turn_id"):
        CharacterExecutionContract.model_validate(_valid_contract(turn_id=""))


def test_execution_contract_is_immutable_and_pins_turn_identity() -> None:
    turn = _turn()
    contract = CharacterAgentL4Executor().build_execution_contract(
        _snapshot(), _interpretation(), _decision(), turn
    )

    assert contract.turn_id == turn.turn_id
    assert contract.causation_id == turn.causation_id
    assert contract.correlation_id == turn.correlation_id
    assert dict(contract.expected_revision_vector) == dict(turn.input_revision_vector)
    with pytest.raises(ValidationError):
        contract.turn_id = "other"  # type: ignore[misc]


def test_legacy_command_translates_once_without_creating_second_request() -> None:
    adapter = CharacterAgentL4Adapter()
    result = adapter.from_legacy_command(_legacy_command(), turn_context=_turn())

    assert result.contract.turn_id == "turn:char_b:event:perception:1"
    assert result.legacy_translation is True
    assert result.contract.idempotency_key.startswith("execution:")
    replay = adapter.from_legacy_command(_legacy_command(), turn_context=_turn())
    assert replay.contract == result.contract
    with pytest.raises(ValueError, match="legacy execution translation conflict"):
        adapter.from_legacy_command(
            _legacy_command().model_copy(update={"dialogue_text": "Different"}),
            turn_context=_turn(),
        )


def test_executor_contract_keeps_realization_hints_advisory() -> None:
    contract = CharacterAgentL4Executor().build_execution_contract(
        _snapshot(), _interpretation(), _decision(), _turn()
    )

    assert contract.allowed_realization_hints
    assert "settlement_result" not in contract.allowed_realization_hints
    assert "settlement_outcome" not in contract.allowed_realization_hints["skill"]
    assert contract.expected_observation


def test_contract_revalidates_runtime_hint_augmentation_and_default_dump_is_plain() -> None:
    contract = CharacterExecutionContract.model_validate(_valid_contract())

    with warnings.catch_warnings(record=True) as captured:
        dumped = contract.model_dump()

    assert not captured
    assert isinstance(dumped["allowed_realization_hints"], dict)
    assert isinstance(dumped["expected_revision_vector"], dict)
    with pytest.raises(ValidationError, match="forbidden execution field"):
        CharacterExecutionContract.model_validate(
            {
                **dumped,
                "allowed_realization_hints": {
                    "presentation": {"global_position": [1, 2, 3]}
                },
            }
        )


def test_canonical_execution_egress_and_authority_request_preserve_contract_pins() -> None:
    from app.main import (
        _as_character_agent_action_request_envelopes,
        _as_character_agent_execution_envelopes,
    )

    contract = CharacterExecutionContract.model_validate(
        _valid_contract(
            expected_memory_revision_vector={"memory:char_b": 4},
            expected_snapshot_revision=5,
            expected_observation={"requested_action": "approach"},
        )
    )
    command = _legacy_command().model_copy(
        update={"execution_payload": {"execution_contract": contract.model_dump()}}
    )

    emitted = _as_character_agent_execution_envelopes([command])

    assert emitted == [
        {"message_type": "character_agent_execution", "payload": contract.model_dump()}
    ]
    authority_requests = _as_character_agent_action_request_envelopes(
        emitted[0]["payload"], producer_ts=0
    )
    request = authority_requests[0]["payload"]
    assert request["request_id"] == f"{contract.idempotency_key}:0"
    assert request["turn_id"] == contract.turn_id
    assert request["idempotency_key"] == contract.idempotency_key
    assert request["causation_id"] == contract.causation_id
    assert request["correlation_id"] == contract.correlation_id
    assert request["expected_revision_vector"] == dict(contract.expected_revision_vector)
    assert request["expected_memory_revision_vector"] == dict(
        contract.expected_memory_revision_vector
    )
    assert request["expected_snapshot_revision"] == contract.expected_snapshot_revision


def test_execution_ingress_rejects_non_contract_body_authority_payload() -> None:
    from app.main import Envelope, _handle_envelope

    messages = _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload=_valid_contract(
                allowed_realization_hints={
                    "presentation": {"global_position": [1, 2, 3]}
                }
            ),
        )
    )

    assert messages[0]["message_type"] == "ack"
    assert messages[0]["payload"]["accepted"] is False
    assert messages[0]["payload"]["route"] == "character_agent_execution_contract"


@pytest.mark.parametrize(
    ("requested_action", "target_ref", "semantic_action_id"),
    [
        ("approach", "character:char_a", "approach"),
        ("interact", "object:obj_letter", "inspect"),
    ],
)
def test_contract_pins_reach_actual_settlement_result(
    requested_action: str,
    target_ref: str,
    semantic_action_id: str,
) -> None:
    from app.main import Envelope, _handle_envelope, reset_runtime_state
    import app.main as main

    reset_runtime_state()
    contract = _valid_contract(
        target_refs=(target_ref,),
        semantic_action_id=semantic_action_id,
        expected_memory_revision_vector={"memory:char_b": 4},
        expected_snapshot_revision=5,
        expected_observation={"requested_action": requested_action},
    )

    main.character_agent_runtime.record_execution_request(
        actor_id="char_b", producer_ts=10,
        payload=CharacterExecutionContract.model_validate(contract).model_dump(mode="json"),
    )
    messages = _handle_envelope(
        Envelope(message_type="character_agent_execution", payload=contract)
    )

    settlements = [
        message["payload"]
        for message in messages
        if message["message_type"] == "world_result"
    ]
    settlements.extend(
        message["payload"]["payload"]
        for message in messages
        if message["message_type"] == "authority_event"
        and message["payload"]["event_type"]
        in {"esm_result_event", "constraint_state_event"}
    )
    assert settlements
    settlement = settlements[0]
    assert settlement["request_ref"] == "execution:turn:char_b:event:perception:1:0"
    assert settlement["result_id"] == (
        "action_resolution:execution:turn:char_b:event:perception:1:0"
    )
    assert settlement["turn_id"] == contract["turn_id"]
    assert settlement["idempotency_key"] == contract["idempotency_key"]
    assert settlement["causation_id"] == contract["causation_id"]
    assert settlement["correlation_id"] == contract["correlation_id"]
    assert settlement["expected_revision_vector"] == contract["expected_revision_vector"]
    assert settlement["expected_memory_revision_vector"] == contract[
        "expected_memory_revision_vector"
    ]
    assert settlement["expected_snapshot_revision"] == contract[
        "expected_snapshot_revision"
    ]

    replay_messages = _handle_envelope(
        Envelope(message_type="character_agent_execution", payload=contract)
    )
    replay_settlements = [
        message["payload"]
        for message in replay_messages
        if message["message_type"] == "world_result"
    ]
    replay_settlements.extend(
        message["payload"]["payload"]
        for message in replay_messages
        if message["message_type"] == "authority_event"
        and message["payload"]["event_type"]
        in {"esm_result_event", "constraint_state_event"}
    )
    assert replay_settlements
    assert replay_settlements[0]["request_ref"] == settlement["request_ref"]
    assert replay_settlements[0]["result_id"] == settlement["result_id"]
    assert replay_settlements[0]["idempotency_key"] == settlement["idempotency_key"]


def test_contract_pins_reach_social_dialogue_settlement(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.main as main

    main.reset_runtime_state()
    monkeypatch.setattr(main, "_backfill_character_agent_speech_perception", lambda **_: None)
    contract = _valid_contract(
        semantic_intent_id="speak_public",
        semantic_action_id="speak_public",
        expected_memory_revision_vector={"memory:char_b": 4},
        expected_snapshot_revision=5,
        expected_observation={
            "requested_action": "speak_public",
            "summary": "Please look here.",
        },
    )

    main.character_agent_runtime.record_execution_request(
        actor_id="char_b", producer_ts=10,
        payload=CharacterExecutionContract.model_validate(contract).model_dump(mode="json"),
    )
    messages = main._handle_envelope(
        main.Envelope(message_type="character_agent_execution", payload=contract)
    )

    response = next(
        message["payload"]
        for message in messages
        if message["message_type"] == "dialogue_response"
    )
    assert response["request_id"] == "execution:turn:char_b:event:perception:1:0"
    assert response["turn_id"] == contract["turn_id"]
    assert response["idempotency_key"] == contract["idempotency_key"]
    assert response["causation_id"] == contract["causation_id"]
    assert response["correlation_id"] == contract["correlation_id"]
    assert response["expected_revision_vector"] == contract["expected_revision_vector"]
    assert response["expected_memory_revision_vector"] == contract[
        "expected_memory_revision_vector"
    ]
    assert response["expected_snapshot_revision"] == contract[
        "expected_snapshot_revision"
    ]
