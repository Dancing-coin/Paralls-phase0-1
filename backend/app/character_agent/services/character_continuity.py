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


__all__ = ["CharacterContinuityService"]
