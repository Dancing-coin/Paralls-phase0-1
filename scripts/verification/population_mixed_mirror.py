"""混合负载故障客户端：按生产连接游标恢复，内容仍使用原 exact-base 校验。"""
import json

from app.ws_protocol import GameplayMirrorDeliveryEnvelope
from scripts.verification.verify_population_transport_cost import WireEvidence


class MixedMirrorReceiver:
    def __init__(self, actor_refs: set[str], *, epoch: int):
        if type(epoch) is not int or epoch <= 0:
            raise ValueError("mixed_mirror_epoch_invalid")
        self.wire = WireEvidence(set(actor_refs), strict_public_windows=False)
        self.wire.epoch = epoch
        self.awaiting = set()

    def _result(self, reason, *, applied=False, request=()):
        return dict(applied=applied, reason=reason, request_actor_refs=sorted(request),
            recovered=not self.awaiting and set(self.wire.snapshots) == self.wire.actor_refs)

    def receive(self, raw: str) -> dict:
        message = json.loads(raw)
        if message["message_type"] == "gameplay_mirror_resync_required":
            payload = message["payload"]
            if (set(payload) != {"actor_ref", "reason_code"} or payload["actor_ref"] not in self.wire.actor_refs
                    or payload["reason_code"] != "mirror_backpressure"):
                raise ValueError("mixed_mirror_control_invalid")
            actor = payload["actor_ref"]
            self.wire.snapshots.pop(actor, None)
            self.awaiting.add(actor)
            return self._result("backpressure", request=(actor,))
        if message["message_type"] != "gameplay_mirror_delivery":
            self.wire.receive(raw)
            return self._result("control")
        payload = message["payload"]
        if any(type(payload.get(field)) is not int or payload[field] <= 0
               for field in ("connection_epoch", "delivery_sequence")):
            raise ValueError("mixed_mirror_cursor_invalid")
        outer = GameplayMirrorDeliveryEnvelope.model_validate(payload)
        if (outer.actor_ref not in self.wire.actor_refs or outer.connection_epoch != self.wire.epoch
                or outer.delivery_kind not in {"snapshot", "delta"}):
            raise ValueError("mixed_mirror_scope_or_epoch_invalid")
        if outer.delivery_sequence <= self.wire.sequence:
            return self._result("old_sequence")
        if outer.delivery_sequence != self.wire.sequence + 1:
            # 与 GameplayMirrorBridge 相同：跳序包连 snapshot 也丢弃，不能通过改写序号接受内容。
            self.wire.sequence = outer.delivery_sequence
            self.wire.snapshots.clear()
            self.awaiting = set(self.wire.actor_refs)
            return self._result("sequence_gap", request=self.awaiting)
        if outer.actor_ref in self.awaiting and outer.delivery_kind == "delta":
            self.wire.sequence = outer.delivery_sequence
            return self._result("awaiting_snapshot")
        # 未恢复前的 delta 不应用；正常状态的坏 delta/校验和错误直接失败，不能伪装为重同步。
        self.wire.receive(raw)
        self.awaiting.discard(outer.actor_ref)
        return self._result("applied", applied=True)
