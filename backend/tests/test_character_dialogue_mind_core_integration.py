import app.main as main
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.config import settings
from app.models.character_perceived import CharacterPerceivedEvent
from app.services.dialogue_service import DialogueService
from app.ws_protocol import Envelope


class _RecordingProvider:
    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def complete(self, request: dict[str, object]) -> dict[str, object]:
        self.requests.append(request)
        return {
            "content": "The profile-backed reply is available.",
            "tone": "neutral",
        }


def _player_dialogue_envelope(*, content: str = "Remember the candle.") -> Envelope:
    return Envelope(
        message_type="player_input",
        payload={
            "player_id": "p1",
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "actor_id": "char_c",
            "intent_type": "dialogue_submit",
            "producer_ts": 2301,
            "target_actor_id": "char_a",
            "content": content,
        },
    )


def _agent_speech_envelope(
    *,
    request_type: str,
    content: str,
    source_ref_lineage: list[str] | None = None,
) -> Envelope:
    action: dict[str, object] = {
        "request_type": request_type,
        "actor_id": "char_b",
        "target_actor_id": "char_a",
        "content": content,
    }
    if source_ref_lineage is not None:
        action["source_ref_lineage"] = source_ref_lineage
    return Envelope(
        message_type="character_agent_execution",
        payload={
            "actor_id": "char_b",
            "action_request_bundle": {
                "requested_actions": [action],
            },
        },
    )


def test_player_dialogue_submit_ingests_target_memory_and_social_record(monkeypatch) -> None:
    monkeypatch.setattr(settings, "dialogue_mode", "stub")
    main.reset_runtime_state()

    messages = main._handle_envelope(_player_dialogue_envelope())
    bundle = main.character_agent_runtime.get_memory_bundle("char_a")

    assert any(message["message_type"] == "dialogue_response" for message in messages)
    assert any(
        "Remember the candle." in str(entry.get("summary", ""))
        for entry in bundle["episodic_memories"]
    )
    assert any(
        entry.get("entity_id") == "char_c"
        for entry in bundle["social_memories"]
    )


def test_dialogue_service_context_provider_populates_online_prompt_context(monkeypatch) -> None:
    monkeypatch.setattr(settings, "dialogue_mode", "online")
    monkeypatch.delenv("CHARACTER_MODEL_ROUTE_OVERRIDE", raising=False)
    provider = _RecordingProvider()
    service = DialogueService(
        gateway=CharacterModelGateway(provider=provider),
        context_provider=lambda actor_id: {
            "profile": {
                "identity_core": {
                    "character_id": actor_id,
                    "canonical_name": "Lin Yue",
                }
            },
            "effective_profile": {
                "identity_core": {
                    "character_id": actor_id,
                    "canonical_name": "Lin Yue",
                },
                "need_hierarchy_layer": {
                    "effective_weights": {
                        "safety": 0.8,
                        "esteem": 0.7,
                    }
                },
            },
            "snapshot": {"audible_entities": ["dialogue_submit:2302:char_c:char_a"]},
            "memory": {
                "working_memory": [],
                "event_memories": [{"summary": "char_c asked about the candle"}],
                "social_memories": [{"entity_id": "char_c", "trust_baseline": 0.5}],
            },
            "need_tension_state": {"dominant_need": "safety", "safety_pressure": 0.2},
        },
    )

    service.generate_reply("char_a", "Did you hear me?")

    assert provider.requests
    request = provider.requests[0]
    context = request["context"]
    user_instruction = str(request["prompt"]["user_instruction"])

    assert request["route"]["route_mode"] == "online_default"
    assert context["profile"]["identity_core"]["character_id"] == "char_a"
    assert context["effective_profile"]["need_hierarchy_layer"]["effective_weights"]["safety"] == 0.8
    assert "canonical_name=Lin Yue" in user_instruction
    assert "effective_profile_summary=" in user_instruction
    assert "need_tension_state=dominant_need=safety" in user_instruction


def test_stub_dialogue_submit_keeps_dialogue_response_contract(monkeypatch) -> None:
    monkeypatch.setattr(settings, "dialogue_mode", "stub")
    main.reset_runtime_state()

    messages = main._handle_envelope(_player_dialogue_envelope(content="Hello."))
    response = next(message for message in messages if message["message_type"] == "dialogue_response")
    payload = response["payload"]

    assert payload["output_type"] == "dialogue_response"
    assert payload["actor_id"] == "char_a"
    assert payload["target_actor_id"] == "char_c"
    assert isinstance(payload["content"], str)
    assert payload["tone"]
    assert payload["tts_required"] is True


def test_agent_speak_private_content_transfers_without_stub_regeneration(monkeypatch) -> None:
    monkeypatch.setattr(settings, "dialogue_mode", "stub")
    main.reset_runtime_state()

    messages = main._handle_envelope(_agent_speech_envelope(
        request_type="speak_private",
        content="Keep this between us.",
    ))
    response = next(message for message in messages if message["message_type"] == "dialogue_response")

    assert response["payload"]["content"] == "Keep this between us."
    assert response["payload"]["tone"] == "neutral"


def test_agent_speak_private_backfills_target_semantic_memory(monkeypatch) -> None:
    monkeypatch.setattr(settings, "dialogue_mode", "stub")
    main.reset_runtime_state()

    main._handle_envelope(_agent_speech_envelope(
        request_type="speak_private",
        content="The west door is unsafe.",
    ))
    bundle = main.character_agent_runtime.get_memory_bundle("char_a")
    timeline = main.character_agent_runtime.get_session_timeline("char_a")
    latest = main.character_perceived_input_service.get_latest("char_a")

    assert latest is not None
    assert "The west door is unsafe." in latest.perceived_summary
    assert any(
        "The west door is unsafe." in str(entry.get("summary", ""))
        for entry in bundle["episodic_memories"]
    )
    assert any(entry.get("entity_id") == "char_b" for entry in bundle["social_memories"])
    assert any(
        entry["event_type"] == "character_perceived_event"
        and "The west door is unsafe." in str(entry.get("payload", {}).get("summary", ""))
        for entry in timeline
    )


def test_agent_speak_public_backfills_other_agents_not_only_speaker(monkeypatch) -> None:
    monkeypatch.setattr(settings, "dialogue_mode", "stub")
    main.reset_runtime_state()
    main.l1_occupancy_service.apply_actor_zone_update(
        actor_id="char_a",
        previous_zone_id="",
        next_zone_id="zone_focus",
        producer_ts=1,
        source_ref="test:char_a",
    )
    main.l1_occupancy_service.apply_actor_zone_update(
        actor_id="char_b",
        previous_zone_id="",
        next_zone_id="zone_focus",
        producer_ts=1,
        source_ref="test:char_b",
    )
    main.l1_occupancy_service.apply_actor_zone_update(
        actor_id="char_c",
        previous_zone_id="",
        next_zone_id="zone_focus",
        producer_ts=1,
        source_ref="test:char_c",
    )

    main._handle_envelope(_agent_speech_envelope(
        request_type="speak_public",
        content="Everyone should watch the letter.",
    ))
    listener_bundle = main.character_agent_runtime.get_memory_bundle("char_a")
    speaker_timeline = main.character_agent_runtime.get_session_timeline("char_b")
    player_shell_timeline = main.character_agent_runtime.get_session_timeline("char_c")

    assert any(
        "Everyone should watch the letter." in str(entry.get("summary", ""))
        for entry in listener_bundle["episodic_memories"]
    )
    assert not any(
        entry["event_type"] == "character_perceived_event"
        and "Everyone should watch the letter." in str(entry.get("payload", {}).get("summary", ""))
        for entry in speaker_timeline
    )
    assert not any(
        "Everyone should watch the letter." in str(entry.get("payload", {}).get("summary", ""))
        for entry in player_shell_timeline
    )


def test_share_info_and_withhold_backfill_target_by_visibility(monkeypatch) -> None:
    monkeypatch.setattr(settings, "dialogue_mode", "stub")
    cases = [
        ("share_info", "The letter has a hidden mark."),
        ("withhold", "I should not say more about the letter."),
    ]

    for request_type, content in cases:
        main.reset_runtime_state()
        main._handle_envelope(_agent_speech_envelope(
            request_type=request_type,
            content=content,
        ))
        target_bundle = main.character_agent_runtime.get_memory_bundle("char_a")
        speaker_timeline = main.character_agent_runtime.get_session_timeline("char_b")

        assert any(
            content in str(entry.get("summary", ""))
            for entry in target_bundle["episodic_memories"]
        )
        assert not any(
            entry["event_type"] == "character_perceived_event"
            and content in str(entry.get("payload", {}).get("summary", ""))
            for entry in speaker_timeline
        )


def test_agent_speech_backfill_cascade_depth_records_without_cognition(monkeypatch) -> None:
    monkeypatch.setattr(settings, "dialogue_mode", "stub")
    monkeypatch.setattr(settings, "character_dialogue_cascade_limit", 3)
    main.reset_runtime_state()

    main._handle_envelope(_agent_speech_envelope(
        request_type="speak_private",
        content="third cascade from speech",
        source_ref_lineage=["root", "reply"],
    ))
    timeline = main.character_agent_runtime.get_session_timeline("char_a")
    event_types = [entry["event_type"] for entry in timeline]

    assert "character_perceived_event" in event_types
    assert "l2_reasoning_request" not in event_types


def test_dialogue_cascade_depth_records_without_triggering_cognition(monkeypatch) -> None:
    monkeypatch.setattr(settings, "dialogue_mode", "stub")
    monkeypatch.setattr(settings, "character_dialogue_cascade_limit", 3)
    main.reset_runtime_state()
    perceived = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="auditory",
        producer_ts=2304,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary='char_b对你说："third cascade"',
        source_candidate_event_id="dialogue_submit:2304:char_b:char_a",
        source_actor_id="char_b",
        target_actor_id="char_a",
        source_ref_lineage=["root", "reply", "reply"],
    )

    commands = main._ingest_dialogue_perception(perceived)
    timeline = main.character_agent_runtime.get_session_timeline("char_a")
    event_types = [entry["event_type"] for entry in timeline]

    assert commands == []
    assert "character_perceived_event" in event_types
    assert "l2_reasoning_request" not in event_types


def test_dialogue_cascade_default_supports_extended_agent_conversation(monkeypatch) -> None:
    monkeypatch.setattr(settings, "dialogue_mode", "stub")
    monkeypatch.setattr(settings, "character_dialogue_cascade_limit", 180)
    main.reset_runtime_state()
    perceived = CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="auditory",
        producer_ts=2305,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary='char_b对你说："extended cascade"',
        source_candidate_event_id="dialogue_submit:2305:char_b:char_a",
        source_actor_id="char_b",
        target_actor_id="char_a",
        source_ref_lineage=[f"reply:{index}" for index in range(30)],
    )
    calls: list[CharacterPerceivedEvent] = []

    def record_ingest(event: CharacterPerceivedEvent) -> list[object]:
        calls.append(event)
        return []

    monkeypatch.setattr(main.character_agent_runtime, "ingest_character_perceived_event", record_ingest)

    main._ingest_dialogue_perception(perceived)

    assert calls == [perceived]
