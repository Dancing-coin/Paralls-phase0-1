from __future__ import annotations

from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from time import monotonic

import pytest

from app.character_agent.runtime import runtime_loop
from test_character_agent_activation_handoff import active_dialogue_decision, runtime


def _release_count(instance):
    return sum(event.event_type == "population.activation.released"
               for event in instance._activation_authority.store.read_events())


def test_activation_lease_spans_caller_wait_and_old_finish_cannot_release_new_lock():
    instance = runtime()
    handle, receipt = instance.begin_actor_activation("char_a", active_dialogue_decision(), producer_ts=1)
    assert receipt.committed and not receipt.lock_released
    assert receipt.lock_scope == "asynchronous_turn"
    assert instance.activation_is_current(handle.lock_ref, handle.token)
    assert instance.activation_lock_is_active("char_a")
    assert instance.finish_actor_activation(handle, reason="completed").lock_released
    next_handle, _ = instance.begin_actor_activation("char_a", active_dialogue_decision(), producer_ts=2)
    assert next_handle.token != handle.token
    assert instance.finish_actor_activation(handle, reason="completed").lock_released
    assert _release_count(instance) == 1
    assert instance.activation_is_current(next_handle.lock_ref, next_handle.token)
    forged = replace(next_handle, generation="wrong-generation")
    assert not instance.finish_actor_activation(forged, reason="completed").committed
    assert _release_count(instance) == 1
    assert instance.finish_actor_activation(next_handle, reason="completed").lock_released
    assert _release_count(instance) == 2


def test_expired_lease_rejects_completion_but_can_still_release(monkeypatch):
    now = monotonic()
    monkeypatch.setattr(runtime_loop, "monotonic", lambda: now)
    instance = runtime()
    handle, _ = instance.begin_actor_activation("char_a", active_dialogue_decision(), producer_ts=1,
                                                 deadline_monotonic=now + 1)
    now += 2
    assert not instance.activation_is_current(handle.lock_ref, handle.token)
    assert instance.finish_actor_activation(handle, reason="deadline_expired").lock_released
    assert not instance.activation_lock_is_active("char_a")


def test_busy_admission_does_not_materialize_or_append_again(monkeypatch):
    instance = runtime()
    calls = []
    monkeypatch.setattr(instance, "materialize_pending_seed_memories", lambda *args: calls.append(args))
    handle, _ = instance.begin_actor_activation("char_a", active_dialogue_decision(), producer_ts=1)
    before = instance._activation_authority.store.export_snapshot()
    rejected, receipt = instance.begin_actor_activation("char_a", active_dialogue_decision(), producer_ts=2)
    assert rejected is None and not receipt.committed and receipt.zero_write
    assert len(calls) == 1
    assert instance._activation_authority.store.export_snapshot() == before
    instance.finish_actor_activation(handle, reason="cancelled")


def test_unrelated_actor_lock_revision_does_not_invalidate_lease():
    instance = runtime()
    first, _ = instance.begin_actor_activation("char_a", active_dialogue_decision(), producer_ts=1)
    second, _ = instance.begin_actor_activation("char_b", active_dialogue_decision().model_copy(update={"actor_id": "char_b"}), producer_ts=2)
    assert instance.activation_is_current(first.lock_ref, first.token)
    assert instance.finish_actor_activation(first, reason="completed").lock_released
    assert instance.activation_is_current(second.lock_ref, second.token)
    instance.finish_actor_activation(second, reason="completed")


def test_materialization_exception_releases_and_preserves_original(monkeypatch):
    instance = runtime()
    original_error = OSError("materialization unavailable")
    monkeypatch.setattr(instance, "materialize_pending_seed_memories", lambda *_: (_ for _ in ()).throw(original_error))
    with pytest.raises(OSError) as error:
        instance.begin_actor_activation("char_a", active_dialogue_decision(), producer_ts=1)
    assert error.value is original_error
    assert _release_count(instance) == 1
    assert not instance.activation_lock_is_active("char_a")


def test_failed_release_keeps_cleanup_obligation_and_rejects_late_completion(monkeypatch):
    instance = runtime()
    handle, _ = instance.begin_actor_activation("char_a", active_dialogue_decision(), producer_ts=1)
    original_release = instance._activation_authority.release_lock
    monkeypatch.setattr(instance._activation_authority, "release_lock", lambda **_: (_ for _ in ()).throw(OSError("disk offline")))
    with pytest.raises(OSError):
        instance.finish_actor_activation(handle, reason="cancelled")
    assert not instance.activation_is_current(handle.lock_ref, handle.token)
    assert instance.activation_lock_is_active("char_a")
    assert instance.pending_actor_activations() == (handle,)
    assert instance.begin_actor_activation("char_a", active_dialogue_decision(), producer_ts=2)[0] is None
    monkeypatch.setattr(instance._activation_authority, "release_lock", original_release)
    assert instance.finish_actor_activation(handle, reason="cancelled").lock_released
    assert instance.pending_actor_activations() == ()
    assert _release_count(instance) == 1


def test_reset_releases_all_activations_and_invalidates_old_tokens():
    instance = runtime()
    handle, _ = instance.begin_actor_activation("char_a", active_dialogue_decision(), producer_ts=1)
    instance.reset_actor_activations()
    assert instance.pending_actor_activations() == ()
    assert not instance.activation_is_current(handle.lock_ref, handle.token)
    assert _release_count(instance) == 1
    again, _ = instance.begin_actor_activation("char_a", active_dialogue_decision(), producer_ts=2)
    assert again.generation != handle.generation
    instance.finish_actor_activation(handle, reason="reset")
    assert instance.activation_is_current(again.lock_ref, again.token)
    instance.reset_actor_activations()


@pytest.mark.parametrize("deadline", [float("nan"), float("inf"), -1.0])
def test_invalid_or_expired_admission_is_zero_write(deadline):
    instance = runtime()
    before = instance._activation_authority.store.export_snapshot()
    if deadline > 0 or deadline != deadline:
        with pytest.raises(ValueError):
            instance.begin_actor_activation("char_a", active_dialogue_decision(), producer_ts=1, deadline_monotonic=deadline)
    else:
        handle, receipt = instance.begin_actor_activation("char_a", active_dialogue_decision(), producer_ts=1, deadline_monotonic=deadline)
        assert handle is None and receipt.zero_write
    assert instance._activation_authority.store.export_snapshot() == before


def test_activation_mutation_on_another_thread_is_rejected():
    instance = runtime()
    handle, _ = instance.begin_actor_activation("char_a", active_dialogue_decision(), producer_ts=1)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(instance.finish_actor_activation, handle, reason="completed")
        with pytest.raises(RuntimeError, match="owner thread"):
            future.result()
    assert instance.activation_is_current(handle.lock_ref, handle.token)
    assert _release_count(instance) == 0
    instance.reset_actor_activations()


def test_sync_original_error_survives_release_error_and_retry_remains_possible(monkeypatch):
    instance = runtime()
    original_release = instance._activation_authority.release_lock
    callback_error, cleanup_error = ValueError("callback error"), OSError("release error")
    monkeypatch.setattr(instance._activation_authority, "release_lock", lambda **_: (_ for _ in ()).throw(cleanup_error))
    with pytest.raises(ValueError) as error:
        instance.activate_actor("char_a", active_dialogue_decision(), producer_ts=1,
                                cognition_callback=lambda: (_ for _ in ()).throw(callback_error))
    assert error.value is callback_error and error.value.__cause__ is cleanup_error
    assert len(instance.pending_actor_activations()) == 1
    monkeypatch.setattr(instance._activation_authority, "release_lock", original_release)
    instance.reset_actor_activations()
    assert not instance.pending_actor_activations()
    assert _release_count(instance) == 1


def test_reset_attempts_other_releases_even_when_one_fails(monkeypatch):
    instance = runtime()
    first, _ = instance.begin_actor_activation("char_a", active_dialogue_decision(), producer_ts=1)
    second, _ = instance.begin_actor_activation("char_b", active_dialogue_decision().model_copy(update={"actor_id": "char_b"}), producer_ts=2)
    original = instance._activation_authority.release_lock

    def release(**kwargs):
        if kwargs["lock_ref"] == first.lock_ref:
            raise OSError("first release failed")
        return original(**kwargs)

    monkeypatch.setattr(instance._activation_authority, "release_lock", release)
    with pytest.raises(OSError):
        instance.reset_actor_activations()
    assert instance.pending_actor_activations() == (first,)
    assert not instance.activation_lock_is_active(second.actor_id)
    assert not instance.activation_is_current(first.lock_ref, first.token)
    monkeypatch.setattr(instance._activation_authority, "release_lock", original)
    instance.reset_actor_activations()
    assert _release_count(instance) == 2


def test_activation_receipts_are_bounded_and_evicted_handle_cannot_release_current():
    instance = runtime()
    first = None
    for index in range(35):
        handle, _ = instance.begin_actor_activation("char_a", active_dialogue_decision(), producer_ts=index)
        first = first or handle
        instance.finish_actor_activation(handle, reason="completed")
    assert len(instance._activation_receipts) == 32
    current, _ = instance.begin_actor_activation("char_a", active_dialogue_decision(), producer_ts=36)
    assert not instance.finish_actor_activation(first, reason="completed").committed
    assert instance.activation_is_current(current.lock_ref, current.token)
    assert _release_count(instance) == 35
    instance.reset_actor_activations()
