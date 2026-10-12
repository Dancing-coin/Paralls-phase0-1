from __future__ import annotations

import pytest

from app.character_agent.models.simulation_seed import CharacterContinuityCommand
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.gameplay.event_schema_registry import EventSchemaRegistration
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.handoff import prepare_intersection
from app.population_continuity.models import PendingChange
from app.population_continuity.world import WorldContinuityRuntime
from test_population_member_ledger import ACTORS, LedgerCase
from test_character_simulation_frame import frame


class HandoffCase(LedgerCase):
    def __init__(self, root):
        super().__init__(root)
        for name in ("locked", "released", "pending_recorded", "requeued"):
            self.schemas.register(EventSchemaRegistration(f"population.activation.{name}", 1, f"activation:{name}:1"))
        self.mode = self.mode.model_copy(update={"world_ref": "world:default"})
        self.world = WorldContinuityRuntime(store=self.store, mode=self.mode, roster=self.roster)
        assert self.world.register_member_ledger(self.initial, continuity_runtime=self.core,
            idempotency_key="register").committed
        self.authority = ProfileActivationAuthority(registry=self.core._profile_registry, store=self.store)
        self.core.set_activation_authority(self.authority)

    def take_lock(self, actor=ACTORS[0]):
        receipt = self.authority.lock(world_ref="world:default", profile_ref=actor,
            expected_revision=self.store.get_stream_head("population:world:default"))
        assert receipt.committed
        return self.authority.active_lock(world_ref="world:default", profile_ref=actor)

    def legacy_command(self, *, key="old-b0"):
        return CharacterContinuityCommand(command_id=key, actor_ref=ACTORS[0],
            expected_character_revision=self.core.get_continuity_revision("char_a"),
            from_tick=0, to_tick=1, simulation_tick_cursor=1,
            source_revision_vector={"world:default": 1},
            state_delta={"presentation_seed": {"task": "照护义务保持"}},
            policy_revision="policy:character-continuity:v1", idempotency_key=key)

    def release(self, lock):
        return self.authority.release_lock(lock_ref=lock.lock_ref,
            expected_revision=self.store.get_stream_head("population:world:default"))

    def restart(self):
        super().restart()
        self.authority = ProfileActivationAuthority(registry=self.core._profile_registry, store=self.store)
        self.core.set_activation_authority(self.authority)


@pytest.fixture
def handoff_case(tmp_path):
    case = HandoffCase(tmp_path)
    try:
        yield case
    finally:
        case.close()


def test_old_uncredentialed_b0_cannot_commit_while_handoff_lock_is_held(handoff_case):
    old = handoff_case.legacy_command()
    identity = handoff_case.core.character_identity_digest("char_a")
    handoff_case.take_lock()
    before = handoff_case.core.get_session_timeline("char_a")
    receipt = handoff_case.core.apply_character_continuity_command(old)
    assert receipt.status == "rejected" and receipt.refusal_reason == "handoff_lock_stale"
    assert handoff_case.core.get_session_timeline("char_a") == before
    assert handoff_case.core.get_continuity_revision("char_a") == 0
    assert handoff_case.core.character_identity_digest("char_a") == identity


def test_an_active_lock_cannot_be_replaced_by_a_second_generation(handoff_case):
    first = handoff_case.take_lock()
    before = handoff_case.store.get_stream_head("population:world:default")
    second = handoff_case.authority.lock(world_ref="world:default", profile_ref=ACTORS[0],
        expected_revision=before)
    assert not second.committed and second.zero_write
    assert second.stop_reason == "activation_lock_active"
    assert handoff_case.store.get_stream_head("population:world:default") == before
    assert handoff_case.authority.active_lock(world_ref="world:default", profile_ref=ACTORS[0]) == first


def test_committed_legacy_replay_remains_valid_while_locked(handoff_case):
    old = handoff_case.legacy_command()
    original = handoff_case.core.apply_character_continuity_command(old)
    assert original.status == "committed"
    handoff_case.take_lock()
    before = handoff_case.core.get_session_timeline("char_a")
    replay = handoff_case.core.apply_character_continuity_command(old)
    assert replay.status == "idempotent_replay" and replay.receipt_ref == original.receipt_ref
    assert handoff_case.core.get_session_timeline("char_a") == before


def test_restart_keeps_lock_and_refuses_old_writer_until_release(handoff_case):
    old = handoff_case.legacy_command()
    lock = handoff_case.take_lock()
    handoff_case.restart()
    assert handoff_case.authority.active_lock(world_ref="world:default", profile_ref=ACTORS[0]) == lock
    assert handoff_case.core.apply_character_continuity_command(old).status == "rejected"
    assert handoff_case.release(lock).committed
    handoff_case.restart()
    assert handoff_case.authority.active_lock(world_ref="world:default", profile_ref=ACTORS[0]) is None
    assert handoff_case.authority.projection("world:default")[ACTORS[0]]["status"] == "requeued"
    assert handoff_case.core.get_continuity_revision("char_a") == 0


def test_pending_obligation_is_recovered_and_released_once(handoff_case):
    lock = handoff_case.take_lock()
    pending = PendingChange(change_ref="pending:care", lock_ref=lock.lock_ref,
        profile_ref=ACTORS[0], expected_revision=lock.held_revision,
        payload={"kind": "survival_state_expiry", "plan_digest": "sha256:pending",
                 "obligation_id": "obligation:survival:state:character:char_a:state:cold", "policy_revision": "1", "expected_survival_revision": 0},
        privacy_scope="project")
    assert handoff_case.authority.record_pending(pending).committed
    handoff_case.restart()
    duplicate = handoff_case.authority.record_pending(pending)
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert handoff_case.release(lock).committed
    view = handoff_case.authority.pending_view_for(world_ref="world:default", reader_scope="authority:activation")
    assert view[pending.change_ref]["status"] == "released"
    released = handoff_case.store.read_stream("population:world:default", event_type="population.activation.released")
    assert released[-1].payload["pending_change_refs"] == [pending.change_ref]


def test_exclusive_startup_releases_only_interrupted_core_world_locks(handoff_case, monkeypatch, tmp_path):
    from app import main
    from app.world_runtime.storage_lease import RuntimeStorageLease

    own = handoff_case.take_lock()
    handoff_case.take_lock(ACTORS[1])
    foreign = handoff_case.authority.lock(world_ref="world:other", profile_ref=ACTORS[0], expected_revision=0)
    assert foreign.committed
    change = PendingChange(change_ref="pending:restart", lock_ref=own.lock_ref, profile_ref=ACTORS[0],
        expected_revision=own.held_revision, privacy_scope="project", payload={
            "kind": "survival_state_expiry", "plan_digest": "sha256:restart",
            "obligation_id": "obligation:survival:state:character:char_a:state:cold",
            "policy_revision": "1", "expected_survival_revision": 0})
    assert handoff_case.authority.record_pending(change).committed
    before = handoff_case.core.get_session_timeline("char_a")
    identity = handoff_case.core.character_identity_digest("char_a")
    handoff_case.restart()
    assert handoff_case.core.get_character_activation_lock("char_a") == own
    monkeypatch.setattr(main, "character_agent_runtime", handoff_case.core, raising=False)
    with RuntimeStorageLease(tmp_path / "restart.db") as lease:
        monkeypatch.setattr(main, "_runtime_storage_lease", lease)
        main._release_interrupted_character_activations()
        head = handoff_case.store.get_stream_head("population:world:default")
        main._release_interrupted_character_activations()
        assert handoff_case.store.get_stream_head("population:world:default") == head
    assert handoff_case.core.get_character_activation_lock("char_a") is None
    assert handoff_case.core.get_character_activation_lock("char_b") is None
    assert handoff_case.authority.active_lock(world_ref="world:other", profile_ref=ACTORS[0]) is not None
    assert handoff_case.core.get_session_timeline("char_a") == before
    assert handoff_case.core.character_identity_digest("char_a") == identity
    releases = handoff_case.store.read_stream("population:world:default", event_type="population.activation.released")
    assert len(releases) == 2 and releases[0].payload["pending_change_refs"] == [change.change_ref]
    handoff_case.restart()
    assert handoff_case.core.get_character_activation_lock("char_a") is None
    assert handoff_case.take_lock().held_revision > own.held_revision


@pytest.mark.parametrize("closed", [False, True])
def test_startup_recovery_requires_held_original_storage_lease(handoff_case, monkeypatch, tmp_path, closed):
    from app import main
    from app.world_runtime.storage_lease import RuntimeStorageLease

    lock = handoff_case.take_lock()
    lease = None
    if closed:
        lease = RuntimeStorageLease(tmp_path / "closed.db")
        lease.close()
    monkeypatch.setattr(main, "character_agent_runtime", handoff_case.core, raising=False)
    monkeypatch.setattr(main, "_runtime_storage_lease", lease)
    before = handoff_case.store.get_stream_heads()
    with pytest.raises(RuntimeError, match="runtime_storage_lease_required"):
        main._release_interrupted_character_activations()
    assert handoff_case.store.get_stream_heads() == before
    assert handoff_case.core.get_character_activation_lock("char_a") == lock


def test_startup_recovery_cannot_release_a_live_activation(handoff_case, monkeypatch, tmp_path):
    from app import main
    from test_character_agent_activation_handoff import active_dialogue_decision
    from app.world_runtime.storage_lease import RuntimeStorageLease

    handle, receipt = handoff_case.core.begin_actor_activation("char_a", active_dialogue_decision(), producer_ts=1)
    assert handle is not None and receipt.committed
    before = handoff_case.store.get_stream_heads()
    monkeypatch.setattr(main, "character_agent_runtime", handoff_case.core, raising=False)
    try:
        with RuntimeStorageLease(tmp_path / "live.db") as lease:
            monkeypatch.setattr(main, "_runtime_storage_lease", lease)
            with pytest.raises(RuntimeError, match="activation_recovery_not_idle"):
                main._release_interrupted_character_activations()
        assert handoff_case.store.get_stream_heads() == before
        assert handoff_case.core.activation_is_current(handle.lock_ref, handle.token)
    finally:
        assert handoff_case.core.finish_actor_activation(handle, reason="completed").committed


def test_startup_release_failure_stops_recovery_with_original_lock(handoff_case, monkeypatch, tmp_path):
    from app import main
    from app.population_continuity.models import ActivationReceipt
    from app.world_runtime.storage_lease import RuntimeStorageLease

    lock = handoff_case.take_lock()
    before = handoff_case.store.get_stream_heads()
    monkeypatch.setattr(main, "character_agent_runtime", handoff_case.core, raising=False)
    monkeypatch.setattr(handoff_case.authority, "release_lock", lambda **kwargs:
        ActivationReceipt(committed=False, status="rejected", profile_ref=ACTORS[0],
            zero_write=True, stop_reason="revision_conflict"))
    with RuntimeStorageLease(tmp_path / "failed.db") as lease:
        monkeypatch.setattr(main, "_runtime_storage_lease", lease)
        with pytest.raises(RuntimeError, match="activation_recovery_failed:revision_conflict"):
            main._release_interrupted_character_activations()
    assert handoff_case.store.get_stream_heads() == before
    assert handoff_case.core.get_character_activation_lock("char_a") == lock


def packet_inputs(handoff_case):
    lock = handoff_case.take_lock()
    current = frame(character_revision=0, tick_cursor=0, activation_lock_ref=lock.lock_ref)
    return current, handoff_case.read(), lock


def test_prepare_packet_is_pure_actor_scoped_and_keeps_protected_codes(handoff_case):
    current, ledger, lock = packet_inputs(handoff_case)
    before = (handoff_case.store.get_stream_heads(), handoff_case.core.get_session_timeline("char_a"))
    packet = prepare_intersection(frame=current, ledger=ledger, trigger_kind="player_dialogue", target_fidelity="B3", lock=lock)
    assert packet.actor_ref == current.actor_ref and packet.group_ref == ledger.cohort_ref
    assert packet.last_confirmed_tick == 0 and packet.continuity_revision == 0
    assert packet.lock_ref == lock.lock_ref and packet.lock_revision == lock.held_revision
    assert "needs.tags" in packet.hard_constraints and "private_memory" in packet.hard_constraints
    assert packet.required_code_refs == ("code:care",)
    assert packet.unresolved_proposals == ()
    assert "code:care-obligation" not in packet.required_code_refs
    assert (handoff_case.store.get_stream_heads(), handoff_case.core.get_session_timeline("char_a")) == before
    assert prepare_intersection(frame=current, ledger=ledger, trigger_kind="player_dialogue", target_fidelity="B3", lock=lock) == packet


@pytest.mark.parametrize("changes", [{"profile_ref": ACTORS[1]}, {"status": "released"},
    {"held_revision": True}, {"lock_ref": "lock:wrong"}])
def test_prepare_packet_rejects_invalid_lock(handoff_case, changes):
    current, ledger, lock = packet_inputs(handoff_case)
    with pytest.raises(ValueError):
        prepare_intersection(frame=current, ledger=ledger, trigger_kind="player_dialogue", target_fidelity="B3",
            lock=lock.model_copy(update=changes))


@pytest.mark.parametrize("tier", ["B0", "B2", "invalid"])
def test_prepare_packet_does_not_ignore_participation(handoff_case, tier):
    current, ledger, lock = packet_inputs(handoff_case)
    with pytest.raises(ValueError):
        prepare_intersection(frame=current, ledger=ledger, trigger_kind="player_dialogue", target_fidelity=tier, lock=lock)


def test_prepare_packet_cannot_accept_model_copy_corruption(handoff_case):
    current, ledger, lock = packet_inputs(handoff_case)
    with pytest.raises(ValueError):
        prepare_intersection(frame=current.model_copy(update={"character_core_revision": True}), ledger=ledger,
            trigger_kind="player_dialogue", target_fidelity="B3", lock=lock)


def test_second_authority_observes_lock_and_release_from_original_store(handoff_case):
    other = ProfileActivationAuthority(registry=handoff_case.core._profile_registry, store=handoff_case.store)
    lock = handoff_case.take_lock()
    assert other.active_lock(world_ref="world:default", profile_ref=ACTORS[0]) == lock
    denied = other.lock(world_ref="world:default", profile_ref=ACTORS[0],
        expected_revision=handoff_case.store.get_stream_head("population:world:default"))
    assert not denied.committed and denied.zero_write
    assert handoff_case.release(lock).committed
    assert other.active_lock(world_ref="world:default", profile_ref=ACTORS[0]) is None


def test_duplicate_lock_and_release_do_not_start_another_driver(handoff_case):
    lock = handoff_case.take_lock()
    head = handoff_case.store.get_stream_head("population:world:default")
    duplicate = handoff_case.authority.lock(world_ref="world:default", profile_ref=ACTORS[0],
        expected_revision=lock.held_revision)
    assert duplicate.committed and duplicate.idempotency_status == "duplicate_replayed"
    assert handoff_case.store.get_stream_head("population:world:default") == head
    released = handoff_case.release(lock)
    assert released.committed
    again = handoff_case.authority.release_lock(lock_ref=lock.lock_ref, expected_revision=head)
    assert again.committed and again.idempotency_status == "duplicate_replayed"
    assert handoff_case.store.get_stream_head("population:world:default") == head + 1
    assert handoff_case.authority.active_lock(world_ref="world:default", profile_ref=ACTORS[0]) is None


@pytest.mark.parametrize("revision", [True, -1, "0"])
def test_invalid_lock_revision_is_zero_write(handoff_case, revision):
    before = handoff_case.store.get_stream_heads()
    result = handoff_case.authority.lock(world_ref="world:default", profile_ref=ACTORS[0], expected_revision=revision)
    assert not result.committed and result.zero_write
    assert handoff_case.store.get_stream_heads() == before


def test_packet_pending_source_is_actor_scoped_and_does_not_become_simulation_tick(handoff_case):
    own = handoff_case.commit_actor_result(ACTORS[0], "handoff:own")
    handoff_case.commit_actor_result(ACTORS[1], "handoff:other")
    current, ledger, lock = packet_inputs(handoff_case)
    packet = prepare_intersection(frame=current, ledger=ledger, trigger_kind="player_dialogue", target_fidelity="B3", lock=lock)
    assert packet.unresolved_proposals == (own,)
    assert packet.last_confirmed_tick == 0
    assert packet.last_confirmed_tick != handoff_case.store.get_event(own).global_sequence


def test_expired_activation_cannot_start_a_second_driver_before_original_release(handoff_case, monkeypatch):
    from app.character_agent.runtime import runtime_loop
    from test_character_agent_activation_handoff import active_dialogue_decision
    now = 100.0
    monkeypatch.setattr(runtime_loop, "monotonic", lambda: now)
    handle, receipt = handoff_case.core.begin_actor_activation("char_a", active_dialogue_decision(),
        producer_ts=1, deadline_monotonic=101.0)
    assert receipt.committed
    now = 102.0
    assert not handoff_case.core.activation_is_current(handle.lock_ref, handle.token)
    second, refused = handoff_case.core.begin_actor_activation("char_a", active_dialogue_decision(), producer_ts=2)
    assert second is None and refused.zero_write
    assert handoff_case.core.apply_character_continuity_command(handoff_case.legacy_command()).status == "rejected"
    assert handoff_case.core.finish_actor_activation(handle, reason="deadline_expired").lock_released
    next_handle, result = handoff_case.core.begin_actor_activation("char_a", active_dialogue_decision(), producer_ts=3)
    assert result.committed and next_handle.token != handle.token
    assert handoff_case.core.finish_actor_activation(next_handle, reason="completed").lock_released


def current_handoff_frame(case, lock):
    from app.population_continuity.siming_contracts import PopulationReadSet
    from test_character_simulation_frame import read_set
    inputs = read_set()
    vector = {"population:world:default": case.store.get_stream_head("population:world:default")}
    for result in case.read().confirmed_results:
        if result.actor_ref == ACTORS[0]:
            for stream, revision in result.source_revision_vector.items():
                vector[stream] = max(vector.get(stream, 0), revision)
    cadence = inputs.cadence.model_copy(update={"world_ref": "world:default",
        "cadence_source_ref": "population:world:default", "cadence_source_revision": vector["population:world:default"],
        "base_revision_vector": vector, "source_revision_vector": {}})
    return frame(character_revision=case.core.get_continuity_revision("char_a"),
        tick_cursor=case.core.get_character_simulation_cursor("char_a"), module_states={},
        activation_lock_ref=lock.lock_ref, read_set=PopulationReadSet.from_inputs(cadence, ()))


def handoff(case, current, *, key="handoff:1"):
    return case.world.prepare_member_handoff(cohort_ref="cohort:test", frame=current,
        trigger_kind="player_dialogue", target_fidelity="B3", activation_authority=case.authority,
        continuity_runtime=case.core, expected_revision=case.revision(), idempotency_key=key)


@pytest.mark.parametrize("restriction", ["authorization", "roster"])
def test_new_handoff_rechecks_current_world_actor_scope(handoff_case, restriction):
    from app.population_continuity.roster import PopulationRoster

    lock = handoff_case.take_lock()
    current = current_handoff_frame(handoff_case, lock)
    restricted = WorldContinuityRuntime(store=handoff_case.store, mode=handoff_case.mode,
        roster=(PopulationRoster(actor_ids=("char_b",)) if restriction == "roster" else handoff_case.roster),
        authorized_actor_refs=(frozenset({ACTORS[1]}) if restriction == "authorization" else None))
    heads = handoff_case.store.get_stream_heads()
    timeline = handoff_case.core.get_session_timeline("char_a")
    with pytest.raises(ValueError, match="member_actor_scope_denied"):
        restricted.prepare_member_handoff(cohort_ref="cohort:test", frame=current,
            trigger_kind="player_dialogue", target_fidelity="B3", activation_authority=handoff_case.authority,
            continuity_runtime=handoff_case.core, expected_revision=1, idempotency_key="new:scope")
    assert handoff_case.store.get_stream_heads() == heads
    assert handoff_case.core.get_session_timeline("char_a") == timeline
    assert handoff_case.core.get_character_activation_lock("char_a") == lock


def test_actual_actor_result_is_consumed_then_handed_off_and_recovered(handoff_case):
    source = handoff_case.commit_actor_result(ACTORS[0], "handoff:consume")
    identity = handoff_case.core.character_identity_digest("char_a")
    lock = handoff_case.take_lock()
    command = handoff_case.command(ACTORS[0], source).model_copy(update={
        "activation_lock_ref": lock.lock_ref, "activation_lock_revision": lock.held_revision})
    assert handoff_case.core.apply_character_continuity_command(command).status == "committed"
    assert handoff_case.world.consume_member_result(cohort_ref="cohort:test", actor_ref=ACTORS[0], result_ref=source,
        continuity_runtime=handoff_case.core, continuity_idempotency_key=command.idempotency_key,
        expected_revision=handoff_case.revision(), idempotency_key="consume:handoff").committed
    current = current_handoff_frame(handoff_case, lock)
    packet, receipt = handoff(handoff_case, current)
    assert receipt.committed and packet.last_confirmed_tick == 11 and packet.continuity_revision == 1
    assert packet.unresolved_proposals == () and packet.required_code_refs == ("code:care",)
    checkpoint = handoff_case.world.create_member_ledger_checkpoint("cohort:test")
    ledger = handoff_case.read()
    assert ledger.member_entries[0].lifecycle == "handoff"
    assert ledger.member_entries[0].last_consumed_result_cursor == handoff_case.store.get_event(source).global_sequence
    assert handoff_case.core.character_identity_digest("char_a") == identity
    handoff_case.restart()
    assert handoff_case.world.read_member_handoff(cohort_ref="cohort:test", actor_ref=ACTORS[0]) == packet
    assert handoff_case.read(checkpoint=checkpoint) == ledger
    before = (handoff_case.store.get_stream_heads(), handoff_case.core.get_session_timeline("char_a"))
    replay_packet, replay_receipt = handoff(handoff_case, current)
    assert replay_packet == packet and replay_receipt.idempotency_status == "duplicate_replayed"
    assert (handoff_case.store.get_stream_heads(), handoff_case.core.get_session_timeline("char_a")) == before


def test_new_owner_event_is_pending_for_next_frame_without_mutating_handoff_packet(handoff_case):
    lock = handoff_case.take_lock()
    packet, receipt = handoff(handoff_case, current_handoff_frame(handoff_case, lock))
    assert receipt.committed
    source = handoff_case.commit_actor_result(ACTORS[0], "handoff:late-owner")
    assert handoff_case.world.read_member_handoff(cohort_ref="cohort:test", actor_ref=ACTORS[0]) == packet
    assert source not in packet.unresolved_proposals
    assert handoff_case.read().member_entries[0].lifecycle == "handoff"
    assert handoff_case.core.get_continuity_revision("char_a") == 0
    handoff_case.restart()
    assert handoff_case.world.read_member_handoff(cohort_ref="cohort:test", actor_ref=ACTORS[0]) == packet
    assert handoff_case.read().confirmed_results[-1].result_ref == source
    assert handoff_case.read().confirmed_results[-1].consumed_core_receipt_ref is None


def test_old_frame_cannot_be_reused_after_core_advances(handoff_case):
    lock = handoff_case.take_lock()
    old = current_handoff_frame(handoff_case, lock)
    command = handoff_case.legacy_command(key="new-driver").model_copy(update={
        "activation_lock_ref": lock.lock_ref, "activation_lock_revision": lock.held_revision})
    assert handoff_case.core.apply_character_continuity_command(command).status == "committed"
    before = handoff_case.store.get_stream_heads()
    with pytest.raises(ValueError, match="handoff_core_frame_stale"):
        handoff(handoff_case, old)
    assert handoff_case.store.get_stream_heads() == before


def test_source_change_before_handoff_append_uses_original_cas(handoff_case, monkeypatch):
    lock = handoff_case.take_lock()
    current = current_handoff_frame(handoff_case, lock)
    append = handoff_case.store.append_batch
    changed = False

    def append_with_competitor(batch):
        nonlocal changed
        if batch.idempotency_record.principal_ref == "world_runtime.cadence" and not changed:
            changed = True
            other = handoff_case.authority.lock(world_ref="world:default", profile_ref=ACTORS[1],
                expected_revision=handoff_case.store.get_stream_head("population:world:default"))
            assert other.committed
        return append(batch)

    monkeypatch.setattr(handoff_case.store, "append_batch", append_with_competitor)
    _, result = handoff(handoff_case, current)
    assert not result.committed
    assert handoff_case.world.read_member_handoff(cohort_ref="cohort:test", actor_ref=ACTORS[0]) is None
    assert handoff_case.read().member_entries[0].lifecycle == "active"
    assert handoff_case.authority.active_lock(world_ref="world:default", profile_ref=ACTORS[0]) == lock


def test_released_lock_cannot_be_used_for_first_handoff(handoff_case):
    lock = handoff_case.take_lock()
    current = current_handoff_frame(handoff_case, lock)
    assert handoff_case.release(lock).committed
    before = handoff_case.store.get_stream_heads()
    with pytest.raises(ValueError, match="handoff_lock_stale"):
        handoff(handoff_case, current)
    assert handoff_case.store.get_stream_heads() == before


def test_pending_results_cannot_hide_entry_revision_in_pure_packet(handoff_case):
    handoff_case.commit_actor_result(ACTORS[0], "handoff:pending-anchor")
    current, ledger, lock = packet_inputs(handoff_case)
    entries = tuple(entry.model_copy(update={"entry_character_revision": 2})
                    if entry.actor_ref == ACTORS[0] else entry for entry in ledger.member_entries)
    with pytest.raises(ValueError, match="handoff_core_frame_stale"):
        prepare_intersection(frame=current, ledger=ledger.model_copy(update={"member_entries": entries}),
            trigger_kind="player_dialogue", target_fidelity="B3", lock=lock)


def test_handoff_commit_without_ack_replays_after_real_restart(handoff_case, monkeypatch):
    lock = handoff_case.take_lock()
    current = current_handoff_frame(handoff_case, lock)
    append = handoff_case.store.append_batch

    def commit_without_ack(batch):
        result = append(batch)
        if result.committed and batch.events[0].event_type == "population.world.member_handoff_recorded@1":
            raise OSError("handoff ACK lost")
        return result

    with monkeypatch.context() as patch:
        patch.setattr(handoff_case.store, "append_batch", commit_without_ack)
        with pytest.raises(OSError, match="ACK lost"):
            handoff(handoff_case, current)
    packet = handoff_case.world.read_member_handoff(cohort_ref="cohort:test", actor_ref=ACTORS[0])
    assert packet is not None
    before = handoff_case.store.get_stream_heads()
    handoff_case.restart()
    again, result = handoff(handoff_case, current)
    assert again == packet and result.idempotency_status == "duplicate_replayed"
    assert handoff_case.store.get_stream_heads() == before


def test_world_handoff_cannot_use_a_lock_outside_cores_bound_world(handoff_case):
    locked = handoff_case.authority.lock(world_ref="world:ledger", profile_ref=ACTORS[0],
        expected_revision=handoff_case.store.get_stream_head("population:world:ledger"))
    assert locked.committed
    lock = handoff_case.authority.active_lock(world_ref="world:ledger", profile_ref=ACTORS[0])
    current = frame(character_revision=0, tick_cursor=0, activation_lock_ref=lock.lock_ref)
    other_world = WorldContinuityRuntime(store=handoff_case.store,
        mode=handoff_case.mode.model_copy(update={"world_ref": "world:ledger"}), roster=handoff_case.roster)
    before = handoff_case.store.get_stream_heads()
    with pytest.raises(ValueError, match="handoff_lock_stale"):
        other_world.prepare_member_handoff(cohort_ref="cohort:test", frame=current,
            trigger_kind="player_dialogue", target_fidelity="B3", activation_authority=handoff_case.authority,
            continuity_runtime=handoff_case.core, expected_revision=1, idempotency_key="other-world:handoff")
    assert handoff_case.store.get_stream_heads() == before
