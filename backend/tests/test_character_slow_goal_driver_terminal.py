from types import SimpleNamespace


def test_driver_does_not_reactivate_terminal_cancelled_goal_proposal():
    from app.character_agent.services.cognition_driver import CharacterCognitionDriver

    entry = SimpleNamespace(child_key="child:goal", actor_id="char_a", source_kind="goal_proposal_trigger", expires_at=30.0)
    progress = SimpleNamespace(status="cancelled", stage="goal_proposal", frame={})
    activations = []

    class Admissions:
        def read(self, key):
            assert key == entry.child_key
            return entry

        def read_progress(self, key):
            assert key == entry.child_key
            return progress

    class Runtime:
        def finish_actor_activation(self, *_args, **_kwargs):
            raise AssertionError("terminal proposal must not acquire an activation")

    class Coordinator:
        admissions = Admissions()
        runtime = Runtime()

    driver = CharacterCognitionDriver(
        coordinator=Coordinator(),
        owner_call=lambda fn: fn(),
        slots=SimpleNamespace(),
        begin_activation=lambda _entry: activations.append(True) or object(),
        on_completed=lambda *_args: (_ for _ in ()).throw(AssertionError("cancelled is not completed")),
    )

    assert driver._prepare(entry.child_key) is None
    assert activations == []


def test_driver_drops_late_result_for_terminal_failed_goal_proposal_without_activation():
    from app.character_agent.services.cognition_driver import CharacterCognitionDriver

    entry = SimpleNamespace(child_key="child:goal", actor_id="char_a", source_kind="goal_proposal_trigger", expires_at=30.0)
    progress = SimpleNamespace(status="failed", stage="goal_proposal", frame={})
    activations = []

    class Admissions:
        def read(self, key):
            assert key == entry.child_key
            return entry

        def read_progress(self, key):
            assert key == entry.child_key
            return progress

    class Runtime:
        def finish_actor_activation(self, *_args, **_kwargs):
            raise AssertionError("failed proposal must not acquire an activation")

    class Coordinator:
        admissions = Admissions()
        runtime = Runtime()

    driver = CharacterCognitionDriver(
        coordinator=Coordinator(),
        owner_call=lambda fn: fn(),
        slots=SimpleNamespace(),
        begin_activation=lambda _entry: activations.append(True) or object(),
        on_completed=lambda *_args: (_ for _ in ()).throw(AssertionError("failed is not completed")),
    )
    future = SimpleNamespace(result=lambda: {"active_goal_frame": {"primary_goal": "late"}, "evidence_refs": []})
    driver._active[entry.child_key] = (
        "goal_proposal", future, SimpleNamespace(close=lambda: None), None
    )

    assert driver._accept(entry.child_key, "goal_proposal", future) is True
    assert activations == []
