"""混合负载的实际 HTTP/WS 输入；只保存关联和状态，不记录凭据或模型正文。"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
import json
from time import perf_counter, time

import httpx
from websockets.asyncio.client import connect

from scripts.launch_trusted_local_gameplay_mirror import request_enrollment
from scripts.verification.verify_population_transport_cost import WireEvidence


def response_evidence(message: dict) -> dict:
    """证据白名单；其余字段不能从模型/私有认知输出溢出到性能报告。"""
    payload = message.get("payload", {})
    return {"message_type": message["message_type"], "event_type": message.get("event_type"),
        **{key: payload[key] for key in (
            "request_id", "request_ref", "result_id", "accepted", "route", "source_type", "status",
            "actor_id", "updated_at", "current_zone_id", "causation_id", "correlation_id",
            "constraint_code", "resolution_status", "current_state", "target_object_id",
            "settlement_status", "settlement_id", "fallback_used") if key in payload}}


def contention_winner(rows: list[dict]) -> str:
    """两个实际请求须一成一败；距离/权限失败不能冒充资源竞争。"""
    accepted = [row for row in rows if row.get("event_type") == "action_resolution_result"
        and row.get("resolution_status") == row.get("settlement_status") == "accepted"]
    rejected = [row for row in rows if row.get("event_type") == "constraint_state_result"
        and row.get("constraint_code") == "invalid_interaction_state"
        and row.get("settlement_status") == "rejected"]
    if (len(rows) != 2 or len(accepted) != 1 or len(rejected) != 1
            or {row.get("actor_id") for row in rows} != {"char_a", "char_c"}
            or {row.get("target_object_id") for row in rows} != {"obj_worktable"}
            or len({row.get("request_ref") for row in rows}) != 2
            or any(not row.get("request_ref", "").startswith("interact:") for row in rows)):
        raise ValueError("mixed_contention_result_invalid")
    return accepted[0]["actor_id"]


class MixedLoadHttpWs:
    """每次输入有独立绑定和关联，响应等待由外层有界调度器隔离。"""

    def __init__(self, *, http_url: str, launcher_secret: str, launch_profile_ref: str,
                 record, timeout_seconds: float = 30) -> None:
        self.http_url = http_url.rstrip("/")
        self.ws_url = self.http_url.replace("http://", "ws://", 1).replace("https://", "wss://", 1) + "/ws"
        self.secret, self.profile = launcher_secret, launch_profile_ref
        self.record, self.timeout = record, timeout_seconds
        self._timestamp = 0

    def timestamp(self) -> int:
        # 同一进程的并发意图也不能碰撞原 ESM/visual fact 的毫秒身份。
        self._timestamp = max(int(time() * 1000), self._timestamp + 1)
        return self._timestamp

    @asynccontextmanager
    async def bound_session(self, *, max_queue=16):
        # 每请求独立租约；30分钟负载不会在第5分钟沿用过期身份。
        enrollment = await asyncio.to_thread(request_enrollment, backend_http_url=self.http_url,
            launch_profile_ref=self.profile, launcher_secret=self.secret)
        async with connect(self.ws_url, compression=None, max_queue=max_queue) as ws:
            payload = enrollment.model_dump(mode="json")
            payload.update(protocol_version=2, capability_offer=dict(protocol_version=2,
                supports_snapshot=True, supports_delta=True, supports_receipt=False,
                projection_schemas=["gameplay_runtime_state.godot.v1"]))
            await ws.send(json.dumps(dict(message_type="websocket_session_bind", payload=payload)))
            async with asyncio.timeout(self.timeout):
                while True:
                    message = json.loads(await ws.recv())
                    if message["message_type"] == "websocket_session_bound":
                        break
                    if message.get("payload", {}).get("accepted") is False:
                        raise ValueError("mixed_session_bind_rejected")
            yield ws, message["payload"]

    @asynccontextmanager
    async def session(self):
        async with self.bound_session() as (ws, _binding):
            yield ws

    async def health(self, event) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout, trust_env=False) as http:
            response = await http.get(self.http_url + "/health")
            if response.status_code != 200 or response.json().get("status") != "ok":
                raise ValueError("mixed_health_failed")
        now = perf_counter()
        self.record(dict(key=event.transaction_id, type="health_response", at=now, status="ok"))
        return dict(response_at=now, status="ok")

    async def snapshot(self, event) -> dict:
        actor = "character:char_a"
        # 混合业务可在同一人口 tick 内更新资源；仍核验完整 wire 与 exact-base。
        wire = WireEvidence({actor}, strict_public_windows=False)
        async with self.session() as ws, asyncio.timeout(self.timeout):
            async def receive():
                raw = await ws.recv()
                message = wire.receive(raw)
                if message["message_type"] == "gameplay_mirror_delivery":
                    # 首个 snapshot 也是后续 delta 的证明基础，不能只保存最终包。
                    self.record(dict(key=event.transaction_id, type="mirror_packet", at=perf_counter(), raw_text=raw))
                return message
            await ws.send(json.dumps(dict(message_type="gameplay_mirror_subscribe", payload=dict(actor_ref=actor))))
            while actor not in wire.snapshots:
                await receive()
            await ws.send(json.dumps(dict(message_type="gameplay_mirror_snapshot_request", payload=dict(actor_ref=actor))))
            accepted = None
            while True:
                message = await receive()
                payload = message.get("payload", {})
                now = perf_counter()
                if message["message_type"] == "ack" and payload.get("source_type") == "gameplay_mirror_snapshot_request":
                    if payload.get("accepted") is not True:
                        raise ValueError("mixed_snapshot_rejected")
                    accepted = now
                    self.record(dict(key=event.transaction_id, type="accepted", at=now, **response_evidence(message)))
                if accepted is not None and message["message_type"] == "gameplay_mirror_delivery":
                    snapshot = wire.snapshots[actor]
                    # 保存实际授权消息供 exact-base 离线复验；从不保存 bind 凭据。
                    self.record(dict(key=event.transaction_id, type="snapshot", at=now, message=message))
                    return dict(accepted_at=accepted, response_at=now, actor_ref=actor,
                        checksum=snapshot.snapshot_checksum, confirmed_tick=snapshot.groups["population_public"].payload["confirmed_tick"])

    async def exchange(self, event, envelope: dict, terminal) -> dict:
        accepted, result = None, None
        async with self.session() as ws, asyncio.timeout(self.timeout):
            self.record(dict(key=event.transaction_id, type="sent", at=perf_counter(),
                source_type=envelope["message_type"], producer_ts=envelope["payload"]["producer_ts"]))
            await ws.send(json.dumps(envelope))
            while accepted is None or result is None:
                message = json.loads(await ws.recv())
                evidence, now = response_evidence(message), perf_counter()
                if message["message_type"] == "ack" and evidence.get("source_type") == envelope["message_type"]:
                    accepted = now
                    self.record(dict(key=event.transaction_id, type="accepted", at=now, **evidence))
                    if evidence.get("accepted") is not True:
                        raise ValueError("mixed_input_rejected")
                if terminal(message):
                    result = dict(response_at=now, **evidence)
                    self.record(dict(key=event.transaction_id, type="response", at=now, **evidence))
        return dict(accepted_at=accepted, **result)

    async def fact(self, event) -> dict:
        timestamp = self.timestamp()
        envelope = dict(message_type="raw_fact_event", payload=dict(
            event_type="raw_fact_event", fact_family="spatial_access_fact", fact_type="actor_entered_zone",
            producer_ts=timestamp, room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
            source=dict(system="godot.raw_fact_emitter", actor_id="char_b"), targets={},
            causation_id=event.transaction_id, correlation_id=event.transaction_id))
        def terminal(message):
            payload = message.get("payload", {})
            return (message["message_type"] == "spatial_access_runtime_state_snapshot"
                and payload.get("updated_at") == timestamp and payload.get("actor_id") == "char_b"
                and payload.get("current_zone_id") == "zone_focus")
        return await self.exchange(event, envelope, terminal)

    async def dialogue(self, event) -> dict:
        envelope = dict(message_type="player_input", payload=dict(player_id="p1", room_id="room_demo",
            actor_id="char_c", intent_type="dialogue_submit", producer_ts=self.timestamp(),
            target_actor_id="char_a", content="Hello", request_id=event.transaction_id))
        return await self.exchange(event, envelope, lambda message:
            message["message_type"] == "dialogue_stream_end" and message.get("payload", {}).get("request_id") == event.transaction_id)

    async def siming_input(self, event) -> dict:
        # 实际L1结构化事实进入authority bus；此ACK只证明输入接纳，模型成功须另查实际provider与阶段回执。
        timestamp = self.timestamp()
        envelope = dict(message_type="visual_fact_event", payload=dict(actor_id="char_c", room_id="room_demo",
            scene_id="scene_demo", zone_id="zone_focus", producer_ts=timestamp, fact_type="light_level_drop",
            relation_type="environment_light_drop", target_environment_id="env_lamp",
            causation_id=event.transaction_id, correlation_id=event.transaction_id))
        result = await self.exchange(event, envelope, lambda message: message["message_type"] == "ack"
            and message.get("payload", {}).get("source_type") == "visual_fact_event"
            and message["payload"].get("route") == "authority_visual_fact")
        return dict(**result, producer_ts=timestamp, correlation_id=event.transaction_id,
            source_event_id=f"visual_fact:{timestamp}:char_c:light_level_drop", input_accepted_only=True)

    async def interact(self, event, *, actor="char_c", interaction="inspect", target="obj_letter") -> dict:
        timestamp = self.timestamp()
        envelope = dict(message_type="player_input", payload=dict(player_id="p1", room_id="room_demo",
            actor_id=actor, intent_type="interact_intent", producer_ts=timestamp,
            target_object_id=target, interaction_type=interaction, request_id=event.transaction_id))
        def terminal(message):
            payload = message.get("payload", {})
            return (message["message_type"] == "world_result"
                and message.get("event_type") in {"action_resolution_result", "constraint_state_result"}
                and payload.get("request_ref") == f"interact:{timestamp}:{target}")
        return await self.exchange(event, envelope, terminal)

    async def move_to_worktable(self, event, actor) -> dict:
        envelope = dict(message_type="player_input", payload=dict(player_id="p1", room_id="room_demo",
            scene_id="scene_demo", zone_id="zone_focus", actor_id=actor, intent_type="move_intent",
            producer_ts=self.timestamp(), request_id=event.transaction_id, move_mode="locomotion",
            target_point=[-.9, .85, -2.]))
        return await self.exchange(event, envelope, lambda message: message["message_type"] == "ack"
            and message.get("payload", {}).get("request_id") == event.transaction_id
            and message["payload"].get("route") == "local_motion")

    async def contend(self, event) -> dict:
        def part(label):
            return replace(event, transaction_id=event.transaction_id + ":" + label)
        await asyncio.gather(*(self.move_to_worktable(part("move:" + actor), actor) for actor in ("char_a", "char_c")))
        rows = await asyncio.gather(*(self.interact(part("use:" + actor), actor=actor, interaction="use",
            target="obj_worktable") for actor in ("char_a", "char_c")))
        winner = contention_winner(rows)
        released = await self.interact(part("release:" + winner), actor=winner, interaction="finish_use", target="obj_worktable")
        if released.get("resolution_status") != "accepted" or released.get("settlement_status") != "accepted":
            raise ValueError("mixed_contention_release_failed")
        result = dict(winner=winner, contenders=rows, release=released)
        self.record(dict(key=event.transaction_id, type="contention", at=perf_counter(), **result))
        return result

    def handlers(self) -> dict:
        return {"health": self.health, "ws_read": self.snapshot, "fact": self.fact,
                "interaction": self.interact, "character_model": self.dialogue, "siming_model": self.siming_input,
                "owner_contention": self.contend}
