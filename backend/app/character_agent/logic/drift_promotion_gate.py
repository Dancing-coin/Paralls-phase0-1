from __future__ import annotations

from app.character_agent.models.drift_candidate import DriftCandidateRecord


class DriftPromotionGate:
    def should_promote(self, candidate: DriftCandidateRecord) -> bool:
        return (
            candidate.cross_scene_count >= 3
            and candidate.reinforcing_events >= 8
            and candidate.stable_time_span == "long_arc"
            and candidate.confidence >= 0.7
        )


__all__ = ["DriftPromotionGate"]
