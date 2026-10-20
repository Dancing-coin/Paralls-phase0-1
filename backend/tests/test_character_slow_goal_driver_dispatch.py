from types import SimpleNamespace

import pytest


def test_driver_dispatches_goal_proposal_admission_to_goal_preparation():
    from app.character_agent.services.cognition_driver import CharacterCognitionDriver

    entry = SimpleNamespace(
        child_key="child:goal", actor_id="char_a", source_kind="goal_proposal_trigger",
        expires_at=30.0,
    )
    progress = None
    prepared_progress = SimpleNamespace(stage="goal_proposal", status="provider_pending", request_json="{}", frame={})

    class Admissions:
        def read(self, key):
            assert key == entry.child_key
            return entry

        def read_progress(self, key):
            return progress if progress is not None else prepared_progress if coordinator.prepared else None

        def list_pending(self, **_kwargs):
            return (entry,)

    class Runtime:
        _l3 = SimpleNamespace(_gateway=object())

        def activation_is_current(self, *_args):
            return True

        def finish_actor_activation(self, *_args, **_kwargs):
            finishes.append(_kwargs.get("reason"))
            return SimpleNamespace(lock_released=True)

    finishes = []
    class Coordinator:
        def __init__(self):
            self.admissions = Admissions()
            self.runtime = Runtime()
            self.prepared = 0

        def _entry(self, key, activation, now):
            return entry

        def prepare_goal_proposal(self, key, *, activation, now):
            self.prepared += 1
            return prepared_progress

        def _validate_provider_pin(self, actor_id, frame):
            return None

    coordinator = Coordinator()
    driver = CharacterCognitionDriver(
        coordinator=coordinator,
        owner_call=lambda fn: fn(),
        slots=SimpleNamespace(),
        begin_activation=lambda _entry: object(),
        on_completed=lambda *_args: None,
        clock=lambda: 10.0,
    )
    result = driver._prepare(entry.child_key)

    assert result[0] == "goal_proposal"
    assert result[1] == b"{}"
    assert coordinator.prepared == 1
    assert driver._handles == {}
    assert finishes == ["provider_pending"]


def test_driver_accepts_goal_proposal_result_before_owner_commit():
    from app.character_agent.services.cognition_driver import CharacterCognitionDriver

    progress = SimpleNamespace(status="provider_pending", stage="goal_proposal", frame={})
    calls = []
    entry = SimpleNamespace(child_key="child:goal", actor_id="char_a", source_kind="goal_proposal_trigger")

    class Admissions:
        def read(self, _key):
            return entry

        def read_progress(self, _key):
            return progress

    class Coordinator:
        admissions = Admissions()
        runtime = SimpleNamespace(finish_actor_activation=lambda *_args, **_kwargs: SimpleNamespace(lock_released=True))

        def accept_goal_proposal_result(self, key, *, activation, now, output):
            calls.append((key, output))

    driver = CharacterCognitionDriver(
        coordinator=Coordinator(), owner_call=lambda fn: fn(), slots=SimpleNamespace(),
        begin_activation=lambda _entry: object(), on_completed=lambda *_args: None,
    )
    driver._handles["child:goal"] = object()
    future = SimpleNamespace(result=lambda: {"active_goal_frame": {"primary_goal": "open"}, "evidence_refs": []})
    accepted = driver._accept("child:goal", "goal_proposal", future)

    assert accepted is True
    assert calls == [("child:goal", {"active_goal_frame": {"primary_goal": "open"}, "evidence_refs": []})]


def test_driver_keeps_goal_result_pending_until_actor_activation_is_available():
    from app.character_agent.services.cognition_driver import CharacterCognitionDriver

    entry = SimpleNamespace(child_key="child:goal", actor_id="char_a", source_kind="goal_proposal_trigger")
    progress = SimpleNamespace(status="provider_pending", stage="goal_proposal", frame={})
    activations = iter((None, object()))
    accepted = []

    class Admissions:
        def read(self, _key):
            return entry

        def read_progress(self, _key):
            return progress

    class Coordinator:
        admissions = Admissions()
        runtime = SimpleNamespace(finish_actor_activation=lambda *_args, **_kwargs: SimpleNamespace(lock_released=True))

        def accept_goal_proposal_result(self, key, *, activation, now, output):
            accepted.append((key, output))

        def terminate_goal_proposal(self, *args, **kwargs):
            raise AssertionError("provider output is successful")

    driver = CharacterCognitionDriver(
        coordinator=Coordinator(), owner_call=lambda fn: fn(), slots=SimpleNamespace(),
        begin_activation=lambda _entry: next(activations), on_completed=lambda *_args: None,
    )
    future = SimpleNamespace(result=lambda: {"active_goal_frame": {"primary_goal": "open"}, "evidence_refs": []})
    driver._active["child:goal"] = ("goal_proposal", future, SimpleNamespace(close=lambda: None), None)

    assert driver._accept("child:goal", "goal_proposal", future) is False
    assert accepted == []
    assert driver._accept("child:goal", "goal_proposal", future) is True
    assert accepted == [("child:goal", {"active_goal_frame": {"primary_goal": "open"}, "evidence_refs": []})]


def test_driver_terminates_failed_goal_proposal_without_fast_loop_fallback():
    from app.character_agent.services.cognition_driver import CharacterCognitionDriver

    entry = SimpleNamespace(child_key="child:goal", actor_id="char_a", source_kind="goal_proposal_trigger")
    progress = SimpleNamespace(status="provider_pending", stage="goal_proposal", frame={})
    terminal = []

    class Admissions:
        def read(self, _key):
            return entry

        def read_progress(self, _key):
            return progress

    class Coordinator:
        admissions = Admissions()
        runtime = SimpleNamespace(finish_actor_activation=lambda *_args, **_kwargs: SimpleNamespace(lock_released=True))

        def terminate_goal_proposal(self, key, *, activation, now, status, reason):
            terminal.append((key, status, reason))

        def accept_provider_error(self, **_kwargs):
            raise AssertionError("slow goal failure must not enter L3 fallback")

    driver = CharacterCognitionDriver(
        coordinator=Coordinator(), owner_call=lambda fn: fn(), slots=SimpleNamespace(),
        begin_activation=lambda _entry: object(), on_completed=lambda *_args: None,
    )
    driver._active["child:goal"] = ("goal_proposal", SimpleNamespace(result=lambda: (_ for _ in ()).throw(RuntimeError("offline"))),
        SimpleNamespace(close=lambda: None), None)

    assert driver._accept("child:goal", "goal_proposal", driver._active["child:goal"][1]) is True
    assert terminal[0][0:2] == ("child:goal", "failed")
    assert "RuntimeError" in terminal[0][2]
