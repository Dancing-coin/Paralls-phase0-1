import asyncio
from contextlib import asynccontextmanager
import json
from time import perf_counter
from types import SimpleNamespace

import pytest

from scripts.verification.population_mixed_faults import MirrorControlledClose, MixedMirrorFaultClient


@pytest.mark.parametrize("already_closed", [False, True])
def test_controlled_close_recovery_uses_fresh_epoch_and_never_swallows_other_revocations(already_closed):
    from scripts.verification.population_mixed_load import MixedLoadEvent
    from scripts.verification.population_mixed_mirror import MixedMirrorReceiver
    closed, sent, records = [], [], []
    class Socket:
        async def recv(self):
            return json.dumps(dict(message_type="websocket_session_revoked", payload=dict(
                reason_code="mirror_delivery_unrecoverable", route="gameplay_mirror_transport")))
        async def send(self, raw):
            sent.append(json.loads(raw))
            if already_closed:
                from websockets.exceptions import ConnectionClosedError
                from websockets.frames import Close
                frame = Close(4403, "mirror_delivery_unrecoverable")
                raise ConnectionClosedError(frame, frame, True)
    class Context:
        async def __aexit__(self, *args):
            closed.append(True)
    async def snapshot(event):
        return dict(confirmed_tick=8)
    client = MixedMirrorFaultClient(SimpleNamespace(timeout=1., snapshot=snapshot, record=records.append), {"actor:a"})
    client.context, client.socket = Context(), Socket()
    client.receiver = MixedMirrorReceiver({"actor:a"}, epoch=1)
    client.pause_started = perf_counter() - 6
    client.pause_ready.set()
    async def reopen(event):
        assert closed == [True] and client.context is None
        client.context = Context()
        client.receiver = MixedMirrorReceiver({"actor:a"}, epoch=2)
    async def catch_up(cutoff, *, require_fresh=False):
        assert cutoff == 8
        if client.receiver.wire.epoch == 1:
            assert require_fresh
            await client._read()
        return dict(epoch=2, sequence=1, confirmed_ticks={"actor:a": 8})
    client._open, client._catch_up = reopen, catch_up
    result = asyncio.run(client.resume_consumer(MixedLoadEvent(0, "resume_consumer", 1, "fault:resume")))
    assert result["previous_epoch"] == 1 and result["epoch"] == 2 and closed == [True, True]
    assert sent == [dict(message_type="websocket_session_revocation_received", payload=dict(
        reason_code="mirror_delivery_unrecoverable", route="gameplay_mirror_transport"))]
    assert sum(row["type"] == "fault_controlled_close" for row in records) == 1

    async def revoked():
        return json.dumps(dict(message_type="websocket_session_revoked", payload=dict(
            reason_code="authorization_revoked", route="gameplay_mirror_transport")))
    client.socket = SimpleNamespace(recv=revoked)
    with pytest.raises(ValueError, match="mixed_fault_revocation_invalid"):
        asyncio.run(client._read())


@pytest.mark.parametrize("code,reason,controlled", [
    (4403, "mirror_delivery_unrecoverable", True),
    (4403, "authorization_revoked", False),
    (1011, "mirror_delivery_unrecoverable", False),
])
def test_direct_socket_close_only_recovers_the_declared_mirror_revocation(code, reason, controlled):
    from websockets.exceptions import ConnectionClosedError
    from websockets.frames import Close
    from scripts.verification.population_mixed_mirror import MixedMirrorReceiver

    class Socket:
        async def recv(self):
            frame = Close(code, reason)
            raise ConnectionClosedError(frame, frame, True)

    records = []
    client = MixedMirrorFaultClient(
        SimpleNamespace(record=records.append), {"actor:a"}
    )
    client.socket = Socket()
    client.receiver = MixedMirrorReceiver({"actor:a"}, epoch=7)
    client.key = "fault:direct-close"

    if controlled:
        with pytest.raises(MirrorControlledClose):
            asyncio.run(client._read())
        assert records == [dict(
            key="fault:direct-close",
            type="fault_controlled_close",
            at=records[0]["at"],
            epoch=7,
            reason_code="mirror_delivery_unrecoverable",
            route="gameplay_mirror_transport",
        )]
    else:
        with pytest.raises(ConnectionClosedError):
            asyncio.run(client._read())
        assert records == []


def test_controlled_close_recovery_rebinds_again_when_baseline_is_revoked():
    from scripts.verification.population_mixed_load import MixedLoadEvent
    from scripts.verification.population_mixed_mirror import MixedMirrorReceiver

    closed, opened = [], []

    class Context:
        async def __aexit__(self, *args):
            closed.append(True)

    async def snapshot(event):
        return dict(confirmed_tick=8)

    client = MixedMirrorFaultClient(
        SimpleNamespace(timeout=1., snapshot=snapshot, record=lambda row: None),
        {"actor:a"},
    )
    client.context, client.socket = Context(), object()
    client.receiver = MixedMirrorReceiver({"actor:a"}, epoch=1)
    client.pause_started = perf_counter() - 6
    client.pause_ready.set()

    async def reopen(event):
        epoch = len(opened) + 2
        opened.append(epoch)
        client.context = Context()
        client.receiver = MixedMirrorReceiver({"actor:a"}, epoch=epoch)
        if epoch == 2:
            await client.close()
            raise MirrorControlledClose()

    async def catch_up(cutoff, *, require_fresh=False):
        if client.receiver.wire.epoch == 1:
            raise MirrorControlledClose()
        return dict(epoch=client.receiver.wire.epoch, sequence=1, confirmed_ticks={"actor:a": cutoff})

    client._open, client._catch_up = reopen, catch_up
    result = asyncio.run(client.resume_consumer(MixedLoadEvent(0, "resume_consumer", 1, "fault:resume")))

    assert opened == [2, 3]
    assert result["previous_epoch"] == 1 and result["epoch"] == 3
    assert closed == [True, True, True]


def test_controlled_close_recovery_rejects_reused_epoch_during_rebind():
    from scripts.verification.population_mixed_load import MixedLoadEvent
    from scripts.verification.population_mixed_mirror import MixedMirrorReceiver

    closed, opened = [], []

    class Context:
        async def __aexit__(self, *args):
            closed.append(True)

    async def snapshot(event):
        return dict(confirmed_tick=8)

    client = MixedMirrorFaultClient(
        SimpleNamespace(timeout=1., snapshot=snapshot, record=lambda row: None),
        {"actor:a"},
    )
    client.context, client.socket = Context(), object()
    client.receiver = MixedMirrorReceiver({"actor:a"}, epoch=1)
    client.pause_started = perf_counter() - 6
    client.pause_ready.set()

    async def reopen(event):
        opened.append(True)
        client.context = Context()
        client.receiver = MixedMirrorReceiver({"actor:a"}, epoch=1)
        await client.close()
        raise MirrorControlledClose()

    async def catch_up(cutoff, *, require_fresh=False):
        raise MirrorControlledClose()

    client._open, client._catch_up = reopen, catch_up
    with pytest.raises(ValueError, match="mixed_fault_epoch_not_renewed"):
        asyncio.run(client.resume_consumer(MixedLoadEvent(0, "resume_consumer", 1, "fault:resume")))

    assert opened == [True]
    assert closed == [True, True]


def test_failed_connection_entry_preserves_original_error_without_exiting_unentered_context():
    class Context:
        async def __aenter__(self):
            raise ConnectionError("connect failed")
        async def __aexit__(self, *args):
            raise AssertionError("unentered context must not be exited")
    transport = SimpleNamespace(bound_session=lambda **_: Context(), timeout=1.)
    client = MixedMirrorFaultClient(transport, {"character:char_a"})
    with pytest.raises(ConnectionError, match="connect failed"):
        asyncio.run(client.slow_consumer(SimpleNamespace(transaction_id="fault:1")))
    assert client.context is None and client.socket is None and not client.pause_ready.is_set()


def test_ungranted_fault_scope_closes_actual_entered_context_once():
    closed = []
    @asynccontextmanager
    async def context(**kwargs):
        try:
            yield object(), dict(allowed_actor_refs=["character:char_b"], connection_epoch=1)
        finally:
            closed.append(True)
    client = MixedMirrorFaultClient(SimpleNamespace(bound_session=context, timeout=1.), {"character:char_a"})
    with pytest.raises(ValueError, match="mixed_fault_scope_not_granted"):
        asyncio.run(client.slow_consumer(SimpleNamespace(transaction_id="fault:1")))
    assert closed == [True] and client.context is None and client.socket is None


def test_healthy_read_failure_after_pause_still_closes_fault_socket():
    closed = []
    class Context:
        async def __aexit__(self, *args):
            closed.append(True)
    async def fail(event):
        raise TimeoutError("healthy read failed")
    client = MixedMirrorFaultClient(SimpleNamespace(timeout=1., snapshot=fail, record=lambda row: None), {"character:char_a"})
    client.context, client.socket = Context(), object()
    client.pause_started = perf_counter() - 6
    client.pause_ready.set()
    from scripts.verification.population_mixed_load import MixedLoadEvent
    with pytest.raises(TimeoutError, match="healthy read failed"):
        asyncio.run(client.resume_consumer(MixedLoadEvent(0, "resume_consumer", 1, "fault:resume")))
    assert closed == [True] and client.context is None

@pytest.mark.parametrize("fresh_packet", [False, True, "old_sequence"])
def test_resume_requires_new_validated_wire_even_when_population_tick_is_unchanged(fresh_packet):
    from test_population_mixed_transport import _mixed_packets
    from scripts.verification.population_mixed_load import MixedLoadEvent
    from scripts.verification.population_mixed_mirror import MixedMirrorReceiver
    packets = _mixed_packets(True)
    reads, closed = [], []
    class Socket:
        async def recv(self):
            reads.append(True)
            if fresh_packet == "old_sequence" and len(reads) == 1:
                return json.dumps(packets[0])
            if fresh_packet is not True:
                raise ConnectionError("paused socket closed")
            return json.dumps(packets[1])
    class Context:
        async def __aexit__(self, *args):
            closed.append(True)
    async def snapshot(event):
        return dict(confirmed_tick=7)
    client = MixedMirrorFaultClient(SimpleNamespace(timeout=1., snapshot=snapshot, record=lambda row: None), {"character:char_a"})
    client.context, client.socket = Context(), Socket()
    client.receiver = MixedMirrorReceiver(client.actors, epoch=1)
    client.receiver.receive(json.dumps(packets[0]))
    client.pause_started = perf_counter() - 6
    client.pause_ready.set()
    event = MixedLoadEvent(0, "resume_consumer", 1, "fault:resume")
    if fresh_packet is True:
        result = asyncio.run(client.resume_consumer(event))
        assert result["sequence"] == 2 and result["confirmed_ticks"] == {"character:char_a": 7}
    else:
        with pytest.raises(ConnectionError, match="paused socket closed"):
            asyncio.run(client.resume_consumer(event))
    assert len(reads) == (2 if fresh_packet == "old_sequence" else 1)
    assert closed == [True]
