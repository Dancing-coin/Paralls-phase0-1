from __future__ import annotations

from app.character_agent.models.drift_candidate import DriftCandidateRecord
from app.character_agent.models.dynamic_state import CharacterDynamicState
from app.character_agent.models.need_tension import NeedTensionState
from app.models.character_agent_runtime import CharacterInterpretation


class DriftAccumulator:
    _EXPLICIT_HINT_PREFIX = "drift_candidate:"

    def observe(
        self,
        *,
        actor_id: str,
        effective_profile: dict[str, object],
        interpretation: CharacterInterpretation,
        dynamic_state: CharacterDynamicState,
        need_tension_state: NeedTensionState,
    ) -> DriftCandidateRecord | None:
        explicit_candidate = self._candidate_from_explicit_hint(
            actor_id=actor_id,
            interpretation=interpretation,
            need_tension_state=need_tension_state,
        )
        if explicit_candidate is not None:
            return (
                None
                if self._is_already_represented_in_drift_layer(
                    effective_profile=effective_profile,
                    candidate_key=explicit_candidate.key,
                )
                else explicit_candidate
            )

        drift_layer = effective_profile.get("long_term_personality_drift_layer", {})

        dominant_need = str(
            need_tension_state.dominant_need
            or dynamic_state.motivation_state.dominant_need
            or ""
        ).strip()
        pressure_sources = [str(item).strip() for item in need_tension_state.pressure_sources if str(item).strip()]
        pressure_values = [
            float(need_tension_state.physiological_pressure),
            float(need_tension_state.safety_pressure),
            float(need_tension_state.belonging_pressure),
            float(need_tension_state.esteem_pressure),
            float(need_tension_state.self_actualization_pressure),
        ]
        dynamic_pressure_values = [
            float(dynamic_state.stress_load),
            float(dynamic_state.social_pressure),
            float(dynamic_state.masking_pressure),
            float(dynamic_state.vigilance_level),
        ]
        signal_strength = max(pressure_values + dynamic_pressure_values, default=0.0)
        if dominant_need == "" and signal_strength <= 0.0 and not pressure_sources:
            return None

        key_root = dominant_need if dominant_need != "" else interpretation.interpretation_type or "runtime"
        confidence = round(min(0.69, max(0.35, signal_strength)), 2)
        reinforcing_events = min(7, max(1, int(round(signal_strength * 7))))
        evidence_parts = [
            f"interpretation={interpretation.interpretation_type}",
            f"dominant_need={dominant_need or 'unspecified'}",
        ]
        if pressure_sources:
            evidence_parts.append(f"pressure_sources={','.join(pressure_sources)}")
        if interpretation.interpreted_summary:
            evidence_parts.append(f"summary={interpretation.interpreted_summary}")
        candidate = DriftCandidateRecord(
            actor_id=actor_id,
            key=f"{key_root}_pressure_pattern",
            direction="increased",
            reinforcing_events=reinforcing_events,
            cross_scene_count=1,
            stable_time_span="short_arc",
            confidence=confidence,
            evidence_summary="; ".join(evidence_parts),
        )
        if self._is_already_represented_in_drift_layer(
            effective_profile={"long_term_personality_drift_layer": drift_layer},
            candidate_key=candidate.key,
        ):
            return None
        return candidate

    def _candidate_from_explicit_hint(
        self,
        *,
        actor_id: str,
        interpretation: CharacterInterpretation,
        need_tension_state: NeedTensionState,
    ) -> DriftCandidateRecord | None:
        reasoning_trace_summary = str(interpretation.reasoning_trace_summary or "").strip()
        if not reasoning_trace_summary.startswith(self._EXPLICIT_HINT_PREFIX):
            return None

        raw_fields = reasoning_trace_summary[len(self._EXPLICIT_HINT_PREFIX) :]
        parsed_fields: dict[str, str] = {}
        for field in raw_fields.replace(";", "|").split("|"):
            key, separator, value = field.partition("=")
            if separator == "":
                continue
            normalized_key = key.strip()
            normalized_value = value.strip()
            if normalized_key == "" or normalized_value == "":
                continue
            parsed_fields[normalized_key] = normalized_value

        evidence_summary = parsed_fields.get("evidence_summary")
        if evidence_summary is None or evidence_summary == "":
            dominant_need = str(need_tension_state.dominant_need or "unspecified").strip() or "unspecified"
            evidence_summary = (
                f"explicit_runtime_hint; dominant_need={dominant_need}; "
                f"summary={interpretation.interpreted_summary}"
            )

        return DriftCandidateRecord(
            actor_id=actor_id,
            key=parsed_fields.get("key", "runtime_drift_signal"),
            direction=parsed_fields.get("direction", "increased"),
            reinforcing_events=self._int_field(parsed_fields.get("reinforcing_events"), default=1),
            cross_scene_count=self._int_field(parsed_fields.get("cross_scene_count"), default=1),
            stable_time_span=parsed_fields.get("stable_time_span", "short_arc"),
            confidence=self._confidence_field(parsed_fields.get("confidence"), default=0.5),
            evidence_summary=evidence_summary,
        )

    def _int_field(self, value: str | None, *, default: int) -> int:
        if value is None:
            return default
        try:
            return max(0, int(value))
        except ValueError:
            return default

    def _confidence_field(self, value: str | None, *, default: float) -> float:
        if value is None:
            return default
        try:
            return max(0.0, min(1.0, float(value)))
        except ValueError:
            return default

    def _is_already_represented_in_drift_layer(
        self,
        *,
        effective_profile: dict[str, object],
        candidate_key: str,
    ) -> bool:
        drift_layer = effective_profile.get("long_term_personality_drift_layer", {})
        if not isinstance(drift_layer, dict):
            return False

        for bucket_name in ("stable_shifts", "reinforced_patterns", "weakened_patterns"):
            bucket = drift_layer.get(bucket_name, [])
            if not isinstance(bucket, list):
                continue
            if candidate_key in {str(item).strip() for item in bucket if str(item).strip()}:
                return True
        return False


__all__ = ["DriftAccumulator"]
