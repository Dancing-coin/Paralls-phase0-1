from __future__ import annotations

from collections.abc import Callable, Sequence

from app.character_agent.models.simulation_seed import (
    CharacterContinuityCommand,
    CharacterContinuityReceipt,
    CharacterMemoryMaterializationReceipt,
)


class CharacterContinuityService:
    """Character Core-owned seam for simulation continuity settlement."""

    def __init__(
        self,
        *,
        apply_command: Callable[[CharacterContinuityCommand], CharacterContinuityReceipt],
        materialize: Callable[[str, int], Sequence[CharacterMemoryMaterializationReceipt]],
    ) -> None:
        self._apply_command = apply_command
        self._materialize = materialize

    def apply_command(self, command: CharacterContinuityCommand) -> CharacterContinuityReceipt:
        return self._apply_command(command)

    def materialize_pending_seed_memories(
        self, actor_id: str, producer_ts: int
    ) -> Sequence[CharacterMemoryMaterializationReceipt]:
        return self._materialize(actor_id, producer_ts)


class CharacterRuntimeContinuityPort:
    """Narrow Siming adapter over the already-built Character Core runtime."""

    def __init__(self, runtime: object) -> None:
        self.runtime = runtime

    def apply_command(self, command: CharacterContinuityCommand) -> CharacterContinuityReceipt:
        return self.runtime.apply_character_continuity_command(command)

    def current_revision(self, actor_ref: str) -> int:
        actor_id = actor_ref.removeprefix("character:")
        return int(self.runtime.get_continuity_revision(actor_id))


__all__ = ["CharacterContinuityService", "CharacterRuntimeContinuityPort"]
