from __future__ import annotations

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.frost_farm_runtime import FrostFarmAuthority
from app.gameplay.replay import GameplayProjectionReplay

from test_frost_farm_settlement import _command, _effect


def test_frost_result_replays_with_checkpoint_and_scope_projection() -> None:
    store = GameplayEventStore()
    FrostFarmAuthority.settle(_effect(), command=_command(), store=store)
    events = store.read_events()
    replay = GameplayProjectionReplay(projector_id="projection:frost", projector_version="v1")
    full = replay.full_replay(events)
    checkpoint = replay.create_checkpoint(events)
    tail = replay.checkpoint_plus_tail_replay(checkpoint, [])
    assert full.projection_hash == tail.projection_hash
    from app.gameplay.frost_farm_runtime import project_frost_result

    assert project_frost_result(full, scope="public").payload["crop_ref"] == "crop:wheat:1"
    assert "last_payload" not in project_frost_result(full, scope="public").payload
