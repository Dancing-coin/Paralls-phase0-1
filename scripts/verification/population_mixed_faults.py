"""实际 WS 暂停读取/断连；按计划时点调用，不压缩正式长测时钟。"""
import asyncio
from dataclasses import replace
import json
from time import perf_counter

from websockets.exceptions import ConnectionClosed

from scripts.verification.population_mixed_mirror import MixedMirrorReceiver
from scripts.verification.verify_population_service_isolation import until


class MirrorControlledClose(Exception):
    """服务端明确收回不可恢复的投影连接；只能以新绑定重建公开基线。"""


class MixedMirrorFaultClient:
    def __init__(self, transport, actor_refs):
        self.transport, self.actors = transport, set(actor_refs)
        self.context = self.socket = self.receiver = None
        self.pause_started = self.disconnected_at = self.disconnected_epoch = None
        self.pause_ready, self.disconnect_ready = asyncio.Event(), asyncio.Event()
        self.key = ""

    async def close(self):
        context, self.context = self.context, None
        self.socket = None
        if context is not None:
            await context.__aexit__(None, None, None)

    async def _read(self):
        try:
            raw = await self.socket.recv()
        except ConnectionClosed as error:
            close = error.rcvd
            if close is None or close.code != 4403 or close.reason != "mirror_delivery_unrecoverable":
                raise
            payload = dict(reason_code=close.reason, route="gameplay_mirror_transport")
            self.transport.record(dict(key=self.key, type="fault_controlled_close", at=perf_counter(),
                epoch=self.receiver.wire.epoch, **payload))
            raise MirrorControlledClose() from error
        message = json.loads(raw)
        if message["message_type"] == "websocket_session_revoked":
            payload = message["payload"]
            if payload != dict(reason_code="mirror_delivery_unrecoverable", route="gameplay_mirror_transport"):
                raise ValueError("mixed_fault_revocation_invalid")
            self.transport.record(dict(key=self.key, type="fault_controlled_close", at=perf_counter(),
                epoch=self.receiver.wire.epoch, **payload))
            try:
                await self.socket.send(json.dumps(dict(message_type="websocket_session_revocation_received", payload=payload)))
            except ConnectionClosed as error:
                # 暂停读取5秒超过服务端1秒ACK等待；只接受对应受控关闭帧。
                if error.rcvd is None or error.rcvd.code != 4403 or error.rcvd.reason != payload["reason_code"]:
                    raise
            raise MirrorControlledClose()
        decision = self.receiver.receive(raw)
        # 先验证授权和协议，再保存公开原包；bind/模型正文均不进入证据。
        if message["message_type"] in {"gameplay_mirror_delivery", "gameplay_mirror_resync_required"}:
            self.transport.record(dict(key=self.key, type="fault_mirror_packet", at=perf_counter(),
                epoch=self.receiver.wire.epoch, raw_text=raw, decision=decision))
        for actor in decision["request_actor_refs"]:
            self.transport.record(dict(key=self.key, type="fault_resync_request", at=perf_counter(), actor_ref=actor))
            await self.socket.send(json.dumps(dict(message_type="gameplay_mirror_resync_request", payload=dict(actor_ref=actor))))
        return decision

    async def _open(self, event):
        if self.context is not None:
            raise ValueError("mixed_fault_connection_already_open")
        deadline = perf_counter() + self.transport.timeout
        while True:
            context = self.transport.bound_session(max_queue=1)
            try:
                self.socket, binding = await context.__aenter__()
                self.context = context
                if not self.actors.issubset(binding["allowed_actor_refs"]):
                    raise ValueError("mixed_fault_scope_not_granted")
                self.receiver = MixedMirrorReceiver(self.actors, epoch=binding["connection_epoch"])
                self.key = event.transaction_id
                self.transport.record(dict(key=self.key, type="fault_bound", at=perf_counter(),
                    epoch=binding["connection_epoch"], actor_refs=sorted(self.actors), max_queue=1))
                # 逐 actor 建立第一份实际基线，避免把初次批量订阅溢出误算成暂停读取故障。
                async with asyncio.timeout(self.transport.timeout):
                    for actor in sorted(self.actors):
                        await self.socket.send(json.dumps(dict(message_type="gameplay_mirror_subscribe", payload=dict(actor_ref=actor))))
                        while actor not in self.receiver.wire.snapshots:
                            await self._read()
                return
            except MirrorControlledClose:
                # max_queue=1 的新绑定可能在初始基线到达前被上一轮投影关闭；
                # 在本次故障请求预算内换 epoch 重建，保留每次关闭证据。
                await self.close()
                if perf_counter() >= deadline:
                    raise
                await asyncio.sleep(0)
            except BaseException:
                await self.close()
                raise

    async def _catch_up(self, cutoff, *, require_fresh=False):
        def complete():
            wire = self.receiver.wire
            return (not self.receiver.awaiting and set(wire.snapshots) == self.actors
                and all(snapshot.groups["population_public"].payload["confirmed_tick"] >= cutoff
                    for snapshot in wire.snapshots.values()))
        async with asyncio.timeout(self.transport.timeout):
            # 暂停前缓存不能证明连接恢复；只有本次读取并实际应用的合法包可解除此门槛。
            fresh = not require_fresh
            while not fresh or not complete():
                decision = await self._read()
                fresh = fresh or decision["applied"]
        return dict(epoch=self.receiver.wire.epoch, sequence=self.receiver.wire.sequence,
            confirmed_ticks={actor: snapshot.groups["population_public"].payload["confirmed_tick"]
                for actor, snapshot in self.receiver.wire.snapshots.items()})

    async def slow_consumer(self, event):
        self.pause_ready.clear()
        await self._open(event)
        self.pause_started = perf_counter()
        self.transport.record(dict(key=self.key, type="fault_pause", at=self.pause_started))
        self.pause_ready.set()
        return dict(pause_started_at=self.pause_started, epoch=self.receiver.wire.epoch)

    async def resume_consumer(self, event):
        async with asyncio.timeout(self.transport.timeout):
            await self.pause_ready.wait()
        await until(self.pause_started + 5)
        resumed = perf_counter()
        self.transport.record(dict(key=self.key, type="fault_resume", at=resumed))
        try:
            healthy = await self.transport.snapshot(replace(event, transaction_id=event.transaction_id + ":healthy"))
            previous_epoch = self.receiver.wire.epoch
            try:
                result = await self._catch_up(healthy["confirmed_tick"], require_fresh=True)
            except MirrorControlledClose:
                await self.close()
                last_epoch = previous_epoch
                async with asyncio.timeout(self.transport.timeout):
                    while True:
                        try:
                            await self._open(event)
                        except MirrorControlledClose:
                            observed_epoch = self.receiver.wire.epoch
                            if observed_epoch <= last_epoch:
                                raise ValueError("mixed_fault_epoch_not_renewed")
                            last_epoch = observed_epoch
                            await self.close()
                            continue
                        current_epoch = self.receiver.wire.epoch
                        if current_epoch <= last_epoch:
                            raise ValueError("mixed_fault_epoch_not_renewed")
                        last_epoch = current_epoch
                        try:
                            result = await self._catch_up(healthy["confirmed_tick"])
                            break
                        except MirrorControlledClose:
                            observed_epoch = self.receiver.wire.epoch
                            if observed_epoch < last_epoch:
                                raise ValueError("mixed_fault_epoch_regressed")
                            last_epoch = observed_epoch
                            await self.close()
            return dict(**result, resumed_at=resumed, pause_started_at=self.pause_started,
                recovered_at=perf_counter(), healthy_cutoff=healthy["confirmed_tick"], previous_epoch=previous_epoch)
        finally:
            await self.close()

    async def disconnect(self, event):
        self.disconnect_ready.clear()
        await self._open(event)
        self.disconnected_epoch = self.receiver.wire.epoch
        await self.close()
        self.disconnected_at = perf_counter()
        self.transport.record(dict(key=self.key, type="fault_disconnect", at=self.disconnected_at, epoch=self.disconnected_epoch))
        self.disconnect_ready.set()
        return dict(disconnected_at=self.disconnected_at, epoch=self.disconnected_epoch)

    async def reconnect(self, event):
        async with asyncio.timeout(self.transport.timeout):
            await self.disconnect_ready.wait()
        await until(self.disconnected_at + 2)
        healthy = await self.transport.snapshot(replace(event, transaction_id=event.transaction_id + ":healthy"))
        try:
            await self._open(event)
            if self.receiver.wire.epoch <= self.disconnected_epoch:
                raise ValueError("mixed_fault_epoch_not_renewed")
            result = await self._catch_up(healthy["confirmed_tick"])
            return dict(**result, disconnected_at=self.disconnected_at, recovered_at=perf_counter(),
                previous_epoch=self.disconnected_epoch, healthy_cutoff=healthy["confirmed_tick"])
        finally:
            await self.close()

    def handlers(self):
        return {name: getattr(self, name) for name in ("slow_consumer", "resume_consumer", "disconnect", "reconnect")}
