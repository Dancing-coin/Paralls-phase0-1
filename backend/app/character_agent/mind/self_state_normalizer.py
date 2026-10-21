from __future__ import annotations

from app.character_agent.models.self_state_snapshot import SelfStateSnapshot
from app.models.self_body_perceived import SelfBodyPerceivedEvent


class SelfStateNormalizer:
    """Project existing self body evidence without inventing owner state."""

    def from_body_event(self, event: SelfBodyPerceivedEvent) -> SelfStateSnapshot:
        return SelfStateSnapshot(
            actor_id=event.actor_id,
            source=event.source_body_result_id,
            captured_at=event.producer_ts,
            producer_ts=event.producer_ts,
            revision=event.source_body_result_id,
            freshness="unknown",
            visibility="actor_private",
            uncertainty="unknown",
            body_state_class=event.body_state_class,
        )
