from app.population_continuity.flood_vertical import FloodPopulationFixture


def test_late_first_core_commit_cannot_roll_back_a_newer_confirmed_window(tmp_path, monkeypatch):
    case = FloodPopulationFixture.create(storage_root=tmp_path)
    try:
        apply = case.capability._continuity_port.apply_command
        def refuse_old(command):
            if command.actor_ref == "character:char_a" and command.to_tick == 3600:
                return apply(command.model_copy(update={"expected_character_revision": 999}))
            return apply(command)
        monkeypatch.setattr(case.capability._continuity_port, "apply_command", refuse_old)
        first = case.run_window(from_tick=0, to_tick=3600)
        assert first.owner_receipts[0].committed
        case.run_window(from_tick=3600, to_tick=7200)
        monkeypatch.setattr(case.capability._continuity_port, "apply_command", apply)
        before = case.authority_snapshot()
        replay = case.redeliver(from_tick=0, to_tick=3600)
        receipt = next(item for item in replay.continuity_receipts if item.actor_ref == "character:char_a")
        assert receipt.status == "requeued" and receipt.refusal_reason == "simulation_cursor_stale"
        assert replay.owner_receipts[0].committed and replay.owner_receipts[0].zero_write
        assert case.authority_snapshot() == before
        case.restart()
        assert case.character_runtime.get_character_simulation_cursor("char_a") == 7200
    finally:
        case.close()


def test_confirmed_owner_survives_real_core_refusal_restart_and_redelivery(tmp_path, monkeypatch):
    case = FloodPopulationFixture.create(storage_root=tmp_path)
    try:
        apply = case.capability._continuity_port.apply_command
        failed = False

        def refuse_first(command):
            nonlocal failed
            if command.actor_ref == "character:char_a" and not failed:
                failed = True
                return apply(command.model_copy(update={"expected_character_revision": 999}))
            return apply(command)

        monkeypatch.setattr(case.capability._continuity_port, "apply_command", refuse_first)
        first = case.run_window(from_tick=0, to_tick=3600)
        assert first.owner_receipts[0].committed
        assert first.continuity_receipts[0].status == "requeued"
        assert case.character_runtime.get_continuity_revision("char_a") == 0
        business = tuple(case.business_events())
        case.restart()
        replay = case.redeliver(from_tick=0, to_tick=3600)
        assert replay.owner_receipts[0].committed and replay.owner_receipts[0].zero_write
        assert replay.continuity_receipts[0].status == "committed"
        assert tuple(case.business_events()) == business
        # 供给结果和独立的班表成员事件各消费一次，重投不增加第三次写入。
        assert case.character_runtime.get_continuity_revision("char_a") == 2
        assert case.character_runtime.get_character_continuity_receipt(
            "char_a", idempotency_key="consume:flood-schedule:core").status == "committed"
        before = case.authority_snapshot()
        case.redeliver(from_tick=0, to_tick=3600)
        assert case.authority_snapshot() == before
        assert case.character_runtime.get_pending_seed_candidates("char_c") == []
        assert all(seed.source_owner_receipt_refs for seed in replay.seed_candidates if seed.owner_effect_status == "settled")
    finally:
        case.close()
