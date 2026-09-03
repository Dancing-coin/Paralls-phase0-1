from app.population_continuity.activation_policy import ActivationPolicy


def test_player_proximity_enters_prewarm_without_loading_private_memory() -> None:
    decision = ActivationPolicy().evaluate(actor_id="char_a", distance_m=8.0, focused=False, interaction_type="none", pending_seed=True, budget=2)
    assert decision.state == "prewarm"
    assert decision.load_private_memory is False


def test_focused_dialogue_enters_active_with_activation_lock() -> None:
    decision = ActivationPolicy().evaluate(actor_id="char_a", distance_m=2.0, focused=True, interaction_type="dialogue", pending_seed=True, budget=2)
    assert decision.state == "active"
    assert decision.requires_activation_lock is True
    assert decision.load_private_memory is True


def test_structured_player_inputs_invoke_activation_once_without_requeueing_active_handoff(monkeypatch) -> None:
    import app.main as main
    from app.config import settings
    from app.ws_protocol import Envelope

    monkeypatch.setattr(settings, "dialogue_mode", "stub")
    main.reset_runtime_state()
    decisions = []
    receipts = []
    evaluate = main.activation_policy.evaluate
    activate = main.character_agent_runtime.activate_actor

    def record_decision(**kwargs):
        decision = evaluate(**kwargs)
        decisions.append(decision)
        return decision

    def record_receipt(*args, **kwargs):
        receipt = activate(*args, **kwargs)
        receipts.append(receipt)
        return receipt

    monkeypatch.setattr(main.activation_policy, "evaluate", record_decision)
    monkeypatch.setattr(main.character_agent_runtime, "activate_actor", record_receipt)
    base = {"player_id": "p1", "room_id": "room_demo", "scene_id": "scene_demo", "zone_id": "zone_focus", "actor_id": "char_c", "producer_ts": 101}
    main._handle_envelope(Envelope(message_type="player_input", payload={**base, "intent_type": "dialogue_submit", "target_actor_id": "char_a", "content": "hello"}))
    main._handle_envelope(Envelope(message_type="player_input", payload={**base, "intent_type": "focus_target_change", "target_actor_id": "char_b"}))
    main._handle_envelope(Envelope(message_type="player_input", payload={**base, "intent_type": "interact_intent", "target_object_id": "character:char_c", "interaction_type": "consequential"}))

    assert [decision.state for decision in decisions] == ["active", "activation_candidate", "activation_candidate"]
    assert len(receipts) == 1
    assert all(receipt.committed for receipt in receipts)


def test_unsupported_actor_produces_zero_write_requeue_audit(monkeypatch) -> None:
    import app.main as main
    from app.models.player_input import FocusTargetChange

    main.reset_runtime_state()
    audits = []
    monkeypatch.setattr(main, "_publish_debug_event", audits.append)
    main._activate_character_for_player_input(
        FocusTargetChange(
            player_id="p1", room_id="room_demo", actor_id="char_c", producer_ts=101,
            target_actor_id="unknown_actor",
        )
    )

    assert audits[-1]["stage"] == "activation_requeue"
    assert audits[-1]["detail"]["decision"]["reason"] == "unsupported_actor"
    assert audits[-1]["detail"]["receipt"] == {}
