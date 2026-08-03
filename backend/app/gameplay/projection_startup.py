"""Fail-closed projection bootstrap for a single Gameplay authority store."""

from __future__ import annotations

from dataclasses import dataclass

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import GameplayFailure, ReplayResult
from app.gameplay.replay import GameplayProjectionReplay


@dataclass(frozen=True)
class ProjectionStartupResult:
    read_ready: bool
    write_ready: bool
    selected_checkpoint_id: str | None
    replay_result: ReplayResult
    failure: GameplayFailure | None = None


class GameplayProjectionStartup:
    """Rebuild one required projection before permitting writes to its store."""

    def __init__(
        self,
        *,
        store: GameplayEventStore,
        replay: GameplayProjectionReplay,
        active_patch_set_revision: str | None = None,
        registry_revision: str | None = None,
        world_config_revision: str | None = None,
    ) -> None:
        self._store = store
        self._replay = replay
        self._active_patch_set_revision = active_patch_set_revision
        self._registry_revision = registry_revision
        self._world_config_revision = world_config_revision

    def bootstrap(self) -> ProjectionStartupResult:
        self._store.set_write_readiness(False)
        events = self._store.read_events()
        checkpoint = self._replay.select_compatible_checkpoint(
            self._store.list_projection_checkpoints(projector_id=self._replay.projector_id),
            events,
            active_patch_set_revision=self._active_patch_set_revision,
            registry_revision=self._registry_revision,
            world_config_revision=self._world_config_revision,
        )
        if checkpoint is None:
            result = self._replay.full_replay(events)
        else:
            tail = [event for event in events if event.global_sequence > checkpoint.last_global_sequence]
            result = self._replay.checkpoint_plus_tail_replay(
                checkpoint,
                tail,
                active_patch_set_revision=self._active_patch_set_revision,
                registry_revision=self._registry_revision,
                world_config_revision=self._world_config_revision,
            )
        if result.succeeded:
            self._store.set_write_readiness(True)
            return ProjectionStartupResult(True, True, checkpoint.checkpoint_id if checkpoint else None, result)
        return ProjectionStartupResult(False, False, checkpoint.checkpoint_id if checkpoint else None, result, result.failure)
