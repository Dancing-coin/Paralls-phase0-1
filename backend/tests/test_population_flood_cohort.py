import pytest

from app.population_continuity.flood_vertical import FloodPopulationFixture


@pytest.fixture
def flood_case(tmp_path):
    value = FloodPopulationFixture.create(storage_root=tmp_path)
    try:
        yield value
    finally:
        value.close()


def test_two_full_windows_use_public_siming_and_real_owner_core_handoff(flood_case):
    identities = {actor: flood_case.identity_digest(actor) for actor in flood_case.actors}
    first = flood_case.run_window(from_tick=0, to_tick=3600)
    assert first.status == "accepted"
    assert first.owner_receipts and first.owner_receipts[0].committed
    assert first.owner_receipts[0].event_family == "gameplay.organization.commerce_commitment_accepted"
    assert all(receipt.status == "committed" for receipt in first.continuity_receipts)
    assert first.continuity_receipts
    second = flood_case.run_window(from_tick=3600, to_tick=7200, player_actor_ref="character:char_a")
    assert second.status == "accepted"
    assert flood_case.member_state("character:char_a") == "handoff"
    assert flood_case.member_state("character:char_b") == "active"
    assert flood_case.member_state("character:char_c") == "active"
    assert flood_case.intersections[0].last_confirmed_tick == 7200
    assert {actor: flood_case.identity_digest(actor) for actor in flood_case.actors} == identities
    assert flood_case.siming_tick_count == 2
    assert flood_case.world.latest_confirmation.advanced_count == 1
    assert not any(event.event_type == "flood_rescue_completed" for event in flood_case.business_events())
    allowed = {"gameplay.organization.membership_recorded", "gameplay.organization.role_term_recorded",
        "gameplay.organization.shift_offer_recorded", "gameplay.organization.work_order_recorded",
        "gameplay.organization.commerce_commitment_accepted"}
    assert {event.event_type for event in flood_case.business_events()} <= allowed


def test_actual_personal_and_b0_values_match_independent_scalar_oracle(flood_case):
    # 独立固定窗标量算例，不调用被测模块或原 advance_b0_row。
    for start, end, fatigue, pressure in ((0, 3600, .16, .11), (3600, 7200, .12, .12)):
        flood_case.run_window(from_tick=start, to_tick=end)
        for actor in flood_case.actors:
            actual = flood_case.needs(actor)
            assert actual["fatigue"] == pytest.approx(fatigue)
            assert actual["need_pressure"] == pytest.approx(pressure)
        assert flood_case.world.population_hot_state.read("char_a")["last_update_tick"] == 0
        assert flood_case.world.population_hot_state.read("char_c")["last_update_tick"] == 0


def test_reporting_and_duplicate_delivery_do_not_change_authorities(flood_case):
    first = flood_case.run_window(from_tick=0, to_tick=3600)
    before = flood_case.authority_snapshot()
    assert flood_case.statistics()["members"] == ("character:char_b",)
    assert flood_case.statistics() == flood_case.statistics()
    assert flood_case.authority_snapshot() == before
    replay = flood_case.redeliver(from_tick=0, to_tick=3600)
    assert replay.owner_receipts[0].committed and replay.owner_receipts[0].zero_write
    assert replay.owner_receipts[0].idempotency_status == "duplicate_replayed"
    assert replay.continuity_receipts[0].status == "idempotent_replay"
    assert flood_case.authority_snapshot() == before
    assert replay.seed_candidates == first.seed_candidates


def test_budget_defer_does_not_fake_personal_progress(flood_case):
    before = {actor: flood_case.character_runtime.get_continuity_revision(actor.removeprefix("character:"))
        for actor in ("character:char_a", "character:char_c")}
    result = flood_case.run_window(from_tick=0, to_tick=3600, budget=0)
    assert result.status in {"accepted", "requeue"}
    assert not result.owner_receipts and not result.continuity_receipts
    assert {actor: flood_case.character_runtime.get_continuity_revision(actor.removeprefix("character:"))
        for actor in before} == before
    assert flood_case.world.latest_confirmation.advanced_count == 1


def test_restart_rebuilds_real_core_member_ledger_and_cadence(flood_case):
    flood_case.run_window(from_tick=0, to_tick=3600)
    before = flood_case.authority_snapshot()
    flood_case.restart()
    assert flood_case.authority_snapshot() == before
    result = flood_case.run_window(from_tick=3600, to_tick=7200, player_actor_ref="character:char_a")
    assert result.status == "accepted"
    assert flood_case.member_state("character:char_a") == "handoff"


def test_actual_actor_schedule_result_is_consumed_only_with_its_core_receipt(flood_case):
    flood_case.run_window(from_tick=0, to_tick=3600)
    ledger = flood_case.world.read_member_ledger(flood_case.cohort_ref)
    assert len(ledger.confirmed_results) == 1
    source = ledger.confirmed_results[0]
    assert source.actor_ref == "character:char_a"
    assert source.result_ref == flood_case.schedule.committed_event_ids[0]
    assert source.consumed_core_receipt_ref is not None
    assert next(entry for entry in ledger.member_entries if entry.actor_ref == source.actor_ref).last_consumed_result_cursor == source.source_cursor
    assert next(entry for entry in ledger.member_entries if entry.actor_ref == "character:char_b").last_consumed_result_cursor == 0


def test_player_can_take_over_the_actual_b0_member_without_advancing_other_personal_actors(flood_case):
    flood_case.run_window(from_tick=0, to_tick=3600, player_actor_ref="character:char_b")
    assert flood_case.member_state("character:char_b") == "handoff"
    assert flood_case.intersections[0].last_confirmed_tick == 3600
    assert flood_case.needs("character:char_b")["fatigue"] == pytest.approx(.16)
    flood_case.run_window(from_tick=3600, to_tick=7200)
    assert flood_case.world.latest_confirmation.advanced_count == 0
    assert flood_case.world.population_hot_state.read("char_b")["last_update_tick"] == 3600


def test_unknown_intersection_target_is_rejected_before_any_business_work(flood_case):
    before = flood_case.authority_snapshot()
    with pytest.raises(ValueError, match="flood_actor_unknown"):
        flood_case.run_window(from_tick=0, to_tick=3600, player_actor_ref="character:unknown")
    assert flood_case.authority_snapshot() == before


def test_b0_b3_b0_uses_new_member_anchor_and_preserves_identity_after_restart(flood_case):
    actor = "character:char_b"
    identity = flood_case.identity_digest(actor)
    flood_case.run_window(from_tick=0, to_tick=3600, player_actor_ref=actor)
    old_cohort = flood_case.cohort_ref
    flood_case.return_to_population(actor)
    assert flood_case.cohort_ref != old_cohort
    assert next(entry for entry in flood_case.world.read_member_ledger(old_cohort).member_entries
        if entry.actor_ref == actor).lifecycle == "handoff"
    anchor = next(entry for entry in flood_case.world.read_member_ledger(flood_case.cohort_ref).member_entries
        if entry.actor_ref == actor)
    assert anchor.entry_character_revision == flood_case.character_runtime.get_continuity_revision("char_b") == 1
    flood_case.restart()
    flood_case.run_window(from_tick=3600, to_tick=7200)
    assert flood_case.world.latest_confirmation.advanced_count == 1
    assert flood_case.needs(actor)["fatigue"] == pytest.approx(.12)
    assert flood_case.identity_digest(actor) == identity


@pytest.mark.parametrize("actor", ["character:char_a", "character:char_c"])
def test_personal_policy_cannot_be_relaxed_by_returning_to_population(flood_case, actor):
    flood_case.run_window(from_tick=0, to_tick=3600, player_actor_ref=actor)
    before = flood_case.authority_snapshot()
    with pytest.raises(ValueError, match="flood_b0_return_denied"):
        flood_case.return_to_population(actor)
    assert flood_case.authority_snapshot() == before


def test_budget_defer_restart_can_replay_the_original_personal_window(flood_case):
    flood_case.run_window(from_tick=0, to_tick=3600, budget=0)
    before = len(flood_case.business_events())
    flood_case.restart()
    replay = flood_case.redeliver(from_tick=0, to_tick=3600)
    # 原冻结 budget 不能在重投时擅自扩大。
    assert not replay.owner_receipts and not replay.continuity_receipts
    assert len(flood_case.business_events()) == before
    next_result = flood_case.run_window(from_tick=3600, to_tick=7200)
    assert next_result.status == "accepted"
    assert all(item.status == "committed" for item in next_result.continuity_receipts)
    assert flood_case.character_runtime.get_character_simulation_cursor("char_c") == 7200


def test_situation_exit_does_not_reset_personal_state_or_protected_identity(flood_case):
    flood_case.run_window(from_tick=0, to_tick=3600)
    before = flood_case.authority_snapshot()
    flood_case.exit_situation()
    assert flood_case.authority_snapshot() == before
    assert flood_case.current_situation is None
    with pytest.raises(ValueError, match="flood_situation_not_active"):
        flood_case.run_window(from_tick=3600, to_tick=7200)
    assert flood_case.authority_snapshot() == before


def test_supply_projection_is_bound_to_the_actual_module_action_proposal(flood_case):
    flood_case.run_window(from_tick=0, to_tick=3600)
    proposals = flood_case.module_proposals[(0, 3600, "character:char_a")]
    action = next(item for item in proposals if item.proposal_kind == "action_candidate")
    event = flood_case.events[(0, 3600)]
    projection = next(row for row in event.payload["population_projections"]
        if row["payload"].get("candidate_kind") == "schedule_gated_supply")
    candidate = projection["payload"]["schedule_gated_supply_source_context"]["candidate"]
    assert candidate["intent_ref"] == action.typed_payload.intent_ref
    assert action.proposal_ref in projection["payload"]["evidence_refs"]


def test_delayed_b3_return_uses_own_core_state_and_survives_restart(flood_case):
    actor = "character:char_b"
    flood_case.run_window(from_tick=0, to_tick=1800, player_actor_ref=actor)
    flood_case.run_window(from_tick=1800, to_tick=3600)
    assert flood_case.character_runtime.get_character_simulation_cursor("char_b") == 3600
    assert flood_case.world.population_hot_state.read("char_b")["last_update_tick"] == 1800
    flood_case.return_to_population(actor)
    flood_case.restart()
    flood_case.run_window(from_tick=3600, to_tick=5400)
    assert flood_case.world.latest_confirmation.advanced_count == 1
    assert flood_case.needs(actor) == pytest.approx(dict(fatigue=.14, need_pressure=.115))


@pytest.mark.parametrize("pending", [False, True])
def test_return_of_one_actor_preserves_other_handoff_and_member_results(flood_case, pending):
    flood_case.run_window(from_tick=0, to_tick=1800, player_actor_ref="character:char_a")
    flood_case.run_window(from_tick=1800, to_tick=3600, player_actor_ref="character:char_b")
    if pending:
        from app.gameplay.organization_government_runtime import OrganizationAuthority
        result = OrganizationAuthority(store=flood_case.store).record_schedule(command_id="flood:second-schedule",
            organization_ref="org:flood-supply", recipient_ref="character:char_a", membership_ref="membership:second",
            assignment_ref="assignment:second", role="farmer", shift_ref="shift:second",
            operating_window_ref="window:second", work_order_ref="work:second",
            effective_from="1970-01-01T00:00:00Z", effective_to=None, visibility_scope="public")
        assert result.committed
        stream = flood_case.world.member_ledger_stream(flood_case.cohort_ref)
        assert flood_case.world.confirm_member_result(cohort_ref=flood_case.cohort_ref, actor_ref="character:char_a",
            result_ref=result.committed_event_ids[0], expected_revision=flood_case.store.get_stream_head(stream),
            idempotency_key="confirm:second-schedule").committed
    old = flood_case.world.read_member_ledger(flood_case.cohort_ref)
    old_a = next(item for item in old.member_entries if item.actor_ref == "character:char_a")
    packet = flood_case.world.read_member_handoff(cohort_ref=flood_case.cohort_ref, actor_ref=old_a.actor_ref)
    flood_case.return_to_population("character:char_b")
    new = flood_case.world.read_member_ledger(flood_case.cohort_ref)
    assert next(item for item in new.member_entries if item.actor_ref == old_a.actor_ref) == old_a
    assert new.confirmed_results == old.confirmed_results
    assert flood_case.world.read_member_handoff(cohort_ref=flood_case.cohort_ref, actor_ref=old_a.actor_ref) == packet
    before = tuple(flood_case.business_events())
    flood_case.restart()
    flood_case.run_window(from_tick=3600, to_tick=5400)
    assert tuple(flood_case.business_events()) == before
    assert flood_case.member_state(old_a.actor_ref) == "handoff"


@pytest.mark.parametrize("failure_stage", ["register", "checkpoint"])
def test_return_failure_can_retry_after_restart_without_losing_other_members(flood_case, monkeypatch, failure_stage):
    flood_case.run_window(from_tick=0, to_tick=1800, player_actor_ref="character:char_b")
    old_cohort = flood_case.cohort_ref
    before = flood_case.world.export_recovery_state()
    target = flood_case.world if failure_stage == "register" else flood_case.store
    method = "register_member_reentry" if failure_stage == "register" else "save_projection_checkpoints_atomic"
    def fail(*args, **kwargs):
        raise OSError("injected reentry failure")
    with monkeypatch.context() as context:
        context.setattr(target, method, fail, raising=False)
        with pytest.raises(OSError, match="injected reentry failure"):
            flood_case.return_to_population("character:char_b")
    assert flood_case.cohort_ref == old_cohort
    assert flood_case.world.export_recovery_state() == before
    flood_case.restart()
    flood_case.return_to_population("character:char_b")
    assert flood_case.member_state("character:char_b") == "active"
    flood_case.restart()
    flood_case.run_window(from_tick=1800, to_tick=3600)
    assert flood_case.needs("character:char_b")["fatigue"] == pytest.approx(.16)


def test_committed_reentry_recovers_when_process_state_did_not_receive_ack(flood_case, monkeypatch):
    flood_case.run_window(from_tick=0, to_tick=1800, player_actor_ref="character:char_b")
    old = flood_case.cohort_ref
    replace = flood_case.publisher.replace_character_participation
    def lose_ack(**kwargs):
        replace(**kwargs)
        raise OSError("ack lost after durable reentry")
    with monkeypatch.context() as context:
        context.setattr(flood_case.publisher, "replace_character_participation", lose_ack)
        with pytest.raises(OSError, match="ack lost"):
            flood_case.return_to_population("character:char_b")
    assert flood_case.cohort_ref == old
    flood_case.restart()
    assert flood_case.cohort_ref != old
    flood_case.run_window(from_tick=1800, to_tick=3600)
    assert flood_case.needs("character:char_b")["fatigue"] == pytest.approx(.16)
