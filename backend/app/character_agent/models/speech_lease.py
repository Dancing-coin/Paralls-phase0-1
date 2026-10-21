from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SpeechLease:
    """Expression permission bounded by the existing admitted turn deadline."""

    request_id: str
    actor_id: str
    target_actor_id: str
    expires_at_monotonic: float

    def __post_init__(self):
        if not self.actor_id or not self.target_actor_id or not math.isfinite(self.expires_at_monotonic):
            raise ValueError("speech lease requires actor, target and finite expiry")

    def permits(self, *, now_monotonic: float, actor_id: str) -> bool:
        return (math.isfinite(now_monotonic) and actor_id == self.actor_id
                and now_monotonic < self.expires_at_monotonic)
