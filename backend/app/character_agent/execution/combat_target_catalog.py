"""Canonical target sources for private perception, without action admission."""
import hashlib
import json

from app.gameplay.canonical_combat_authority import CanonicalCombatTargetReader
from app.gameplay.event_store import GameplayEventStoreSnapshotError


class CharacterCombatTargetCatalog:
    """Perceive hostile actors the canonical sources admit as current and visible.

    Production deliberately grants no action: combat admission is not
    implemented, so every descriptor is marked ``perception_only``.  That
    marker is what keeps the target visible in the candidate universe as an
    explicitly pruned record instead of an empty catalog that reads as "nothing
    is here".
    """

    def __init__(self, *, store, presence, timeline):
        if presence.store is not store:
            raise ValueError("combat_target_store_mismatch")
        self._store, self._presence, self._timeline = store, presence, timeline
        self._reader = CanonicalCombatTargetReader(store=store)
        self.last_rejected: list[dict[str, object]] = []

    def project_character_targets(self, snapshot):
        self.last_rejected = []
        timeline = self._timeline()
        if timeline is None or timeline.status != "active":
            return []
        world, timeline_ref = timeline.world_scope_ref, timeline.timeline_id
        actor_ref = self._canonical(snapshot.actor_id)
        try:
            active = self._presence.projection(world)
            if actor_ref not in active:
                return []
            presence_rows = self._store.read_stream(self._presence_stream(world))
            faction_rows = self._store.read_stream(self._faction_stream(world, timeline_ref))
        except (KeyError, TypeError, ValueError, GameplayEventStoreSnapshotError) as exc:
            # Scope-level source failure removes the whole catalog, but never
            # without a reason reaching the caller.
            self.last_rejected.append({"scope": "combat_sources", "reason": type(exc).__name__})
            return []
        descriptors = []
        for target in sorted(set(snapshot.visible_target_refs)):
            # One target must not be able to erase the others: a missing
            # presence, life or faction row is a per-target failure.
            try:
                descriptor = self._descriptor_for(
                    snapshot=snapshot, target=target, active=active,
                    presence_rows=presence_rows, faction_rows=faction_rows,
                    world=world, timeline_ref=timeline_ref, actor_ref=actor_ref,
                )
            except (KeyError, StopIteration, TypeError, ValueError, GameplayEventStoreSnapshotError) as exc:
                self.last_rejected.append({"target": str(target), "reason": type(exc).__name__})
                continue
            if descriptor is not None:
                descriptors.append(descriptor)
        return descriptors

    def _descriptor_for(
        self,
        *,
        snapshot,
        target,
        active,
        presence_rows,
        faction_rows,
        world,
        timeline_ref,
        actor_ref,
    ):
        target_ref = self._canonical(target)
        if target_ref == actor_ref or target_ref not in active:
            return None
        actors = (actor_ref, target_ref)
        presences = [
            self._latest(presence_rows, "character_ref", actor) for actor in actors
        ]
        lives = [self._latest_life(actor) for actor in actors]
        factions = [
            row for row in faction_rows
            if row.payload.get("actor_ref") == actor_ref
            and row.payload.get("target_ref") == target_ref
        ]
        if not factions:
            return None
        decision = self._reader.source_eligibility(
            actor_ref=actor_ref, target_ref=target_ref,
            presence_event_ids=tuple(row.event_id for row in presences),
            life_event_ids=tuple(row.event_id for row in lives),
            faction_event_id=factions[-1].event_id,
            world_ref=world, timeline_ref=timeline_ref,
            actor_incarnation_ref=f"{actor_ref}@{active[actor_ref]['incarnation']}",
            target_incarnation_ref=f"{target_ref}@{active[target_ref]['incarnation']}",
        )
        if not decision["eligible"]:
            return None
        pins = dict(
            decision, actor_ref=actor_ref, target_ref=target_ref,
            scope={name: getattr(snapshot, name) for name in ("room_id", "scene_id", "zone_id")},
        )
        digest = "sha256:" + hashlib.sha256(
            json.dumps(pins, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return dict(
            target_ref=target, target_refs={"character": target},
            target_visibility="visible", supported_intents=[], perception_only=True,
            owner_route="",
            target_admission_digest=digest,
            target_revision_vector=decision["source_revisions"],
            combat_source_context=decision,
            source_refs=[f"combat-source:{ref}" for ref in decision["source_event_ids"]],
            required_conditions={"visibility": "satisfied", "range": "unknown", "authority": "unknown"},
            affordance_result={"status": "unavailable", "reason": "combat_action_admission_pending"},
        )

    def _latest(self, rows, field, actor):
        """Match the actor ref in either spelling, newest first.

        Presence and life rows have historically been written both with and
        without the ``character:`` prefix.  Reading only one spelling turns a
        naming difference into a vanished target.
        """
        names = {actor, actor.removeprefix("character:")}
        return next(row for row in reversed(rows) if row.payload.get(field) in names)

    def _latest_life(self, actor):
        rows = [
            row for suffix in {actor, actor.removeprefix("character:")}
            for row in self._store.read_stream(self._life_stream(suffix))
            if row.payload.get("actor_ref") == actor
        ]
        return max(rows, key=lambda row: row.global_sequence)

    @staticmethod
    def _presence_stream(world):
        return f"presence:{world}"

    @staticmethod
    def _faction_stream(world, timeline_ref):
        return f"faction:{world}:{timeline_ref}"

    @staticmethod
    def _life_stream(actor):
        return f"gameplay:character:life:{actor}"

    @staticmethod
    def _canonical(actor):
        return actor if actor.startswith("character:") else "character:" + actor
