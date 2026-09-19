from contextlib import ExitStack
import json

import pytest

from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.gateway.model_provider import CharacterModelProvider
from scripts.verification.population_mixed_provider import MixedProviderProbe


def request():
    return json.dumps(dict(task_kind="dialogue_generation", context={}, route=dict(provider_kind="local"),
        prompt={}, policy={})).encode()


def test_local_or_invalid_character_output_is_never_qualified_provider_success():
    rows = []
    probe = MixedProviderProbe(rows.append)
    gateway = CharacterModelGateway(provider=CharacterModelProvider(provider_kind="local"))
    with ExitStack() as stack:
        probe.install(stack)
        gateway.complete_prepared_request(request())
        list(gateway.stream_prepared_request(request(), cancelled=lambda: False))
        gateway._provider._offline_complete = lambda _: dict(content="", tone="neutral")
        with pytest.raises(ValueError):
            gateway.complete_prepared_request(request())
    calls = [row for row in rows if row["type"] == "provider_result"]
    assert len(calls) == 3 and [row["validated"] for row in calls] == [True, True, False]
    assert all(not row["qualified_success"] and row["fallback_used"] for row in calls)
    assert probe.active == 0 and probe.peak_active == 1
    assert all("request_sha256" in row and "content" not in json.dumps(row) for row in calls)


def test_disabled_siming_completion_has_original_call_proof_but_no_live_success():
    from app.models.siming_event import FairnessStateSnapshot
    from app.models.visual_fact import VisualFactEvent
    from app.services.phase0_authority_event_adapter import Phase0AuthorityEventAdapter
    from app.services.siming_continuation import SimingProviderRequest, SimingProviderCompletion, run_siming_provider
    from app.services.siming_llm_provider import DisabledSimingLlmCandidateProvider
    from scripts.verification.population_mixed_provider import _hash
    snapshot = FairnessStateSnapshot(snapshot_id='snapshot:1', room_id='room_demo', scene_id='scene_demo',
        zone_id='zone_focus', causation_id='source:1', correlation_id='mixed:siming:1')
    event = Phase0AuthorityEventAdapter().visual_fact_event(VisualFactEvent(actor_id='char_c', room_id='room_demo',
        scene_id='scene_demo', zone_id='zone_focus', producer_ts=1, fact_type='light_level_drop'))
    rows = []
    probe = MixedProviderProbe(rows.append)
    with ExitStack() as stack:
        probe.install(stack)
        for stage in ('candidate', 'adaptive'):
            request = SimingProviderRequest(stage=stage, event=event, snapshot=snapshot, compiled_context={})
            completion = SimingProviderCompletion.model_validate_json(
                run_siming_provider(DisabledSimingLlmCandidateProvider(), request.model_dump_json().encode()))
            assert completion.error == ''
            assert len(rows) == (1 if stage == 'candidate' else 2)
            row = rows[-1]
            kwargs = (dict(snapshot=request.snapshot, recent_events=[request.event], recent_audit=[]) if stage == 'candidate'
                else dict(compiled_context={}, correlation_id=request.event.correlation_id))
            assert row['request_sha256'] == _hash(kwargs)
            assert row['output_sha256'] == _hash(completion.candidates if stage == 'candidate' else completion.proposal_batch)
            assert row['family'] == 'siming' and row['stage'] == stage and row['validated'] is True
            assert row['qualified_success'] is False and row['transport_attempted'] is False
            assert row['transport_succeeded'] is False and row['provider_kind'] == 'disabled'
    assert probe.active == 0 and probe.peak_active == 1


def test_scheduled_timeout_targets_one_siming_transport_call_and_then_releases(monkeypatch):
    from app.services.siming_llm_provider import HttpSimingLlmCandidateProvider, SimingLlmProviderTimeout
    from app.models.siming_event import FairnessStateSnapshot
    from app.models.visual_fact import VisualFactEvent
    from app.services.phase0_authority_event_adapter import Phase0AuthorityEventAdapter
    provider = HttpSimingLlmCandidateProvider(api_key="not-logged", endpoint="https://test.invalid", model="test", timeout_seconds=1)
    calls = []
    def transport(self, payload):
        calls.append(payload)
        return dict(output_text=json.dumps(dict(candidates=[]))), "request:test", 1, "a" * 64
    monkeypatch.setattr(HttpSimingLlmCandidateProvider, "_post_json", transport)
    rows = []
    probe = MixedProviderProbe(rows.append)
    snapshot = FairnessStateSnapshot(snapshot_id="snapshot:1", room_id="room_demo", scene_id="scene_demo",
        zone_id="zone_focus", causation_id="source:1", correlation_id="mixed:siming:1")
    event = Phase0AuthorityEventAdapter().visual_fact_event(VisualFactEvent(actor_id="char_c", room_id="room_demo",
        scene_id="scene_demo", zone_id="zone_focus", producer_ts=1, fact_type="light_level_drop"))
    kwargs = dict(snapshot=snapshot, recent_events=[event], recent_audit=[])
    with ExitStack() as stack:
        probe.install(stack)
        probe.arm_timeout("fault:1")
        with pytest.raises(SimingLlmProviderTimeout):
            provider.generate_candidates(**kwargs)
        assert provider.generate_candidates(**kwargs) == []
    assert len(calls) == 1 and probe.active == 0
    results = [row for row in rows if row["type"] == "provider_result"]
    assert len(results) == 2 and results[0]["fault_key"] == "fault:1"
    assert results[0]["transport_attempted"] is False and results[0]["qualified_success"] is False
    assert results[1]["transport_succeeded"] is True and results[1]["validated"] is True
    assert results[1]["source_event_ids"] == [event.event_id]
    assert "not-logged" not in json.dumps(rows) and "output_text" not in json.dumps(rows)


def test_completed_stream_closed_by_real_consumer_is_successful_but_invalid_http_output_is_not():
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    class Handler(BaseHTTPRequestHandler):
        invalid = False
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if payload.get("stream"):
                raw = b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\ndata: [DONE]\n\n'
            else:
                content = dict(content="" if self.invalid else "hello", tone="neutral")
                raw = json.dumps(dict(choices=[dict(message=dict(content=json.dumps(content)))])).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    provider = CharacterModelProvider(provider_kind="openai_compatible", endpoint_url=f"http://127.0.0.1:{server.server_port}",
        model_name="local-protocol-test", api_key="never-log-test-key")
    gateway = CharacterModelGateway(provider=provider)
    frozen = json.loads(request())
    frozen["route"]["provider_kind"] = "openai_compatible"
    frozen = json.dumps(frozen).encode()
    rows = []
    probe = MixedProviderProbe(rows.append)
    try:
        with ExitStack() as stack:
            probe.install(stack)
            generator = gateway.stream_prepared_request(frozen, cancelled=lambda: False)
            for event in generator:
                if event["event"] == "completed":
                    break
            generator.close()
            Handler.invalid = True
            with pytest.raises(ValueError):
                gateway.complete_prepared_request(frozen)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert [row["qualified_success"] for row in rows] == [True, False]
    assert all(row["transport_succeeded"] for row in rows) and probe.active == 0
    assert rows[0]["error"] is None and rows[1]["error"] == "ValueError"
    assert "never-log-test-key" not in json.dumps(rows) and "hello" not in json.dumps(rows)

@pytest.mark.parametrize('failure', ['http503', 'invalid_stream'])
def test_failed_character_stream_records_actual_transport_attempt_without_leaking_body(failure):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    from urllib.error import HTTPError
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            calls.append(True)
            self.rfile.read(int(self.headers['Content-Length']))
            raw = b'data: invalid-private-body\n\n'
            self.send_response(503 if failure == 'http503' else 200)
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    provider = CharacterModelProvider(provider_kind='openai_compatible', endpoint_url=f'http://127.0.0.1:{server.server_port}',
        model_name='stream-failure-test', api_key='private-test-key')
    gateway = CharacterModelGateway(provider=provider)
    frozen = json.loads(request())
    frozen['route']['provider_kind'] = 'openai_compatible'
    rows = []
    probe = MixedProviderProbe(rows.append)
    try:
        with ExitStack() as stack:
            probe.install(stack)
            with pytest.raises(HTTPError if failure == 'http503' else ValueError):
                list(gateway.stream_prepared_request(json.dumps(frozen).encode(), cancelled=lambda: False))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert calls == [True] and probe.active == 0
    row, = rows
    assert row['transport_attempted'] is True
    assert row['transport_succeeded'] is False and row['qualified_success'] is False and row['validated'] is False
    assert (row['provider_kind'], row['model'], row['endpoint_host']) == ('openai_compatible', 'stream-failure-test', '127.0.0.1')
    assert 'private-test-key' not in json.dumps(rows) and 'invalid-private-body' not in json.dumps(rows)
