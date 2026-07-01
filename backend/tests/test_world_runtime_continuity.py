from app.world_runtime.continuity import RuntimeContinuityState


def test_runtime_continuity_state_tracks_ongoing_contact_and_interrupted_action() -> None:
    state = RuntimeContinuityState(
        actor_id="char_a",
        ongoing_contact_target="char_c",
        interrupted_action="approach",
        last_transition_kind="paused",
    )

    assert state.actor_id == "char_a"
    assert state.ongoing_contact_target == "char_c"
    assert state.interrupted_action == "approach"
    assert state.last_transition_kind == "paused"
