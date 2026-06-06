from collections.abc import Callable

from app.models.raw_fact import RawFactEvent
from app.models.runtime_state import SpatialAccessRuntimeStateSnapshot

Message = dict[str, object]
SpatialAccessFactRouteHandler = Callable[[RawFactEvent, str], list[Message]]


class SpatialAccessFactHandler:
    def __init__(self) -> None:
        self._snapshots: dict[str, SpatialAccessRuntimeStateSnapshot] = {}

    def get_snapshot(self, actor_id: str) -> SpatialAccessRuntimeStateSnapshot | None:
        return self._snapshots.get(actor_id)

    def handle_event(self, event: RawFactEvent, source_type: str) -> list[Message]:
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

        if event.fact_type == "actor_entered_zone":
            snapshot.nearby_actor_refs = []
            return

        if event.fact_type == "actor_approached_actor":
            target_actor_id = event.targets.actor_id
            snapshot.nearby_actor_refs = [target_actor_id] if target_actor_id != "" else []
            return

        if event.fact_type == "privacy_boundary_changed":
            next_privacy_band = event.world.state_after
            if next_privacy_band != "":
                snapshot.privacy_band = next_privacy_band


_default_spatial_access_fact_handler = SpatialAccessFactHandler()


def handle_spatial_access_fact_event(event: RawFactEvent, source_type: str) -> list[Message]:
    return _default_spatial_access_fact_handler.handle_event(event, source_type)
