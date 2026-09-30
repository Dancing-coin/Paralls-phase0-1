from test_character_cognition_coordinator import setup


def _advance_to_l3_ready(rt, coordinator, child, handle):
    coordinator.begin_entry(child.child_key, activation=handle, now=110.0)
    coordinator.resume_entry(child.child_key, activation=handle, now=111.0)
    for stage in ("l2", "l3"):
        pending = getattr(coordinator, f"prepare_{stage}")(child.child_key, activation=handle, now=112.0)
        gateway = rt._l2._gateway if stage == "l2" else rt._l3._gateway
        output = gateway.complete_prepared_request(pending.request_json.encode())
        getattr(coordinator, f"accept_{stage}")(child.child_key, activation=handle, now=113.0, output=output)
        getattr(coordinator, f"freeze_{stage}")(child.child_key, activation=handle, now=114.0)
        ready = getattr(coordinator, f"resume_{stage}")(child.child_key, activation=handle, now=115.0)
    return ready


def test_durable_siming_execution_command_carries_canonical_contract(tmp_path):
    rt, _admissions, coordinator, child, handle = setup(tmp_path)
    ready = _advance_to_l3_ready(rt, coordinator, child, handle)

    planned = coordinator.freeze_execution(child.child_key, activation=handle, now=116.0)
    commands = planned.plan["after"]["commands"]

    assert len(commands) == 1
    contract = commands[0]["execution_payload"]["execution_contract"]
    assert contract["turn_id"] == f"turn:{child.actor_id}:{child.payload['message_id']}"
    assert contract["actor_ref"] == f"character:{child.actor_id}"
    assert contract["idempotency_key"] == f"execution:{contract['turn_id']}"
    assert contract["causation_id"] == child.payload["causation_id"]
    assert contract["correlation_id"] == child.payload["correlation_id"]

    rt.close()
from types import SimpleNamespace


def test_empty_canonical_siming_egress_fails_closed(tmp_path, monkeypatch):
    import app.main as main
    from app.models.character_agent_runtime import CharacterGoalCommand

    class Store:
        def __init__(self):
            self.receipts = {}
        def read_receipt(self, actor_id, *, kind, key):
            return self.receipts.get((actor_id, kind, key))
        def save_receipt(self, actor_id, *, kind, key, receipt):
            self.receipts[(actor_id, kind, key)] = receipt

    class Sink:
        def __init__(self):
            self.calls = 0
        def post(self, payload):
            self.calls += 1
            return True

    store = Store()
    sink = Sink()
    origin = SimpleNamespace(connection_ref="connection:test", binding_pin=("session:test", "epoch:test", 1))
    routes = SimpleNamespace(
        resolve=lambda _causation: origin,
        connections={origin.connection_ref: sink},
    )
    command = CharacterGoalCommand(
        actor_id="char_b", command_type="observe", ttl_ms=1000, causation_id="cause:test", correlation_id="corr:test", producer_ts=300,
        execution_payload={"actor_id": "char_b", "action_request_bundle": {"requested_actions": []}},
    )
    entry = SimpleNamespace(
        child_key="child:test", actor_id="char_b", source_event={"causation_id": "siming:test"},
    )
    progress = SimpleNamespace(
        progress_digest="sha256:progress", frame={"commands": [command.model_dump(mode="json")], "suggestion": None},
    )
    monkeypatch.setattr(main, "character_agent_runtime", SimpleNamespace(_session_store=store), raising=False)
    monkeypatch.setattr(main, "_cognition_output_routes", routes, raising=False)
    monkeypatch.setattr(main, "_cognition_origin_current", lambda *_args: True)

    main._complete_siming_character_transport(entry, progress)

    assert sink.calls == 0
    assert store.read_receipt("char_b", kind="cognition_output", key="child:test")["status"] == "handoff_started"
    assert store.read_receipt("char_b", kind="cognition_transport", key="child:test") == {
        "status": "not_sent", "reason": "execution_contract_missing", "sent_frames": 0,
    }


