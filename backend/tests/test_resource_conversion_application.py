"""Resource conversion application boundary checks."""
from types import SimpleNamespace

from app import main
from app.gameplay.event_store import DurableGameplayEventStore
from app.gameplay.resource_body_runtime import ResourceBodyRuntimeProjector
from app.services.websocket_session_auth_service import WebSocketConnectionContext
from app.ws_protocol import Envelope
from test_resource_conversion_service import _command, _setup


def test_resource_conversion_rechecks_live_timeline_before_append(tmp_path, monkeypatch):
    store, auth, _, projection = _setup(tmp_path)
    driver = SimpleNamespace(
        world_runtime=SimpleNamespace(mode=SimpleNamespace(world_ref="world:bakery")),
        clock=SimpleNamespace(timeline=SimpleNamespace(timeline_id="timeline:main")),
    )
    monkeypatch.setattr(main, "gameplay_event_store", store, raising=False)
    monkeypatch.setattr(main, "embodied_controller_auth_service", auth, raising=False)
    monkeypatch.setattr(main, "_population_runtime_driver", driver, raising=False)
    capability_reads = 0

    def capability(principal, actor, revision):
        nonlocal capability_reads
        capability_reads += 1
        if capability_reads == 2:
            driver.clock.timeline.timeline_id = "timeline:changed"
        return True

    monkeypatch.setattr(main, "resource_conversion_capability_resolver", capability, raising=False)
    before = len(store.read_events())
    try:
        result = main._handle_envelope(
            Envelope(message_type="resource_conversion", payload=_command(projection).model_dump(mode="json")),
            connection_context=WebSocketConnectionContext(
                remote_host="127.0.0.1", observed_at=2, connection_ref="connection:equipment",
            ),
        )[0]["payload"]
        assert result == {"accepted": False, "error_code": "resource_conversion_scope_conflict"}
        assert len(store.read_events()) == before
    finally:
        store.close()


def test_resource_conversion_default_denial_and_durable_response_recovery(tmp_path, monkeypatch):
    store, auth, _, projection = _setup(tmp_path)
    monkeypatch.setattr(main, "gameplay_event_store", store, raising=False)
    monkeypatch.setattr(main, "embodied_controller_auth_service", auth, raising=False)
    monkeypatch.setattr(main, "_population_runtime_driver", SimpleNamespace(
        world_runtime=SimpleNamespace(mode=SimpleNamespace(world_ref="world:bakery")),
        clock=SimpleNamespace(timeline=SimpleNamespace(timeline_id="timeline:main")),
    ))
    monkeypatch.setattr(main, "resource_conversion_capability_resolver", None)
    request = Envelope(message_type="resource_conversion", payload=_command(projection).model_dump(mode="json"))
    context = WebSocketConnectionContext(remote_host="127.0.0.1", observed_at=2,
                                         connection_ref="connection:equipment")

    def route():
        return main._handle_envelope(request, connection_context=context)[0]["payload"]

    reopened = None
    try:
        count = len(store.read_events())
        assert route() == {"accepted": False, "error_code": "resource_conversion_capability_required"}
        assert len(store.read_events()) == count
        monkeypatch.setattr(main, "resource_conversion_capability_resolver", lambda *args: True)
        first = route()
        assert first["accepted"], first
        count = len(store.read_events())
        expected = ResourceBodyRuntimeProjector().rebuild_resources(
            "char_a", store.read_stream("gameplay:resources:char_a"))
        store.close()
        reopened = DurableGameplayEventStore(tmp_path / "conversion.sqlite")
        monkeypatch.setattr(main, "gameplay_event_store", reopened)
        replay = route()
        assert replay["accepted"], replay
        assert replay["receipt"]["idempotency_status"] == "duplicate_replayed"
        assert replay["receipt"]["committed_event_ids"] == first["receipt"]["committed_event_ids"]
        assert len(reopened.read_events()) == count
        assert ResourceBodyRuntimeProjector().rebuild_resources(
            "char_a", reopened.read_stream("gameplay:resources:char_a")) == expected
    finally:
        (reopened or store).close()
