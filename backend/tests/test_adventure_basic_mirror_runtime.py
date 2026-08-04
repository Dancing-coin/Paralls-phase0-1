from __future__ import annotations

from pathlib import Path

from app.gameplay.adventure_basic_mirror_runtime import AdventureBasicMirrorRuntime
from app.gameplay.godot_mirror_delivery import (
    GameplayGodotProjectionPublisher,
    GameplayGodotProjectionRepository,
    GameplayMirrorAfterCommitDelivery,
    GameplayMirrorSubscriptionRegistry,
)
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.websocket_session_auth_service import WebSocketConnectionContext
from app.ws_protocol import Envelope


def test_scenario_one_mirror_delivery_waits_for_its_committed_outbox() -> None:
    repository = GameplayGodotProjectionRepository()
    publisher = GameplayGodotProjectionPublisher(repository=repository)
    subscriptions = GameplayMirrorSubscriptionRegistry(projection_source=repository.view_for)
    delivered: list[tuple[str, dict[str, object]]] = []
    delivery = GameplayMirrorAfterCommitDelivery(
        registry=subscriptions,
        deliver=lambda session_ref, payload: delivered.append((session_ref, payload)),
    )

    def after_transaction_dispatched(transaction) -> None:
        publisher.after_transaction_dispatched(transaction)
        delivery.deliver_for_committed_actor_refs(
            affected_actor_refs=tuple(
                actor_ref
                for hint in transaction.projection_refresh_hints
                if hint.projection_id == "godot_mirror"
                for actor_ref in hint.actor_refs
            )
        )

    runtime = AdventureBasicMirrorRuntime.create(
        scenario_id="scenario-1",
        publisher=publisher,
        authority_bus=InMemoryAuthorityEventBus(),
        after_transaction_dispatched=after_transaction_dispatched,
    )
    subscriptions.grant_read_scope(session_ref="session:scenario-1", actor_ref=runtime.actor_ref)
    _subscription, initial = subscriptions.subscribe(
        session_ref="session:scenario-1",
        actor_ref=runtime.actor_ref,
    )

    assert initial["groups"]["adventure.basic.scenario-1"]["payload"]["presentation_state"] == "sword_offer_available"
    result = runtime.execute_canonical_success()

    assert result.committed is True
    assert len(result.transaction_ids) == 2
    assert all(transaction.outbox_entries for transaction in runtime.store.read_transactions())
    assert all(transaction.projection_refresh_hints for transaction in runtime.store.read_transactions())
    assert [session_ref for session_ref, _payload in delivered] == ["session:scenario-1", "session:scenario-1"]
    assert [
        payload["groups"]["adventure.basic.scenario-1"]["payload"]["presentation_state"]
        for _session_ref, payload in delivered
    ] == ["sword_purchased", "sword_equipped"]
    assert delivered[-1][1]["groups"]["adventure.basic.scenario-1"]["payload"]["presentation_state"] == "sword_equipped"


def test_scenario_two_canonical_action_accepts_its_committed_settlement_batch() -> None:
    repository = GameplayGodotProjectionRepository()
    publisher = GameplayGodotProjectionPublisher(repository=repository)
    runtime = AdventureBasicMirrorRuntime.create(
        scenario_id="scenario-2",
        publisher=publisher,
        authority_bus=InMemoryAuthorityEventBus(),
        after_transaction_dispatched=lambda _transaction: None,
    )

    result = runtime.execute_canonical_success()

    assert result.committed is True
    assert result.transaction_ids[-1] == "tx:adventure-basic:scenario-2:sword-swing"


def test_server_selected_adventure_runtime_delivers_only_after_canonical_authority_commit(monkeypatch) -> None:
    import app.main as main

    monkeypatch.setattr(main.settings, "adventure_basic_mirror_live_scenario", "scenario-1")
    monkeypatch.setattr(main.settings, "gameplay_mirror_launcher_bootstrap_secret", "adventure-basic-test-secret")
    main.reset_runtime_state()
    assert main.adventure_basic_mirror_runtime is not None

    actor_ref = main.adventure_basic_mirror_runtime.actor_ref
    credential = main.websocket_session_auth_service.create_trusted_local_launch_credential(
        principal_ref="principal:adventure-basic-probe",
        allowed_actor_refs=(actor_ref,),
        issued_at=10,
        expires_at=100,
    )
    context = WebSocketConnectionContext(
        remote_host="127.0.0.1",
        observed_at=11,
        connection_ref="connection:adventure-basic",
    )
    main._handle_envelope(
        Envelope(
            message_type="websocket_session_bind",
            payload={
                "credential_kind": "trusted_local_launch",
                "credential": credential,
                "protocol_version": 1,
            },
        ),
        connection_context=context,
    )
    initial = main._handle_envelope(
        Envelope(message_type="gameplay_mirror_subscribe", payload={"actor_ref": actor_ref}),
        connection_context=context,
    )
    assert initial[1]["groups"]["adventure.basic.scenario-1"]["payload"]["presentation_state"] == "sword_offer_available"
    assert context.binding is not None
    delivered: list[dict[str, object]] = []
    main.gameplay_mirror_connection_registry.register(
        session_ref=context.binding.session_ref,
        connection_ref=context.connection_ref,
        connection_epoch=context.binding.connection_epoch,
        deliver=delivered.append,
    )

    from fastapi.testclient import TestClient

    client = TestClient(main.app, client=("127.0.0.1", 47061))
    client_selected = client.post(
        "/internal/trusted-local-adventure-basic-live-probe-commit",
        headers={"X-Gameplay-Mirror-Launcher-Secret": "adventure-basic-test-secret"},
        json={"scenario_id": "scenario-5"},
    )
    response = client.post(
        "/internal/trusted-local-adventure-basic-live-probe-commit",
        headers={"X-Gameplay-Mirror-Launcher-Secret": "adventure-basic-test-secret"},
        json={},
    )

    assert client_selected.status_code == 422
    assert response.status_code == 200
    assert response.json()["scenario_id"] == "scenario-1"
    assert response.json()["actor_ref"] == actor_ref
    assert len(delivered) == 2
    assert delivered[-1]["payload"]["payload"]["groups"]["adventure.basic.scenario-1"]["payload"]["presentation_state"] == "sword_equipped"


def test_live_adventure_basic_probe_uses_the_existing_trusted_local_mirror_path() -> None:
    root = Path(__file__).resolve().parents[2]
    probe = (root / "scripts" / "verification" / "LiveAdventureBasicMirrorDeliveryProbe.gd").read_text(encoding="utf-8")
    verifier = (root / "scripts" / "verification" / "verify_live_adventure_basic_mirror.py").read_text(encoding="utf-8")

    assert "load_session_enrollment_from_environment" in probe
    assert "gameplay_mirror_delivery_received" in probe
    assert "adventure.basic." in probe
    assert 'call_deferred("_subscribe_bound_actor")' in probe
    assert 'call_deferred("_observe_initial_projection")' in probe
    assert "world_result_received.emit" not in probe
    assert "final_presentation_state_invalid" not in probe
    assert "trusted-local-adventure-basic-live-probe-commit" in verifier
    assert "ensure_backend" in verifier
    assert "live-adventure-basic-mirror-{scenario_id}-runtime.json" in verifier
    assert 'runtime.get("resync_required") is False' in verifier
    assert '"scenario-1"' in verifier and '"scenario-5"' in verifier
