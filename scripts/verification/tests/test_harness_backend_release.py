from __future__ import annotations

import socket
import sys
import time
from types import SimpleNamespace

import pytest

import common


def test_free_endpoint_is_observed_without_slow_process_inventory(monkeypatch):
    clock = [0.]
    def sleep(seconds):
        clock[0] += seconds
    def slow_inventory(port):
        clock[0] += 16.
        return None
    observations = []
    def refused(address, timeout):
        observations.append((address, timeout))
        raise ConnectionRefusedError()
    monkeypatch.setattr(common, 'time', SimpleNamespace(time=lambda: clock[0], monotonic=lambda: clock[0], sleep=sleep))
    monkeypatch.setattr(common, 'get_health', lambda: None)
    monkeypatch.setattr(common, '_find_listener_pid', slow_inventory)
    monkeypatch.setattr(socket, 'create_connection', refused)
    assert common.wait_for_backend_release(port=43210)
    assert len(observations) == 2 and all(address == ('127.0.0.1', 43210) for address, _ in observations)
    assert clock[0] < 15.


@pytest.mark.parametrize('error', [TimeoutError(), PermissionError(), OSError('unavailable')])
def test_uncertain_probe_is_not_reported_as_released(monkeypatch, error):
    clock = [0.]
    def sleep(seconds):
        clock[0] += seconds
    def probe(address, timeout):
        clock[0] += timeout
        raise error
    monkeypatch.setattr(common, 'time', SimpleNamespace(time=lambda: clock[0], monotonic=lambda: clock[0], sleep=sleep))
    monkeypatch.setattr(socket, 'create_connection', probe)
    monkeypatch.setattr(common, 'get_health', lambda: None)
    monkeypatch.setattr(common, '_find_listener_pid', lambda port: None)
    assert not common.wait_for_backend_release(timeout_seconds=.25)
    assert clock[0] <= .25


def test_reoccupied_endpoint_resets_consecutive_clear_observations(monkeypatch):
    clock = [0.]
    outcomes = iter([False, True, False, False])
    connections = []
    def sleep(seconds):
        clock[0] += seconds
    def probe(address, timeout):
        occupied = next(outcomes)
        connections.append(occupied)
        if not occupied:
            raise ConnectionRefusedError()
        class Connection:
            def __enter__(self): return self
            def __exit__(self, *args): pass
        return Connection()
    monkeypatch.setattr(common, 'time', SimpleNamespace(time=lambda: clock[0], monotonic=lambda: clock[0], sleep=sleep))
    monkeypatch.setattr(socket, 'create_connection', probe)
    monkeypatch.setattr(common, 'get_health', lambda: None)
    monkeypatch.setattr(common, '_find_listener_pid', lambda port: None)
    assert common.wait_for_backend_release()
    assert connections == [False, True, False, False]


def test_non_http_listener_is_not_released_or_terminated():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        listener.listen(16)
        port = listener.getsockname()[1]
        assert not common.wait_for_backend_release(port=port, timeout_seconds=.25)
        with socket.create_connection(('127.0.0.1', port), timeout=1):
            pass
    assert common.wait_for_backend_release(port=port)


def test_stopping_owned_listener_releases_endpoint(tmp_path):
    port_path = tmp_path / 'port.txt'
    code = (
        "import socket,sys,time\n"
        "from pathlib import Path\n"
        "s=socket.socket();s.bind(('127.0.0.1',0));s.listen(16)\n"
        "ready=Path(sys.argv[1]);pending=ready.with_suffix('.tmp')\n"
        "pending.write_text(str(s.getsockname()[1]));pending.replace(ready)\n"
        "time.sleep(30)\n"
    )
    with common.OwnedProcess([sys.executable, '-c', code, str(port_path)]) as owner:
        deadline = time.monotonic() + 10
        while not port_path.exists():
            assert owner.process.poll() is None and time.monotonic() < deadline
            time.sleep(.01)
        port = int(port_path.read_text())
        assert not common.wait_for_backend_release(port=port, timeout_seconds=.25)
        common.stop_backend(owner.process)
        assert owner.process.poll() is not None
        assert common.wait_for_backend_release(port=port)


def test_late_refusal_does_not_pass_after_deadline(monkeypatch):
    clock = [0.]
    def probe(address, timeout):
        clock[0] += 2.
        raise ConnectionRefusedError()
    monkeypatch.setattr(common, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    monkeypatch.setattr(socket, 'create_connection', probe)
    assert not common.wait_for_backend_release(timeout_seconds=1., clear_observations_required=1)
