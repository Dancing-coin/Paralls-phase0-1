"""原 ASGI loop 上的四槽调度；所有领域调用回到唯一 owner。"""
import asyncio
from threading import Event
from time import monotonic, time

from app.services.siming_continuation import (
    RETRYABLE_SIMING_PROVIDER_ERRORS,
    SimingProviderCompletion,
    run_siming_provider,
)


_PROVIDER_RETRY_DELAYS = (1.0, 2.0, 4.0)


def _run_provider(job, provider, cancelled, emit):
    # 与 dialogue 共用槽签名，模型只收到冻结请求，取消不会提前释放实际 I/O 槽。
    return run_siming_provider(provider, job.request_json)


class SimingDriver:
    def __init__(self, *, coordinator, owner_call, slots, clock=time, retry_clock=monotonic):
        self.coordinator = coordinator
        self.owner_call = owner_call
        self.slots = slots
        self.clock = clock
        self.retry_clock = retry_clock
        self._active = {}
        self._unsubmitted = {}
        self._provider_attempts = {}
        self._retry_after = {}
        self._closed = False
        self._polling = False

    async def poll(self):
        if self._closed:
            return
        if self._polling:
            raise RuntimeError("siming_driver_poll_busy")
        self._polling = True
        try:
            for job in tuple(self._unsubmitted.values()):
                await self._cancel_unsubmitted(job)
            for identity, (key, job, revision, future, slot, cancelled) in tuple(self._active.items()):
                if not future.done():
                    continue
                try:
                    try:
                        completion = future.result()
                    except Exception as error:
                        error_kind = type(error).__name__
                        await self.owner_call(lambda: self.coordinator.fail_ready(key, job,
                            provider_revision=revision, error_kind=error_kind, now=self.clock()))
                        self._provider_attempts.pop(identity, None)
                        self._retry_after.pop(identity, None)
                    else:
                        completion_error = SimingProviderCompletion.model_validate_json(completion).error
                        retryable_error = completion_error in RETRYABLE_SIMING_PROVIDER_ERRORS
                        attempt = self._provider_attempts.get(identity, 1)
                        if retryable_error and attempt > len(_PROVIDER_RETRY_DELAYS):
                            await self.owner_call(lambda: self.coordinator.fail_ready(key, job,
                                provider_revision=revision, error_kind=completion_error,
                                now=self.clock()))
                            self._provider_attempts.pop(identity, None)
                            self._retry_after.pop(identity, None)
                        else:
                            await self.owner_call(lambda: self.coordinator.finish_ready(key, job, completion,
                                provider_revision=revision, now=self.clock()))
                            if retryable_error:
                                self._provider_attempts[identity] = attempt + 1
                                self._retry_after[identity] = (
                                    self.retry_clock() + _PROVIDER_RETRY_DELAYS[attempt - 1])
                            else:
                                self._provider_attempts.pop(identity, None)
                                self._retry_after.pop(identity, None)
                finally:
                    slot.close()
                # owner 未确认时保留已结束 future；重试同 completion，绝不重调模型。
                self._active.pop(identity, None)
            if self._closed:
                return
            keys = await self.owner_call(lambda: self.coordinator.take_ready(now=self.clock()))
            for key in keys:
                identity = key.entry_id
                if (identity in self._active or self._closed
                        or self.retry_clock() < self._retry_after.get(identity, 0)):
                    continue
                slot = self.slots.acquire()
                if slot is None:
                    break
                prepared = None
                try:
                    prepared = await self._prepare(key)
                    if prepared is None or self._closed:
                        self._provider_attempts.pop(identity, None)
                        self._retry_after.pop(identity, None)
                        slot.close()
                        if prepared is not None:
                            await self._cancel_unsubmitted(prepared[0])
                        continue
                    job, provider, revision = prepared
                    cancelled = Event()
                    future = slot.submit(job, provider, cancelled, None, runner=_run_provider)
                    self._retry_after.pop(identity, None)
                    self._active[identity] = key, job, revision, future, slot, cancelled
                except BaseException:
                    slot.close()
                    if prepared is not None:
                        # 账本已经保存请求但线程未接纳，清本地 token 后按原请求重启。
                        await self._cancel_unsubmitted(prepared[0])
                    raise
        finally:
            self._polling = False

    async def _cancel_unsubmitted(self, job):
        # 清理命令也可能暂时排不进 owner；保留持有者，下一 poll 先收口再领取新任务。
        self._unsubmitted[job.turn_id] = job
        await self.owner_call(lambda: self.coordinator.runtime.cancel_turn(job.turn_id))
        self._unsubmitted.pop(job.turn_id, None)

    async def _prepare(self, key):
        # shield 保留已排入 owner 的命令；取消后必须接回其结果再清理未交付 token。
        task = asyncio.create_task(self.owner_call(lambda: self.coordinator.prepare_ready(key, now=self.clock())))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            async def finish_unsubmitted():
                prepared = await task
                if prepared is not None:
                    await self._cancel_unsubmitted(prepared[0])
            cleanup = asyncio.create_task(finish_unsubmitted())
            while not cleanup.done():
                try:
                    await asyncio.shield(cleanup)
                except asyncio.CancelledError:
                    # 多次取消不能让已运行的 owner 命令失去其清理拥有者。
                    continue
            cleanup.result()
            raise

    async def close(self):
        if self._closed and not self._unsubmitted:
            return
        self._closed = True
        try:
            await self.owner_call(self.coordinator.runtime.reset_turns)
            self._unsubmitted.clear()
            self._provider_attempts.clear()
            self._retry_after.clear()
        finally:
            for _, _, _, _, slot, cancelled in self._active.values():
                cancelled.set()
                slot.close()
            self._active.clear()
