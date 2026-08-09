from __future__ import annotations

from app.services.websocket_session_auth_service import WebSocketConnectionContext
from app.ws_protocol import Envelope
import app.main as main


def _connection(connection_ref: str = "ws_connection:door-test") -> WebSocketConnectionContext:
    return WebSocketConnectionContext(
        remote_host="127.0.0.1",
        observed_at=100,
        connection_ref=connection_ref,
    )


def _bind_controller(
    connection_context: WebSocketConnectionContext,
    *,
    actor_id: str = "char_c",
    controller_instance_id: str = "controller:char_c:door",
) -> list[dict[str, object]]:
    credential = main.embodied_controller_auth_service.create_trusted_local_launch_credential(
        actor_id=actor_id,
        controller_instance_id=controller_instance_id,
        issued_at=100,
        expires_at=200,
    )
    return main._handle_envelope(
        Envelope(
            message_type="embodied_controller_bind",
            payload={
                "credential_kind": "trusted_local_launch",
                "credential": credential,
                "actor_id": actor_id,
                "controller_instance_id": controller_instance_id,
                "protocol_version": 1,
            },
        ),
        connection_context=connection_context,
    )


def _move_actor(
    connection_context: WebSocketConnectionContext,
    *,
    actor_id: str,
    producer_ts: int,
    target_point: tuple[float, float, float],
) -> None:
    main._handle_envelope(
        Envelope(
            message_type="player_input",
            payload={
                "player_id": "p1",
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "actor_id": actor_id,
                "intent_type": "move_intent",
                "move_mode": "walk",
                "producer_ts": producer_ts,
                "target_point": list(target_point),
            },
        ),
        connection_context=connection_context,
    )


def _interact(
    connection_context: WebSocketConnectionContext,
    *,
    producer_ts: int,
    interaction_type: str,
    actor_id: str = "char_c",
) -> list[dict[str, object]]:
    return main._handle_envelope(
        Envelope(
            message_type="player_input",
            payload={
                "player_id": "p1",
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "actor_id": actor_id,
                "intent_type": "interact_intent",
                "producer_ts": producer_ts,
                "target_object_id": "obj_archive_door",
                "interaction_type": interaction_type,
            },
        ),
        connection_context=connection_context,
    )


def _first_message(messages: list[dict[str, object]], message_type: str) -> dict[str, object]:
    return next(message for message in messages if message.get("message_type") == message_type)


def _first_world_result(messages: list[dict[str, object]], event_type: str) -> dict[str, object]:
    return next(
        message
        for message in messages
        if message.get("message_type") == "world_result" and message.get("event_type") == event_type
    )


def _door_state() -> str:
    return main.esm_service.interaction_state_for(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        target_object_id="obj_archive_door",
    )


def _door_outcome(
    grant_id: str,
    *,
    connection_epoch: int,
    outcome_nonce: str,
    payload_digest: str = "sha256:door-terminal",
) -> dict[str, object]:
    return {
        "interaction_attempt_id": "attempt:obj_archive_door:interact:110:obj_archive_door",
        "phase": "terminal",
        "terminal_status": "contact_observed",
        "observed_at": 130,
        "actor_pose_ref": "pose:char_c:door-open",
        "target_binding_ref": "binding:obj_archive_door:1",
        "contact_observation": {
            "contact_ref": "contact:attempt:obj_archive_door:1",
            "actor_contact_ref": "collider:char_c:hand_r",
            "target_collider_ref": "collider:obj_archive_door:body",
            "contact_window_ref": "window:door-open:1",
            "observation_rule_ref": "observation_rule:archive_door_contact:v1",
            "hand_alignment_error_m": 0.02,
        },
        "trace_refs": ["trace:door:terminal"],
        "causation_id": "interact:110",
        "correlation_id": "interact:110",
        "controller_grant_id": grant_id,
        "connection_epoch": connection_epoch,
        "terminal_sequence": 1,
        "outcome_nonce": outcome_nonce,
        "payload_digest": payload_digest,
    }


def test_archive_door_open_requires_bound_controller_and_close_fails_closed() -> None:
    main.reset_runtime_state()
    connection = _connection()
    _move_actor(connection, actor_id="char_c", producer_ts=90, target_point=(0.0, 1.2, -3.1))

    missing_binding = _interact(connection, producer_ts=100, interaction_type="open")
    missing_constraint = _first_world_result(missing_binding, "constraint_state_result")

    assert missing_constraint["payload"]["constraint_code"] == "controller_binding_required"
    assert _door_state() == "closed"

    _bind_controller(connection)
    close_attempt = _interact(connection, producer_ts=101, interaction_type="close")
    close_constraint = _first_world_result(close_attempt, "constraint_state_result")

    assert close_constraint["payload"]["constraint_code"] == "physical_close_not_implemented"
    assert _door_state() == "closed"


def test_archive_door_preflight_replays_same_grant_and_blocks_competing_attempts() -> None:
    main.reset_runtime_state()
    connection = _connection()
    _bind_controller(connection)
    _move_actor(connection, actor_id="char_c", producer_ts=90, target_point=(0.0, 1.2, -3.1))

    first = _interact(connection, producer_ts=110, interaction_type="open")
    replay = _interact(connection, producer_ts=110, interaction_type="open")
    competing = _interact(connection, producer_ts=111, interaction_type="open")

    first_preflight = _first_message(first, "embodied_action_request")
    replay_preflight = _first_message(replay, "embodied_action_request")
    occupancy_constraint = _first_world_result(competing, "constraint_state_result")

    assert first_preflight["payload"]["grant"]["grant_id"] == replay_preflight["payload"]["grant"]["grant_id"]
    assert first_preflight["payload"]["request"]["interaction_attempt_id"] == replay_preflight["payload"]["request"]["interaction_attempt_id"]
    assert first_preflight["payload"]["request"]["affordance_id"] == "affordance:obj_archive_door:open"
    assert first_preflight["payload"]["request"]["binding_revision"] == 4
    assert occupancy_constraint["payload"]["constraint_code"] == "stance_occupied"
    assert _door_state() == "closed"


def test_expired_abandoned_door_grant_releases_only_its_local_occupancy_reservation() -> None:
    main.reset_runtime_state()
    connection = _connection()
    _bind_controller(connection)
    _move_actor(connection, actor_id="char_c", producer_ts=90, target_point=(0.0, 1.2, -3.1))

    first = _first_message(_interact(connection, producer_ts=110, interaction_type="open"), "embodied_action_request")
    retry_at = int(first["payload"]["grant"]["expires_at"]) + 1
    retry = _first_message(_interact(connection, producer_ts=retry_at, interaction_type="open"), "embodied_action_request")

    assert retry["payload"]["grant"]["grant_id"] != first["payload"]["grant"]["grant_id"]
    assert main.default_scene_archive_door_embodied_service.commit_count == 0
    assert _door_state() == "closed"


def test_archive_door_outcome_commits_once_and_duplicate_replays_without_second_mutation() -> None:
    main.reset_runtime_state()
    connection = _connection()
    _bind_controller(connection)
    _move_actor(connection, actor_id="char_c", producer_ts=90, target_point=(0.0, 1.2, -3.1))

    preflight = _first_message(_interact(connection, producer_ts=110, interaction_type="open"), "embodied_action_request")
    grant = preflight["payload"]["grant"]
    payload = _door_outcome(
        str(grant["grant_id"]),
        connection_epoch=int(grant["connection_epoch"]),
        outcome_nonce=str(grant["one_time_outcome_nonce"]),
    )

    first = main._handle_envelope(
        Envelope(message_type="embodied_local_outcome", payload=payload),
        connection_context=connection,
    )
    duplicate = main._handle_envelope(
        Envelope(message_type="embodied_local_outcome", payload=payload),
        connection_context=connection,
    )

    first_receipt = _first_message(first, "embodied_settlement_result")
    first_object = _first_world_result(first, "object_state_result")
    duplicate_receipt = _first_message(duplicate, "embodied_settlement_result")
    duplicate_object = _first_world_result(duplicate, "object_state_result")

    assert first_receipt["payload"]["outcome"] == "committed"
    assert first_object["payload"]["previous_state"] == "closed"
    assert first_object["payload"]["current_state"] == "open"
    assert duplicate_receipt["payload"]["idempotent"] is True
    assert duplicate_object["payload"]["result_id"] == first_object["payload"]["result_id"]
    assert main.default_scene_archive_door_embodied_service.commit_count == 1
    assert _door_state() == "open"


def test_archive_door_range_and_revision_failures_do_not_mutate_state() -> None:
    main.reset_runtime_state()
    connection = _connection()
    _bind_controller(connection)
    _move_actor(connection, actor_id="char_c", producer_ts=90, target_point=(0.0, 1.2, 25.0))

    out_of_range = _interact(connection, producer_ts=110, interaction_type="open")
    range_constraint = _first_world_result(out_of_range, "constraint_state_result")

    assert range_constraint["payload"]["constraint_code"] == "out_of_range"
    assert _door_state() == "closed"

    _move_actor(connection, actor_id="char_c", producer_ts=91, target_point=(0.0, 1.2, -3.1))
    accepted = _first_message(_interact(connection, producer_ts=112, interaction_type="open"), "embodied_action_request")
    grant = accepted["payload"]["grant"]
    main.default_scene_archive_door_embodied_service.binding_revision += 1

    rejected = main._handle_envelope(
        Envelope(
            message_type="embodied_local_outcome",
            payload=_door_outcome(
                str(grant["grant_id"]),
                connection_epoch=int(grant["connection_epoch"]),
                outcome_nonce=str(grant["one_time_outcome_nonce"]),
                payload_digest="sha256:door-terminal-revision-stale",
            ),
        ),
        connection_context=connection,
    )
    receipt = _first_message(rejected, "embodied_settlement_result")

    assert receipt["payload"]["outcome"] == "rejected"
    assert receipt["payload"]["error_code"] == "binding_revision_mismatch"
    assert not any(
        message.get("message_type") == "world_result" and message.get("event_type") == "object_state_result"
        for message in rejected
    )
    assert main.default_scene_archive_door_embodied_service.commit_count == 0
    assert _door_state() == "closed"


def test_archive_door_rejected_terminal_receives_settlement_without_object_mutation() -> None:
    main.reset_runtime_state()
    connection = _connection()
    _bind_controller(connection)
    _move_actor(connection, actor_id="char_c", producer_ts=90, target_point=(0.0, 1.2, -3.1))

    preflight = _first_message(_interact(connection, producer_ts=110, interaction_type="open"), "embodied_action_request")
    grant = preflight["payload"]["grant"]
    payload = _door_outcome(
        str(grant["grant_id"]),
        connection_epoch=int(grant["connection_epoch"]),
        outcome_nonce=str(grant["one_time_outcome_nonce"]),
        payload_digest="sha256:door-terminal-stance-occupied",
    )
    payload["terminal_status"] = "failed_precondition"
    payload["failure_code"] = "stance_occupied"
    payload["contact_observation"] = None
    payload["local_ownership_restored"] = True
    payload["selected_action_tags"] = [
        "start_move",
        "turn_to_target",
        "raise_hand",
        "tap_contact",
        "recover_balance",
    ]
    payload["phase_action_tags"] = {"recover": ["recover_balance"]}
    payload["local_root_motion_phase_refs"] = {"recover": ["recovery_local_only"]}

    rejected = main._handle_envelope(
        Envelope(message_type="embodied_local_outcome", payload=payload),
        connection_context=connection,
    )
    receipt = _first_message(rejected, "embodied_settlement_result")

    assert receipt["payload"]["settlement_id"]
    assert receipt["payload"]["outcome"] == "not_committed"
    assert receipt["payload"]["error_code"] == "stance_occupied"
    assert not any(message.get("event_type") == "object_state_result" for message in rejected)
    assert main.default_scene_archive_door_embodied_service.commit_count == 0
    assert _door_state() == "closed"


def test_archive_door_grant_remains_valid_for_a_bounded_physical_approach() -> None:
    main.reset_runtime_state()
    connection = _connection()
    _bind_controller(connection)
    _move_actor(connection, actor_id="char_c", producer_ts=90, target_point=(0.0, 1.2, -3.1))

    preflight = _first_message(_interact(connection, producer_ts=110, interaction_type="open"), "embodied_action_request")
    grant = preflight["payload"]["grant"]
    payload = _door_outcome(
        str(grant["grant_id"]),
        connection_epoch=int(grant["connection_epoch"]),
        outcome_nonce=str(grant["one_time_outcome_nonce"]),
        payload_digest="sha256:door-terminal-bounded-approach",
    )
    payload["observed_at"] = 25_110

    settled = main._handle_envelope(
        Envelope(message_type="embodied_local_outcome", payload=payload),
        connection_context=connection,
    )
    receipt = _first_message(settled, "embodied_settlement_result")

    assert receipt["payload"]["settlement_status"] == "applied"
    assert _door_state() == "open"


def test_archive_door_state_change_after_preflight_rejects_as_door_state_stale() -> None:
    main.reset_runtime_state()
    connection = _connection()
    _bind_controller(connection)
    _move_actor(connection, actor_id="char_c", producer_ts=90, target_point=(0.0, 1.2, -3.1))

    preflight = _first_message(_interact(connection, producer_ts=110, interaction_type="open"), "embodied_action_request")
    grant = preflight["payload"]["grant"]
    main.esm_service.commit_interaction_state(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        target_object_id="obj_archive_door",
        current_state="open",
    )

    rejected = main._handle_envelope(
        Envelope(
            message_type="embodied_local_outcome",
            payload=_door_outcome(
                str(grant["grant_id"]),
                connection_epoch=int(grant["connection_epoch"]),
                outcome_nonce=str(grant["one_time_outcome_nonce"]),
                payload_digest="sha256:door-terminal-state-stale",
            ),
        ),
        connection_context=connection,
    )
    receipt = _first_message(rejected, "embodied_settlement_result")

    assert receipt["payload"]["settlement_id"]
    assert receipt["payload"]["outcome"] == "rejected"
    assert receipt["payload"]["error_code"] == "door_state_stale"
    assert not any(message.get("event_type") == "object_state_result" for message in rejected)
    assert main.default_scene_archive_door_embodied_service.commit_count == 0
    assert _door_state() == "open"


def test_archive_door_changed_duplicate_digest_is_rejected_without_second_mutation() -> None:
    main.reset_runtime_state()
    connection = _connection()
    _bind_controller(connection)
    _move_actor(connection, actor_id="char_c", producer_ts=90, target_point=(0.0, 1.2, -3.1))

    preflight = _first_message(_interact(connection, producer_ts=110, interaction_type="open"), "embodied_action_request")
    grant = preflight["payload"]["grant"]
    payload = _door_outcome(
        str(grant["grant_id"]),
        connection_epoch=int(grant["connection_epoch"]),
        outcome_nonce=str(grant["one_time_outcome_nonce"]),
    )
    main._handle_envelope(Envelope(message_type="embodied_local_outcome", payload=payload), connection_context=connection)

    changed = {**payload, "payload_digest": "sha256:door-terminal-changed"}
    rejected = main._handle_envelope(
        Envelope(message_type="embodied_local_outcome", payload=changed),
        connection_context=connection,
    )

    assert rejected[0]["payload"]["accepted"] is False
    assert rejected[0]["payload"]["error_code"] == "grant_consumed"
    assert not any(message.get("event_type") == "object_state_result" for message in rejected)
    assert main.default_scene_archive_door_embodied_service.commit_count == 1
    assert _door_state() == "open"


def test_archive_door_settlement_is_ledger_correlated_and_receipt_pins_object_result() -> None:
    main.reset_runtime_state()
    connection = _connection()
    _bind_controller(connection)
    _move_actor(connection, actor_id="char_c", producer_ts=90, target_point=(0.0, 1.2, -3.1))

    preflight = _first_message(_interact(connection, producer_ts=110, interaction_type="open"), "embodied_action_request")
    request = preflight["payload"]["request"]
    grant = preflight["payload"]["grant"]
    attempt_id = str(request["interaction_attempt_id"])

    phase = main._handle_envelope(
        Envelope(
            message_type="embodied_phase_event",
            payload={
                "grant_id": grant["grant_id"],
                "connection_epoch": grant["connection_epoch"],
                "source_sequence": 1,
                "payload_digest": "sha256:door-phase:acquire-target",
            },
        ),
        connection_context=connection,
    )
    assert phase[0]["payload"]["accepted"] is True

    payload = _door_outcome(
        str(grant["grant_id"]),
        connection_epoch=int(grant["connection_epoch"]),
        outcome_nonce=str(grant["one_time_outcome_nonce"]),
        payload_digest="sha256:door-terminal-with-contact-evidence",
    )
    payload["terminal_sequence"] = 2

    settled = main._handle_envelope(
        Envelope(message_type="embodied_local_outcome", payload=payload),
        connection_context=connection,
    )
    receipt = _first_message(settled, "embodied_settlement_result")
    object_result = _first_world_result(settled, "object_state_result")
    settlement_id = receipt["payload"]["settlement_id"]

    assert settlement_id
    assert object_result["payload"]["settlement_id"] == settlement_id
    assert object_result["payload"]["interaction_attempt_id"] == attempt_id
    assert object_result["payload"]["grant_id"] == grant["grant_id"]
    presentation = main._handle_envelope(
        Envelope(
            message_type="embodied_presentation_observed",
            payload={
                "interaction_attempt_id": attempt_id,
                "settlement_id": settlement_id,
                "snapshot_digest": "sha256:archive-door-presentation:applied",
            },
        ),
        connection_context=connection,
    )

    assert presentation[0]["payload"]["accepted"] is True
    assert [event.event_kind for event in main.embodied_evidence_ledger.events_for_attempt(attempt_id)] == [
        "request_authorized",
        "registry_binding",
        "local_phase",
        "terminal_local_observation",
        "settlement",
        "presentation",
    ]
    assert main.embodied_evidence_ledger.validate_replay(attempt_id).accepted is True
