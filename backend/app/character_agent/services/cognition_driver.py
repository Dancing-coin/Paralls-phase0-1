"""Character 持久阶段的 loop 调度；只有冻结请求进入共用四槽 worker。"""
import asyncio
from threading import Event
from time import monotonic, time


_PROVIDER_RETRY_DELAYS = (1.0, 2.0, 4.0)


def _run_provider(request, gateway, cancelled, emit):
    return gateway.complete_prepared_request(request)


class CharacterCognitionDriver:
    def __init__(self, *, coordinator, owner_call, slots, begin_activation, on_completed,
                 clock=time, retry_clock=monotonic):
        self.coordinator = coordinator
        self.owner_call, self.slots = owner_call, slots
        self.begin_activation, self.on_completed, self.clock = begin_activation, on_completed, clock
        self.retry_clock = retry_clock
        self._active, self._handles = {}, {}
        self._provider_attempts, self._retry_after = {}, {}
        self._cursor = None
        self._closed = self._polling = False

    async def _owner(self, command):
        task = asyncio.create_task(self.owner_call(command))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            # owner 中已取得的 lease 保存在 _handles，取消不能遗失未交付请求的拥有者。
            while not task.done():
                try:
                    await asyncio.shield(task)
                except asyncio.CancelledError:
                    continue
            task.result()
            raise

    def _keys(self):
        entries = self.coordinator.admissions.list_pending(limit=32, cursor=self._cursor)
        self._cursor = (entries[-1].admitted_at, entries[-1].child_key) if len(entries) == 32 else None
        return tuple(dict.fromkeys((*self._handles, *(entry.child_key for entry in entries))))

    def _release(self, key, reason):
        self._provider_attempts.pop(key, None)
        self._retry_after.pop(key, None)
        handle = self._handles.get(key)
        if handle is not None:
            receipt = self.coordinator.runtime.finish_actor_activation(handle, reason=reason)
            if not receipt.lock_released:
                raise RuntimeError('cognition_activation_cleanup_pending')
            self._handles.pop(key)

    def _stale(self, key, error):
        admissions = self.coordinator.admissions
        entry, progress = admissions.read(key), admissions.read_progress(key)
        if progress is None or progress.status not in {'completed', 'stale'}:
            admissions.advance_progress(key=key, expected_revision=progress.revision if progress else 0,
                stage=progress.stage if progress else 'entry', status='stale',
                frame=progress.frame if progress else dict(actor_id=entry.actor_id, stage='entry'),
                plan=progress.plan if progress else None, reason=str(error), now=self.clock())
        self._release(key, 'stale')

    def _prepare(self, key):
        c = self.coordinator
        entry = c.admissions.read(key)
        progress = c.admissions.read_progress(key)
        if progress is not None and progress.status in {'completed', 'stale'}:
            if progress.status == 'completed':
                self.on_completed(entry, progress)
            self._release(key, progress.status)
            return None
        if self.clock() >= entry.expires_at:
            self._stale(key, ValueError('cognition_admission_expired'))
            return None
        try:
            if key not in self._handles:
                handle = self.begin_activation(entry)
                if handle is None:
                    return None
                self._handles[key] = handle
            handle = self._handles[key]
            # 原状态机至多跨过一个 effect 和下一 request；无模型调用在 owner 内。
            for _ in range(8):
                progress = c.admissions.read_progress(key)
                if progress is None:
                    c.begin_entry(key, activation=handle, now=self.clock())
                elif progress.status == 'commit_started':
                    getattr(c, 'resume_'+progress.stage)(key, activation=handle, now=self.clock())
                elif progress.status == 'result_ready':
                    getattr(c, 'freeze_'+progress.stage)(key, activation=handle, now=self.clock())
                elif progress.status == 'stage_ready':
                    if progress.stage in {'entry', 'l2'}:
                        getattr(c, 'prepare_'+('l2' if progress.stage == 'entry' else 'l3'))(key, activation=handle, now=self.clock())
                    elif c.runtime.get_control_mode(entry.actor_id) == 'player_priority_assisted':
                        c.prepare_suggestion(key, activation=handle, now=self.clock())
                    else:
                        c.freeze_execution(key, activation=handle, now=self.clock())
                elif progress.status == 'provider_pending':
                    if self.retry_clock() < self._retry_after.get(key, 0):
                        return None
                    c._entry(key, handle, self.clock())
                    c._validate_provider_pin(entry.actor_id, progress.frame)
                    gateway = c.runtime._l2._gateway if progress.stage == 'l2' else c.runtime._l3._gateway
                    return progress.stage, progress.request_json.encode('utf-8'), gateway
                else:
                    if progress.status == 'completed':
                        self.on_completed(entry, progress)
                    self._release(key, progress.status)
                    return None
            raise RuntimeError('cognition_stage_iteration_limit')
        except ValueError as error:
            current = c.admissions.read_progress(key)
            if current is not None and current.status == 'completed':
                # 完成投递失败不抹除义务；调用方须按原terminal key幂等重放。
                raise
            self._stale(key, error)
            return None

    def _accept(self, key, stage, future):
        c = self.coordinator
        if c.admissions.read_progress(key).status in {'completed', 'stale'}:
            return
        handle = self._handles[key]
        try:
            output = future.result()
        except Exception as provider_error:
            if stage == 'suggestion':
                self._stale(key, provider_error)
                return
            try:
                c.accept_provider_error(key, activation=handle, now=self.clock(), stage=stage, error=provider_error)
            except Exception as acceptance_error:
                progress = c.admissions.read_progress(key)
                if (acceptance_error is provider_error and progress is not None
                        and progress.stage == stage and progress.status == 'provider_pending'):
                    attempt = self._provider_attempts.get(key, 1)
                    if attempt > len(_PROVIDER_RETRY_DELAYS):
                        self._stale(key, ValueError(
                            'cognition_provider_retry_exhausted:' + type(provider_error).__name__))
                        return
                    # 强制在线模式保留原冻结请求；短退避避免持续外部故障压垮 owner。
                    self._provider_attempts[key] = attempt + 1
                    self._retry_after[key] = self.retry_clock() + _PROVIDER_RETRY_DELAYS[attempt - 1]
                    return
                if isinstance(acceptance_error, ValueError):
                    self._stale(key, acceptance_error)
                    return
                raise
        else:
            try:
                getattr(c, 'accept_'+stage)(key, activation=handle, now=self.clock(), output=output)
                self._provider_attempts.pop(key, None)
                self._retry_after.pop(key, None)
            except ValueError as error:
                self._stale(key, error)

    async def poll(self):
        if self._closed:
            return
        if self._polling:
            raise RuntimeError('cognition_driver_poll_busy')
        self._polling = True
        try:
            for key, (stage, future, slot, cancelled) in tuple(self._active.items()):
                if not future.done():
                    continue
                try:
                    await self._owner(lambda: self._accept(key, stage, future))
                finally:
                    slot.close()
                self._active.pop(key)
            for key in await self._owner(self._keys):
                if key in self._active or self._closed:
                    continue
                slot = self.slots.acquire()
                if slot is None:
                    break
                try:
                    prepared = await self._owner(lambda: self._prepare(key))
                    if prepared is None or self._closed:
                        slot.close()
                        if self._closed:
                            await self._owner(lambda: self._release(key, 'shutdown'))
                        continue
                    stage, request, gateway = prepared
                    cancelled = Event()
                    future = slot.submit(request, gateway, cancelled, None, runner=_run_provider)
                    self._active[key] = stage, future, slot, cancelled
                except BaseException:
                    slot.close()
                    raise
        finally:
            self._polling = False

    async def close(self):
        self._closed = True
        try:
            await self._owner(lambda: [self._release(key, 'shutdown') for key in tuple(self._handles)])
        finally:
            for _, _, slot, cancelled in self._active.values():
                cancelled.set()
                slot.close()
            self._active.clear()
