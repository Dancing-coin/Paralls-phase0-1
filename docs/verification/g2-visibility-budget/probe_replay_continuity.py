"""Show why a scoped replay result is not proof of a complete global tail."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))
from app.gameplay.models import GameplayEvent
from app.gameplay.replay import GameplayProjectionReplay


def main():
    events = [GameplayEvent(event_id=f"e{i}", event_type="test", schema_version=1,
        stream_id=f"stream:{i}", stream_revision=1, global_sequence=i,
        transaction_id="tx", command_id="cmd", causation_id="cmd", correlation_id="cmd",
        visibility_policy="authority_only", payload={}) for i in (1, 2, 3)]
    replay = GameplayProjectionReplay(projector_id="probe", projector_version="1")
    full = replay.full_replay(events)
    missing = replay.continue_replay(replay.full_replay(events[:1]), events[2:])
    assert full.succeeded and missing.succeeded
    assert full.applied_event_ids == ["e1", "e2", "e3"]
    assert missing.applied_event_ids == ["e1", "e3"]
    assert full.last_global_sequence == missing.last_global_sequence == 3
    assert full.projection_hash != missing.projection_hash
    print("full: success, cursor 3, events e1/e2/e3")
    print("missing: success, cursor 3, events e1/e3, different hash")


if __name__ == "__main__":
    main()
