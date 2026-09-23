import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from app.gameplay.godot_mirror_delivery import GameplayGodotMirrorSyncAdapter, GameplayMirrorDeltaEncoder
from scripts.verification import population_mixed_transport
from scripts.verification.population_mixed_transport import MixedLoadHttpWs, response_evidence, contention_winner
from scripts.verification.verify_population_transport_cost import WireEvidence
from test_gameplay_mirror_session_access_service import _projection_source
from test_mirror_delta_transport import _message, _send


def test_performance_evidence_excludes_dialogue_private_state_and_credentials():
    result = response_evidence({"message_type": "dialogue_stream_end", "payload": {
        "request_id": "mixed:1", "status": "completed", "fallback_used": False,
        "content": "private model text", "api_key": "secret", "memory": {"private": True},
        "authorization": "Bearer secret"}})
    assert result == {"message_type": "dialogue_stream_end", "event_type": None,
        "request_id": "mixed:1", "status": "completed", "fallback_used": False}


def test_response_evidence_keeps_exact_authority_correlation_without_calling_it_committed():
    result = response_evidence({"message_type": "world_result", "event_type": "constraint_state_result",
        "payload": {"request_ref": "interact:123:obj_worktable", "result_id": "result:123",
                    "constraint_code": "invalid_interaction_state", "content": "not evidence"}})
    assert result["request_ref"] == "interact:123:obj_worktable"
    assert result["constraint_code"] == "invalid_interaction_state"
    assert "content" not in result and "committed" not in result


def test_mixed_bound_session_disables_protocol_ping(monkeypatch):
    options = {}

    class Socket:
        async def send(self, raw):
            assert json.loads(raw)["message_type"] == "websocket_session_bind"

        async def recv(self):
            return json.dumps({"message_type": "websocket_session_bound", "payload": {
                "allowed_actor_refs": ["character:char_a"], "connection_epoch": 1}})

    class Context:
        async def __aenter__(self):
            return Socket()

        async def __aexit__(self, *args):
            return None

    def connect(url, **kwargs):
        options.update(url=url, **kwargs)
        return Context()

    monkeypatch.setattr(population_mixed_transport, "connect", connect)
    monkeypatch.setattr(population_mixed_transport, "request_enrollment", lambda **_: SimpleNamespace(
        model_dump=lambda **_: {"credential": "test"}))
    client = MixedLoadHttpWs(http_url="http://unused", launcher_secret="unused",
        launch_profile_ref="unused", record=lambda row: None)

    async def exercise():
        async with client.bound_session(max_queue=1):
            pass

    asyncio.run(exercise())

    assert options == {"url": "ws://unused/ws", "compression": None,
        "max_queue": 1, "ping_interval": None}


def test_contention_requires_distinct_requests_one_authority_success_and_state_constraint():
    won = dict(actor_id="char_a", request_ref="interact:1:obj_worktable", target_object_id="obj_worktable",
        event_type="action_resolution_result", resolution_status="accepted", settlement_status="accepted")
    lost = dict(actor_id="char_c", request_ref="interact:2:obj_worktable", target_object_id="obj_worktable",
        event_type="constraint_state_result", constraint_code="invalid_interaction_state", settlement_status="rejected")
    assert contention_winner([won, lost]) == "char_a"
    for rows in ([won, won], [lost, lost], [won, {**lost, "constraint_code": "out_of_reach"}],
                 [won, {**lost, "request_ref": won["request_ref"]}],
                 [{**won, "settlement_status": "rejected"}, lost]):
        with pytest.raises(ValueError, match="mixed_contention_result_invalid"):
            contention_winner(rows)

def _mixed_packets(force_snapshot):
    actor = "character:char_a"
    sync = GameplayGodotMirrorSyncAdapter()
    encoder = GameplayMirrorDeltaEncoder()
    packets = []
    for sequence in (1, 2):
        view = _projection_source(actor)
        base = view.groups["resources"]
        target = sync.snapshot(replace(view, source_facade_revision=f"facade:{sequence}",
            source_revision_vector={actor: sequence}, groups={
                "population_public": replace(base, group_id="population_public",
                    projection_revision="population:7", payload={"confirmed_tick": 7}),
                "resources": replace(base, projection_revision=f"resources:{sequence}",
                    payload={"value": sequence})}))
        message = _message(sequence, actor=actor)
        message["payload"].update(facade_revision=target.facade_revision,
            source_revision_vector=dict(target.source_revision_vector), payload=sync.snapshot_payload(target))
        packets.append(_send(encoder, message, force_snapshot=force_snapshot))
    return packets


@pytest.mark.parametrize("force_snapshot", [True, False])
def test_mixed_snapshot_accepts_resource_updates_at_same_population_tick(force_snapshot):
    first, second = _mixed_packets(force_snapshot)
    records, sent = [], []
    responses = iter([first, {"message_type": "ack", "payload": {
        "accepted": True, "source_type": "gameplay_mirror_snapshot_request"}}, second])

    class Socket:
        async def send(self, raw):
            sent.append(json.loads(raw))

        async def recv(self):
            return json.dumps(next(responses))

    @asynccontextmanager
    async def session():
        yield Socket()

    client = MixedLoadHttpWs(http_url="http://unused", launcher_secret="unused",
        launch_profile_ref="unused", record=records.append)
    client.session = session
    result = asyncio.run(client.snapshot(SimpleNamespace(transaction_id="mixed:resource")))
    assert result["confirmed_tick"] == 7
    assert result["checksum"] == (second["payload"].get("target_snapshot_checksum")
        or second["payload"]["payload"]["snapshot_checksum"])
    assert [message["message_type"] for message in sent] == [
        "gameplay_mirror_subscribe", "gameplay_mirror_snapshot_request"]
    assert [record["type"] for record in records] == ["mirror_packet", "accepted", "mirror_packet", "snapshot"]
    replay = WireEvidence({"character:char_a"}, strict_public_windows=False)
    for record in records:
        if record["type"] == "mirror_packet":
            replay.receive(record["raw_text"])
    assert replay.snapshots["character:char_a"].snapshot_checksum == result["checksum"]
    strict = WireEvidence({"character:char_a"})
    strict.receive(json.dumps(first))
    with pytest.raises(ValueError, match="cost_probe_window_conflict"):
        strict.receive(json.dumps(second))


def test_mixed_wire_still_rejects_incorrect_delta_base():
    first, second = _mixed_packets(False)
    wire = WireEvidence({"character:char_a"}, strict_public_windows=False)
    wire.receive(json.dumps(first))
    second["payload"]["base_facade_revision"] = "wrong-base"
    with pytest.raises(ValueError, match="cost_probe_delta_anchor_mismatch"):
        wire.receive(json.dumps(second))
    assert wire.sequence == 1


@pytest.mark.parametrize("status", [None, "accepted", "pending"])
def test_contention_rejects_unconfirmed_or_contradictory_loser(status):
    won = dict(actor_id="char_a", request_ref="interact:1:obj_worktable", target_object_id="obj_worktable",
        event_type="action_resolution_result", resolution_status="accepted", settlement_status="accepted")
    lost = dict(actor_id="char_c", request_ref="interact:2:obj_worktable", target_object_id="obj_worktable",
        event_type="constraint_state_result", constraint_code="invalid_interaction_state")
    if status is not None:
        lost["settlement_status"] = status
    with pytest.raises(ValueError, match="mixed_contention_result_invalid"):
        contention_winner([won, lost])
