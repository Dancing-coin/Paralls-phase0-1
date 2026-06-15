from dataclasses import dataclass

from app.models.siming_event import InterventionCandidate, SelectedPath


@dataclass(frozen=True)
class SimingFeasibilityResult:
    accepted: bool
    selected_path: SelectedPath
    reasons: list[str]


class SimingExecutionFeasibility:
    def evaluate(self, candidate: InterventionCandidate) -> SimingFeasibilityResult:
        if candidate.proposed_band == "environment_request":
            if not candidate.target_environment_id:
                return SimingFeasibilityResult(False, "no_action", ["missing_environment_target"])
            return SimingFeasibilityResult(
                True, "environment_change_path", ["esm_result_required_for_success"]
            )

        if candidate.proposed_band == "fact_reveal" and candidate.target_environment_id:
            return SimingFeasibilityResult(True, "visual_fact_path", ["visual_fact_path_available"])

        if candidate.proposed_band in {"impulse", "opportunity", "fact_reveal"} and candidate.target_actor_id:
            return SimingFeasibilityResult(
                True, "character_input_path", ["character_input_path_available"]
            )

        return SimingFeasibilityResult(False, "no_action", ["no_executable_path"])
