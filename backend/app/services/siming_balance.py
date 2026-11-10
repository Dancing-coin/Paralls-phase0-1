"""司命公平分布评估。"""

from app.models.siming_event import FairnessDistribution, FairnessStateSnapshot
from app.services.siming_knowledge_graph import SimingKnowledgeGraph


class SimingBalanceSystem:
    def __init__(self, knowledge_graph: SimingKnowledgeGraph) -> None:
        self._knowledge_graph = knowledge_graph

    def evaluate_fairness(self, actor_ids: list[str], current_tick: int, *, snapshot: FairnessStateSnapshot | None = None, suspicion_heat: dict[str, float] | None = None) -> FairnessStateSnapshot:
        if current_tick < 0 or len(set(actor_ids)) != len(actor_ids) or any(not actor for actor in actor_ids):
            raise ValueError("invalid tick or actor ids")
        if snapshot is None:
            snapshot = FairnessStateSnapshot(snapshot_id=f"balance:{current_tick}", room_id="", scene_id="", zone_id="", causation_id="", correlation_id="", eligible_actor_ids=actor_ids)
        observations = {actor: self._knowledge_graph.fairness_observations(actor, current_tick) for actor in actor_ids}
        quality = {"full": 1.0, "partial": 0.6, "minimal": 0.3, "none": 0.0}
        metrics = {
            "information_distribution": ("information", {a: float(v[0]) for a, v in observations.items()}),
            "participation_distribution": ("participation", {a: float(v[1]) for a, v in observations.items()}),
            "conversation_access_fairness": ("conversation_access", {a: sum(quality[q] for q in v[2]) / len(v[2]) if v[2] else 0.0 for a, v in observations.items()}),
            "evidence_visibility_distribution": ("evidence_visibility", {a: float(v[3]) for a, v in observations.items()}),
        }
        distributions = {field: self._distribution(name, scores) for field, (name, scores) in metrics.items()}
        if suspicion_heat is not None:
            if set(suspicion_heat) != set(actor_ids) or any(not 0 <= value <= 1 for value in suspicion_heat.values()):
                raise ValueError("suspicion heat must cover actors with values between 0 and 1")
            distributions["suspicion_heat_distribution"] = self._distribution("suspicion_heat", suspicion_heat)
        score = sum(1 - item.gini_coefficient for item in distributions.values()) / len(distributions)
        urgency = "critical" if score < .3 else "high" if score < .4 else "medium" if score < .5 else "low" if score < .6 else "none"
        return snapshot.model_copy(update={"suspicion_heat_distribution": None, **distributions, "overall_fairness_score": score, "needs_intervention": score < .6, "intervention_urgency": urgency})

    @staticmethod
    def _distribution(name: str, scores: dict[str, float]) -> FairnessDistribution:
        values = sorted(scores.values())
        total = sum(values)
        gini = max(0.0, min(1.0, 2 * sum((i + 1) * value for i, value in enumerate(values)) / (len(values) * total) - (len(values) + 1) / len(values))) if total else 0.0
        level = "balanced" if gini < .2 else "slight_tilt" if gini < .4 else "moderate_tilt" if gini < .6 else "severe_tilt" if gini < .8 else "critical"
        mean = total / len(values) if values else 0
        return FairnessDistribution(metric_name=name, actor_scores=scores, gini_coefficient=gini, imbalance_level=level, marginalized_actors=[a for a, value in scores.items() if mean and value < mean * .5], dominant_actors=[a for a, value in scores.items() if mean and value > mean * 1.5])
