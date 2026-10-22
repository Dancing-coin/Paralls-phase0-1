"""Read-only, owner-validated Presence evidence for later Soul admission."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from app.population_continuity.presence_runtime import PopulationPresenceAuthority


@dataclass(frozen=True)
class SoulPresenceSource:
    actor_ref: str
    world_ref: str
    incarnation: int
    presence_event_id: str
    activation_event_id: str
    read_revisions: Mapping[str, int]
    source_event_refs: tuple[str, ...]
    last_global_sequence: int


class SoulPresenceSourceReader:
    """Capture current identity evidence; consumers must CAS every read head.

    Presence proves incarnation, not LifeState or Soul permissions. Until a
    Life owner adapter is admitted, only a pinned empty Life stream is usable.
    """

    def __init__(self, *, presence: PopulationPresenceAuthority, life_sources=None):
        if type(presence) is not PopulationPresenceAuthority or presence._sources is None:
            raise ValueError('soul_presence_source_authority')
        self._presence = presence
        self._store = presence.store
        if life_sources is not None and getattr(life_sources, "_store", None) is not self._store:
            raise ValueError('soul_presence_source_life_store')
        self._life_sources = life_sources

    def read(self, *, actor_ref: str, world_ref: str,
             expected_incarnation: int | None = None) -> SoulPresenceSource:
        if (not isinstance(actor_ref, str) or not actor_ref or ':' in actor_ref
                or actor_ref.strip() != actor_ref):
            raise ValueError('soul_presence_source_actor')
        if not isinstance(world_ref, str) or not world_ref or world_ref.strip() != world_ref:
            raise ValueError('soul_presence_source_world')
        if expected_incarnation is not None and (type(expected_incarnation) is not int or expected_incarnation < 1):
            raise ValueError('soul_presence_source_incarnation')
        profile = f'character:{actor_ref}'
        stream = self._presence.stream_id(world_ref)
        head = self._store.get_stream_head(stream)
        active, _ = self._presence._history(world_ref, head=head)
        incarnation = active.get(profile)
        if incarnation is None:
            raise ValueError('soul_presence_source_absent')
        if expected_incarnation is not None and expected_incarnation != incarnation:
            raise ValueError('soul_presence_source_incarnation')
        events = self._store.read_stream(stream, to_revision=head)
        if len(events) != head:
            raise ValueError('soul_presence_source_history')
        spawn = None
        for revision, event in enumerate(events, 1):
            if event.stream_revision != revision:
                raise ValueError('soul_presence_source_history')
            request, operation = self._presence._validated_event(event, world_ref)
            if request.character_ref == profile and operation == 'spawned' and event.payload['incarnation'] == incarnation:
                spawn = event
        if spawn is None:
            raise ValueError('soul_presence_source_history')
        activation = self._presence._sources.read(spawn.payload['source_activation_event_id'],
            world_ref=world_ref, profile_ref=profile)
        life_stream = f'gameplay:character:life:{profile}'
        life_head = self._store.get_stream_head(life_stream)
        life_refs: tuple[str, ...] = ()
        if life_head:
            if self._life_sources is None:
                raise ValueError('soul_presence_source_life_unavailable')
            life = self._life_sources.read(actor_ref=actor_ref, world_ref=world_ref,
                                           incarnation=incarnation, boundary_revision=life_head)
            if life.state != 'alive':
                raise ValueError('soul_presence_source_life_ineligible')
            life_refs = life.source_event_refs
        refs = tuple(dict.fromkeys((*activation.source_event_refs, *(event.event_id for event in events), *life_refs)))
        life_read_revisions = (dict(life.read_revisions) if life_head and self._life_sources is not None
                               else {life_stream: 0})
        return SoulPresenceSource(actor_ref, world_ref, incarnation, spawn.event_id, activation.event_id,
            MappingProxyType(dict(activation.read_revisions) | {stream: head} | life_read_revisions), refs,
            max(activation.last_global_sequence, *(event.global_sequence for event in events),
                *(self._store.get_event(ref).global_sequence for ref in life_refs)))
