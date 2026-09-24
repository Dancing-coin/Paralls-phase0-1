from __future__ import annotations

from app.character_agent.models.embodied_episode import CandidateActionObservation
from app.character_agent.services.embodied_episode_service import EmbodiedEpisodeService
from app.character_agent.models.turn_context import CharacterTurnContext
from app.contracts.l1.action_request import ActionRequest
from app.models.player_input import InteractIntent
from app.services.embodied_execution_ingress import TurnExecutionCorrelation
from app.services.websocket_session_auth_service import WebSocketConnectionContext
import app.main as main


def _connection() -> WebSocketConnectionContext:
    return WebSocketConnectionContext(
        remote_host="127.0.0.1", observed_at=100, connection_ref="ws_connection:turn-door"
    )


def _bind(connection: WebSocketConnectionContext) -> None:
    credential = main.embodied_controller_auth_service.create_trusted_local_launch_credential(
        actor_id="char_c", controller_instance_id="controller:char_c:turn-door", issued_at=100, expires_at=200
    )
    main._handle_envelope(
        main.Envelope(
            message_type="embodied_controller_bind",
            payload={
                "credential_kind": "trusted_local_launch", "credential": credential,
                "actor_id": "char_c", "controller_instance_id": "controller:char_c:turn-door", "protocol_version": 1,
            },
        ),
        connection_context=connection,
    )


def _turn_request() -> ActionRequest:
    return ActionRequest(
        request_id="character-door:1", request_type="interact", room_id="room_demo", scene_id="scene_demo",
        zone_id="zone_focus", actor_id="char_c", action_type="character_agent_execution",
        target_entity_refs={"actor_ids": [], "object_ids": ["obj_archive_door"], "environment_ids": []},
        action_profile="open", producer_ts=110, causation_id="turn:char_c:door-1", correlation_id="turn:char_c:door-1",
        turn_id="turn:char_c:door-1", idempotency_key="execution:char_c:door-1",
        expected_revision_vector={"world": 1}, expected_memory_revision_vector={"memory": 1},
        expected_snapshot_revision=1, target_object_id="obj_archive_door", payload={"interaction_type": "open"},
    )


def _event() -> InteractIntent:
    return InteractIntent(
        player_id="character_agent", room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
        actor_id="char_c", intent_type="interact_intent", producer_ts=110,
        target_object_id="obj_archive_door", interaction_type="open",
    )


def _move_actor(connection: WebSocketConnectionContext) -> None:
    main._handle_envelope(
        main.Envelope(
            message_type="player_input",
            payload={
                "player_id": "character_agent", "room_id": "room_demo", "scene_id": "scene_demo",
                "zone_id": "zone_focus", "actor_id": "char_c", "intent_type": "move_intent",
                "move_mode": "walk", "producer_ts": 90, "target_point": [0.0, 1.2, -3.1],
            },
        ),
        connection_context=connection,
    )


def _outcome(grant: dict[str, object]) -> dict[str, object]:
    return {
        "interaction_attempt_id": str(grant["interaction_attempt_id"]), "phase": "terminal",
        "terminal_status": "contact_observed", "observed_at": 130, "actor_pose_ref": "pose:char_c:door",
        "target_binding_ref": "binding:obj_archive_door:1",
        "contact_observation": {"contact_ref": "contact:turn-door", "actor_contact_ref": "collider:char_c:hand_r",
            "target_collider_ref": "collider:obj_archive_door:body", "contact_window_ref": "window:turn-door",
            "observation_rule_ref": "observation_rule:archive_door_contact:v1", "hand_alignment_error_m": 0.02},
        "causation_id": "turn:char_c:door-1", "correlation_id": "turn:char_c:door-1",
        "controller_grant_id": str(grant["grant_id"]), "connection_epoch": int(grant["connection_epoch"]),
        "terminal_sequence": 1, "outcome_nonce": str(grant["one_time_outcome_nonce"]),
        "payload_digest": "sha256:turn-door-terminal",
    }


def _candidate() -> CandidateActionObservation:
    return CandidateActionObservation(
        candidate_id="candidate:turn-door", target_ref="obj_archive_door", semantic_action_id="open",
        reviewed_target_ref="obj_archive_door", reviewed_action_ref="affordance:obj_archive_door:open",
        expected_observation={"current_state": "open"}, confidence=1.0, evidence_refs=("capture:door:pre",),
    )


def _turn() -> CharacterTurnContext:
    return CharacterTurnContext.begin(
        actor_id="char_c", source_event_ref="door-1", producer_ts=110,
        causation_id="turn:char_c:door-1", correlation_id="turn:char_c:door-1",
        input_revision_vector={"world": 1}, memory_revision_vector={"memory": 1},
        policy_revision="1", snapshot_revision=1,
    )


def test_archive_door_turn_has_one_contract_receipt_and_confirmed_episode() -> None:
    main.reset_runtime_state()
    connection = _connection()
    _bind(connection)
    _move_actor(connection)
    correlation = TurnExecutionCorrelation(
        turn_id="turn:char_c:door-1", execution_contract_ref="execution:char_c:door-1",
        episode_ref="episode:turn:char_c:door-1:candidate:turn-door", pre_capture_ref="capture:door:pre",
    )
    preflight = main.default_scene_archive_door_embodied_service.preflight(
        event=_event(), action_request=_turn_request(), actor_position=(0.0, 1.2, -3.1),
        connection_ref=connection.connection_ref, now=110, turn_correlation=correlation,
    )

    assert preflight.accepted is True
    grant = preflight.embodied_action_request["grant"]
    settled = main.default_scene_archive_door_embodied_service.handle_local_outcome(
        _outcome(grant), connection_ref=connection.connection_ref, now=130,
    )

    receipt = settled.settlement_payload
    assert receipt is not None
    assert receipt["outcome"] == "committed"
    assert receipt["turn_id"] == "turn:char_c:door-1"
    assert receipt["execution_contract_ref"] == "execution:char_c:door-1"
    assert receipt["episode_ref"] == correlation.episode_ref
    assert settled.object_result is not None
    assert settled.object_result.turn_id == "turn:char_c:door-1"
    episode = EmbodiedEpisodeService().complete(
        EmbodiedEpisodeService().begin(_turn(), _candidate(), pre_capture_ref="capture:door:pre"),
        authority_result=receipt, post_capture_ref="capture:door:post", observed_state="open",
    )
    assert episode.outcome == "confirmed_success"
    assert episode.turn_id == "turn:char_c:door-1"
    assert episode.post_capture_ref == "capture:door:post"


def test_turn_correlation_requires_contract_identity_and_rejected_settlement_does_not_mutate() -> None:
    invalid = TurnExecutionCorrelation.from_payload({"turn_id": "turn:char_c:door-2"})
    assert invalid.accepted is False
    assert invalid.error_code == "execution_contract_ref_required"

    main.reset_runtime_state()
    connection = _connection()
    _bind(connection)
    _move_actor(connection)
    correlation = TurnExecutionCorrelation(
        turn_id="turn:char_c:door-2", execution_contract_ref="execution:char_c:door-2",
        episode_ref="episode:turn:char_c:door-2:candidate", pre_capture_ref="capture:door:pre",
    )
    preflight = main.default_scene_archive_door_embodied_service.preflight(
        event=_event(), action_request=_turn_request().model_copy(update={"turn_id": correlation.turn_id, "idempotency_key": correlation.execution_contract_ref}),
        actor_position=(0.0, 1.2, -3.1), connection_ref=connection.connection_ref, now=110,
        turn_correlation=correlation,
    )
    grant = preflight.embodied_action_request["grant"]
    main.default_scene_archive_door_embodied_service.binding_revision += 1
    rejected = main.default_scene_archive_door_embodied_service.handle_local_outcome(
        _outcome(grant), connection_ref=connection.connection_ref, now=130,
    )

    assert rejected.settlement_payload["error_code"] == "binding_revision_mismatch"
    assert rejected.settlement_payload["turn_id"] == correlation.turn_id
    assert rejected.object_result is None
    assert main.default_scene_archive_door_embodied_service.commit_count == 0
