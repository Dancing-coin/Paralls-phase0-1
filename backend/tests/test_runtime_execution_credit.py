"""IPC 与原 owner 共用执行信用，结果等待不继续占执行额度。"""
import multiprocessing
from threading import Event

import pytest

from app.services.runtime_execution import RuntimeExecution, RuntimeQueueFull


def test_ipc_and_internal_owner_work_share_one_execution_capacity():
    credit = multiprocessing.get_context('spawn').BoundedSemaphore(3)
    entered, release = Event(), Event()
    execution = RuntimeExecution(execution_credit=credit)
    try:
        running = execution.submit(lambda: (entered.set(), release.wait(2)))
        assert entered.wait(1)
        # 两项已经进入 IPC，转交 owner 时不能重复获取信用。
        assert credit.acquire(False)
        assert credit.acquire(False)
        with pytest.raises(RuntimeQueueFull):
            execution.submit(lambda: '不应接纳')
        first = execution.submit_admitted(lambda: 'first')
        second = execution.submit_admitted(lambda: 'second')
        assert not credit.acquire(False)
        release.set()
        assert running.result(2)
        assert first.result(2) == 'first'
        assert second.result(2) == 'second'
        # 原结果仍被调用方持有，也不妨碍新完成授权命令获取信用。
        assert execution.submit(lambda: '授权').result(2) == '授权'
        assert all(credit.acquire(False) for _ in range(3))
        assert not credit.acquire(False)
    finally:
        release.set()
        execution.stop()


def test_cancelled_admitted_command_releases_once_and_reentrant_is_inline():
    credit = multiprocessing.get_context('spawn').BoundedSemaphore(2)
    entered, release = Event(), Event()
    execution = RuntimeExecution(execution_credit=credit)
    ran = []
    try:
        running = execution.submit(lambda: (entered.set(), release.wait(2),
            execution.submit(lambda: 'inline').result()))
        assert entered.wait(1)
        assert credit.acquire(False)
        cancelled = execution.submit_admitted(lambda: ran.append(True))
        assert cancelled.cancel()
        assert credit.acquire(False)
        credit.release()
        release.set()
        assert running.result(2)[2] == 'inline'
        assert execution.submit(lambda: 'barrier').result(2) == 'barrier'
        assert ran == []
        assert credit.acquire(False)
        assert credit.acquire(False)
        assert not credit.acquire(False)
    finally:
        release.set()
        execution.stop()


def reserve_in_child(credit, pipe):
    pipe.send(credit.acquire(False) and credit.acquire(False))
    pipe.recv()
    credit.release()
    credit.release()


def test_real_spawn_credit_is_shared_with_parent_owner():
    context = multiprocessing.get_context('spawn')
    credit = context.BoundedSemaphore(3)
    parent, child = context.Pipe()
    process = context.Process(target=reserve_in_child, args=(credit, child))
    process.start()
    entered, release = Event(), Event()
    execution = RuntimeExecution(execution_credit=credit)
    try:
        assert parent.poll(5) and parent.recv() is True
        running = execution.submit(lambda: (entered.set(), release.wait(3)))
        assert entered.wait(1)
        with pytest.raises(RuntimeQueueFull):
            execution.submit(lambda: '不应接纳')
        parent.send('release')
        process.join(3)
        assert process.exitcode == 0
        queued = execution.submit(lambda: 'child已释放')
        release.set()
        running.result(2)
        assert queued.result(2) == 'child已释放'
    finally:
        release.set()
        execution.stop()
        if process.is_alive():
            process.terminate()
            process.join(3)
        parent.close()
        child.close()


def test_execution_credit_snapshot_tracks_real_shared_current_and_peak():
    from app.services.runtime_execution import RuntimeExecutionCredit
    context = multiprocessing.get_context('spawn')
    credit = RuntimeExecutionCredit(3)
    parent, child = context.Pipe()
    process = context.Process(target=reserve_in_child, args=(credit, child))
    process.start()
    try:
        assert parent.poll(5) and parent.recv() is True
        assert credit.snapshot() == {'capacity': 3, 'current': 2, 'peak': 2}
        assert credit.acquire(False)
        assert not credit.acquire(False)
        assert credit.snapshot() == {'capacity': 3, 'current': 3, 'peak': 3}
        credit.release()
        parent.send('release')
        process.join(3)
        assert process.exitcode == 0
        assert credit.snapshot() == {'capacity': 3, 'current': 0, 'peak': 3}
        with pytest.raises(ValueError):
            credit.release()
        assert credit.snapshot()['current'] == 0
    finally:
        if process.is_alive():
            process.terminate()
            process.join(3)
        parent.close()
        child.close()


def test_credit_admission_and_snapshot_do_not_wait_on_shared_counter_lock():
    from threading import Thread
    from time import perf_counter
    from app.services.runtime_execution import RuntimeExecutionCredit
    credit = RuntimeExecutionCredit(2)
    entered, release = Event(), Event()
    def hold():
        with credit._counts.get_lock():
            entered.set()
            release.wait(2)
    thread = Thread(target=hold)
    thread.start()
    assert entered.wait(1)
    try:
        started = perf_counter()
        assert credit.acquire(False) is True
        credit.release()
        assert credit.snapshot() == {'capacity': 2, 'current': 0, 'peak': None}
        assert perf_counter() - started < .1
    finally:
        release.set()
        thread.join(2)
    assert credit.snapshot() == {'capacity': 2, 'current': 0, 'peak': None}


def hold_credit_statistics(credit, pipe):
    credit._counts.get_lock().acquire()
    pipe.send('held')
    pipe.recv()


def test_dead_statistics_lock_owner_cannot_block_execution_terminal():
    from app.services.runtime_execution import RuntimeExecutionCredit
    context = multiprocessing.get_context('spawn')
    credit = RuntimeExecutionCredit(2)
    execution = RuntimeExecution(execution_credit=credit)
    parent, child = context.Pipe()
    entered, release = Event(), Event()
    future = execution.submit(lambda: (entered.set(), release.wait(3), 'completed'))
    assert entered.wait(1)
    process = context.Process(target=hold_credit_statistics, args=(credit, child))
    process.start()
    try:
        assert parent.poll(5) and parent.recv() == 'held'
        process.terminate()
        process.join(3)
        release.set()
        assert future.result(2)[2] == 'completed'
        assert execution.stop(timeout_seconds=.5)
        assert execution.closed.done()
        assert credit.snapshot() == {'capacity': 2, 'current': 0, 'peak': None}
    finally:
        release.set()
        if process.is_alive():
            process.terminate()
            process.join(3)
        parent.close()
        child.close()

def test_short_statistics_contention_preserves_exact_peak():
    from threading import Thread
    from time import sleep
    from app.services.runtime_execution import RuntimeExecutionCredit
    credit = RuntimeExecutionCredit(3)
    entered, acquiring = Event(), Event()
    def hold():
        with credit._counts.get_lock():
            entered.set()
            assert acquiring.wait(1)
            sleep(.005)
    thread = Thread(target=hold)
    thread.start()
    assert entered.wait(1)
    try:
        acquiring.set()
        assert credit.acquire(False)
        thread.join(1)
        assert credit.acquire(False)
        credit.release()
        credit.release()
        assert credit.snapshot() == {'capacity': 3, 'current': 0, 'peak': 2}
    finally:
        acquiring.set()
        thread.join(1)


def test_snapshot_waits_for_short_contention_without_losing_real_peak():
    from threading import Thread
    from time import sleep
    from app.services.runtime_execution import RuntimeExecutionCredit
    credit = RuntimeExecutionCredit(3)
    assert credit.acquire(False)
    assert credit.acquire(False)
    credit.release()
    entered, reading = Event(), Event()
    def hold():
        with credit._counts.get_lock():
            entered.set()
            assert reading.wait(1)
            sleep(.005)
    thread = Thread(target=hold)
    thread.start()
    assert entered.wait(1)
    try:
        reading.set()
        assert credit.snapshot() == {'capacity': 3, 'current': 1, 'peak': 2}
    finally:
        reading.set()
        thread.join(1)
        credit.release()
