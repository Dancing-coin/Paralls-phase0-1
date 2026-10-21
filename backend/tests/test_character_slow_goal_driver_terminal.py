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


def test_driver_stales_goal_proposal_through_terminal_owner_receipt():
    from app.character_agent.services.cognition_driver import CharacterCognitionDriver

    entry = SimpleNamespace(child_key="child:goal", actor_id="char_a", source_kind="goal_proposal_trigger", expires_at=30.0)
    progress = SimpleNamespace(status="provider_pending", stage="goal_proposal", frame={}, plan=None, revision=3)
    calls = []
    handle = object()

    class Admissions:
        def read(self, key):
            return entry

        def read_progress(self, key):
            return progress

        def advance_progress(self, **kwargs):
            raise AssertionError("goal stale must use the terminal owner receipt")

    class Runtime:
        def finish_actor_activation(self, _handle, *, reason):
            calls.append(("finish", reason))
            return SimpleNamespace(lock_released=True)

    class Coordinator:
        admissions = Admissions()
        runtime = Runtime()

        def terminate_goal_proposal(self, key, *, activation, now, status, reason):
            calls.append(("terminate", key, activation, status, reason))

    driver = CharacterCognitionDriver(
        coordinator=Coordinator(), owner_call=lambda fn: fn(), slots=SimpleNamespace(),
        begin_activation=lambda _entry: handle, on_completed=lambda *_args: None,
        clock=lambda: 12.0,
    )
    driver._stale(entry.child_key, ValueError("source_changed"))

    assert calls[0][:4] == ("terminate", entry.child_key, handle, "stale")
    assert calls[0][4] == "source_changed"
    assert calls[1] == ("finish", "stale")
