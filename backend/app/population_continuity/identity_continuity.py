"""Canonical presence identity read owner (本次设计并实现).

Identity continuity is derived only from Population Presence events and the
canonical LifeState stream. It never promotes private memory or health to a
world fact and never emits resurrection events.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.gameplay.event_store import GameplayEventStore
from app.population_continuity.presence_runtime import PopulationPresenceAuthority


@dataclass(frozen=True)
class IdentityContinuityReceipt:
    character_ref: str
    world_ref: str
    incarnation: int | None
    status: str
    source_event_refs: tuple[str, ...]
    source_revision_vector: dict[str, int]
    view_digest: str


class PresenceIdentityOwner:
    """Read owner for stable character identity and per-spawn incarnations."""

    def __init__(self, *, store: GameplayEventStore):
        self.store = store

    def read(self, *, world_ref: str, character_ref: str) -> IdentityContinuityReceipt:
        stream = PopulationPresenceAuthority.stream_id(world_ref)
        life_stream = f"gameplay:character:life:{character_ref}"
        events = [e for e in self.store.read_stream(stream)
                  if e.payload.get("character_ref") == character_ref]
        # Schema-2 deaths are emitted only by the confirmed case-death caller.
        # Schema-1 life events remain readable for historical replay, but only
        # when their original life-state authority transaction is intact.
        dead = False
        for event in self.store.read_stream(life_stream):
            if event.payload.get("to_state") != "dead":
                continue
            transaction = self.store.get_transaction(event.transaction_id)
            if transaction is None or event not in transaction.events:
                continue
            principal = transaction.idempotency_record.principal_ref
            if event.schema_version >= 2 and principal == "authority:character:life-state":
                dead = True
                break
            if event.schema_version == 1 and principal == "authority:character:life-state":
                # Legacy receipts are accepted as historical facts only; no
                # new caller may create this form.
                dead = True
                break
        active = None
        for event in events:
            if event.event_type == "population.presence.spawned":
                active = int(event.payload["incarnation"])
            elif event.event_type == "population.presence.despawned" and active == event.payload.get("incarnation"):
                active = None
        status = "dead" if dead else ("present" if active is not None else "absent")
        refs = tuple(event.event_id for event in events)
        revisions = {stream: self.store.get_stream_head(stream), life_stream: self.store.get_stream_head(life_stream)}
        payload = {"character_ref": character_ref, "world_ref": world_ref,
                   "incarnation": active, "status": status, "source_event_refs": refs,
                   "source_revision_vector": revisions}
        digest = "sha256:" + hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return IdentityContinuityReceipt(character_ref, world_ref, active, status, refs, revisions, digest)


__all__ = ["IdentityContinuityReceipt", "PresenceIdentityOwner"]
