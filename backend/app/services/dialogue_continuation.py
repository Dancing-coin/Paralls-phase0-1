"""对话 owner 续执行；跨线程只交付冻结请求和独立 provider。"""
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
import json
import math
from threading import BoundedSemaphore, Lock
from time import monotonic, time
from uuid import uuid4

from app.models.ai_output import DialogueResponse
from app.models.dialogue_audio import DialogueAudio
from app.models.player_input import DialogueSubmit


def _json(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()


@dataclass(frozen=True)
class PreparedDialogueJob:
    ticket_id: str
    token: str
    stage: str
    actor_id: str
    request_json: bytes


@dataclass(frozen=True)
class DialogueAdvance:
    status: str
    job: PreparedDialogueJob | None = None
    provider: object = None
    messages_json: bytes = b'[]'
    reason: str = ''
    fallback_used: bool = False
    replayed: bool = False


@dataclass
class _PendingDialogue:
    event: DialogueSubmit
    handle: object
    connection_ref: str
    binding_pin: tuple
    job: PreparedDialogueJob | None = None
    cognition_job: object = None
    pin: tuple = ()
    response: DialogueResponse | None = None
    context_actor_ids: tuple[str, ...] = ()
    fallback_used: bool = False


class DialogueCoordinator:
    def __init__(self, *, runtime, character_service, auth, begin_activation,
                 prepare_cognition, speech_content, finish_response):
        self.runtime = runtime
        self.character_service = character_service
        self.auth = auth
        self._begin_activation = begin_activation
        self._prepare_cognition = prepare_cognition
        self._speech_content = speech_content
        self._finish_response = finish_response
        self._connections = {}
        self._pending = {}
        self._receipts = OrderedDict()
        self._accepting = True

    def connect(self, connection_ref: str) -> None:
        self._connections[connection_ref] = ()

    def bind(self, connection_ref: str, binding) -> None:
        self.cancel_connection(connection_ref, reason='session_changed')
        self._connections[connection_ref] = self._binding_pin(binding)

    @staticmethod
    def _binding_pin(binding) -> tuple:
        return () if binding is None else (binding.session_ref, binding.connection_epoch, binding.lease_expires_at)

    def _connection_current(self, connection_ref, pin) -> bool:
        if connection_ref not in self._connections or self._connections[connection_ref] != pin:
            return False
        if not pin:
            return True
        binding = self.auth.resolve_binding(pin[0])
        return (binding is not None and binding.binding_state == 'bound_active'
                and self._binding_pin(binding) == pin and int(time()) <= binding.lease_expires_at)

    def begin(self, event_json: bytes, *, connection_ref: str, deadline_monotonic: float) -> DialogueAdvance:
        if not math.isfinite(deadline_monotonic):
            raise ValueError('dialogue deadline must be finite')
        event = DialogueSubmit.model_validate_json(event_json)
        pin = self._connections.get(connection_ref, ())
        if not self._accepting or not self._connection_current(connection_ref, pin):
            return DialogueAdvance('requeued', reason='connection_invalid')
        if len(self._pending) >= 4:
            return DialogueAdvance('requeued', reason='provider_capacity')
        if any(turn.connection_ref == connection_ref and turn.event.request_id == event.request_id
               for turn in self._pending.values()):
            return DialogueAdvance('requeued', reason='dialogue_stream_duplicate')
        handle, receipt = self._begin_activation(event, deadline_monotonic)
        if handle is None:
            return DialogueAdvance('requeued', reason=receipt.stop_reason if receipt else 'activation_not_owned')
        ticket_id = uuid4().hex
        turn = _PendingDialogue(event, handle, connection_ref, pin, context_actor_ids=(handle.actor_id,))
        self._pending[ticket_id] = turn
        try:
            def cognition_finished(_turn_id, reason):
                if reason != 'completed':
                    self.cancel(ticket_id, reason=reason)
            cognition = self._prepare_cognition(event, handle, cognition_finished)
            return self._after_cognition(ticket_id, turn, cognition)
        except BaseException:
            self.cancel(ticket_id, reason='failed')
            raise

    def _stage(self, ticket_id, turn, stage, request_json, provider):
        job = PreparedDialogueJob(ticket_id, uuid4().hex, stage, turn.handle.actor_id, request_json)
        turn.job = job
        turn.pin = self._capture_pin(turn)
        return DialogueAdvance('pending', job=job, provider=provider, fallback_used=turn.fallback_used)

    def _capture_pin(self, turn):
        return tuple((actor, self.runtime._capture_cognition_pin(actor)) for actor in turn.context_actor_ids)

    def _after_cognition(self, ticket_id, turn, advance):
        if advance.status == 'pending':
            turn.cognition_job = advance.next_job
            gateway = (self.runtime._l2._gateway if advance.next_job.task_kind == 'l2_reasoning'
                       else self.runtime._l3._gateway)
            return self._stage(ticket_id, turn, 'cognition', advance.next_job.request_json, gateway)
        turn.cognition_job = None
        if advance.status != 'completed':
            self.cancel(ticket_id, reason=advance.reason or advance.status)
            return DialogueAdvance('requeued', reason=advance.reason)
        content = self._speech_content(advance.result or [])
        if content:
            # cognition 直接发言始终属于被激活的接收者；agent fallback 才沿用发起者。
            turn.response = self.character_service.build_dialogue_response(
                turn.event, {'content': content, 'tone': 'neutral'}).model_copy(update={
                    'actor_id': turn.event.target_actor_id, 'target_actor_id': turn.event.actor_id})
            return self._tts(ticket_id, turn)
        request = self.character_service.prepare_dialogue(turn.event)
        speaker = turn.event.actor_id if turn.event.player_id == 'character_agent' else turn.event.target_actor_id
        turn.context_actor_ids = tuple(dict.fromkeys((turn.handle.actor_id, speaker)))
        return self._stage(ticket_id, turn, 'dialogue_generation', request, self.character_service.dialogue._gateway)

    def _tts(self, ticket_id, turn):
        response = turn.response
        return self._stage(ticket_id, turn, 'tts', _json({'actor_id': response.actor_id, 'content': response.content}),
                           self.character_service.tts)

    def advance(self, job: PreparedDialogueJob, completion_json: bytes) -> DialogueAdvance:
        completion = json.loads(completion_json)
        fingerprint = _json(completion)
        cached = self._receipts.get(job.token)
        if cached is not None:
            old_job, old_payload, receipt = cached
            if old_job == job and old_payload == fingerprint:
                return replace(receipt, replayed=True)
            return DialogueAdvance('zero_write', reason='completion_conflict')
        turn = self._pending.get(job.ticket_id)
        if turn is None or turn.job != job:
            return DialogueAdvance('zero_write', reason='dialogue_token_invalid')
        reason = ''
        if not self._connection_current(turn.connection_ref, turn.binding_pin):
            reason = 'connection_invalid'
        elif not self.runtime.activation_is_current(turn.handle.lock_ref, turn.handle.token):
            reason = 'activation_invalid'
        elif self._capture_pin(turn) != turn.pin:
            reason = 'context_stale'
        if reason:
            self.cancel(job.ticket_id, reason=reason)
            return DialogueAdvance('zero_write', reason=reason)
        try:
            if job.stage == 'cognition':
                kwargs = ({'error': RuntimeError(str(completion['error']))} if 'error' in completion
                          else {'output': completion['output']})
                advance = self.runtime.commit_cognition_result(turn.cognition_job, **kwargs)
                result = self._after_cognition(job.ticket_id, turn, advance)
            elif 'error' in completion or completion.get('cancelled'):
                self.cancel(job.ticket_id, reason='failed' if 'error' in completion else 'cancelled')
                result = DialogueAdvance('failed' if 'error' in completion else 'cancelled', reason=str(completion.get('error', '')))
            elif job.stage == 'dialogue_generation':
                turn.response = self.character_service.build_dialogue_response(turn.event, completion['output'])
                turn.fallback_used = bool(completion.get('fallback_used', False))
                result = self._tts(job.ticket_id, turn)
            else:
                audio = DialogueAudio.model_validate(completion['output'])
                response = turn.response.model_copy(update={'audio': audio})
                messages = self._finish_response(response)
                self.cancel(job.ticket_id, reason='completed')
                result = DialogueAdvance('completed', messages_json=_json(messages), fallback_used=turn.fallback_used)
        except BaseException:
            self.cancel(job.ticket_id, reason='failed')
            raise
        self._receipts[job.token] = (job, fingerprint, result)
        while len(self._receipts) > 32:
            self._receipts.popitem(last=False)
        return result

    def cancel(self, ticket_id: str, *, reason: str) -> DialogueAdvance:
        # 先从 admission 中移除；子 continuation 的结束不拥有外层 activation。
        turn = self._pending.pop(ticket_id, None)
        if turn is None:
            return DialogueAdvance('zero_write', reason='dialogue_token_invalid')
        try:
            if turn.cognition_job is not None:
                self.runtime.cancel_cognition_turn(turn.cognition_job.turn_id, reason=reason)
        finally:
            receipt = self.runtime.finish_actor_activation(turn.handle, reason=reason)
            if not receipt.lock_released:
                raise RuntimeError(receipt.stop_reason or 'activation_release_failed')
        return DialogueAdvance('cancelled', reason=reason)

    def cancel_connection(self, connection_ref: str, *, reason: str) -> None:
        first_error = None
        for ticket_id, turn in tuple(self._pending.items()):
            if turn.connection_ref == connection_ref:
                try:
                    self.cancel(ticket_id, reason=reason)
                except Exception as error:
                    first_error = first_error or error
        if first_error is not None:
            raise first_error

    def disconnect(self, connection_ref: str) -> None:
        self._connections.pop(connection_ref, None)
        self.cancel_connection(connection_ref, reason='disconnected')

    def close(self, *, reason='shutdown') -> None:
        self._accepting = False
        first_error = None
        for connection_ref in tuple(self._connections):
            try:
                self.cancel_connection(connection_ref, reason=reason)
            except Exception as error:
                first_error = first_error or error
        self._connections.clear()
        self._receipts.clear()
        for cleanup in (self.runtime.reset_cognition_jobs, self.runtime.reset_actor_activations):
            try:
                cleanup()
            except Exception as error:
                first_error = first_error or error
        if first_error is not None:
            raise first_error


def run_dialogue_provider(job: PreparedDialogueJob, provider, cancelled, emit) -> bytes:
    """不接收 runtime、会话、generator 或 owner closure；异常只作为 JSON 文本返回。"""
    try:
        if job.stage == 'cognition':
            return _json({'output': provider.complete_prepared_request(job.request_json)})
        if job.stage == 'tts':
            request = json.loads(job.request_json)
            return _json({'output': provider.synthesize(request['actor_id'], request['content']).model_dump(mode='json')})
        for item in provider.stream_prepared_request(job.request_json, cancelled=cancelled.is_set):
            if item['event'] == 'delta':
                emit(str(item['delta']))
            elif item['event'] == 'completed':
                return _json({'output': item['output'], 'fallback_used': bool(item.get('fallback_used', False))})
            elif item['event'] == 'cancelled':
                return _json({'cancelled': True})
            else:
                raise ValueError('unsupported dialogue provider event')
        raise ValueError('dialogue provider ended without completion')
    except Exception as error:
        return _json({'error': f'{type(error).__name__}: {error}'})


class DialogueProviderSlots:
    """四个 turn 预留槽；取消不能把仍在 HTTP 中的线程变成空闲槽。"""
    def __init__(self):
        self._slots = BoundedSemaphore(4)
        self._executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='dialogue-provider')

    def acquire(self):
        return _ProviderSlot(self) if self._slots.acquire(blocking=False) else None


class _ProviderSlot:
    def __init__(self, pool):
        self.pool = pool
        self._lock = Lock()
        self._future = None
        self._closed = False

    def submit(self, job, provider, cancelled, emit, *, runner=None):
        with self._lock:
            if self._closed or (self._future is not None and not self._future.done()):
                raise RuntimeError('dialogue provider slot is unavailable')
            self._future = self.pool._executor.submit(run_dialogue_provider if runner is None else runner,
                job, provider, cancelled, emit)
            return self._future

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            future = self._future
        if future is None:
            self.pool._slots.release()
        else:
            future.add_done_callback(lambda _: self.pool._slots.release())
