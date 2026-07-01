from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot
from app.models.character_perceived import CharacterPerceivedEvent
from app.models.self_body_perceived import SelfBodyPerceivedEvent
from app.world_runtime.intelligence_upgrade import CanonicalPerceptBundle


class CharacterAgentL1Service:
    def __init__(self) -> None:
        self._snapshots: dict[str, CharacterPrivateWorldSnapshot] = {}

    def get_snapshot(self, actor_id: str) -> CharacterPrivateWorldSnapshot | None:
        return self._snapshots.get(actor_id)

    def apply_character_perceived_event(self, event: CharacterPerceivedEvent) -> CharacterPrivateWorldSnapshot:
        snapshot = self._get_or_create_snapshot(
            actor_id=event.actor_id,
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            producer_ts=event.producer_ts,
        )
        if event.percept_channel == "visual":
            snapshot.visible_entities = [event.perceived_summary]
        elif event.percept_channel == "auditory":
            snapshot.audible_entities = [event.perceived_summary]
        elif event.percept_channel == "olfactory":
            snapshot.olfactory_entities = self._append_unique(snapshot.olfactory_entities, event.perceived_summary)
        elif event.percept_channel == "thermal":
            snapshot.thermal_entities = self._append_unique(snapshot.thermal_entities, event.perceived_summary)
        elif event.percept_channel == "tactile":
            snapshot.tactile_entities = self._append_unique(snapshot.tactile_entities, event.perceived_summary)
        else:
            snapshot.unresolved_signals = self._append_unique(snapshot.unresolved_signals, event.perceived_summary)
            if event.clarity_score < 0.7 or event.certainty_score < 0.7:
                snapshot.active_anomalies = self._append_unique(snapshot.active_anomalies, event.perceived_summary)
                snapshot.distraction_level = "elevated"
        if event.clarity_score < 0.75:
            snapshot.partial_observations = self._append_unique(snapshot.partial_observations, event.perceived_summary)
        if event.certainty_score < 0.65:
            snapshot.distorted_details = self._append_unique(snapshot.distorted_details, event.perceived_summary)
        if event.certainty_score < 0.45:
            snapshot.missed_details = self._append_unique(snapshot.missed_details, event.perceived_summary)
        if event.clarity_score < 0.85 or event.certainty_score < 0.85:
            snapshot.salience_tags = self._append_unique(
                snapshot.salience_tags,
                f"{event.percept_channel}:{event.perceived_summary}",
            )
        attention_target = self._resolve_attention_target(
            target_actor_id=event.target_actor_id,
            target_object_id=event.target_object_id,
            target_environment_id=event.target_environment_id,
        )
        if attention_target != "":
            snapshot.attention_targets = [attention_target]
            snapshot.current_attention_targets = [attention_target]
            if event.percept_channel == "spatial":
                snapshot.local_spatial_confidence_map = {
                    attention_target: event.certainty_score,
                }
            if event.target_actor_id != "":
                snapshot.short_horizon_social_presence = [event.target_actor_id]
        else:
            snapshot.current_attention_targets = snapshot.attention_targets.copy()
        snapshot.clarity_score = event.clarity_score
        snapshot.certainty_score = event.certainty_score
        snapshot.attention_pressure = max(snapshot.attention_pressure, min(1.0, max(event.clarity_score, event.certainty_score)))
        snapshot.updated_at = event.producer_ts
        snapshot.producer_ts = event.producer_ts
        return snapshot

    def apply_self_body_perceived_event(self, event: SelfBodyPerceivedEvent) -> CharacterPrivateWorldSnapshot:
        snapshot = self._get_or_create_snapshot(
            actor_id=event.actor_id,
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            producer_ts=event.producer_ts,
        )
        snapshot.body_state_hints = [f"{event.body_state_class}:{event.perceived_summary}"]
        snapshot.current_attention_targets = snapshot.attention_targets.copy()
        snapshot.updated_at = event.producer_ts
        snapshot.producer_ts = event.producer_ts
        return snapshot

    def apply_siming_output(self, payload: dict[str, object]) -> CharacterPrivateWorldSnapshot:
        actor_id = str(payload.get("target_actor_id", "") or "")
        snapshot = self._get_or_create_snapshot(
            actor_id=actor_id,
            room_id=str(payload.get("room_id", "") or "room_demo"),
            scene_id=str(payload.get("scene_id", "") or "scene_demo"),
            zone_id=str(payload.get("zone_id", "") or "zone_focus"),
            producer_ts=int(payload.get("producer_ts", 0) or 0),
        )
        target_object_id = str(payload.get("target_object_id", "") or "")
        target_actor_id = str(payload.get("target_actor_id", "") or "")
        target_environment_id = str(payload.get("target_environment_id", "") or "")
        attention_target = target_object_id or target_environment_id or target_actor_id
        if attention_target != "":
            snapshot.attention_targets = [attention_target]
            snapshot.current_attention_targets = [attention_target]
        presentation_hint = str(payload.get("presentation_hint", "") or "").strip()
        snapshot.last_siming_catalyst = presentation_hint or None
        if snapshot.last_siming_catalyst is not None:
            snapshot.vigilance_level = "elevated"
        pressure_hint = str(payload.get("pressure_hint", "") or "").strip()
        if pressure_hint != "":
            snapshot.distraction_level = "elevated"
            pressure_marker = f"siming_pressure:{pressure_hint}"
            if pressure_marker not in snapshot.unresolved_signals:
                snapshot.unresolved_signals = (snapshot.unresolved_signals + [pressure_marker])[-4:]
        reason_scope = str(payload.get("reason_scope", "") or "").strip()
        if reason_scope != "":
            reason_scope_tag = f"siming_reason_scope:{reason_scope}"
            if reason_scope_tag not in snapshot.bias_tags:
                snapshot.bias_tags = (snapshot.bias_tags + [reason_scope_tag])[-4:]
        salience_boost = payload.get("salience_boost")
        if attention_target != "" and isinstance(salience_boost, int | float):
            snapshot.local_spatial_confidence_map = {
                **snapshot.local_spatial_confidence_map,
                attention_target: max(
                    float(snapshot.local_spatial_confidence_map.get(attention_target, 0.0) or 0.0),
                    min(1.0, max(0.0, float(salience_boost))),
                ),
            }
        snapshot.updated_at = int(payload.get("producer_ts", 0) or 0)
        snapshot.producer_ts = int(payload.get("producer_ts", 0) or 0)
        return snapshot

    def apply_canonical_percept_bundle(self, bundle: CanonicalPerceptBundle) -> CharacterPrivateWorldSnapshot:
        if bundle.consumer_kind != "character":
            raise ValueError("CharacterAgentL1Service only accepts character CanonicalPerceptBundle payloads")
        producer_ts = self._producer_ts_from_bundle(bundle)
        zone_id = str(bundle.local_spatial_state.get("zone_id", "") or "zone_focus")
        snapshot = self._get_or_create_snapshot(
            actor_id=bundle.subject_id,
            room_id=str(bundle.local_spatial_state.get("room_id", "") or "room_demo"),
            scene_id=str(bundle.local_spatial_state.get("scene_id", "") or "scene_demo"),
            zone_id=zone_id,
            producer_ts=producer_ts,
        )
        snapshot.zone_id = zone_id
        target_ref = self._bundle_target_ref(bundle)
        if target_ref:
            snapshot.attention_targets = [target_ref]
            snapshot.current_attention_targets = [target_ref]
            snapshot.local_spatial_confidence_map = {
                **snapshot.local_spatial_confidence_map,
                target_ref: max(float(snapshot.local_spatial_confidence_map.get(target_ref, 0.0) or 0.0), 0.75),
            }
        for fact_ref in bundle.structured_fact_refs:
            snapshot.recent_world_changes = self._append_unique(snapshot.recent_world_changes, fact_ref)
            if "target_unreachable" in fact_ref or "expected_target_missing" in fact_ref:
                snapshot.recent_constraint_results = self._append_unique(snapshot.recent_constraint_results, fact_ref)
        if bundle.uncertainty:
            snapshot.active_anomalies = self._append_unique(
                snapshot.active_anomalies,
                str(bundle.uncertainty.get("reason", "l1_world_fact_uncertainty") or "l1_world_fact_uncertainty"),
            )
            snapshot.distraction_level = "elevated"
        visibility = str(bundle.environment_state.get("visibility_level", "") or "")
        if visibility in {"reduced", "blocked"}:
            snapshot.salience_tags = self._append_unique(snapshot.salience_tags, f"environment_visibility:{visibility}")
        snapshot.updated_at = producer_ts
        snapshot.producer_ts = producer_ts
        return snapshot

    def _append_unique(self, entries: list[str], value: str) -> list[str]:
        if value == "":
            return entries
        if value in entries:
            return entries
        return (entries + [value])[-4:]

    def _resolve_attention_target(
        self,
        *,
        target_actor_id: str,
        target_object_id: str,
        target_environment_id: str,
    ) -> str:
        return target_actor_id or target_object_id or target_environment_id

    def _bundle_target_ref(self, bundle: CanonicalPerceptBundle) -> str:
        target_ref = str(bundle.target_state.get("target_ref", "") or "")
        if target_ref:
            return target_ref
        attention = bundle.attention_state
        for key in ("target_actor_ids", "target_object_ids", "target_environment_ids"):
            values = attention.get(key, [])
            if isinstance(values, list) and values:
                return str(values[0])
        return ""

    def _producer_ts_from_bundle(self, bundle: CanonicalPerceptBundle) -> int:
        try:
            return int(str(bundle.query_id).split(":")[-1])
        except ValueError:
            return 0

    def _get_or_create_snapshot(
        self,
        *,
        actor_id: str,
        room_id: str,
        scene_id: str,
        zone_id: str,
        producer_ts: int,
    ) -> CharacterPrivateWorldSnapshot:
        existing = self._snapshots.get(actor_id)
        if existing is not None:
            return existing

        snapshot = CharacterPrivateWorldSnapshot(
            actor_id=actor_id,
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            producer_ts=producer_ts,
            updated_at=producer_ts,
        )
        self._snapshots[actor_id] = snapshot
        return snapshot
