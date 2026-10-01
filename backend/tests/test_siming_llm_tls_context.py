from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Barrier, Event, Thread
from types import SimpleNamespace
import ssl

import certifi
import httpx
import pytest

from app.services.siming_llm_provider import (
    HttpSimingLlmCandidateProvider,
    SimingLlmProviderError,
    SimingLlmProviderTimeout,
)
from app.services.dialogue_continuation import DialogueProviderSlots


def make_provider(key="dummy-a"):
    return HttpSimingLlmCandidateProvider(api_key=key, endpoint="https://provider.invalid/responses",
        model="dummy", timeout_seconds=1.75)


@pytest.fixture
def offline_http(monkeypatch):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("SSL_CERT_DIR", raising=False)
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(name, raising=False)
    state = SimpleNamespace(clients=[], verify=[], requests=[], contexts=[], ca_options=[], error=None)
    client_init = httpx.Client.__init__
    context_factory = ssl.create_default_context

    def create_context(*args, **kwargs):
        context = context_factory(*args, **kwargs)
        state.ca_options.append(kwargs)
        state.contexts.append(context)
        return context

    def create_client(client, *args, **kwargs):
        state.verify.append(kwargs.get("verify", True))
        client_init(client, *args, **kwargs)
        state.clients.append(client)

    def handle_request(transport, request):
        state.requests.append(request)
        if state.error == "timeout":
            raise httpx.ReadTimeout("controlled timeout", request=request)
        return httpx.Response(500 if state.error == "http" else 200,
            headers={"set-cookie": "provider_session=first; Path=/", "x-request-id": "dummy-request"},
            json={"accepted": True}, request=request)

    # 仅替换网络发送；真实 Client、transport、证书加载、cookie 处理和关闭仍执行。
    monkeypatch.setattr(ssl, "create_default_context", create_context)
    monkeypatch.setattr(httpx.Client, "__init__", create_client)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", handle_request)
    return state


def test_sequential_posts_reuse_one_verified_context_but_close_each_client(offline_http):
    provider = make_provider()
    results = [provider._post_json({"ordinal": index}) for index in range(3)]

    assert len(offline_http.contexts) == 1
    assert all(context is offline_http.contexts[0] for context in offline_http.verify)
    assert offline_http.contexts[0].verify_mode == ssl.CERT_REQUIRED
    assert offline_http.contexts[0].check_hostname is True
    assert offline_http.contexts[0].cert_store_stats()["x509_ca"] > 0
    assert len(offline_http.clients) == 3
    assert len({id(client) for client in offline_http.clients}) == 3
    assert all(client.is_closed for client in offline_http.clients)
    assert all(result[0] == {"accepted": True} and result[1] == "dummy-request" for result in results)


def test_concurrent_first_posts_construct_only_one_context(offline_http):
    provider = make_provider()
    barrier = Barrier(4)

    def call(index):
        barrier.wait(timeout=5)
        return provider._post_json({"ordinal": index})

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(call, range(4)))

    assert len(offline_http.contexts) == 1
    assert all(context is offline_http.contexts[0] for context in offline_http.verify)
    assert len(results) == 4
    assert len(offline_http.clients) == 4
    assert all(client.is_closed for client in offline_http.clients)


def test_context_is_lazy_and_isolated_between_providers(offline_http):
    first, second = make_provider("dummy-a"), make_provider("dummy-b")
    assert offline_http.contexts == []
    assert offline_http.clients == []

    first._post_json({"same": True})
    second._post_json({"same": True})
    first._post_json({"same": True})

    assert len(offline_http.contexts) == 2
    assert offline_http.verify[0] is offline_http.verify[2]
    assert offline_http.verify[0] is not offline_http.verify[1]
    assert [request.headers["authorization"] for request in offline_http.requests] == [
        "Bearer dummy-a", "Bearer dummy-b", "Bearer dummy-a",
    ]
    assert all("cookie" not in request.headers for request in offline_http.requests)
    assert all(request.extensions["timeout"] == dict(connect=1.75, read=1.75, write=1.75, pool=1.75)
               for request in offline_http.requests)
    assert all(client.is_closed for client in offline_http.clients)


@pytest.mark.parametrize("ca_error", ["missing", "invalid"])
def test_failed_context_initialization_can_retry(offline_http, monkeypatch, tmp_path, ca_error):
    provider = make_provider()
    ca_path = tmp_path / "invalid-ca.pem"
    if ca_error == "invalid":
        ca_path.write_text("not a certificate", encoding="ascii")
    monkeypatch.setenv("SSL_CERT_FILE", str(ca_path))
    with pytest.raises(FileNotFoundError if ca_error == "missing" else ssl.SSLError):
        provider._post_json({"same": True})
    assert offline_http.requests == []

    monkeypatch.delenv("SSL_CERT_FILE")
    provider._post_json({"same": True})
    provider._post_json({"same": True})

    assert len(offline_http.contexts) == 1
    assert len(offline_http.requests) == 2
    assert all(context is offline_http.contexts[0] for context in offline_http.verify)


@pytest.mark.parametrize("ca_source", ["file_over_directory", "directory", "default"])
def test_context_preserves_ca_environment_precedence(offline_http, monkeypatch, tmp_path, ca_source):
    provider = make_provider()
    if ca_source == "file_over_directory":
        monkeypatch.setenv("SSL_CERT_FILE", certifi.where())
        monkeypatch.setenv("SSL_CERT_DIR", str(tmp_path / "ignored-directory"))
        expected = {"cafile": certifi.where()}
    elif ca_source == "directory":
        monkeypatch.setenv("SSL_CERT_DIR", str(tmp_path))
        expected = {"capath": str(tmp_path)}
    else:
        expected = {"cafile": certifi.where()}

    provider._post_json({"same": True})
    provider._post_json({"same": True})

    assert offline_http.ca_options == [expected]
    context = offline_http.verify[0]
    assert isinstance(context, ssl.SSLContext)
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.check_hostname is True
    if ca_source != "directory":
        assert context.cert_store_stats()["x509_ca"] > 0


def test_ca_environment_change_applies_when_provider_is_rebuilt(offline_http, monkeypatch, tmp_path):
    replacement_ca = tmp_path / "replacement-ca.pem"
    replacement_ca.write_bytes(Path(certifi.where()).read_bytes())
    original = make_provider()
    original._post_json({"same": True})
    monkeypatch.setenv("SSL_CERT_FILE", str(replacement_ca))
    original._post_json({"same": True})
    replacement = make_provider()
    replacement._post_json({"same": True})

    assert offline_http.ca_options == [{"cafile": certifi.where()}, {"cafile": str(replacement_ca)}]
    assert offline_http.verify[0] is offline_http.verify[1]
    assert offline_http.verify[0] is not offline_http.verify[2]


@pytest.mark.parametrize("error,expected", [("timeout", SimingLlmProviderTimeout), ("http", SimingLlmProviderError)])
def test_transport_errors_keep_context_and_close_temporary_client(offline_http, error, expected):
    provider = make_provider()
    offline_http.error = error
    for _ in range(2):
        with pytest.raises(expected):
            provider._post_json({"same": True})

    assert len(offline_http.contexts) == 1
    assert all(client.is_closed for client in offline_http.clients)
    assert all(request.extensions["timeout"]["read"] == 1.75 for request in offline_http.requests)


def test_cancelled_slots_wait_for_real_http_completion_and_close_clients(monkeypatch):
    release = Event()
    started = [Event() for _ in range(4)]
    clients = []
    client_init = httpx.Client.__init__

    def create_client(client, *args, **kwargs):
        client_init(client, *args, **kwargs)
        clients.append(client)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            started[payload["ordinal"]].set()
            if not release.wait(10):
                return
            raw = b'{"accepted":true}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass

    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    monkeypatch.setattr(httpx.Client, "__init__", create_client)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    provider = HttpSimingLlmCandidateProvider(api_key="dummy-local",
        endpoint=f"http://127.0.0.1:{server.server_port}", model="dummy", timeout_seconds=10)
    pool = DialogueProviderSlots()
    slots, futures, cancellations = [], [], []

    def run(index, provider, cancelled, emit):
        return provider._post_json({"ordinal": index})

    try:
        for index in range(4):
            slot = pool.acquire()
            slots.append(slot)
            cancelled = Event()
            cancellations.append(cancelled)
            futures.append(slot.submit(index, provider, cancelled, None, runner=run))
        assert all(signal.wait(5) for signal in started)
        for slot, cancelled in zip(slots, cancellations):
            cancelled.set()
            slot.close()
        assert pool.acquire() is None
        assert all(not future.done() for future in futures)
        release.set()
        assert all(future.result(5)[0] == {"accepted": True} for future in futures)
        assert len(clients) == 4
        assert all(client.is_closed for client in clients)
        pool._executor.shutdown(wait=True)
        replacement = pool.acquire()
        assert replacement is not None
        replacement.close()
    finally:
        release.set()
        for slot in slots:
            slot.close()
        pool._executor.shutdown(wait=True)
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
