from app.population_continuity.fair_focus import FairFocusQueue, FocusCandidate


def test_starvation_credit_read_interface_keeps_b0_private():
    from app.population_continuity.hot_state import get_starvation_credit_for_siming
    row = {"starvation_credit": 0.5, "fatigue": 0.3}
    assert get_starvation_credit_for_siming("actor_a", row) == 0.5
    assert get_starvation_credit_for_siming("actor_b", {}) == 0.0
    assert row == {"starvation_credit": 0.5, "fatigue": 0.3}


def test_queue_uses_optional_reader_once_and_spends_only_local_credit():
    rows = {"actor_a": {"starvation_credit": 0.5}, "actor_b": {"starvation_credit": 0.9}}
    calls = []
    def read(actor):
        calls.append(actor)
        return rows[actor]
    queue = FairFocusQueue(hot_state_reader=read)
    candidates = [FocusCandidate(actor_ref=actor, source="fairness_seed") for actor in rows]
    assert queue.select(candidates, limit=1).selected[0].actor_ref == "actor_b"
    queue.observe_service(["actor_b"])
    assert queue.credit_for("actor_b") == 0.0
    assert queue.select(candidates, limit=1).selected[0].actor_ref == "actor_a"
    assert sorted(calls) == ["actor_a", "actor_b"]
    assert rows["actor_b"]["starvation_credit"] == 0.9


def test_default_queue_does_not_read_or_depend_on_b0():
    queue = FairFocusQueue()
    queue.accrue(["actor_a"])
    assert queue.credit_for("actor_a") == 0.1
