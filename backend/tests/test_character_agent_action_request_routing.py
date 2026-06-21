from app.character_agent.execution.l4_executor import CharacterAgentL4Executor
from app.main import reset_runtime_state, _handle_envelope
from app.models.character_agent_runtime import CharacterInterpretation, CharacterIntentDecision, CharacterPrivateWorldSnapshot
from app.ws_protocol import Envelope


def _snapshot() -> CharacterPrivateWorldSnapshot:
    return CharacterPrivateWorldSnapshot(
        actor_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=1600,
        updated_at=1600,
        attention_targets=["obj_letter"],
    )


def _interpretation() -> CharacterInterpretation:
    return CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="the letter should be inspected",
        interpretation_type="opportunity",
        salience_score=0.9,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="high",
        attention_target="obj_letter",
        inner_prompt_candidate="inspect before speaking",
    )


def test_l4_executor_emits_action_request_bundle_for_object_inspection() -> None:
    executor = CharacterAgentL4Executor()
    decision = CharacterIntentDecision(
        actor_id="char_b",
        selected_intent="inspect_object",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="the letter should be inspected",
    )

    plan = executor.build_execution_plan(
        snapshot=_snapshot(),
        interpretation=_interpretation(),
        decision=decision,
    )

    assert plan["action_request_bundle"]["requested_actions"]
    assert plan["action_request_bundle"]["requested_actions"][0]["request_type"] == "interact"
    assert plan["action_request_bundle"]["requested_actions"][0]["target_object_id"] == "obj_letter"


def test_l4_executor_emits_action_request_bundle_for_actor_approach() -> None:
    executor = CharacterAgentL4Executor()
    decision = CharacterIntentDecision(
        actor_id="char_b",
        selected_intent="approach",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="close distance to char_a",
    )
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=1601,
        updated_at=1601,
        attention_targets=["char_a"],
    )
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="close distance to char_a",
        interpretation_type="social_signal",
        salience_score=0.8,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="medium",
        attention_target="char_a",
        inner_prompt_candidate="approach char_a",
    )

    plan = executor.build_execution_plan(
        snapshot=snapshot,
        interpretation=interpretation,
        decision=decision,
    )

    assert plan["action_request_bundle"]["requested_actions"]
    assert plan["action_request_bundle"]["requested_actions"][0]["request_type"] == "approach"
    assert plan["action_request_bundle"]["requested_actions"][0]["target_actor_id"] == "char_a"


def test_l4_executor_emits_action_request_bundle_for_public_speech() -> None:
    executor = CharacterAgentL4Executor()
    decision = CharacterIntentDecision(
        actor_id="char_b",
        selected_intent="speak_public",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="address char_a in public",
    )
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=1604,
        updated_at=1604,
        attention_targets=["char_a"],
    )
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="address char_a in public",
        interpretation_type="social_signal",
        salience_score=0.9,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="high",
        attention_target="char_a",
        inner_prompt_candidate="speak publicly to char_a",
    )

    plan = executor.build_execution_plan(
        snapshot=snapshot,
        interpretation=interpretation,
        decision=decision,
    )

    assert plan["action_request_bundle"]["requested_actions"]
    assert plan["action_request_bundle"]["requested_actions"][0]["request_type"] == "speak_public"
    assert plan["action_request_bundle"]["requested_actions"][0]["target_actor_id"] == "char_a"
    assert plan["action_request_bundle"]["requested_actions"][0]["content"] == "address char_a in public"


def test_l4_executor_emits_action_request_bundle_for_private_speech() -> None:
    executor = CharacterAgentL4Executor()
    decision = CharacterIntentDecision(
        actor_id="char_b",
        selected_intent="speak_private",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="address char_a privately",
    )
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=1609,
        updated_at=1609,
        attention_targets=["char_a"],
    )
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="address char_a privately",
        interpretation_type="social_signal",
        salience_score=0.91,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="high",
        attention_target="char_a",
        inner_prompt_candidate="speak privately to char_a",
    )

    plan = executor.build_execution_plan(
        snapshot=snapshot,
        interpretation=interpretation,
        decision=decision,
    )

    assert plan["action_request_bundle"]["requested_actions"]
    assert plan["action_request_bundle"]["requested_actions"][0]["request_type"] == "speak_private"
    assert plan["action_request_bundle"]["requested_actions"][0]["target_actor_id"] == "char_a"
    assert plan["action_request_bundle"]["requested_actions"][0]["content"] == "address char_a privately"


def test_l4_executor_emits_action_request_bundle_for_share_info() -> None:
    executor = CharacterAgentL4Executor()
    decision = CharacterIntentDecision(
        actor_id="char_b",
        selected_intent="share_info",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="share what char_b knows with char_a",
    )
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=1610,
        updated_at=1610,
        attention_targets=["char_a"],
    )
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="share what char_b knows with char_a",
        interpretation_type="social_signal",
        salience_score=0.91,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="high",
        attention_target="char_a",
        inner_prompt_candidate="share information with char_a",
    )

    plan = executor.build_execution_plan(
        snapshot=snapshot,
        interpretation=interpretation,
        decision=decision,
    )

    assert plan["action_request_bundle"]["requested_actions"]
    assert plan["action_request_bundle"]["requested_actions"][0]["request_type"] == "share_info"
    assert plan["action_request_bundle"]["requested_actions"][0]["target_actor_id"] == "char_a"
    assert plan["action_request_bundle"]["requested_actions"][0]["content"] == "share what char_b knows with char_a"


def test_l4_executor_emits_action_request_bundle_for_withhold() -> None:
    executor = CharacterAgentL4Executor()
    decision = CharacterIntentDecision(
        actor_id="char_b",
        selected_intent="withhold",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="choose not to reveal information to char_a",
    )
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=1611,
        updated_at=1611,
        attention_targets=["char_a"],
    )
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="choose not to reveal information to char_a",
        interpretation_type="social_signal",
        salience_score=0.9,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="medium",
        attention_target="char_a",
        inner_prompt_candidate="withhold information from char_a",
    )

    plan = executor.build_execution_plan(
        snapshot=snapshot,
        interpretation=interpretation,
        decision=decision,
    )

    assert plan["action_request_bundle"]["requested_actions"]
    assert plan["action_request_bundle"]["requested_actions"][0]["request_type"] == "withhold"
    assert plan["action_request_bundle"]["requested_actions"][0]["target_actor_id"] == "char_a"
    assert plan["action_request_bundle"]["requested_actions"][0]["content"] == "choose not to reveal information to char_a"


def test_l4_executor_emits_action_request_bundle_for_seek_private_distance() -> None:
    executor = CharacterAgentL4Executor()
    decision = CharacterIntentDecision(
        actor_id="char_b",
        selected_intent="seek_private_distance",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="create more private space around char_a",
    )
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=1606,
        updated_at=1606,
        attention_targets=["char_a"],
    )
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="create more private space around char_a",
        interpretation_type="social_signal",
        salience_score=0.85,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="medium",
        attention_target="char_a",
        inner_prompt_candidate="seek private distance from char_a",
    )

    plan = executor.build_execution_plan(
        snapshot=snapshot,
        interpretation=interpretation,
        decision=decision,
    )

    assert plan["action_request_bundle"]["requested_actions"]
    assert plan["action_request_bundle"]["requested_actions"][0]["request_type"] == "seek_private_distance"
    assert plan["action_request_bundle"]["requested_actions"][0]["target_actor_id"] == "char_a"


def test_l4_executor_emits_action_request_bundle_for_withdraw() -> None:
    executor = CharacterAgentL4Executor()
    decision = CharacterIntentDecision(
        actor_id="char_b",
        selected_intent="withdraw",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="create more distance from char_a",
    )
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=1607,
        updated_at=1607,
        attention_targets=["char_a"],
    )
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="create more distance from char_a",
        interpretation_type="social_signal",
        salience_score=0.82,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="low",
        attention_target="char_a",
        inner_prompt_candidate="withdraw from char_a",
    )

    plan = executor.build_execution_plan(
        snapshot=snapshot,
        interpretation=interpretation,
        decision=decision,
    )

    assert plan["action_request_bundle"]["requested_actions"]
    assert plan["action_request_bundle"]["requested_actions"][0]["request_type"] == "withdraw"
    assert plan["action_request_bundle"]["requested_actions"][0]["target_actor_id"] == "char_a"


def test_l4_executor_emits_action_request_bundle_for_follow_target() -> None:
    executor = CharacterAgentL4Executor()
    decision = CharacterIntentDecision(
        actor_id="char_b",
        selected_intent="follow_target",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="keep following char_a",
    )
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=1608,
        updated_at=1608,
        attention_targets=["char_a"],
    )
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="keep following char_a",
        interpretation_type="social_signal",
        salience_score=0.83,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="medium",
        attention_target="char_a",
        inner_prompt_candidate="follow char_a",
    )

    plan = executor.build_execution_plan(
        snapshot=snapshot,
        interpretation=interpretation,
        decision=decision,
    )

    assert plan["action_request_bundle"]["requested_actions"]
    assert plan["action_request_bundle"]["requested_actions"][0]["request_type"] == "follow_target"
    assert plan["action_request_bundle"]["requested_actions"][0]["target_actor_id"] == "char_a"


def test_l4_executor_emits_action_request_bundle_for_break_contact() -> None:
    executor = CharacterAgentL4Executor()
    decision = CharacterIntentDecision(
        actor_id="char_b",
        selected_intent="break_contact",
        persona_passed=True,
        logic_passed=True,
        gain_loss_passed=True,
        rationale="break contact with char_a",
    )
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id="char_b",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=1612,
        updated_at=1612,
        attention_targets=["char_a"],
    )
    interpretation = CharacterInterpretation(
        actor_id="char_b",
        interpreted_summary="break contact with char_a",
        interpretation_type="social_signal",
        salience_score=0.8,
        ambiguity_level="low",
        risk_level="low",
        opportunity_level="low",
        attention_target="char_a",
        inner_prompt_candidate="break contact from char_a",
    )

    plan = executor.build_execution_plan(
        snapshot=snapshot,
        interpretation=interpretation,
        decision=decision,
    )

    assert plan["action_request_bundle"]["requested_actions"]
    assert plan["action_request_bundle"]["requested_actions"][0]["request_type"] == "break_contact"
    assert plan["action_request_bundle"]["requested_actions"][0]["target_actor_id"] == "char_a"


def test_character_agent_execution_envelope_keeps_settlement_authority_in_esm() -> None:
    reset_runtime_state()
    messages = _handle_envelope(
        Envelope(
            message_type="player_input",
            payload={
                "player_id": "p1",
                "room_id": "room_demo",
                "actor_id": "char_c",
                "intent_type": "focus_target_change",
                "producer_ts": 1601,
                "target_object_id": "obj_letter",
            },
        )
    )

    action_requests = [message for message in messages if message["message_type"] == "action_request"]
    world_results = [message for message in messages if message["message_type"] == "world_result"]

    assert action_requests == []
    assert world_results == []


def test_backend_maps_execution_plan_requested_actions_to_action_request_envelopes() -> None:
    from app.main import _as_character_agent_action_request_envelopes

    execution_payload = {
        "actor_id": "char_b",
        "action_request_bundle": {
            "requested_actions": [
                {
                    "request_type": "interact",
                    "actor_id": "char_b",
                    "target_object_id": "obj_letter",
                    "interaction_type": "inspect",
                }
            ]
        },
    }

    messages = _as_character_agent_action_request_envelopes(execution_payload, producer_ts=1602)

    assert messages
    assert messages[0]["message_type"] == "action_request"
    assert messages[0]["payload"]["request_type"] == "interact"
    assert messages[0]["payload"]["source"]["system"] == "character_agent_l4"
    assert messages[0]["payload"]["target_entity_refs"]["object_ids"] == ["obj_letter"]


def test_backend_maps_execution_plan_approach_requests_to_action_request_envelopes() -> None:
    from app.main import _as_character_agent_action_request_envelopes

    execution_payload = {
        "actor_id": "char_b",
        "action_request_bundle": {
            "requested_actions": [
                {
                    "request_type": "approach",
                    "actor_id": "char_b",
                    "target_actor_id": "char_a",
                }
            ]
        },
    }

    messages = _as_character_agent_action_request_envelopes(execution_payload, producer_ts=1603)

    assert messages
    assert messages[0]["message_type"] == "action_request"
    assert messages[0]["payload"]["request_type"] == "approach"
    assert messages[0]["payload"]["source"]["system"] == "character_agent_l4"
    assert messages[0]["payload"]["target_entity_refs"]["actor_ids"] == ["char_a"]


def test_backend_maps_execution_plan_public_speech_requests_to_authority_chain_entry() -> None:
    from app.main import _as_character_agent_action_request_envelopes

    execution_payload = {
        "actor_id": "char_b",
        "action_request_bundle": {
            "requested_actions": [
                {
                    "request_type": "speak_public",
                    "actor_id": "char_b",
                    "target_actor_id": "char_a",
                    "content": "Look at the letter.",
                }
            ]
        },
    }

    messages = _as_character_agent_action_request_envelopes(execution_payload, producer_ts=1605)

    assert messages
    assert messages[0]["message_type"] == "character_agent_dialogue_request"
    assert messages[0]["payload"]["target_actor_id"] == "char_a"
    assert messages[0]["payload"]["content"] == "Look at the letter."


def test_backend_maps_execution_plan_private_speech_requests_to_authority_chain_entry() -> None:
    from app.main import _as_character_agent_action_request_envelopes

    execution_payload = {
        "actor_id": "char_b",
        "action_request_bundle": {
            "requested_actions": [
                {
                    "request_type": "speak_private",
                    "actor_id": "char_b",
                    "target_actor_id": "char_a",
                    "content": "Keep this between us.",
                }
            ]
        },
    }

    messages = _as_character_agent_action_request_envelopes(execution_payload, producer_ts=1609)

    assert messages
    assert messages[0]["message_type"] == "character_agent_dialogue_request"
    assert messages[0]["payload"]["target_actor_id"] == "char_a"
    assert messages[0]["payload"]["content"] == "Keep this between us."


def test_backend_maps_execution_plan_share_info_requests_to_authority_chain_entry() -> None:
    from app.main import _as_character_agent_action_request_envelopes

    execution_payload = {
        "actor_id": "char_b",
        "action_request_bundle": {
            "requested_actions": [
                {
                    "request_type": "share_info",
                    "actor_id": "char_b",
                    "target_actor_id": "char_a",
                    "content": "The letter matters.",
                }
            ]
        },
    }

    messages = _as_character_agent_action_request_envelopes(execution_payload, producer_ts=1610)

    assert messages
    assert messages[0]["message_type"] == "character_agent_dialogue_request"
    assert messages[0]["payload"]["target_actor_id"] == "char_a"
    assert messages[0]["payload"]["content"] == "The letter matters."


def test_backend_maps_execution_plan_withhold_requests_to_authority_chain_entry() -> None:
    from app.main import _as_character_agent_action_request_envelopes

    execution_payload = {
        "actor_id": "char_b",
        "action_request_bundle": {
            "requested_actions": [
                {
                    "request_type": "withhold",
                    "actor_id": "char_b",
                    "target_actor_id": "char_a",
                    "content": "I should not say more.",
                }
            ]
        },
    }

    messages = _as_character_agent_action_request_envelopes(execution_payload, producer_ts=1611)

    assert messages
    assert messages[0]["message_type"] == "character_agent_dialogue_request"
    assert messages[0]["payload"]["target_actor_id"] == "char_a"
    assert messages[0]["payload"]["content"] == "I should not say more."


def test_backend_maps_execution_plan_seek_private_distance_requests_to_action_request_envelopes() -> None:
    from app.main import _as_character_agent_action_request_envelopes

    execution_payload = {
        "actor_id": "char_b",
        "action_request_bundle": {
            "requested_actions": [
                {
                    "request_type": "seek_private_distance",
                    "actor_id": "char_b",
                    "target_actor_id": "char_a",
                }
            ]
        },
    }

    messages = _as_character_agent_action_request_envelopes(execution_payload, producer_ts=1606)

    assert messages
    assert messages[0]["message_type"] == "action_request"
    assert messages[0]["payload"]["request_type"] == "seek_private_distance"
    assert messages[0]["payload"]["target_entity_refs"]["actor_ids"] == ["char_a"]


def test_backend_maps_execution_plan_withdraw_requests_to_action_request_envelopes() -> None:
    from app.main import _as_character_agent_action_request_envelopes

    execution_payload = {
        "actor_id": "char_b",
        "action_request_bundle": {
            "requested_actions": [
                {
                    "request_type": "withdraw",
                    "actor_id": "char_b",
                    "target_actor_id": "char_a",
                }
            ]
        },
    }

    messages = _as_character_agent_action_request_envelopes(execution_payload, producer_ts=1607)

    assert messages
    assert messages[0]["message_type"] == "action_request"
    assert messages[0]["payload"]["request_type"] == "withdraw"
    assert messages[0]["payload"]["target_entity_refs"]["actor_ids"] == ["char_a"]


def test_backend_maps_execution_plan_follow_target_requests_to_action_request_envelopes() -> None:
    from app.main import _as_character_agent_action_request_envelopes

    execution_payload = {
        "actor_id": "char_b",
        "action_request_bundle": {
            "requested_actions": [
                {
                    "request_type": "follow_target",
                    "actor_id": "char_b",
                    "target_actor_id": "char_a",
                }
            ]
        },
    }

    messages = _as_character_agent_action_request_envelopes(execution_payload, producer_ts=1608)

    assert messages
    assert messages[0]["message_type"] == "action_request"
    assert messages[0]["payload"]["request_type"] == "follow_target"
    assert messages[0]["payload"]["target_entity_refs"]["actor_ids"] == ["char_a"]


def test_backend_maps_execution_plan_break_contact_requests_to_action_request_envelopes() -> None:
    from app.main import _as_character_agent_action_request_envelopes

    execution_payload = {
        "actor_id": "char_b",
        "action_request_bundle": {
            "requested_actions": [
                {
                    "request_type": "break_contact",
                    "actor_id": "char_b",
                    "target_actor_id": "char_a",
                }
            ]
        },
    }

    messages = _as_character_agent_action_request_envelopes(execution_payload, producer_ts=1612)

    assert messages
    assert messages[0]["message_type"] == "action_request"
    assert messages[0]["payload"]["request_type"] == "break_contact"
    assert messages[0]["payload"]["target_entity_refs"]["actor_ids"] == ["char_a"]


def test_character_agent_execution_message_routes_break_contact_request_through_esm_with_settlement_result() -> None:
    reset_runtime_state()
    messages = _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "break_contact",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                        }
                    ]
                },
            },
        )
    )

    assert messages[0]["message_type"] == "ack"
    assert messages[0]["payload"]["route"] == "esm_service"
    assert any(message["message_type"] == "action_request" for message in messages)
    world_results = [message for message in messages if message["message_type"] == "world_result"]
    assert world_results
    assert world_results[0]["event_type"] == "action_resolution_result"
    assert world_results[0]["entity_id"] == "char_a"


def test_character_agent_execution_message_routes_withdraw_request_through_esm_with_settlement_result() -> None:
    reset_runtime_state()
    messages = _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "withdraw",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                        }
                    ]
                },
            },
        )
    )

    assert messages[0]["message_type"] == "ack"
    assert messages[0]["payload"]["route"] == "esm_service"
    assert any(message["message_type"] == "action_request" for message in messages)
    world_results = [message for message in messages if message["message_type"] == "world_result"]
    assert world_results
    assert world_results[0]["event_type"] == "action_resolution_result"
    assert world_results[0]["entity_id"] == "char_a"


def test_character_agent_execution_message_routes_public_speech_through_character_service() -> None:
    reset_runtime_state()
    messages = _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "speak_public",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                            "content": "Look at the letter.",
                        }
                    ]
                },
            },
        )
    )

    assert messages[0]["message_type"] == "ack"
    assert messages[0]["payload"]["route"] == "character_service"
    assert any(message["message_type"] == "character_agent_dialogue_request" for message in messages)
    assert any(message["message_type"] == "dialogue_response" for message in messages)


def test_character_agent_execution_message_routes_private_speech_through_character_service() -> None:
    reset_runtime_state()
    messages = _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "speak_private",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                            "content": "Keep this between us.",
                        }
                    ]
                },
            },
        )
    )

    assert messages[0]["message_type"] == "ack"
    assert messages[0]["payload"]["route"] == "character_service"
    assert any(message["message_type"] == "character_agent_dialogue_request" for message in messages)
    assert any(message["message_type"] == "dialogue_response" for message in messages)


def test_character_agent_execution_message_routes_share_info_through_character_service() -> None:
    reset_runtime_state()
    messages = _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "share_info",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                            "content": "The letter matters.",
                        }
                    ]
                },
            },
        )
    )

    assert messages[0]["message_type"] == "ack"
    assert messages[0]["payload"]["route"] == "character_service"
    assert any(message["message_type"] == "character_agent_dialogue_request" for message in messages)
    assert any(message["message_type"] == "dialogue_response" for message in messages)


def test_character_agent_execution_message_routes_withhold_through_character_service() -> None:
    reset_runtime_state()
    messages = _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "withhold",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                            "content": "I should not say more.",
                        }
                    ]
                },
            },
        )
    )

    assert messages[0]["message_type"] == "ack"
    assert messages[0]["payload"]["route"] == "character_service"
    assert any(message["message_type"] == "character_agent_dialogue_request" for message in messages)
    assert any(message["message_type"] == "dialogue_response" for message in messages)


def test_character_agent_execution_message_routes_interact_request_through_esm() -> None:
    reset_runtime_state()
    messages = _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "interact",
                            "actor_id": "char_b",
                            "target_object_id": "obj_letter",
                            "interaction_type": "inspect",
                        }
                    ]
                },
            },
        )
    )

    assert messages[0]["message_type"] == "ack"
    assert messages[0]["payload"]["route"] == "esm_service"
    assert any(message["message_type"] == "action_request" for message in messages)
    assert any(message["message_type"] == "world_result" for message in messages)


def test_character_agent_execution_message_routes_approach_request_through_esm_with_settlement_result() -> None:
    reset_runtime_state()
    messages = _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "approach",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                        }
                    ]
                },
            },
        )
    )

    assert messages[0]["message_type"] == "ack"
    assert messages[0]["payload"]["route"] == "esm_service"
    assert any(message["message_type"] == "action_request" for message in messages)
    world_results = [message for message in messages if message["message_type"] == "world_result"]
    assert world_results
    assert world_results[0]["event_type"] == "action_resolution_result"
    assert world_results[0]["entity_id"] == "char_a"
    assert world_results[0]["payload"]["action_profile"] == "approach"
    assert world_results[0]["payload"]["source_action_request_type"] == "approach"
    assert world_results[0]["payload"]["applied_state_changes"] == ["social_spatial_state_result"]


def test_character_agent_execution_message_routes_follow_target_request_through_esm_with_settlement_result() -> None:
    reset_runtime_state()
    messages = _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "follow_target",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                        }
                    ]
                },
            },
        )
    )

    assert messages[0]["message_type"] == "ack"
    assert messages[0]["payload"]["route"] == "esm_service"
    assert any(message["message_type"] == "action_request" for message in messages)
    world_results = [message for message in messages if message["message_type"] == "world_result"]
    assert world_results
    assert world_results[0]["event_type"] == "action_resolution_result"
    assert world_results[0]["entity_id"] == "char_a"
    assert world_results[0]["payload"]["action_profile"] == "follow_target"
    assert world_results[0]["payload"]["source_action_request_type"] == "follow_target"
    assert world_results[0]["payload"]["applied_state_changes"] == ["social_spatial_state_result"]


def test_character_agent_execution_message_routes_seek_private_distance_request_through_esm_with_settlement_result() -> None:
    reset_runtime_state()
    messages = _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "seek_private_distance",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                        }
                    ]
                },
            },
        )
    )

    assert messages[0]["message_type"] == "ack"
    assert messages[0]["payload"]["route"] == "esm_service"
    assert any(message["message_type"] == "action_request" for message in messages)
    world_results = [message for message in messages if message["message_type"] == "world_result"]
    assert world_results
    assert world_results[0]["event_type"] == "action_resolution_result"
    assert world_results[0]["entity_id"] == "char_a"
    assert world_results[0]["payload"]["action_profile"] == "seek_private_distance"
    assert world_results[0]["payload"]["source_action_request_type"] == "seek_private_distance"
    assert world_results[0]["payload"]["applied_state_changes"] == ["social_spatial_state_result"]


def test_approach_request_and_settlement_are_written_back_to_runtime_timeline() -> None:
    import app.main as main

    reset_runtime_state()
    _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "approach",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                        }
                    ]
                },
            },
        )
    )

    timeline = main.character_agent_runtime.get_session_timeline("char_b")
    bundle = main.character_agent_runtime.get_memory_bundle("char_b")

    event_types = [entry["event_type"] for entry in timeline]
    assert "character_agent_execution_request" in event_types
    assert "character_agent_settlement_result" in event_types
    assert any(entry["event_type"] == "character_agent_execution_request" for entry in bundle["working_memory"])
    assert any(entry["event_type"] == "character_agent_settlement_result" for entry in bundle["working_memory"])


def test_follow_target_request_and_settlement_are_written_back_to_runtime_timeline() -> None:
    import app.main as main

    reset_runtime_state()
    _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "follow_target",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                        }
                    ]
                },
            },
        )
    )

    timeline = main.character_agent_runtime.get_session_timeline("char_b")
    bundle = main.character_agent_runtime.get_memory_bundle("char_b")

    event_types = [entry["event_type"] for entry in timeline]
    assert "character_agent_execution_request" in event_types
    assert "character_agent_settlement_result" in event_types
    assert any(entry["event_type"] == "character_agent_execution_request" for entry in bundle["working_memory"])
    assert any(entry["event_type"] == "character_agent_settlement_result" for entry in bundle["working_memory"])


def test_seek_private_distance_request_and_settlement_are_written_back_to_runtime_timeline() -> None:
    import app.main as main

    reset_runtime_state()
    _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "seek_private_distance",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                        }
                    ]
                },
            },
        )
    )

    timeline = main.character_agent_runtime.get_session_timeline("char_b")
    bundle = main.character_agent_runtime.get_memory_bundle("char_b")

    event_types = [entry["event_type"] for entry in timeline]
    assert "character_agent_execution_request" in event_types
    assert "character_agent_settlement_result" in event_types
    assert any(entry["event_type"] == "character_agent_execution_request" for entry in bundle["working_memory"])
    assert any(entry["event_type"] == "character_agent_settlement_result" for entry in bundle["working_memory"])


def test_approach_settlement_is_written_into_episodic_memory() -> None:
    import app.main as main

    reset_runtime_state()
    _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "approach",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                        }
                    ]
                },
            },
        )
    )

    bundle = main.character_agent_runtime.get_memory_bundle("char_b")

    assert bundle["episodic_memories"]
    assert bundle["episodic_memories"][-1]["summary"] == "approach accepted"


def test_follow_target_settlement_is_written_into_episodic_memory() -> None:
    import app.main as main

    reset_runtime_state()
    _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "follow_target",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                        }
                    ]
                },
            },
        )
    )

    bundle = main.character_agent_runtime.get_memory_bundle("char_b")

    assert bundle["episodic_memories"]
    assert bundle["episodic_memories"][-1]["summary"] == "follow_target accepted"


def test_seek_private_distance_settlement_is_written_into_episodic_memory() -> None:
    import app.main as main

    reset_runtime_state()
    _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "seek_private_distance",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                        }
                    ]
                },
            },
        )
    )

    bundle = main.character_agent_runtime.get_memory_bundle("char_b")

    assert bundle["episodic_memories"]
    assert bundle["episodic_memories"][-1]["summary"] == "seek_private_distance accepted"


def test_break_contact_request_and_settlement_are_written_back_to_runtime_timeline() -> None:
    import app.main as main

    reset_runtime_state()
    _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "break_contact",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                        }
                    ]
                },
            },
        )
    )

    timeline = main.character_agent_runtime.get_session_timeline("char_b")
    bundle = main.character_agent_runtime.get_memory_bundle("char_b")

    event_types = [entry["event_type"] for entry in timeline]
    assert "character_agent_execution_request" in event_types
    assert "character_agent_settlement_result" in event_types
    assert any(entry["event_type"] == "character_agent_execution_request" for entry in bundle["working_memory"])
    assert any(entry["event_type"] == "character_agent_settlement_result" for entry in bundle["working_memory"])


def test_withdraw_request_and_settlement_are_written_back_to_runtime_timeline() -> None:
    import app.main as main

    reset_runtime_state()
    _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "withdraw",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                        }
                    ]
                },
            },
        )
    )

    timeline = main.character_agent_runtime.get_session_timeline("char_b")
    bundle = main.character_agent_runtime.get_memory_bundle("char_b")

    event_types = [entry["event_type"] for entry in timeline]
    assert "character_agent_execution_request" in event_types
    assert "character_agent_settlement_result" in event_types
    assert any(entry["event_type"] == "character_agent_execution_request" for entry in bundle["working_memory"])
    assert any(entry["event_type"] == "character_agent_settlement_result" for entry in bundle["working_memory"])


def test_actor_target_settlements_carry_structured_social_spatial_metadata() -> None:
    import app.main as main

    reset_runtime_state()
    messages = _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "break_contact",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                        }
                    ]
                },
            },
        )
    )

    world_result_payloads = [message["payload"] for message in messages if message["message_type"] == "world_result"]
    assert world_result_payloads
    payload = world_result_payloads[0]

    assert payload["action_profile"] == "break_contact"
    assert payload["source_action_request_type"] == "break_contact"
    assert payload["applied_state_changes"] == ["social_spatial_state_result"]
    assert "stable_state_summary" in payload


def test_break_contact_settlement_is_written_into_episodic_memory() -> None:
    import app.main as main

    reset_runtime_state()
    _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "break_contact",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                        }
                    ]
                },
            },
        )
    )

    bundle = main.character_agent_runtime.get_memory_bundle("char_b")

    assert bundle["episodic_memories"]
    assert bundle["episodic_memories"][-1]["summary"] == "break_contact accepted"


def test_withdraw_settlement_is_written_into_episodic_memory() -> None:
    import app.main as main

    reset_runtime_state()
    _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "withdraw",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                        }
                    ]
                },
            },
        )
    )

    bundle = main.character_agent_runtime.get_memory_bundle("char_b")

    assert bundle["episodic_memories"]
    assert bundle["episodic_memories"][-1]["summary"] == "withdraw accepted"


def test_character_agent_execution_request_and_settlement_are_written_back_to_runtime_timeline() -> None:
    import app.main as main

    reset_runtime_state()
    _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "interact",
                            "actor_id": "char_b",
                            "target_object_id": "obj_letter",
                            "interaction_type": "inspect",
                        }
                    ]
                },
            },
        )
    )

    timeline = main.character_agent_runtime.get_session_timeline("char_b")
    bundle = main.character_agent_runtime.get_memory_bundle("char_b")

    event_types = [entry["event_type"] for entry in timeline]
    assert "character_agent_execution_request" in event_types
    assert "character_agent_settlement_result" in event_types
    assert any(entry["event_type"] == "character_agent_execution_request" for entry in bundle["working_memory"])
    assert any(entry["event_type"] == "character_agent_settlement_result" for entry in bundle["working_memory"])


def test_agent_originated_settlement_is_written_into_episodic_memory() -> None:
    import app.main as main

    reset_runtime_state()
    _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "interact",
                            "actor_id": "char_b",
                            "target_object_id": "obj_letter",
                            "interaction_type": "inspect",
                        }
                    ]
                },
            },
        )
    )

    bundle = main.character_agent_runtime.get_memory_bundle("char_b")

    assert bundle["episodic_memories"]
    assert bundle["episodic_memories"][-1]["summary"] == "interaction accepted"


def test_public_speech_request_and_dialogue_response_are_written_back_to_runtime_timeline() -> None:
    import app.main as main

    reset_runtime_state()
    _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "speak_public",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                            "content": "Look at the letter.",
                        }
                    ]
                },
            },
        )
    )

    timeline = main.character_agent_runtime.get_session_timeline("char_b")
    bundle = main.character_agent_runtime.get_memory_bundle("char_b")

    event_types = [entry["event_type"] for entry in timeline]
    assert "character_agent_execution_request" in event_types
    assert "character_agent_dialogue_response" in event_types
    assert any(entry["event_type"] == "character_agent_execution_request" for entry in bundle["working_memory"])
    assert any(entry["event_type"] == "character_agent_dialogue_response" for entry in bundle["working_memory"])


def test_public_speech_response_is_written_into_episodic_memory() -> None:
    import app.main as main

    reset_runtime_state()
    _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "speak_public",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                            "content": "Look at the letter.",
                        }
                    ]
                },
            },
        )
    )

    bundle = main.character_agent_runtime.get_memory_bundle("char_b")

    assert bundle["episodic_memories"]
    assert bundle["episodic_memories"][-1]["summary"].startswith("dialogue_response:")


def test_withhold_request_and_dialogue_response_are_written_back_to_runtime_timeline() -> None:
    import app.main as main

    reset_runtime_state()
    _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "withhold",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                            "content": "I should not say more.",
                        }
                    ]
                },
            },
        )
    )

    timeline = main.character_agent_runtime.get_session_timeline("char_b")
    bundle = main.character_agent_runtime.get_memory_bundle("char_b")

    event_types = [entry["event_type"] for entry in timeline]
    assert "character_agent_execution_request" in event_types
    assert "character_agent_dialogue_response" in event_types
    assert any(entry["event_type"] == "character_agent_execution_request" for entry in bundle["working_memory"])
    assert any(entry["event_type"] == "character_agent_dialogue_response" for entry in bundle["working_memory"])


def test_withhold_response_is_written_into_episodic_memory() -> None:
    import app.main as main

    reset_runtime_state()
    _handle_envelope(
        Envelope(
            message_type="character_agent_execution",
            payload={
                "actor_id": "char_b",
                "action_request_bundle": {
                    "requested_actions": [
                        {
                            "request_type": "withhold",
                            "actor_id": "char_b",
                            "target_actor_id": "char_a",
                            "content": "I should not say more.",
                        }
                    ]
                },
            },
        )
    )

    bundle = main.character_agent_runtime.get_memory_bundle("char_b")

    assert bundle["episodic_memories"]
    assert bundle["episodic_memories"][-1]["summary"].startswith("dialogue_response:")
