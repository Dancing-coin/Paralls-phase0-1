import pytest
from types import SimpleNamespace
from app import main
from app.gameplay.event_store import DurableGameplayEventStore
from app.services.siming_audit_writer import SqliteSimingAuditWriter


@pytest.mark.parametrize('reset', [False, True])
@pytest.mark.parametrize('failure', [False, True])
def test_main_closes_gameplay_before_replacement_or_lease_release(tmp_path, monkeypatch, reset, failure):
    store = DurableGameplayEventStore(tmp_path / 'owned.sqlite3')
    closed = []
    original = store.close
    def close():
        closed.append('store')
        if failure: raise OSError('store close failed')
        original()
    monkeypatch.setattr(store, 'close', close)
    for name in ('character_agent_runtime', 'heavenly_graph', 'harness_execution_trace', 'harness_capability_store'):
        monkeypatch.setattr(main, name, None, raising=False)
    monkeypatch.setattr(main, '_mirror_transport_routes', {})
    monkeypatch.setattr(main, '_close_character_continuations', lambda **_: None)
    monkeypatch.setattr(main, '_close_failed_runtime_resources', lambda: None)
    monkeypatch.setattr(main, 'gameplay_event_store', store, raising=False)
    lease = SimpleNamespace(close=lambda: closed.append('lease'))
    monkeypatch.setattr(main, '_runtime_storage_lease', lease)
    def stop_after_replacement(*args): raise LookupError('replacement reached')
    monkeypatch.setattr(main, 'build_production_package_registry', stop_after_replacement)
    try:
        if failure:
            with pytest.raises(OSError, match='store close failed'):
                (main._reset_runtime_state if reset else main.close_runtime_resources)()
            assert main._runtime_storage_lease is lease
            assert main.gameplay_event_store is store
            assert closed == ['store']
        elif reset:
            with pytest.raises(LookupError, match='replacement reached'): main._reset_runtime_state()
            assert main.gameplay_event_store is not store
            assert closed == ['store']
        else:
            main.close_runtime_resources()
            assert closed == ['store', 'lease']
            assert main._runtime_storage_lease is None
    finally: original()


def test_main_closes_siming_audit_before_replacement_can_fail(tmp_path, monkeypatch):
    writer = SqliteSimingAuditWriter(tmp_path / "audit.sqlite3")
    closed = []
    original = writer.close

    def close():
        closed.append("audit")
        original()

    monkeypatch.setattr(writer, "close", close)
    for name in ("character_agent_runtime", "heavenly_graph", "harness_execution_trace", "harness_capability_store"):
        monkeypatch.setattr(main, name, None, raising=False)
    monkeypatch.setattr(main, "_mirror_transport_routes", {})
    monkeypatch.setattr(main, "_close_character_continuations", lambda **_: None)
    monkeypatch.setattr(main, "_close_failed_runtime_resources", lambda: None)
    monkeypatch.setattr(main, "siming_audit_writer", writer, raising=False)
    monkeypatch.setattr(main, "gameplay_event_store", None, raising=False)
    monkeypatch.setattr(
        main,
        "build_production_package_registry",
        lambda *_: (_ for _ in ()).throw(LookupError("replacement reached")),
    )

    with pytest.raises(LookupError, match="replacement reached"):
        main._reset_runtime_state()

    assert closed == ["audit"]
