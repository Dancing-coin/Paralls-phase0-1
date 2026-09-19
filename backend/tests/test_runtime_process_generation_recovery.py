"""真实重启后的旧 IPC 不能命中新进程的关联、连接或业务分派。"""
import asyncio
import json
import os

import pytest


def generation_recovery_child(commands, controls, results, notifications, settings_json):
    from contextlib import ExitStack
    from pathlib import Path
    from unittest.mock import patch
    from app import main
    from app.services import runtime_process
    from scripts.verification.population_godot_runner import write_json

    directory = Path(os.environ["PARALLS_GENERATION_CRASH_PROBE"])
    options = json.loads((directory / "probe.json").read_text(encoding="utf-8"))
    phase, surface = options["phase"], options["surface"]
    original_get, original_put = runtime_process._get, runtime_process._put
    original_http = runtime_process._dispatch_http

    def capture(name, value):
        path = directory / (phase + "-" + name + ".json")
        if not path.exists():
            write_json(path, value)

    async def get(queue):
        raw = await original_get(queue)
        if queue is commands.queue:
            value = runtime_process._decode(raw)
            if value.get("operation") == "http.request":
                capture("command", value)
        return raw

    async def put(queue, value, **kwargs):
        if queue is notifications and value.get("kind") == "send":
            capture("notification", value)
        if queue is results and value.get("kind") == "result":
            capture("result", value)
            if phase == "probe" and surface == "result":
                # 新关联的真实结果暂缓发送，保证负例没有抢跑成功的歧义。
                async with asyncio.timeout(20):
                    while not (directory / "release").exists():
                        await asyncio.sleep(.01)
        return await original_put(queue, value, **kwargs)

    async def http(app, payload):
        capture("http-entered", dict(route=payload["route"], pid=os.getpid()))
        return await original_http(app, payload)

    with ExitStack() as stack:
        stack.enter_context(patch.object(main, "start_population_runtime", lambda: None))
        stack.enter_context(patch.object(runtime_process, "_get", get))
        stack.enter_context(patch.object(runtime_process, "_put", put))
        stack.enter_context(patch.object(runtime_process, "_dispatch_http", http))
        runtime_process.runtime_child_main(commands, controls, results, notifications, settings_json)


@pytest.mark.parametrize("surface", ["result", "notification", "command"])
def test_old_generation_is_rejected_after_actual_owner_restart(tmp_path, monkeypatch, surface):
    from app.config import Settings
    from app.services import runtime_process
    from scripts.verification.population_godot_runner import write_json

    monkeypatch.setenv("PARALLS_GENERATION_CRASH_PROBE", str(tmp_path))
    monkeypatch.setattr(runtime_process, "CHILD_TARGET", generation_recovery_child)
    settings = Settings(heavenly_graph_path=str(tmp_path / "state" / "graph.sqlite3"),
                        character_model_provider_kind="local", siming_llm_mode="disabled")
    http_payload = dict(route="orchestrate_structured_interaction", path="/interaction/orchestrate",
        method="POST", query="", headers=[["content-type", "application/json"]],
        remote_host="127.0.0.1", remote_port=1, body=json.dumps(dict(
            intent=dict(intent_id="intent:restart", actor_id="char_a",
                        target_refs=dict(object_ids=["obj_box"]), semantic_intent="inspect"),
            player_id="player", target_object_id="obj_box", producer_ts=1)))

    async def until(predicate):
        async with asyncio.timeout(8):
            while not predicate():
                await asyncio.sleep(.01)

    async def file(name):
        path = tmp_path / (name + ".json")
        await until(path.exists)
        return json.loads(path.read_text(encoding="utf-8"))

    async def connect(host, sent):
        async def send(message):
            sent.append(message)
        async def close(code, reason):
            pass
        await host.connect("connection:reused", path="/ws", query={}, remote_host="127.0.0.1",
                           send_json=send, close_socket=close)

    async def run():
        write_json(tmp_path / "probe.json", dict(surface=surface, phase="first"))
        first = runtime_process.RuntimeProcess(settings.model_dump_json())
        try:
            await asyncio.wait_for(first.start(), 20)
            old_generation, old_pid = first.snapshot()["process_generation"], first.process.pid
            if surface == "result":
                assert (await first.request("runtime.snapshot", {}))["status"] == "ok"
            elif surface == "notification":
                sent = []
                await connect(first, sent)
                await first.envelope("connection:reused", dict(message_type="character_actor_status",
                                                              payload=dict(actor_id="char_b")))
                await until(lambda: bool(sent))
            else:
                assert (await first.request("http.request", http_payload))["status"] == 200
                assert (await file("first-http-entered"))["pid"] == old_pid
            old_message = await file("first-" + surface)
            assert old_message["generation"] == old_generation
            first.process.terminate()
            await asyncio.to_thread(first.process.join, 5)
            assert not first.process.is_alive() and first.process.exitcode != 0
        finally:
            await first.close()

        write_json(tmp_path / "probe.json", dict(surface=surface, phase="probe"))
        second = runtime_process.RuntimeProcess(settings.model_dump_json())
        pending = None
        try:
            await asyncio.wait_for(second.start(), 20)
            assert second.process.pid != old_pid
            assert second.snapshot()["process_generation"] != old_generation
            if surface == "result":
                pending = asyncio.create_task(second.request("runtime.snapshot", {}))
                new_message = await file("probe-result")
                assert new_message["sequence"] == old_message["sequence"]
                assert not pending.done() and second.pending_count == 1
                second._results.put_nowait(runtime_process._encode(old_message))
                with pytest.raises(runtime_process.RuntimeProcessError):
                    await asyncio.wait_for(pending, 5)
                assert second.pending_count == 0
            elif surface == "notification":
                sent = []
                await connect(second, sent)
                second._notifications.put_nowait(runtime_process._encode(old_message))
                await until(lambda: second._failure is not None)
                assert sent == []
            else:
                second._commands.put_nowait(runtime_process._encode(old_message))
                await until(lambda: second._failure is not None)
                assert not (tmp_path / "probe-http-entered.json").exists()
            assert second.snapshot()["status"] == "unhealthy"
        finally:
            (tmp_path / "release").touch()
            if pending is not None:
                await asyncio.gather(pending, return_exceptions=True)
            await second.close()

        # 未受旧消息污染的新实例仍能走相同原 typed HTTP 业务链。
        write_json(tmp_path / "probe.json", dict(surface=surface, phase="positive"))
        third = runtime_process.RuntimeProcess(settings.model_dump_json())
        try:
            await asyncio.wait_for(third.start(), 20)
            assert (await third.request("http.request", http_payload))["status"] == 200
            assert (await file("positive-http-entered"))["pid"] == third.process.pid
        finally:
            await third.close()
        assert third.process.exitcode == 0

    asyncio.run(run())
