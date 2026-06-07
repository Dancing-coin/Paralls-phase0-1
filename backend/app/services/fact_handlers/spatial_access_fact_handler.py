from collections.abc import Callable

from app.models.raw_fact import RawFactEvent
from app.models.runtime_state import SpatialAccessRuntimeStateSnapshot

Message = dict[str, object]
SpatialAccessFactRouteHandler = Callable[[RawFactEvent, str], list[Message]]


class SpatialAccessFactHandler:
    def __init__(self) -> None:
        self._snapshots: dict[str, SpatialAccessRuntimeStateSnapshot] = {}
        self._expiry_deadlines_by_actor: dict[str, dict[str, int]] = {}

    def get_snapshot(self, actor_id: str) -> SpatialAccessRuntimeStateSnapshot | None:
        return self._snapshots.get(actor_id)

    def handle_event(self, event: RawFactEvent, source_type: str) -> list[Message]:
        actor_id = event.source.actor_id
        self._prune_expired_state(actor_id, event.producer_ts)
        snapshot = self._get_or_create_snapshot(event)
        self._apply_event(snapshot, event)
        return [
            {
                "message_type": "ack",
                "payload": {
                    "accepted": True,
                    "source_type": source_type,
                    "route": "authority_spatial_access_fact",
                },
            },
            {
                "message_type": "spatial_access_runtime_state_snapshot",
                "payload": snapshot.model_dump(),
            },
        ]

    def _get_actor_expiry_map(self, actor_id: str) -> dict[str, int]:
        return self._expiry_deadlines_by_actor.setdefault(actor_id, {})

    def _prune_expired_state(self, actor_id: str, now_ms: int) -> None:
        snapshot = self._snapshots.get(actor_id)
        if snapshot is None:
            return
        expiry_map = self._expiry_deadlines_by_actor.get(actor_id, {})
        expiry_deadline = expiry_map.get("nearby_actor_refs")
        if expiry_deadline is None:
            return
        if now_ms < expiry_deadline:
            return
        snapshot.nearby_actor_refs = []
        expiry_map.pop("nearby_actor_refs", None)

    def _get_or_create_snapshot(self, event: RawFactEvent) -> SpatialAccessRuntimeStateSnapshot:
        actor_id = event.source.actor_id
        existing = self._snapshots.get(actor_id)
        if existing is not None:
            return existing

        snapshot = SpatialAccessRuntimeStateSnapshot(
            actor_id=actor_id,
            room_id=event.room_id,
            scene_id=event.scene_id,
            current_zone_id=event.zone_id,
            producer_ts=event.producer_ts,
            updated_at=event.producer_ts,
        )
        self._snapshots[actor_id] = snapshot
        return snapshot

    def _apply_event(self, snapshot: SpatialAccessRuntimeStateSnapshot, event: RawFactEvent) -> None:
        snapshot.room_id = event.room_id
        snapshot.scene_id = event.scene_id
        snapshot.current_zone_id = event.zone_id
        snapshot.producer_ts = event.producer_ts
        snapshot.updated_at = event.producer_ts

        effect_kind = event.effect_kind
        subject_key = event.subject_key

        if subject_key == "":
            effect_kind, subject_key = self._legacy_effect_semantics(event)

        if effect_kind == "set" and subject_key == "current_zone_id":
            snapshot.current_zone_id = event.zone_id
            if event.fact_type == "actor_entered_zone":
                snapshot.nearby_actor_refs = []
                self._get_actor_expiry_map(event.source.actor_id).pop("nearby_actor_refs", None)
            return

        if effect_kind == "replace" and subject_key == "nearby_actor_refs":
            target_actor_id = event.targets.actor_id
            snapshot.nearby_actor_refs = [target_actor_id] if target_actor_id != "" else []
            expiry_map = self._get_actor_expiry_map(event.source.actor_id)
            if event.ttl_ms is not None and event.ttl_ms > 0:
                expiry_map["nearby_actor_refs"] = event.producer_ts + event.ttl_ms
            else:
                expiry_map.pop("nearby_actor_refs", None)
            return

        if effect_kind == "clear" and subject_key == "nearby_actor_refs":
            snapshot.nearby_actor_refs = []
            self._get_actor_expiry_map(event.source.actor_id).pop("nearby_actor_refs", None)
            return

        if effect_kind == "set" and subject_key == "privacy_band":
            next_privacy_band = event.world.state_after
            if next_privacy_band != "":
                snapshot.privacy_band = next_privacy_band

    @staticmethod
    def _legacy_effect_semantics(event: RawFactEvent) -> tuple[str, str]:
        if event.fact_type == "actor_entered_zone":
            return ("set", "current_zone_id")
        if event.fact_type == "actor_approached_actor":
            return ("replace", "nearby_actor_refs")
        if event.fact_type == "actor_left_actor_range":
            return ("clear", "nearby_actor_refs")
        if event.fact_type == "privacy_boundary_changed":
            return ("set", "privacy_band")
        return (event.effect_kind, event.subject_key)


_default_spatial_access_fact_handler = SpatialAccessFactHandler()


def handle_spatial_access_fact_event(event: RawFactEvent, source_type: str) -> list[Message]:
    return _default_spatial_access_fact_handler.handle_event(event, source_type)
