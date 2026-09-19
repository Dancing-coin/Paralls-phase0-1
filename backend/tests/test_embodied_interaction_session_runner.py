"""真实后端探针隔离回归；Python客户端代替Godot，不作为引擎运行证据。"""
from __future__ import annotations

import asyncio
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest
import websockets


ROOT = Path(__file__).resolve().parents[2]


async def _receive_session_events() -> list[dict]:
    async with websockets.connect("ws://127.0.0.1:8000/ws") as socket:
        await socket.send(json.dumps({
            "message_type": "embodied_interaction_session_probe",
            "payload": {
                "session_id": "session:handshake:godot-websocket",
                "semantic_action": "handshake",
                "initiator_ref": "character:siming",
                "participant_refs": ["character:siming", "character:maya"],
                "target_refs": ["character:maya"],
            },
        }))
        messages = []
        try:
            async with asyncio.timeout(3):
                while len(messages) < 5:
                    messages.append(json.loads(await socket.recv()))
        except TimeoutError:
            pass
        return messages


@pytest.mark.parametrize("enforce_wall_clock", [False, True], ids=["isolated-storage", "wall-clock"])
def test_profile_repeated_in_one_run_receives_fresh_events(monkeypatch, enforce_wall_clock):
    monkeypatch.syspath_prepend(str(ROOT / "scripts/verification"))
    gate = importlib.import_module("scripts.verification.verify_embodied_interaction_session")
    from run_context import attempt_scope, run_scope
    from common import verification_dir

    # 全套Harness中执行本测试时也拥有独立上下文，不覆盖父级profile的证据。
    for key in ("HARNESS_RUN_ID", "HARNESS_PROJECT_ROOT", "HARNESS_EVIDENCE_ROOT",
                "HARNESS_ATTEMPT_ROOT", "HARNESS_ATTEMPT_ID"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("CHARACTER_MODEL_PROVIDER_KIND", "local")
    monkeypatch.setenv("SIMING_LLM_MODE", "disabled")
    monkeypatch.setattr(sys, "argv", ["verify", "--godot-exe", sys.executable])
    observations = []
    storage_paths = []
    ensure_backend = gate.ensure_backend

    def start_backend(*args, **kwargs):
        storage_paths.append(Path(kwargs["env"]["PARALLS_HEAVENLY_GRAPH_PATH"]))
        return ensure_backend(*args, **kwargs)

    monkeypatch.setattr(gate, "ensure_backend", start_backend)

    def run(command, cwd, log, **kwargs):
        log.write_text("Python验证客户端，未运行Godot\n", encoding="utf-8")
        if command[1:3] == ["-m", "pytest"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if enforce_wall_clock:
            # 帧计数会在联网等待完成前退出；进程兜底必须按真实秒数。
            assert "--quit-after" not in command
            assert 8 < kwargs["timeout_seconds"] <= 30
        messages = asyncio.run(_receive_session_events())
        events = [row["payload"] for row in messages if row["message_type"] == "embodied_interaction_session_event"]
        observations.append(events)
        live_ok = len(events) == 4 and events[-1]["state"] == "realizing"
        # 只替代前端报告；消息必须从原Uvicorn/owner进程的真实WS收到。
        gate.write_json(verification_dir(ROOT) / "embodied-interaction-session-godot-runtime.json", {
            "status": "godot-runtime-interaction-session-verified" if live_ok else "test-client-failed",
            "bridge_route_ok": True, "bus_signal_ok": True, "bridge_legacy_reuse": False,
            "live_backend": {"accepted": live_ok},
        })
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(gate, "run_command", run)
    with run_scope(ROOT) as context:
        for profile in ("harness-embodied-task", "embodied-interaction-session"):
            with attempt_scope(context, profile, 1):
                assert gate.main() == 0
    assert len(observations) == 2
    assert len(set(storage_paths)) == 2
    assert all(not path.parent.exists() for path in storage_paths)
    assert all([row["event_type"] for row in events] == [
        "embodied.interaction_session.proposed", "embodied.interaction_session.accepted",
        "embodied.interaction_session.authorized", "embodied.interaction_session.realizing",
    ] for events in observations)
