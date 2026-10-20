"""Canonical target sources for private perception, without action admission."""
import hashlib
import json

from app.gameplay.canonical_combat_authority import CanonicalCombatTargetReader
from app.gameplay.event_store import GameplayEventStoreSnapshotError


class CharacterCombatTargetCatalog:
    def __init__(self, *, store, presence, timeline):
        if presence.store is not store:
            raise ValueError("combat_target_store_mismatch")
        self._store, self._presence, self._timeline = store, presence, timeline
        self._reader = CanonicalCombatTargetReader(store=store)

    def project_character_targets(self, snapshot):
        timeline = self._timeline()
        if timeline is None or timeline.status != "active":
            return []
        world, timeline_ref = timeline.world_scope_ref, timeline.timeline_id
        actor_ref = self._canonical(snapshot.actor_id)
        try:
            active = self._presence.projection(world)
            if actor_ref not in active:
                return []
            presence_rows = self._store.read_stream(f"presence:{world}")
            faction_rows = self._store.read_stream(f"faction:{world}:{timeline_ref}")
            descriptors = []
            for target in sorted(set(snapshot.visible_target_refs)):
                target_ref = self._canonical(target)
                if target_ref == actor_ref or target_ref not in active:
                    continue
                actors = (actor_ref, target_ref)
                presences = [next(row for row in reversed(presence_rows)
                    if row.payload.get("character_ref") == actor) for actor in actors]
                lives = [max((row for suffix in {actor, actor.removeprefix("character:")}
                    for row in self._store.read_stream(f"gameplay:character:life:{suffix}")
                    if row.payload.get("actor_ref") == actor), key=lambda row: row.global_sequence)
                    for actor in actors]
                factions = [row for row in faction_rows if row.payload.get("actor_ref") == actor_ref
                            and row.payload.get("target_ref") == target_ref]
                if not factions:
                    continue
                decision = self._reader.source_eligibility(actor_ref=actor_ref, target_ref=target_ref,
                    presence_event_ids=tuple(row.event_id for row in presences),
                    life_event_ids=tuple(row.event_id for row in lives), faction_event_id=factions[-1].event_id,
                    world_ref=world, timeline_ref=timeline_ref,
                    actor_incarnation_ref=f"{actor_ref}@{active[actor_ref]['incarnation']}",
                    target_incarnation_ref=f"{target_ref}@{active[target_ref]['incarnation']}")
                if not decision["eligible"]:
                    continue
                pins = dict(decision, actor_ref=actor_ref, target_ref=target_ref,
                    scope={name: getattr(snapshot, name) for name in ("room_id", "scene_id", "zone_id")})
                digest = "sha256:" + hashlib.sha256(json.dumps(
                    pins, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                descriptors.append(dict(target_ref=target, target_refs={"character": target},
                    target_visibility="visible", supported_intents=[], owner_route="",
                    target_admission_digest=digest, target_revision_vector=decision["source_revisions"],
                    combat_source_context=decision,
                    source_refs=[f"combat-source:{ref}" for ref in decision["source_event_ids"]],
                    required_conditions={"visibility": "satisfied", "range": "unknown", "authority": "unknown"},
                    affordance_result={"status": "unavailable", "reason": "combat_action_admission_pending"}))
            return descriptors
        except (KeyError, StopIteration, TypeError, ValueError, GameplayEventStoreSnapshotError):
            return []

    @staticmethod
    def _canonical(actor):
        return actor if actor.startswith("character:") else "character:" + actor
