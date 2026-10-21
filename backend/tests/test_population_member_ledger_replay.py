from __future__ import annotations

import pytest

from app.population_continuity.member_ledger import pending_member_results
from test_population_member_ledger import ACTORS, ledger_case


def test_full_and_real_checkpoint_tail_preserve_pending_results(ledger_case):
    first = ledger_case.commit_actor_result(ACTORS[0], "result:first")
    checkpoint = ledger_case.world.create_member_ledger_checkpoint("cohort:test")
    second = ledger_case.commit_actor_result(ACTORS[1], "result:second")
    assert ledger_case.consume_for(ACTORS[0], first).committed
    ledger_case.restart()
    full = ledger_case.read()
    tail = ledger_case.read(checkpoint=checkpoint)
    assert full == tail
    assert pending_member_results(full, actor_ref=ACTORS[0]) == ()
    assert pending_member_results(full, actor_ref=ACTORS[1]) == (second,)
    assert full.group_cursor == 0


def test_owner_commit_before_core_acceptance_survives_restart(ledger_case):
    ref = ledger_case.commit_actor_result(ACTORS[0], "result:owner-first")
    owner_head = ledger_case.store.get_stream_head("gameplay:organization:org:test")
    ledger_case.restart()
    assert pending_member_results(ledger_case.read(), actor_ref=ACTORS[0]) == (ref,)
    assert ledger_case.core.get_continuity_revision("char_a") == 0
    assert ledger_case.consume_for(ACTORS[0], ref).committed
    assert ledger_case.store.get_stream_head("gameplay:organization:org:test") == owner_head
    assert ledger_case.core.get_continuity_revision("char_a") == 1


def test_core_commit_before_marker_append_survives_restart_without_reapply(ledger_case, monkeypatch):
    ref = ledger_case.commit_actor_result(ACTORS[0], "result:core-first")
    command = ledger_case.command(ACTORS[0], ref)
    actual = ledger_case.core.apply_character_continuity_command(command)
    assert actual.status == "committed"
    owner_head = ledger_case.store.get_stream_head("gameplay:organization:org:test")
    original = ledger_case.store.append_batch

    def crash(batch):
        if any(event.event_type == "population.world.member_ledger_recorded@1" for event in batch.events):
            raise RuntimeError("crash_before_consumption_marker")
        return original(batch)

    with monkeypatch.context() as patch:
        patch.setattr(ledger_case.store, "append_batch", crash)
        with pytest.raises(RuntimeError, match="crash_before_consumption_marker"):
            ledger_case.consume_for(ACTORS[0], ref, apply=False)
    ledger_case.restart()
    assert ledger_case.core.get_continuity_revision("char_a") == 1
    assert ledger_case.consume_for(ACTORS[0], ref, apply=False).committed
    assert ledger_case.core.get_continuity_revision("char_a") == 1
    assert ledger_case.store.get_stream_head("gameplay:organization:org:test") == owner_head
    assert pending_member_results(ledger_case.read(), actor_ref=ACTORS[0]) == ()
    assert ledger_case.core.get_character_continuity_receipt("char_a", idempotency_key=command.idempotency_key) == actual


def test_duplicate_consumption_and_changed_idempotency_are_distinguished(ledger_case):
    ref = ledger_case.commit_actor_result(ACTORS[0], "result:first")
    assert ledger_case.consume_for(ACTORS[0], ref).committed
    before = ledger_case.store.get_last_global_sequence()
    duplicate = ledger_case.consume_for(ACTORS[0], ref, apply=False)
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert ledger_case.store.get_last_global_sequence() == before
    with pytest.raises(ValueError, match="member_idempotency_conflict"):
        ledger_case.world.consume_member_result(cohort_ref="cohort:test", actor_ref=ACTORS[1], result_ref=ref,
            continuity_runtime=ledger_case.core, continuity_idempotency_key=f"apply:{ref}",
            expected_revision=ledger_case.revision(), idempotency_key=f"consume:{ref}")
    assert ledger_case.store.get_last_global_sequence() == before


def test_committed_marker_survives_missing_ack_without_duplicate_effect(ledger_case, monkeypatch):
    ref = ledger_case.commit_actor_result(ACTORS[0], "result:after-marker")
    command = ledger_case.command(ACTORS[0], ref)
    assert ledger_case.core.apply_character_continuity_command(command).status == "committed"
    original = ledger_case.store.append_batch

    def crash_after_commit(batch):
        result = original(batch)
        if result.committed and any(event.event_type == "population.world.member_ledger_recorded@1" for event in batch.events):
            raise RuntimeError("crash_after_consumption_marker")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(ledger_case.store, "append_batch", crash_after_commit)
        with pytest.raises(RuntimeError, match="crash_after_consumption_marker"):
            ledger_case.consume_for(ACTORS[0], ref, apply=False)
    ledger_case.restart()
    before = ledger_case.store.get_last_global_sequence()
    duplicate = ledger_case.consume_for(ACTORS[0], ref, apply=False)
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert ledger_case.store.get_last_global_sequence() == before
    assert ledger_case.core.get_continuity_revision("char_a") == 1


@pytest.mark.parametrize("mutation", ["hash", "scope", "cursor"])
def test_checkpoint_corruption_and_wrong_scope_fail_closed(ledger_case, mutation):
    ledger_case.commit_actor_result(ACTORS[0], "result:first")
    checkpoint = ledger_case.world.create_member_ledger_checkpoint("cohort:test")
    updates = {"hash": {"projection_hash": "sha256:corrupted"},
        "scope": {"projector_id": "other-cohort"}, "cursor": {"last_global_sequence": 10000}}
    before = ledger_case.store.get_last_global_sequence()
    with pytest.raises(ValueError, match="member_checkpoint_invalid"):
        ledger_case.read(checkpoint=checkpoint.model_copy(update=updates[mutation]))
    assert ledger_case.store.get_last_global_sequence() == before
