"""单局 spawn 进程边界；跨进程只传命名 JSON，不传运行时对象或 callable。"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import json
import multiprocessing
import os
from queue import Empty, Full
from time import time
from uuid import uuid4

IPC_CAPACITY = 128
RUNTIME_HTTP_ROUTE_NAMES = frozenset({
    "debug_siming_read_model", "orchestrate_structured_interaction",
    "issue_trusted_local_gameplay_mirror_enrollment", "issue_trusted_local_embodied_controller_enrollment",
    "commit_trusted_local_gameplay_mirror_live_probe", "commit_trusted_local_gameplay_mirror_live_probe_reconnect",
    "confirm_trusted_local_gameplay_mirror_live_prediction", "reject_trusted_local_gameplay_mirror_live_prediction",
    "close_trusted_local_gameplay_mirror_live_probe_transport", "commit_trusted_local_adventure_basic_live_probe",
})


@dataclass(frozen=True)
class RuntimeCommandChannel:
    """仅 spawn bootstrap 资源；业务消息仍只在 queue 中传严格 JSON。"""
    queue: object
    execution_credit: object


class RuntimeProcessError(RuntimeError):
    pass


def _encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _decode(value):
    if not isinstance(value, str):
        raise ValueError("runtime_ipc_json_required")
    def invalid_constant(_):
        raise ValueError("runtime_ipc_nonfinite")
    result = json.loads(value, parse_constant=invalid_constant)
    if not isinstance(result, dict) or type(result.get("schema")) is not int or result.get("schema") != 1:
        raise ValueError("runtime_ipc_schema")
    return result


async def _get(queue):
    while True:
        try:
            return await asyncio.to_thread(queue.get, True, .05)
        except Empty:
            await asyncio.sleep(0)


async def _put(queue, value, *, abandoned=None):
    encoded = _encode(value)
    while True:
        if abandoned is not None and abandoned.is_set():
            return
        try:
            queue.put_nowait(encoded)
            return
        except Full:
            await asyncio.sleep(.02)


class RuntimeProcess:
    """parent 生命周期与有界 IPC 关联表；不把收包等同于 owner 命令接纳。"""
    def __init__(self, settings_json: str):
        self._settings_json = settings_json
        context = multiprocessing.get_context("spawn")
        self._commands, self._controls, self._results, self._notifications = (
            context.Queue(maxsize=IPC_CAPACITY) for _ in range(4))
        from app.services.runtime_execution import RuntimeExecutionCredit
        self._execution_credit = RuntimeExecutionCredit(IPC_CAPACITY)
        self.process = context.Process(target=CHILD_TARGET, args=(RuntimeCommandChannel(self._commands, self._execution_credit),
            self._controls, self._results, self._notifications, settings_json), name="game-runtime")
        self._generation = None
        self._sequence = 0
        self._pending = {}
        self._runtime_pending = {}
        self._envelope_pending = {}
        self._health = {"status": "unhealthy", "runtime_execution": None}
        self._reader = self._monitor = None
        self._ready = self._stopped = None
        self._closing = self._closed = False
        self._failure = None
        self._close_task = None
        self._connections = {}
        self._send_tasks = {}
        self._finalizing_sends = set()
        self._closing_event = asyncio.Event()
        self._socket_close_tasks = set()
        self._notifications_reader = None

    @property
    def pending_count(self):
        return len(self._pending)

    def snapshot(self):
        from copy import deepcopy
        result = deepcopy(self._health)
        result.update(child_pid=self.process.pid, process_generation=self._generation,
                      execution_credit=self._execution_credit.snapshot(),
                      ipc_pending=len(self._pending), ipc_capacity=IPC_CAPACITY,
                      pending_send=len(self._send_tasks), notification_capacity=IPC_CAPACITY,
                      runtime_pending=len(self._runtime_pending), runtime_pending_capacity=IPC_CAPACITY,
                      transport_pending=len(self._envelope_pending), transport_pending_capacity=IPC_CAPACITY)
        if self._closing or self._failure or self.process.pid is None or not self.process.is_alive():
            result["status"] = "unhealthy"
        return result

    async def start(self):
        if self._ready is not None:
            raise RuntimeProcessError("runtime_process_already_started")
        loop = asyncio.get_running_loop()
        self._ready, self._stopped = loop.create_future(), loop.create_future()
        self._ready.add_done_callback(lambda done: None if done.cancelled() else done.exception())
        try:
            self.process.start()
            self._reader = asyncio.create_task(self._read_results())
            self._monitor = asyncio.create_task(self._watch_process())
            self._notifications_reader = asyncio.create_task(self._read_notifications())
            return await asyncio.shield(self._ready)
        except BaseException:
            await self.close()
            raise

    def _submit_request(self, operation: str, payload: dict):
        if (self._closing or self._failure or self._generation is None or not self.process.is_alive()):
            raise RuntimeProcessError("runtime_process_unavailable")
        if not isinstance(operation, str) or not isinstance(payload, dict):
            raise ValueError("runtime_ipc_command_invalid")
        if len(self._pending) >= IPC_CAPACITY:
            raise RuntimeProcessError("runtime_queue_full")
        sequence = self._sequence + 1
        encoded = _encode(dict(schema=1, kind="command", generation=self._generation,
            sequence=sequence, operation=operation, payload=payload))
        future = asyncio.get_running_loop().create_future()
        # 调用方取消后原结果仍会到达；消费异常避免丢失等待者产生后台告警。
        future.add_done_callback(lambda done: None if done.cancelled() else done.exception())
        try:
            self._commands.put_nowait(encoded)
        except Full:
            raise RuntimeProcessError("runtime_queue_full") from None
        self._sequence = sequence
        self._pending[sequence] = future
        # 取消等待者不撤回可能已执行的事实；结果到达或进程终结才回收关联项。
        return future

    async def request(self, operation: str, payload: dict):
        return await asyncio.shield(self._submit_request(operation, payload))

    async def enqueue_runtime(self, connection_ref, payload):
        from app.ws_protocol import RuntimeEnqueueRequest
        from app.models.raw_fact import RawFactEvent
        request = RuntimeEnqueueRequest.model_validate(payload)
        if request.command.message_type == 'raw_fact_event':
            RawFactEvent.model_validate(request.command.payload)
        connection = self._connections.get(connection_ref)
        if connection is None or connection['closed']:
            raise RuntimeProcessError('runtime_connection_closed')
        barrier = connection.get('barrier')
        if barrier is not None:
            await asyncio.shield(barrier)
        identity = (connection_ref, request.request_id)
        reason = ('duplicate_pending_request' if identity in self._runtime_pending else
                  'connection_queue_full' if len(self._runtime_pending) + len(self._envelope_pending) >= IPC_CAPACITY else
                  'connection_unavailable' if connection['revoked'] or not connection['binding_pin']
                      or int(time()) > connection['binding_pin'][2] else None)
        if reason is None:
            if not self._execution_credit.acquire(False):
                reason = 'runtime_queue_full'
            else:
                try:
                    future = self._submit_request('runtime.enqueue', dict(connection_ref=connection_ref,
                        connection_generation=connection['generation'], binding_pin=connection['binding_pin'],
                        request=request.model_dump(mode='json')))
                except BaseException as error:
                    self._execution_credit.release()
                    if not isinstance(error, RuntimeProcessError):
                        raise
                    reason = str(error)
                else:
                    acknowledged = asyncio.Event()
                    self._runtime_pending[identity] = dict(acknowledged=acknowledged, state_revision=connection['state_revision'],
                        connection_generation=connection['generation'], request_sequence=self._sequence, terminal=False)
                    def handed_off(done):
                        if done.cancelled() or done.exception() is not None:
                            self._close_connection_socket(connection, 1011, 'runtime_enqueue_handoff_failed')
                    future.add_done_callback(handed_off)
        admission = dict(request_id=request.request_id, accepted=reason is None)
        if reason is not None:
            admission['reason'] = reason
        delivery_id = f"{self._generation}:{connection['generation']}:admission:{uuid4().hex}"
        if len(self._send_tasks) >= IPC_CAPACITY:
            self._begin_disconnect(connection_ref, connection)
            raise RuntimeProcessError('runtime_notification_capacity')
        task = asyncio.create_task(self._deliver(dict(delivery_id=delivery_id, connection_ref=connection_ref,
            connection_generation=connection['generation'], state_revision=connection['state_revision'],
            message=dict(message_type='runtime_admission', payload=admission))))
        self._send_tasks[delivery_id] = (connection_ref, task)
        try:
            if await task != 'sent':
                raise RuntimeProcessError('runtime_admission_send_failed')
            if reason is None:
                acknowledged.set()
                pending = self._runtime_pending.get(identity)
                if pending is not None and pending['acknowledged'] is acknowledged and pending['terminal']:
                    self._runtime_pending.pop(identity, None)
        except BaseException:
            self._begin_disconnect(connection_ref, connection)
            raise
        finally:
            self._send_tasks.pop(delivery_id, None)
        return admission

    async def connect(self, connection_ref, *, path, query, remote_host, send_json, close_socket):
        if connection_ref in self._connections or len(self._connections) >= IPC_CAPACITY:
            raise RuntimeProcessError("runtime_connections_full")
        generation = uuid4().hex
        connection = dict(ref=connection_ref, generation=generation, send=send_json, close=close_socket, closed=False,
                          connect_sequence=self._sequence + 1, state_revision=0, binding_pin=[], revoked=False, send_lock=asyncio.Lock(),
                          disconnected=asyncio.get_running_loop().create_future())
        self._connections[connection_ref] = connection
        try:
            return await self.request("transport.connect", dict(connection_ref=connection_ref,
                connection_generation=generation, path=path, query=query, remote_host=remote_host))
        except asyncio.CancelledError:
            # request 仍可能在 child 生效，保留原 registration 到独立 disconnect 收口。
            self._begin_disconnect(connection_ref, connection)
            raise
        except BaseException:
            self._connections.pop(connection_ref, None)
            raise

    async def envelope(self, connection_ref, envelope):
        if envelope.get('message_type') == 'runtime_enqueue':
            raise ValueError('runtime_enqueue_requires_command_queue')
        connection = self._connections[connection_ref]
        if connection["closed"]:
            raise RuntimeProcessError("runtime_connection_closed")
        if len(self._envelope_pending) + len(self._runtime_pending) >= IPC_CAPACITY:
            raise RuntimeProcessError('runtime_transport_pending_full')
        sequence = self._sequence + 1
        future = self._submit_request("transport.envelope", dict(connection_ref=connection_ref,
            connection_generation=connection["generation"], envelope=envelope))
        barrier = asyncio.get_running_loop().create_future()
        barrier.add_done_callback(lambda done: None if done.cancelled() else done.exception())
        self._envelope_pending[(connection_ref, sequence)] = barrier
        connection['barrier'] = barrier
        try:
            return await asyncio.shield(future)
        except Exception as error:
            self._envelope_pending.pop((connection_ref, sequence), None)
            if not barrier.done():
                barrier.set_exception(error)
            raise

    def _begin_disconnect(self, connection_ref, connection):
        if connection.get("disconnect_task") is None:
            connection["closed"] = True
            task = asyncio.create_task(self._disconnect(connection_ref, connection))
            connection["disconnect_task"] = task
            task.add_done_callback(lambda done: None if done.cancelled() else done.exception())
        return connection["disconnect_task"]

    async def disconnect(self, connection_ref):
        connection = self._connections.get(connection_ref)
        if connection is not None:
            await asyncio.shield(self._begin_disconnect(connection_ref, connection))

    async def _disconnect(self, connection_ref, connection):
        for delivery_id, (ref, task) in tuple(self._send_tasks.items()):
            if ref == connection_ref and delivery_id not in self._finalizing_sends:
                task.cancel()
        if not self._failure and self.process.is_alive():
            await _put(self._controls, dict(schema=1, kind="disconnect", generation=self._generation,
                connection_ref=connection_ref, connection_generation=connection["generation"],
                connect_sequence=connection["connect_sequence"]), abandoned=self._closing_event)
            await asyncio.shield(connection["disconnected"])
        if self._connections.get(connection_ref) is connection:
            self._connections.pop(connection_ref, None)
        for identity, pending in tuple(self._runtime_pending.items()):
            if identity[0] == connection_ref and pending["connection_generation"] == connection["generation"]:
                pending["acknowledged"].set()
                self._runtime_pending.pop(identity, None)

    def _close_connection_socket(self, connection, code, reason):
        connection["closed"] = True
        for identity, pending in tuple(self._runtime_pending.items()):
            if identity[0] == connection["ref"] and pending["connection_generation"] == connection["generation"]:
                pending["acknowledged"].set()
                self._runtime_pending.pop(identity, None)
        for identity, (ref, task) in tuple(self._send_tasks.items()):
            if (ref == connection["ref"] and self._connections.get(ref) is connection
                    and identity not in self._finalizing_sends):
                task.cancel()
        if not connection.get("close_task"):
            task = asyncio.create_task(connection["close"](code, reason))
            connection["close_task"] = task
            self._socket_close_tasks.add(task)
            task.add_done_callback(self._socket_close_tasks.discard)
            task.add_done_callback(lambda done: None if done.cancelled() else done.exception())

    async def _read_notifications(self):
        try:
            while True:
                value = _decode(await _get(self._notifications))
                if value.get("generation") != self._generation or value.get("kind") != "send":
                    raise ValueError("runtime_notification_invalid")
                delivery_id, ref = value.get("delivery_id"), value.get("connection_ref")
                if not isinstance(delivery_id, str) or delivery_id in self._send_tasks:
                    raise ValueError("runtime_delivery_identity_invalid")
                # 本地 admission 与 child 通知共享发送表，正常满额只背压。
                while len(self._send_tasks) >= IPC_CAPACITY:
                    await asyncio.sleep(.02)
                task = asyncio.create_task(self._deliver(value))
                self._send_tasks[delivery_id] = (ref, task)
                def finished(done, value=value):
                    identity = value["delivery_id"]
                    self._finalizing_sends.add(identity)
                    terminal = asyncio.create_task(self._finish_delivery(value, done))
                    self._send_tasks[identity] = (value["connection_ref"], terminal)
                task.add_done_callback(finished)
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._fail(type(error).__name__)

    async def _deliver(self, value):
        delivery_id = value["delivery_id"]
        status = "failed"
        completion = value["message"].get("message_type") == "runtime_completion"
        identity = (value["connection_ref"], value["message"].get("payload", {}).get("request_id"))
        pending = None
        try:
            if completion:
                candidate = self._runtime_pending.get(identity)
                if (candidate is None or candidate['state_revision'] != value.get('state_revision')
                        or candidate['connection_generation'] != value.get('connection_generation')
                        or candidate['request_sequence'] != value.get('request_sequence')):
                    return status
                pending = candidate
                await pending['acknowledged'].wait()
            connection = self._connections.get(value["connection_ref"])
            if connection is None:
                return status
            async with connection['send_lock']:
                if (not connection["closed"] and not self._closing
                        and connection["generation"] == value.get("connection_generation")
                        and connection["state_revision"] == value.get("state_revision", 0)
                        and (not connection["revoked"] or value["message"].get("message_type") == "websocket_session_revoked")
                        and (not connection["binding_pin"] or int(time()) <= connection["binding_pin"][2]
                             or value["message"].get("message_type") == "websocket_session_revoked")):
                    lease = connection["binding_pin"][2] if connection["binding_pin"] else None
                    deadline = value.get("lease_deadline")
                    if deadline is not None and (type(deadline) is not int or lease is None or deadline > lease or time() >= deadline):
                        return status
                    if lease is not None and value["message"].get("message_type") != "websocket_session_revoked":
                        async with asyncio.timeout(max(0.0, (deadline if deadline is not None else lease + 1) - time())):
                            await connection["send"](value["message"])
                    else:
                        await connection["send"](value["message"])
                    status = "sent"
        except (Exception, asyncio.CancelledError):
            pass
        return status

    async def _finish_delivery(self, value, done):
        delivery_id = value["delivery_id"]
        try:
            status = "failed" if done.cancelled() else done.result()
            if not self._closing and self.process.is_alive():
                await _put(self._controls, dict(schema=1, kind="send_result", generation=self._generation,
                    delivery_id=delivery_id, status=status), abandoned=self._closing_event)
        finally:
            self._send_tasks.pop(delivery_id, None)
            self._finalizing_sends.discard(delivery_id)

    def _fail(self, reason):
        self._failure = reason
        self._closing_event.set()
        if self._ready is not None and not self._ready.done():
            self._ready.set_exception(RuntimeProcessError(reason))
        for future in self._pending.values():
            if not future.done():
                future.set_exception(RuntimeProcessError(reason))
        self._pending.clear()
        for future in self._envelope_pending.values():
            if not future.done():
                future.set_exception(RuntimeProcessError(reason))
        self._envelope_pending.clear()
        for connection in tuple(self._connections.values()):
            self._close_connection_socket(connection, 1011, reason)
            if not connection["disconnected"].done():
                connection["disconnected"].set_result(None)

    async def _watch_process(self):
        while self.process.is_alive():
            await asyncio.sleep(.02)
        if not self._closing:
            self._fail("runtime_child_exited")

    async def _read_results(self):
        try:
            while True:
                result = _decode(await _get(self._results))
                kind = result.get("kind")
                if kind == "ready":
                    if self._generation is not None or not isinstance(result.get("generation"), str):
                        raise ValueError("runtime_ipc_ready_invalid")
                    self._generation = result["generation"]
                    self._health = result["health"]
                    self._ready.set_result(self.snapshot())
                    continue
                if kind == "failure" and self._generation is None:
                    self._generation = result.get("generation")
                if result.get("generation") != self._generation:
                    raise ValueError("runtime_ipc_generation")
                if kind == "health":
                    self._health = result["health"]
                elif kind == "result":
                    if type(result.get("sequence")) is not int:
                        raise ValueError("runtime_ipc_result_sequence")
                    future = self._pending.pop(result["sequence"], None)
                    if future is None:
                        raise ValueError("runtime_ipc_unknown_result")
                    if result.get("error"):
                        future.set_exception(RuntimeProcessError(result["error"]))
                    else:
                        future.set_result(result["value"])
                elif kind == "runtime_terminal":
                    identity = (result['connection_ref'], result['request_id'])
                    pending = self._runtime_pending.get(identity)
                    if (pending is not None and pending['connection_generation'] == result['connection_generation']
                            and pending['request_sequence'] == result['request_sequence']):
                        pending['terminal'] = True
                        if pending['acknowledged'].is_set():
                            self._runtime_pending.pop(identity, None)
                elif kind == "envelope_processed":
                    future = self._envelope_pending.pop((result['connection_ref'], result['sequence']), None)
                    if future is not None and not future.done():
                        if result.get('error'):
                            future.set_exception(RuntimeProcessError(result['error']))
                        else:
                            future.set_result(None)
                elif kind == "connection_state":
                    connection = self._connections.get(result["connection_ref"])
                    status = "failed"
                    if connection is not None and not connection["closed"] and connection["generation"] == result["connection_generation"]:
                        revision, pin = result["state_revision"], result["binding_pin"]
                        if (type(revision) is not int or revision != connection["state_revision"] + 1
                                or not isinstance(pin, list) or (pin and (len(pin) != 3 or not isinstance(pin[0], str)
                                    or type(pin[1]) is not int or type(pin[2]) is not int))
                                or type(result.get("revoked")) is not bool
                                or connection["revoked"] and not result["revoked"]):
                            raise ValueError("runtime_connection_state_invalid")
                        connection.update(state_revision=revision, binding_pin=pin, revoked=result["revoked"])
                        for identity, (ref, task) in tuple(self._send_tasks.items()):
                            if ref == result["connection_ref"] and identity not in self._finalizing_sends:
                                task.cancel()
                        status = "sent"
                    await _put(self._controls, dict(schema=1, kind="send_result", generation=self._generation,
                        delivery_id=result["delivery_id"], status=status), abandoned=self._closing_event)
                elif kind == "socket_close":
                    connection = self._connections.get(result["connection_ref"])
                    if connection is not None and connection["generation"] == result["connection_generation"]:
                        self._close_connection_socket(connection, result["code"], result["reason"])
                elif kind == "disconnected":
                    connection = self._connections.get(result["connection_ref"])
                    if connection is not None and connection["generation"] == result["connection_generation"]:
                        connection["closed"] = True
                        if not connection["disconnected"].done():
                            connection["disconnected"].set_result(None)
                elif kind == "stopped":
                    self._stopped.set_result(None)
                    return
                elif kind == "failure":
                    self._fail(result["error"])
                else:
                    raise ValueError("runtime_ipc_result_invalid")
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self._fail(type(error).__name__)

    async def close(self):
        if self._close_task is None or (self._close_task.done() and not self._closed):
            self._close_task = asyncio.create_task(self._close())
        try:
            await asyncio.shield(self._close_task)
        except asyncio.CancelledError:
            while not self._close_task.done():
                try:
                    await asyncio.shield(self._close_task)
                except asyncio.CancelledError:
                    continue
            self._close_task.result()
            raise

    async def _close(self):
        if self._closed:
            return
        self._closing = True
        self._closing_event.set()
        async def shutdown():
            for identity, (_, task) in tuple(self._send_tasks.items()):
                if identity not in self._finalizing_sends:
                    task.cancel()
            await _put(self._controls, dict(schema=1, kind="shutdown", generation=self._generation, last_sequence=self._sequence))
            await asyncio.shield(self._stopped)

        try:
            if self.process.pid is not None and self.process.is_alive():
                # 结果读取任务退出后已无人能消费 stopped，继续等待只会耗尽关闭期限。
                if self._reader is not None and self._reader.done() and not self._stopped.done():
                    self.process.terminate()
                else:
                    try:
                        # control 本身也可能被阻塞，必须共享同一关闭期限。
                        await asyncio.wait_for(shutdown(), 15)
                    except (TimeoutError, RuntimeProcessError):
                        self._fail("runtime_shutdown_unknown")
                        self.process.terminate()
            if self.process.pid is not None:
                await asyncio.to_thread(self.process.join, 5)
                if self.process.is_alive():
                    raise RuntimeProcessError("runtime_shutdown_incomplete")
        finally:
            self._fail(self._failure or "runtime_stopped")
            # 未确认死亡时保持句柄/通道，后续 close 仍可完成原 child 的收口。
            if self.process.pid is None or not self.process.is_alive():
                for task in (self._reader, self._monitor, self._notifications_reader):
                    if task is not None:
                        task.cancel()
                await asyncio.gather(*(task for task in (self._reader, self._monitor, self._notifications_reader) if task is not None), return_exceptions=True)
                while self._send_tasks:
                    await asyncio.gather(*(task for _, task in tuple(self._send_tasks.values())), return_exceptions=True)
                    await asyncio.sleep(0)
                for task in self._socket_close_tasks:
                    task.cancel()
                await asyncio.gather(*self._socket_close_tasks, return_exceptions=True)
                for queue in (self._commands, self._controls, self._results, self._notifications):
                    queue.cancel_join_thread()
                    queue.close()
                self._closed = True



def runtime_child_main(command_queue, control_queue, result_queue, notification_queue, settings_json: str):
    """固定 spawn 入口；验证 wrapper 可先安装 probe，再调用同一生产装配。"""
    from app.services.process_qos import high_qos
    with high_qos():
        abandoned = asyncio.run(_run_child(command_queue, control_queue, result_queue, notification_queue, settings_json))
        from threading import Thread
        queues = (command_queue.queue, control_queue, result_queue, notification_queue)
        for queue in queues:
            queue.close()
        # join_thread 本身不能取消；用一个 daemon waiter，并持续监督至真实 flush 完成。
        def flush():
            for queue in queues:
                queue.join_thread()
        waiter = Thread(target=flush, name="runtime-ipc-flush", daemon=True)
        waiter.start()
        while waiter.is_alive():
            parent = multiprocessing.parent_process()
            if abandoned or (parent is not None and not parent.is_alive()):
                # parent 已死亡，不再有人接收；取消进程退出时对 feeder 的隐式 join。
                for queue in queues:
                    queue.cancel_join_thread()
                return
            waiter.join(.02)



async def _run_child(commands, controls, results, notifications, settings_json):
    execution_credit = commands.execution_credit
    commands = commands.queue
    from app import config
    configured = config.Settings.model_validate_json(settings_json)
    # wrapper 可能已导入 gateway/main；更新原共享配置对象，不留下旧引用。
    for name in config.Settings.model_fields:
        setattr(config.settings, name, getattr(configured, name))
    from app import main
    if multiprocessing.parent_process() is not None:
        import gc
        # owner 热路径会产生大量短命对象；降低第零代回收频率以限制 Windows 堆碎片。
        _, generation_one, generation_two = gc.get_threshold()
        gc.set_threshold(21000, generation_one, generation_two)
    main.settings = config.settings
    main._runtime_execution_credit = execution_credit
    generation = uuid4().hex
    stopped = asyncio.Event()
    shutdown_target = None
    parent_gone = asyncio.Event()
    sequence = 0
    tasks = []
    receiver = None
    connections = {}
    deliveries = {}
    cancelled_connections = {}
    http_tasks = set()

    async def emit(kind, **payload):
        await _put(results, dict(schema=1, kind=kind, generation=generation, **payload), abandoned=parent_gone)

    async def serve(channel, path):
        from fastapi import WebSocketDisconnect
        try:
            handler = main.websocket_endpoint if path == "/ws" else main.debug_websocket_endpoint
            await handler(channel)
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except Exception:
            await channel.close(code=1011, reason="runtime_connection_failed")

    async def finish_connection(channel, completed):
        if not completed.cancelled():
            completed.exception()
        try:
            await channel.finish_envelopes()
            await emit("disconnected", connection_ref=channel.connection_ref,
                       connection_generation=channel.connection_generation)
        finally:
            if connections.get(channel.connection_ref) is channel:
                connections.pop(channel.connection_ref, None)

    def session_done(channel, completed):
        channel.finalizing = True
        channel.task = asyncio.create_task(finish_connection(channel, completed))

    async def control():
        nonlocal shutdown_target
        while True:
            value = _decode(await _get(controls))
            if value.get("generation") not in (None, generation):
                raise ValueError("runtime_ipc_control_invalid")
            kind = value.get("kind")
            if kind == "shutdown":
                shutdown_target = value.get("last_sequence", sequence)
                if type(shutdown_target) is not int or shutdown_target < sequence:
                    raise ValueError("runtime_shutdown_sequence_invalid")
                if sequence >= shutdown_target:
                    stopped.set()
                continue
            if kind == "send_result":
                future = deliveries.get(value.get("delivery_id"))
                if future is not None and not future.done():
                    future.set_result(value.get("status"))
            elif kind == "disconnect":
                channel = connections.get(value.get("connection_ref"))
                if channel is not None and channel.connection_generation == value.get("connection_generation"):
                    if not channel.finalizing and not channel.disconnecting:
                        channel.disconnecting = True
                        channel.task.cancel()
                elif channel is None:
                    number = value.get("connect_sequence")
                    if type(number) is not int or number <= 0:
                        raise ValueError("runtime_disconnect_sequence_invalid")
                    if number > sequence:
                        identity = value.get("connection_ref"), value.get("connection_generation")
                        if len(cancelled_connections) >= IPC_CAPACITY and identity not in cancelled_connections:
                            raise ValueError("runtime_cancelled_connections_full")
                        cancelled_connections[identity] = number
                    await emit("disconnected", connection_ref=value["connection_ref"],
                               connection_generation=value["connection_generation"])
            else:
                raise ValueError("runtime_ipc_control_invalid")

    async def http_request(number, payload):
        try:
            response = await _dispatch_http(main.component_app, payload)
            await emit("result", sequence=number, value=response)
        except Exception as error:
            await emit("result", sequence=number, error=str(error) or type(error).__name__)

    async def receive():
        nonlocal sequence
        while True:
            value = _decode(await _get(commands))
            number = value.get("sequence")
            if (value.get("kind") != "command" or value.get("generation") != generation
                    or type(number) is not int or number <= sequence or not isinstance(value.get("payload"), dict)):
                raise ValueError("runtime_ipc_command_invalid")
            sequence = number
            if shutdown_target is not None:
                if value.get('operation') == 'runtime.enqueue':
                    execution_credit.release()
                await emit('result', sequence=number, error='runtime_stopping')
                if number >= shutdown_target:
                    stopped.set()
                continue
            if value.get("operation") == "runtime.snapshot" and value["payload"] == {}:
                await emit("result", sequence=number, value=main.health())
            elif value.get("operation") == "runtime.enqueue":
                transferred = False
                try:
                    from app.ws_protocol import RuntimeEnqueueRequest
                    payload = value['payload']
                    channel = connections.get(payload.get('connection_ref'))
                    if (channel is None or channel.disconnecting or channel.finalizing
                            or channel.connection_generation != payload.get('connection_generation')
                            or channel.runtime_enqueue is None):
                        raise ValueError('runtime_connection_unavailable')
                    request = RuntimeEnqueueRequest.model_validate(payload['request'])
                    await channel.runtime_enqueue(request, transferred=True, expected_pin=payload['binding_pin'], request_sequence=number)
                    transferred = True
                    await emit('result', sequence=number, value={})
                except Exception as error:
                    await emit('result', sequence=number, error=str(error) or type(error).__name__)
                finally:
                    if not transferred:
                        execution_credit.release()
            elif value.get("operation") == "http.request":
                if len(http_tasks) >= IPC_CAPACITY:
                    await emit('result', sequence=number, error='runtime_http_capacity')
                else:
                    task = asyncio.create_task(http_request(number, value['payload']))
                    http_tasks.add(task)
                    task.add_done_callback(http_tasks.discard)
            elif value.get("operation") in {"transport.connect", "transport.envelope"}:
                payload = value["payload"]
                ref = payload.get("connection_ref")
                try:
                    if value["operation"] == "transport.connect":
                        if (not isinstance(ref, str) or ref in connections or len(connections) >= IPC_CAPACITY
                                or payload.get("path") not in {"/ws", "/debug/ws"}
                                or not isinstance(payload.get("query"), dict)
                                or not isinstance(payload.get("remote_host"), str)
                                or not isinstance(payload.get("connection_generation"), str)):
                            raise ValueError("runtime_connection_invalid")
                        identity = ref, payload["connection_generation"]
                        cancelled = cancelled_connections.pop(identity, None)
                        if cancelled is None:
                            channel = _RuntimeConnection(payload, generation, notifications, emit, deliveries, parent_gone)
                            connections[ref] = channel
                            channel.task = asyncio.create_task(serve(channel, payload["path"]))
                            channel.task.add_done_callback(lambda done, channel=channel: session_done(channel, done))
                        elif cancelled != number:
                            raise ValueError("runtime_cancelled_connection_sequence_invalid")
                    else:
                        channel = connections.get(ref)
                        if (channel is None or channel.connection_generation != payload.get("connection_generation")
                                or not isinstance(payload.get("envelope"), dict)):
                            raise ValueError("runtime_connection_invalid")
                        if payload['envelope'].get('message_type') == 'runtime_enqueue':
                            raise ValueError('runtime_enqueue_requires_command_queue')
                        channel.inbound.put_nowait((number, payload["envelope"]))
                        channel.pending_envelopes.add(number)
                    await emit("result", sequence=number, value={})
                except (ValueError, asyncio.QueueFull) as error:
                    await emit("result", sequence=number, error=str(error) or "runtime_connection_queue_full")
            else:
                await emit("result", sequence=number, error="runtime_unknown_command")

    async def watch_parent():
        while True:
            parent = multiprocessing.parent_process()
            if parent is not None and not parent.is_alive():
                parent_gone.set()
                stopped.set()
                return
            await asyncio.sleep(.02)

    async def heartbeat():
        while True:
            await emit("health", health=main.health())
            await asyncio.sleep(.1)

    parent_watch = asyncio.create_task(watch_parent())
    try:
        await main._start_population_runtime_on_startup()
        await emit("ready", health=main.health(), child_pid=os.getpid())
        receiver = asyncio.create_task(receive())
        tasks = [asyncio.create_task(control()), receiver, asyncio.create_task(heartbeat())]
        end = asyncio.create_task(stopped.wait())
        tasks.append(end)
        done, _ = await asyncio.wait([*tasks, parent_watch], return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except Exception as error:
        await emit("failure", error=type(error).__name__)
    finally:
        # 先停止接纳新连接，control 继续服务现有 session 的发送/断连收口。
        if receiver is not None:
            receiver.cancel()
            await asyncio.gather(receiver, return_exceptions=True)
        for task in tuple(http_tasks):
            task.cancel()
        await asyncio.gather(*http_tasks, return_exceptions=True)
        for channel in tuple(connections.values()):
            if not channel.finalizing and not channel.disconnecting:
                channel.disconnecting = True
                channel.task.cancel()
        while connections:
            await asyncio.gather(*(channel.task for channel in tuple(connections.values())), return_exceptions=True)
            await asyncio.sleep(0)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        try:
            await main._stop_population_runtime_on_shutdown()
            execution = main.runtime_execution
            if execution is not None:
                # 原 shutdown 的 join 超时会保留 owner；不能把返回当作资源已关闭。
                await asyncio.shield(asyncio.wrap_future(execution.closed))
                await asyncio.to_thread(execution.stop)
        except Exception as error:
            await emit("failure", error=type(error).__name__)
            # 关闭失败保留原 child/lease；parent 到期强停只证明 unknown，不发 STOPPED。
            while True:
                parent = multiprocessing.parent_process()
                if parent is not None and not parent.is_alive():
                    return True
                await asyncio.sleep(.1)
        else:
            await emit("stopped")
        finally:
            parent_watch.cancel()
            await asyncio.gather(parent_watch, return_exceptions=True)
    return parent_gone.is_set()


CHILD_TARGET = runtime_child_main


class _RuntimeConnection:
    """child 内原 WS 协程使用的窄通道；send 等 parent 实际 socket 回执。"""
    def __init__(self, metadata, generation, notifications, emit, deliveries, parent_gone):
        from types import SimpleNamespace
        self.connection_ref = metadata["connection_ref"]
        self.connection_generation = metadata["connection_generation"]
        self.query_params = metadata["query"]
        self.client = SimpleNamespace(host=metadata["remote_host"])
        self.inbound = asyncio.Queue(maxsize=IPC_CAPACITY)
        self._generation, self._notifications, self._emit = generation, notifications, emit
        self._deliveries, self._parent_gone = deliveries, parent_gone
        self.task = None
        self.runtime_enqueue = None
        self.pending_envelopes = set()
        self._current_envelope = None
        self.finalizing = False
        self.disconnecting = False
        self._closed = False
        self._state_revision = 0
        self._binding_pin = []
        self._revoked = False
        self._binding_sync = None

    def synchronize_binding(self, pin, *, revoked=False):
        pin = list(pin)
        revoked = self._revoked or revoked
        if pin == self._binding_pin and revoked == self._revoked:
            return self._binding_sync or asyncio.sleep(0)
        self._state_revision += 1
        self._binding_pin, self._revoked = pin, revoked
        previous = self._binding_sync
        self._binding_sync = asyncio.create_task(self._publish_binding(self._state_revision, pin, revoked, previous))
        return self._binding_sync

    async def _receipt(self, future):
        from fastapi import WebSocketDisconnect
        parent_dead = asyncio.create_task(self._parent_gone.wait())
        try:
            done, _ = await asyncio.wait([future, parent_dead], return_when=asyncio.FIRST_COMPLETED)
            if future not in done or future.result() != "sent":
                raise WebSocketDisconnect(code=1006)
        finally:
            parent_dead.cancel()
            await asyncio.gather(parent_dead, return_exceptions=True)

    async def _publish_binding(self, revision, pin, revoked, previous):
        from fastapi import WebSocketDisconnect
        if previous is not None:
            await asyncio.shield(previous)
        if len(self._deliveries) >= IPC_CAPACITY:
            raise WebSocketDisconnect(code=1013)
        identity = f"{self._generation}:{self.connection_generation}:state:{revision}"
        future = asyncio.get_running_loop().create_future()
        self._deliveries[identity] = future
        try:
            await self._emit("connection_state", connection_ref=self.connection_ref,
                connection_generation=self.connection_generation, delivery_id=identity,
                state_revision=revision, binding_pin=pin, revoked=revoked)
            await self._receipt(future)
        finally:
            self._deliveries.pop(identity, None)

    async def accept(self):
        pass

    async def receive_json(self):
        if self._current_envelope is not None:
            sequence = self._current_envelope
            self._current_envelope = None
            await self._emit('envelope_processed', connection_ref=self.connection_ref,
                connection_generation=self.connection_generation, sequence=sequence)
            self.pending_envelopes.discard(sequence)
        value = await self.inbound.get()
        if isinstance(value, tuple):
            self._current_envelope, value = value
        return value

    async def finish_runtime_request(self, request_id, request_sequence):
        # 仅清理已完成/取消命令的 parent 关联，不发送失去授权的业务文本。
        await self._emit('runtime_terminal', connection_ref=self.connection_ref,
            connection_generation=self.connection_generation, request_id=request_id, request_sequence=request_sequence)

    async def finish_envelopes(self):
        for sequence in tuple(self.pending_envelopes):
            await self._emit('envelope_processed', connection_ref=self.connection_ref,
                connection_generation=self.connection_generation, sequence=sequence, error='runtime_connection_closed')
            self.pending_envelopes.discard(sequence)

    async def receive_text(self):
        return _encode(await self.receive_json())

    async def send_runtime_completion(self, message, *, request_sequence):
        await self.send_json(message, request_sequence=request_sequence)

    async def send_fenced_json(self, message, *, lease_deadline):
        await self.send_json(message, lease_deadline=lease_deadline)

    async def send_json(self, message, *, lease_deadline=None, request_sequence=None):
        from fastapi import WebSocketDisconnect
        if self._closed or len(self._deliveries) >= IPC_CAPACITY:
            raise WebSocketDisconnect(code=1013)
        revision = self._state_revision
        if self._binding_sync is not None:
            await asyncio.shield(self._binding_sync)
        if revision != self._state_revision or len(self._deliveries) >= IPC_CAPACITY:
            raise WebSocketDisconnect(code=1006)
        delivery_id = f"{self._generation}:{self.connection_generation}:{uuid4().hex}"
        future = asyncio.get_running_loop().create_future()
        self._deliveries[delivery_id] = future
        try:
            await _put(self._notifications, dict(schema=1, kind="send", generation=self._generation,
                connection_ref=self.connection_ref, connection_generation=self.connection_generation,
                delivery_id=delivery_id, state_revision=revision, lease_deadline=lease_deadline, request_sequence=request_sequence, message=message), abandoned=self._parent_gone)
            await self._receipt(future)
        finally:
            self._deliveries.pop(delivery_id, None)

    async def close(self, code=1000, reason=""):
        self._closed = True
        await self._emit("socket_close", connection_ref=self.connection_ref,
            connection_generation=self.connection_generation, code=code, reason=reason)


async def _dispatch_http(component_app, payload):
    """只复用登记的原 typed HTTP routes；真实 peer/header 由 parent Request 提取。"""
    route = next((route for route in component_app.routes
                  if route.name == payload.get("route") and route.name in RUNTIME_HTTP_ROUTE_NAMES), None)
    if (route is None or payload.get("method") not in route.methods
            or not isinstance(payload.get("path"), str) or not route.path_regex.fullmatch(payload["path"])):
        raise ValueError("runtime_http_route_invalid")
    if (not isinstance(payload.get("body"), str) or not isinstance(payload.get("query"), str)
            or not isinstance(payload.get("remote_host"), str) or type(payload.get("remote_port")) is not int
            or not isinstance(payload.get("headers"), list)
            or any(not isinstance(row, list) or len(row) != 2 or any(not isinstance(x, str) for x in row)
                   for row in payload["headers"])):
        raise ValueError("runtime_http_metadata_invalid")
    scope = dict(type="http", asgi={"version": "3.0"}, http_version="1.1", method=payload["method"],
                 scheme="http", path=payload["path"], raw_path=payload["path"].encode("utf-8"), root_path="",
                 query_string=payload["query"].encode("latin-1"),
                 headers=[(key.encode("latin-1"), value.encode("latin-1")) for key, value in payload["headers"]],
                 client=(payload["remote_host"], payload["remote_port"]), server=("runtime-child", 0))
    response, chunks = {}, []
    received = False
    async def receive():
        nonlocal received
        if received:
            return {"type": "http.disconnect"}
        received = True
        return {"type": "http.request", "body": payload["body"].encode("utf-8"), "more_body": False}
    async def send(message):
        if message["type"] == "http.response.start":
            response.update(status=message["status"], headers=[
                [key.decode("latin-1"), value.decode("latin-1")] for key, value in message.get("headers", [])])
        elif message["type"] == "http.response.body":
            chunks.append(message.get("body", b""))
    await component_app(scope, receive, send)
    response["body"] = b"".join(chunks).decode("utf-8")
    return response
