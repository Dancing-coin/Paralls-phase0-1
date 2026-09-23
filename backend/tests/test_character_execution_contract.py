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
    assert contract.expected_observation
