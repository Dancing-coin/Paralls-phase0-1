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
            return SimpleNamespace(lock_released=True)

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


def test_driver_accepts_goal_proposal_result_before_owner_commit():
    from app.character_agent.services.cognition_driver import CharacterCognitionDriver

    progress = SimpleNamespace(status="provider_pending", stage="goal_proposal", frame={})
    calls = []

    class Admissions:
        def read_progress(self, _key):
            return progress

    class Coordinator:
        admissions = Admissions()

        def accept_goal_proposal_result(self, key, *, activation, now, output):
            calls.append((key, output))

    driver = CharacterCognitionDriver(
        coordinator=Coordinator(), owner_call=lambda fn: fn(), slots=SimpleNamespace(),
        begin_activation=lambda _entry: object(), on_completed=lambda *_args: None,
    )
    driver._handles["child:goal"] = object()
    future = SimpleNamespace(result=lambda: {"active_goal_frame": {"primary_goal": "open"}, "evidence_refs": []})
    driver._accept("child:goal", "goal_proposal", future)

    assert calls == [("child:goal", {"active_goal_frame": {"primary_goal": "open"}, "evidence_refs": []})]
