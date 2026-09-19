"""单局运行时的有界、可重入写入执行域。"""
from concurrent.futures import Future
from queue import Empty, Full, Queue
from threading import Lock, Thread, current_thread, get_ident
from time import monotonic
from typing import Callable, TypeVar

T = TypeVar('T')


class RuntimeQueueFull(RuntimeError):
    pass


class RuntimeStopped(RuntimeError):
    pass


class RuntimeExecutionCredit:
    """跨 spawn 的执行额度与真实在途计数；结果关联/发送不占此额度。"""
    def __init__(self, capacity=128):
        from multiprocessing import get_context
        if capacity <= 0:
            raise ValueError('capacity must be positive')
        context = get_context('spawn')
        self.capacity = capacity
        self._semaphore = context.BoundedSemaphore(capacity)
        self._counts = context.Array('q', [0, 0])
        self._statistics_failed = context.Semaphore(0)

    def acquire(self, block=False):
        lock = self._counts.get_lock()
        # 短争用等待统计提交；失主仍有硬截止，不能阻塞唯一 owner。
        observed = lock.acquire(timeout=.02)
        try:
            if not self._semaphore.acquire(block):
                return False
            if observed:
                self._counts[0] += 1
                self._counts[1] = max(self._counts[1], self._counts[0])
            else:
                self._statistics_failed.release()
            return True
        finally:
            if observed:
                lock.release()

    def release(self):
        lock = self._counts.get_lock()
        # 短争用等待统计提交；失主仍有硬截止，不能阻塞唯一 owner。
        observed = lock.acquire(timeout=.02)
        try:
            # OS semaphore 才是容量权威；统计锁失主不能阻止原命令终结。
            self._semaphore.release()
            if observed:
                self._counts[0] -= 1
            else:
                self._statistics_failed.release()
        finally:
            if observed:
                lock.release()

    def snapshot(self):
        lock = self._counts.get_lock()
        # 与更新共享短截止；读到一致值，失主时仍返回未知而不堵住 transport。
        if not lock.acquire(timeout=.02):
            return dict(capacity=self.capacity, current=self.capacity - self._semaphore.get_value(), peak=None)
        try:
            current = self.capacity - self._semaphore.get_value()
            peak = None if self._statistics_failed.get_value() else self._counts[1]
            return dict(capacity=self.capacity, current=current, peak=peak)
        finally:
            lock.release()


class RuntimeExecution:
    def __init__(self, max_pending: int = 128, *, on_stop: Callable[[], None] | None = None,
                 execution_credit=None):
        if max_pending <= 0:
            raise ValueError('max_pending must be positive')
        self._queue = Queue(maxsize=max_pending)
        self._execution_credit = execution_credit
        self._lock = Lock()
        self._accepting = True
        self._failure = None
        self._queue_wait_ms = self._service_ms = 0.0
        self._owner = None
        self._on_stop = on_stop or (lambda: None)
        self.closed: Future[None] = Future()
        self._thread = Thread(target=self._run, name='runtime-owner', daemon=True)
        self._thread.start()

    def submit(self, fn: Callable[[], T]) -> Future[T]:
        return self._submit(fn, transferred=False)

    def submit_admitted(self, fn: Callable[[], T]) -> Future[T]:
        """转交已经占用 IPC 执行信用的命令；失败时信用仍属于调用者。"""
        if self._execution_credit is None or current_thread() is self._thread:
            raise ValueError('runtime_admitted_credit_required')
        return self._submit(fn, transferred=True)

    def _submit(self, fn, *, transferred):
        future = Future()
        with self._lock:
            # 排空期间已接纳命令的同步回调仍属于同一命令，不算外部新任务。
            if current_thread() is not self._thread:
                if not self._accepting:
                    raise RuntimeStopped('runtime_stopped')
                credit = self._execution_credit
                if credit is not None and not transferred and not credit.acquire(False):
                    raise RuntimeQueueFull('runtime_queue_full')
                try:
                    self._queue.put_nowait((fn, future, monotonic()))
                except Full:
                    if credit is not None and not transferred:
                        credit.release()
                    raise RuntimeQueueFull('runtime_queue_full') from None
                if credit is not None:
                    # Future 的首次 result/error/cancel 终态只触发一次；不等 socket 发送。
                    future.add_done_callback(lambda _: credit.release())
                return future
        self._execute(fn, future, monotonic())
        return future

    def _execute(self, fn, future, queued_at):
        started = monotonic()
        if not future.set_running_or_notify_cancel():
            return
        try:
            future.set_result(fn())
        except BaseException as exc:
            with self._lock:
                self._failure = type(exc).__name__
            future.set_exception(exc)
        finally:
            with self._lock:
                self._queue_wait_ms = (started - queued_at) * 1000
                self._service_ms = (monotonic() - started) * 1000

    def _run(self):
        self._owner = get_ident()
        try:
            self._drain()
        finally:
            # 终结器不占队列额度；即使队列已满也会在排空后由 owner 关闭资源。
            self._execute(self._on_stop, self.closed, monotonic())

    def _drain(self):
        while True:
            try:
                fn, future, queued_at = self._queue.get(timeout=0.05)
            except Empty:
                with self._lock:
                    if not self._accepting and self._queue.empty():
                        return
                continue
            try:
                self._execute(fn, future, queued_at)
            finally:
                self._queue.task_done()

    def stop(self, *, timeout_seconds: float = 10.0) -> bool:
        with self._lock:
            self._accepting = False
        if get_ident() != self._owner:
            self._thread.join(timeout=max(0.0, timeout_seconds))
        stopped = not self._thread.is_alive()
        if not stopped:
            with self._lock:
                self._failure = 'shutdown_timeout'
        return stopped

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                'state': 'unhealthy' if self._failure else (
                    'running' if self._accepting else 'stopping' if self._thread.is_alive() else 'stopped'
                ),
                'queue_depth': self._queue.qsize(),
                'queue_wait_ms': self._queue_wait_ms,
                'service_ms': self._service_ms,
                'failure': self._failure,
            }
