from __future__ import annotations

from app.services.embodied_evidence_ledger import EmbodiedEvidenceLedger


def _valid_ledger() -> EmbodiedEvidenceLedger:
    ledger = EmbodiedEvidenceLedger()
    ledger.append(
        attempt_id="attempt:kick-chair:1",
        event_kind="request_authorized",
        emitter_kind="backend",
        emitter_id="backend:authority",
        emitter_epoch=1,
        source_sequence=1,
        payload_digest="sha256:request",
        payload={"interaction_attempt_id": "attempt:kick-chair:1", "causation_id": "cause:1"},
    )
    ledger.append(
        attempt_id="attempt:kick-chair:1",
        event_kind="registry_binding",
        emitter_kind="backend",
        emitter_id="backend:registry",
        emitter_epoch=1,
        source_sequence=2,
        payload_digest="sha256:binding",
        payload={"binding_revision": 7},
    )
    ledger.append(
        attempt_id="attempt:kick-chair:1",
        event_kind="local_phase",
        emitter_kind="controller",
        emitter_id="controller:char_a",
        emitter_epoch=3,
        source_sequence=1,
        payload_digest="sha256:phase1",
        payload={"phase": "execute_contact"},
    )
    ledger.append(
        attempt_id="attempt:kick-chair:1",
        event_kind="terminal_local_observation",
        emitter_kind="controller",
        emitter_id="controller:char_a",
        emitter_epoch=3,
        source_sequence=2,
        payload_digest="sha256:terminal",
        payload={"terminal_status": "contact_observed"},
    )
    ledger.append(
        attempt_id="attempt:kick-chair:1",
        event_kind="settlement",
        emitter_kind="backend",
        emitter_id="backend:settlement",
        emitter_epoch=1,
        source_sequence=3,
        payload_digest="sha256:settlement",
        payload={"outcome": "committed", "settlement_writer_kind": "esm_compatibility_adapter"},
    )
    ledger.append(
        attempt_id="attempt:kick-chair:1",
        event_kind="presentation",
        emitter_kind="godot_mirror",
        emitter_id="godot:mirror",
        emitter_epoch=1,
        source_sequence=1,
        payload_digest="sha256:presentation",
        payload={"presentation_status": "visible_state_changed"},
    )
    return ledger


def test_evidence_ledger_assigns_server_sequence_and_replay_validates_causal_chain() -> None:
    ledger = _valid_ledger()

    events = ledger.events_for_attempt("attempt:kick-chair:1")
    replay = ledger.validate_replay("attempt:kick-chair:1")

    assert [event.server_ledger_sequence for event in events] == [1, 2, 3, 4, 5, 6]
    assert replay.accepted is True
    assert replay.error_code == ""


def test_replay_rejects_duplicate_settlement() -> None:
    ledger = _valid_ledger()
    ledger.append(
        attempt_id="attempt:kick-chair:1",
        event_kind="settlement",
        emitter_kind="backend",
        emitter_id="backend:settlement",
        emitter_epoch=1,
        source_sequence=4,
        payload_digest="sha256:settlement2",
        payload={"outcome": "committed"},
    )

    replay = ledger.validate_replay("attempt:kick-chair:1")

    assert replay.accepted is False
    assert replay.error_code == "duplicate_settlement"


def test_replay_rejects_presentation_before_commit() -> None:
    ledger = EmbodiedEvidenceLedger()
    ledger.append(
        attempt_id="attempt:kick-chair:1",
        event_kind="request_authorized",
        emitter_kind="backend",
        emitter_id="backend:authority",
        emitter_epoch=1,
        source_sequence=1,
        payload_digest="sha256:request",
        payload={},
    )
    ledger.append(
        attempt_id="attempt:kick-chair:1",
        event_kind="presentation",
        emitter_kind="godot_mirror",
        emitter_id="godot:mirror",
        emitter_epoch=1,
        source_sequence=1,
        payload_digest="sha256:presentation",
        payload={"presentation_status": "visible_state_changed"},
    )

    replay = ledger.validate_replay("attempt:kick-chair:1")

    assert replay.accepted is False
    assert replay.error_code == "presentation_before_settlement"


def test_ledger_rejects_source_sequence_gap_and_digest_mismatch() -> None:
    ledger = EmbodiedEvidenceLedger()
    accepted = ledger.append(
        attempt_id="attempt:kick-chair:1",
        event_kind="local_phase",
        emitter_kind="controller",
        emitter_id="controller:char_a",
        emitter_epoch=3,
        source_sequence=1,
        payload_digest="sha256:phase1",
        payload={},
    )
    gap = ledger.append(
        attempt_id="attempt:kick-chair:1",
        event_kind="local_phase",
        emitter_kind="controller",
        emitter_id="controller:char_a",
        emitter_epoch=3,
        source_sequence=3,
        payload_digest="sha256:phase3",
        payload={},
    )
    mismatch = ledger.append(
        attempt_id="attempt:kick-chair:1",
        event_kind="local_phase",
        emitter_kind="controller",
        emitter_id="controller:char_a",
        emitter_epoch=3,
        source_sequence=1,
        payload_digest="sha256:different",
        payload={},
    )

    assert accepted.accepted is True
    assert gap.accepted is False
    assert gap.error_code == "source_sequence_gap"
    assert mismatch.accepted is False
    assert mismatch.error_code == "source_sequence_digest_mismatch"


def test_public_projection_filters_private_payload_fields() -> None:
    ledger = _valid_ledger()

    projection = ledger.public_projection(
        "attempt:kick-chair:1",
        extra_payload={
            "interaction_attempt_id": "attempt:kick-chair:1",
            "settlement_status": "committed",
            "public_effect_summary": "chair tipped",
            "private_participant_terms": {"char_b": "hidden"},
            "vla_prompt_context": "hidden",
        },
    )

    assert projection["extra_payload"] == {
        "interaction_attempt_id": "attempt:kick-chair:1",
        "settlement_status": "committed",
        "public_effect_summary": "chair tipped",
    }
