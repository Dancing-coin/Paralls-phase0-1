from app.models.siming_story_graph import (
    StoryCandidateRanking,
    StoryCandidateRejection,
    StoryDecisionCandidate,
)


class StoryNodeOrchestrator:
    GATE_ORDER = (
        "confirmed_fact",
        "player_choice",
        "actor_autonomy",
        "world_feasibility",
        "safety",
        "playability_fairness",
        "open_obligation",
        "reachable_attractor",
    )
    _REJECTION_REASONS = {
        "confirmed_fact": "fact_gate_failed",
        "player_choice": "player_choice_gate_failed",
        "actor_autonomy": "actor_autonomy_gate_failed",
        "world_feasibility": "world_feasibility_gate_failed",
        "safety": "safety_gate_failed",
        "playability_fairness": "playability_fairness_gate_failed",
        "open_obligation": "open_obligation_gate_failed",
        "reachable_attractor": "reachable_attractor_gate_failed",
    }

    def rank(
        self,
        candidates: list[StoryDecisionCandidate],
    ) -> StoryCandidateRanking:
        eligible: list[StoryDecisionCandidate] = []
        rejected: list[StoryCandidateRejection] = []
        for candidate in candidates:
            failed_gate = next(
                (
                    gate
                    for gate in self.GATE_ORDER
                    if not getattr(candidate, gate)
                ),
                None,
            )
            if failed_gate is None:
                eligible.append(candidate)
            else:
                rejected.append(
                    StoryCandidateRejection(
                        candidate_id=candidate.candidate_id,
                        reason=self._REJECTION_REASONS[failed_gate],
                    )
                )
        return StoryCandidateRanking(
            eligible=sorted(
                eligible,
                key=lambda item: (-item.narrative_score, item.candidate_id),
            ),
            rejected=rejected,
        )
