"""Social source admission; no live model or Godot claims."""
from app.gameplay.canonical_combat_authority import CanonicalCombatTargetReader
from app.gameplay.event_store import DurableGameplayEventStore
from test_combat_settlement_threat_consumer import _sources


def test_neutral_participants_resolve_real_presence_life_without_faction_reads(tmp_path, monkeypatch):
    store = DurableGameplayEventStore(tmp_path / "world.db")
    sources = _sources(store)
    original = store.read_stream

    def read(stream, *args, **kwargs):
        assert not stream.startswith("faction:"), "social source must not read faction"
        return original(stream, *args, **kwargs)

    monkeypatch.setattr(store, "read_stream", read)
    before = store.get_last_global_sequence()
    result = CanonicalCombatTargetReader(store=store).resolve_current_participants(
        actor_ref="character:char_a", target_ref="character:char_b",
        world_ref=sources.world_ref, timeline_ref=sources.timeline_ref,
        eligible_life_states=frozenset({"alive"}),
    )
    assert result is not None and result["eligible"]
    assert result["source_event_ids"] == [*sources.presence_source_event_ids, *sources.life_state_source_event_ids]
    assert not any(stream.startswith("faction:") for stream in result["source_revisions"])
    assert store.get_last_global_sequence() == before
    store.close()
