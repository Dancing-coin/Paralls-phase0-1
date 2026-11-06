from pydantic import BaseModel, ConfigDict, Field

from app.models.siming_event import FairnessStateSnapshot
from app.models.siming_narrative import NarrativeCoreResult, QualitySignal
from app.models.siming_runtime_state import FairnessDimensionSnapshot, StateTreeSnapshot
from app.services.siming_fairness_aggregate import compute_fairness_aggregate
from app.services.siming_feature_registry import SimingFeatureRegistry


REQUIRED_DIMENSIONS = (
    "information_distribution",
    "participation_distribution",
    "conversation_access_fairness",
    "suspicion_heat_distribution",
    "evidence_visibility_distribution",
)


class QualityMonitorResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot: FairnessStateSnapshot
    signals: list[QualitySignal] = Field(default_factory=list)
    risk_tags: list[str] = Field(default_factory=list)


class SimingQualityMonitor:
    # A single actor whose suspicion exceeds this is treated as a runaway risk:
    # suspicion concentrating on one person is the failure mode, not heat itself.
    SUSPICION_HEAT_THRESHOLD = 0.75

    def __init__(
        self,
        *,
        feature_registry: SimingFeatureRegistry | None = None,
        force_failed_dimensions: set[str] | None = None,
    ) -> None:
        self._feature_registry = feature_registry or SimingFeatureRegistry()
        self._force_failed_dimensions = force_failed_dimensions or set()

    def evaluate(
        self,
        *,
        state_tree: StateTreeSnapshot,
        narrative: NarrativeCoreResult,
    ) -> QualityMonitorResult:
        signals = [
            signal
            for signal in self._signals_for(state_tree=state_tree, narrative=narrative)
            if signal.dimension not in self._force_failed_dimensions
        ]
        dimensions: dict[str, FairnessDimensionSnapshot] = {}
        risk_tags: list[str] = []

        for dimension_id in REQUIRED_DIMENSIONS:
            if dimension_id in self._force_failed_dimensions:
                dimensions[dimension_id] = FairnessDimensionSnapshot(
                    dimension_id=dimension_id,
                    status="unavailable",
                    score=0.0,
                    reason="auditor unavailable",
                    mapped_to_policy=True,
                )
                risk_tags.append("quality_monitor_partial")
                continue

            dimension_signals = [signal for signal in signals if signal.dimension == dimension_id]
            dimensions[dimension_id] = self._dimension_from_signals(dimension_id, dimension_signals)

        for registration in self._feature_registry.fairness_dimensions():
            if registration.dimension_id in dimensions:
                continue
            dimensions[registration.dimension_id] = FairnessDimensionSnapshot(
                dimension_id=registration.dimension_id,
                status="fresh",
                score=0.0,
                reason="registered fairness dimension available",
                mapped_to_policy=(
                    self._feature_registry.policy_mapping_for(registration.dimension_id) is not None
                ),
            )

        established_fact_id = state_tree.environment.summary.get("established_fact_id")
        target_actor_id = state_tree.character.summary.get("target_actor_id")
        aggregate = compute_fairness_aggregate(dimensions)

        return QualityMonitorResult(
            snapshot=FairnessStateSnapshot(
                snapshot_id=f"fairness:{state_tree.snapshot_id}",
                room_id=state_tree.room_id,
                scene_id=state_tree.scene_id,
                zone_id=state_tree.zone_id,
                causation_id=state_tree.causation_id,
                correlation_id=state_tree.correlation_id,
                known_fact_ids=[str(established_fact_id)] if established_fact_id else [],
                eligible_actor_ids=[str(target_actor_id)] if target_actor_id else [],
                blocked_actor_ids=[],
                recent_intervention_ids=[],
                dimensions=dimensions,
                global_imbalance_score=aggregate.score,
                dominant_imbalance_type=aggregate.dominant,
                imbalance_reasons=list(aggregate.reasons),
            ),
            signals=signals,
            risk_tags=sorted(set(risk_tags)),
        )

    def _signals_for(
        self,
        *,
        state_tree: StateTreeSnapshot,
        narrative: NarrativeCoreResult,
    ) -> list[QualitySignal]:
        signals: list[QualitySignal] = []
        visible_actor_ids = state_tree.environment.summary.get("visible_actor_ids", [])
        target_actor_id = str(state_tree.character.summary.get("target_actor_id", "") or "")

        if target_actor_id and isinstance(visible_actor_ids, list) and target_actor_id not in visible_actor_ids:
            signals.append(
                QualitySignal(
                    signal_id=f"quality:{state_tree.snapshot_id}:information_distribution",
                    dimension="information_distribution",
                    severity="high",
                    target_refs=[target_actor_id],
                    evidence_refs=[str(state_tree.environment.summary.get("established_fact_id", ""))],
                    suggested_action_band="fact_reveal",
                    reason="established fact is not visible to target actor",
                )
            )

        if int(state_tree.character.summary.get("recent_participation_count", 0) or 0) == 0:
            signals.append(
                QualitySignal(
                    signal_id=f"quality:{state_tree.snapshot_id}:participation_distribution",
                    dimension="participation_distribution",
                    severity="medium",
                    target_refs=[target_actor_id] if target_actor_id else [],
                    suggested_action_band="opportunity",
                    reason="target actor has no recent participation",
                )
            )

        candidate_actor_ids = state_tree.storyline.summary.get("conversation_candidate_actor_ids", [])
        if target_actor_id and isinstance(candidate_actor_ids, list) and target_actor_id not in candidate_actor_ids:
            signals.append(
                QualitySignal(
                    signal_id=f"quality:{state_tree.snapshot_id}:conversation_access_fairness",
                    dimension="conversation_access_fairness",
                    severity="medium",
                    target_refs=[target_actor_id],
                    suggested_action_band="opportunity",
                    reason="target actor is excluded from candidate conversation access",
                )
            )

        if narrative.seeds:
            signals.append(
                QualitySignal(
                    signal_id=f"quality:{state_tree.snapshot_id}:evidence_visibility_distribution",
                    dimension="evidence_visibility_distribution",
                    severity="medium",
                    target_refs=narrative.seeds[0].target_refs,
                    evidence_refs=narrative.seeds[0].basis_fact_refs,
                    suggested_action_band=narrative.seeds[0].suggested_band,
                    reason="narrative seed requires evidence visibility surface",
                )
            )

        # Suspicion heat was previously hard-coded as unavailable, which left one
        # of the five fairness dimensions permanently unmeasurable.  Derive it
        # from the recorded per-actor attention instead, so the dimension has a
        # real source and can still report "unavailable" only when truly absent.
        suspicion_heat = state_tree.character.summary.get("suspicion_heat")
        if isinstance(suspicion_heat, dict):
            heat_values = {
                str(actor_id): float(value)
                for actor_id, value in suspicion_heat.items()
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            }
            hot_actors = sorted(
                actor_id for actor_id, value in heat_values.items() if value >= self.SUSPICION_HEAT_THRESHOLD
            )
            if hot_actors:
                signals.append(
                    QualitySignal(
                        signal_id=f"quality:{state_tree.snapshot_id}:suspicion_heat_distribution",
                        dimension="suspicion_heat_distribution",
                        severity="high" if len(hot_actors) == 1 else "medium",
                        target_refs=hot_actors,
                        suggested_action_band="fact_reveal",
                        reason=(
                            "suspicion concentrated on a single actor"
                            if len(hot_actors) == 1
                            else "suspicion heat spread across actors"
                        ),
                    )
                )
            else:
                signals.append(
                    QualitySignal(
                        signal_id=f"quality:{state_tree.snapshot_id}:suspicion_heat_distribution",
                        dimension="suspicion_heat_distribution",
                        severity="ok",
                        target_refs=[],
                        suggested_action_band="none",
                        reason="suspicion heat within bounds",
                    )
                )

        return signals

    def _dimension_from_signals(
        self,
        dimension_id: str,
        signals: list[QualitySignal],
    ) -> FairnessDimensionSnapshot:
        if dimension_id == "suspicion_heat_distribution" and not signals:
            # Only reachable when the state tree carries no suspicion_heat source
            # at all; a present-but-calm source emits an "ok" signal instead.
            return FairnessDimensionSnapshot(
                dimension_id=dimension_id,
                status="unavailable",
                score=0.0,
                reason="suspicion heat source absent",
                mapped_to_policy=True,
            )

        if not signals:
            return FairnessDimensionSnapshot(
                dimension_id=dimension_id,
                status="fresh",
                score=0.0,
                reason="no imbalance detected",
                mapped_to_policy=True,
            )

        severity_score = {
            "ok": 0.0,
            "low": 0.25,
            "medium": 0.6,
            "high": 0.9,
            "partial": 0.0,
            "unavailable": 0.0,
        }
        score = max(severity_score[signal.severity] for signal in signals)
        if any(signal.severity == "high" for signal in signals):
            status = "stale"
        elif any(signal.severity == "medium" for signal in signals):
            status = "partial"
        elif any(signal.severity == "partial" for signal in signals):
            status = "partial"
        else:
            status = "fresh"

        return FairnessDimensionSnapshot(
            dimension_id=dimension_id,
            status=status,
            score=score,
            reason="; ".join(signal.reason for signal in signals),
            mapped_to_policy=True,
        )
