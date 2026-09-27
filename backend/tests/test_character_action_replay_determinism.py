from __future__ import annotations

from scripts.verification.character_action_replay import CharacterActionReplayTrace


def fixture() -> CharacterActionReplayTrace:
    trace = CharacterActionReplayTrace()
    trace.append(1, {"intent": "walk", "claim": "locomotion"}, {"accepted": True}, {"velocity": [1, 0]}, [{"contact": "wall"}], {"outcome": "committed", "idempotency": "new"})
    trace.append(1, {"intent": "attack", "claim": "right_arm"}, {"accepted": True}, {"action": "slash"}, [{"marker": "contact"}], {"outcome": "duplicate", "idempotency": "replayed"})
    trace.append(2, {"intent": "expired"}, {"accepted": False}, {}, [], {"outcome": "rejected", "recovery": "lease_expired"})
    return trace


def test_replay_logical_digest_is_stable_across_runs() -> None:
    first = fixture().replay()
    second = fixture().replay()
    assert first == second
    assert first["dynamic_rigidbody_bitwise_determinism"] is False
    assert first["authority_digest"]
