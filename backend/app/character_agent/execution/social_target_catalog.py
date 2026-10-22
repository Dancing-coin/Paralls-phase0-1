"""Read-only neutral social target admission from current owner sources."""

import hashlib
import json

from app.gameplay.canonical_combat_authority import CanonicalCombatTargetReader


_ACTIONS = ("approach", "follow_target", "seek_private_distance", "withdraw", "break_contact")


class CharacterSocialTargetCatalog:
    def __init__(self, *, store, source, scopes, timeline):
        self._store, self._source, self._timeline = store, source, timeline
        self._scopes = {scope.actor_id: scope for scope in scopes}

    def project_character_targets(self, snapshot):
        timeline = self._timeline()
        if timeline is None or timeline.status != "active":
            return []
        actor = self._canonical(snapshot.actor_id)
        actor_scope = self._scopes.get(snapshot.actor_id)
        if actor_scope is None or any(getattr(actor_scope, name) != getattr(snapshot, name)
                                      for name in ("room_id", "scene_id", "zone_id")):
            return []
        reader = CanonicalCombatTargetReader(store=self._store)
        descriptors = []
        for raw_target in sorted(set(snapshot.visible_target_refs)):
            target = self._canonical(raw_target)
            if target == actor or raw_target not in snapshot.visible_target_refs:
                continue
            lineage = snapshot.visible_target_sources.get(raw_target, [])
            if not lineage or any(not isinstance(ref, str) or not ref.strip() for ref in lineage):
                continue
            target_scope = self._scopes.get(raw_target.removeprefix("character:"))
            if target_scope is None or any(getattr(target_scope, name) != getattr(snapshot, name)
                                           for name in ("room_id", "scene_id", "zone_id")):
                continue
            if (target_scope.scene_instance_id != actor_scope.scene_instance_id
                    or target_scope.scene_revision != actor_scope.scene_revision):
                continue
            neutral = reader.resolve_current_participants(
                actor_ref=actor, target_ref=target, world_ref=timeline.world_scope_ref,
                timeline_ref=timeline.timeline_id, eligible_life_states=frozenset({"alive"}),
            )
            if neutral is None:
                continue
            try:
                actor_evidence = self._source.read(actor_id=snapshot.actor_id, room_id=snapshot.room_id,
                    scene_id=snapshot.scene_id, scene_instance_id=actor_scope.scene_instance_id,
                    zone_id=snapshot.zone_id, scene_revision=actor_scope.scene_revision)
                target_evidence = self._source.read(actor_id=raw_target.removeprefix("character:"),
                    room_id=snapshot.room_id, scene_id=snapshot.scene_id,
                    scene_instance_id=target_scope.scene_instance_id, zone_id=snapshot.zone_id,
                    scene_revision=target_scope.scene_revision)
            except (KeyError, TypeError, ValueError):
                continue
            revisions = dict(neutral["source_revisions"])
            revisions.update(actor_evidence.read_stream_revisions)
            revisions.update(target_evidence.read_stream_revisions)
            context = dict(neutral, visual_lineage=list(lineage), execution_scope={
                "room_id": snapshot.room_id, "scene_id": snapshot.scene_id,
                "zone_id": snapshot.zone_id, "scene_instance_id": actor_scope.scene_instance_id,
                "scene_revision": actor_scope.scene_revision,
            }, spatial_source_refs=[actor_evidence.event_ref, target_evidence.event_ref],
                spatial_admission_digests=[actor_evidence.admission_digest, target_evidence.admission_digest])
            admission_context = {key: value for key, value in context.items() if key != "spatial_source_refs"}
            for action in _ACTIONS:
                payload = {"actor_ref": actor, "target_ref": target, "action": action,
                           "context": admission_context, "source_revisions": neutral["source_revisions"]}
                digest = "sha256:" + hashlib.sha256(json.dumps(
                    payload, sort_keys=True, separators=(",", ":"),
                ).encode()).hexdigest()
                descriptors.append({
                    "target_ref": raw_target, "target_refs": {"character": raw_target},
                    "target_visibility": "visible", "target_provenance": list(lineage),
                    "supported_intents": [action], "owner_route": "social_spatial_owner",
                    "target_admission_digest": digest, "target_revision_vector": dict(revisions),
                    "social_source_context": context,
                    "source_refs": [*neutral["source_event_ids"], actor_evidence.event_ref,
                                    target_evidence.event_ref, *lineage],
                    "required_conditions": {"visibility": "satisfied", "range": "satisfied",
                                             "authority": "satisfied"},
                    "affordance_result": {"status": "available", "reason": "admitted_social_spatial"},
                })
        return descriptors

    @staticmethod
    def _canonical(actor):
        value = actor if isinstance(actor, str) else ""
        return value if value.startswith("character:") else "character:" + value
