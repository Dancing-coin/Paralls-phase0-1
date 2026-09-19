from threading import Event, get_ident

import pytest

from app.services.runtime_execution import RuntimeExecution, RuntimeQueueFull, RuntimeStopped


def test_fifo_owner_reentrant_and_exceptions():
    execution = RuntimeExecution(max_pending=4)
    seen = []
    try:
        owner = execution.submit(get_ident).result(timeout=2)
        assert owner != get_ident()
        nested = execution.submit(lambda: execution.submit(get_ident).result()).result(timeout=2)
        assert nested == owner
        futures = [execution.submit(lambda i=i: seen.append((i, get_ident()))) for i in range(3)]
        for future in futures:
            future.result(timeout=2)
        assert seen == [(i, owner) for i in range(3)]
        def fail():
            raise ValueError('private input must not appear')
        with pytest.raises(ValueError):
            execution.submit(fail).result(timeout=2)
        assert execution.snapshot()['failure'] == 'ValueError'
        assert execution.snapshot()['state'] == 'unhealthy'
    finally:
        assert execution.stop(timeout_seconds=2)
    with pytest.raises(RuntimeStopped):
        execution.submit(get_ident)


def test_full_queue_timeout_drains_and_cannot_restart():
    execution = RuntimeExecution(max_pending=1)
    entered, release = Event(), Event()
    def blocked():
        entered.set()
        release.wait(3)
    first = execution.submit(blocked)
    assert entered.wait(2)
    second = execution.submit(get_ident)
    try:
        with pytest.raises(RuntimeQueueFull):
            execution.submit(get_ident)
        assert not execution.stop(timeout_seconds=0.01)
        assert execution.snapshot()['state'] == 'unhealthy'
        with pytest.raises(RuntimeStopped):
            execution.submit(get_ident)
    finally:
        release.set()
        assert execution.stop(timeout_seconds=2)
    first.result(timeout=1)
    assert second.result(timeout=1) != get_ident()


def test_stop_finalizer_runs_on_owner_after_full_queue_drains():
    entered, release = Event(), Event()
    order = []
    execution = RuntimeExecution(max_pending=1, on_stop=lambda: order.append(('close', get_ident())))
    def block():
        entered.set()
        release.wait(2)
        order.append(('first', get_ident()))
    first = execution.submit(block)
    assert entered.wait(1)
    second = execution.submit(lambda: order.append(('second', get_ident())))
    try:
        assert not execution.stop(timeout_seconds=0.01)
    finally:
        release.set()
        assert execution.stop(timeout_seconds=2)
    assert [kind for kind, _ in order] == ['first', 'second', 'close']
    assert len({owner for _, owner in order}) == 1


def test_accepted_command_can_reenter_while_stop_drains():
    entered, release = Event(), Event()
    execution = RuntimeExecution()
    def command():
        entered.set()
        release.wait(2)
        return execution.submit(get_ident).result()
    future = execution.submit(command)
    assert entered.wait(1)
    try:
        assert not execution.stop(timeout_seconds=0.01)
    finally:
        release.set()
        assert execution.stop(timeout_seconds=2)
    assert future.result(timeout=1) != get_ident()
