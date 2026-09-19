"""真实 owner 在 provider 等待中被终止；同一原库重启后恢复原入站。"""
import asyncio
import json
import os

import pytest


def crash_recovery_child(commands, controls, results, notifications, settings_json):
    from contextlib import ExitStack
    from pathlib import Path
    from threading import get_ident
    from time import monotonic, sleep
    from unittest.mock import patch
    from app import main
    from app.models.siming_heavenly_memory import SimingAdmissionKey
    from app.services.runtime_process import runtime_child_main
    from app.services.siming_llm_provider import DisabledSimingLlmCandidateProvider
    from app.character_agent.gateway.model_gateway import CharacterModelGateway
    from app.character_agent.services.cognition_coordinator import CharacterCognitionCoordinator
    from scripts.verification.population_godot_runner import write_json
    from scripts.verification.population_mixed_provider import _hash
    from test_siming_llm_runtime import make_visual_fact_event, make_candidate

    directory = Path(os.environ["PARALLS_COGNITION_CRASH_PROBE"])
    options = json.loads((directory / "probe.json").read_text(encoding="utf-8"))
    family, phase = options["family"], options["phase"]
    event = make_visual_fact_event()
    key = SimingAdmissionKey(scope=main.SimingHeavenlyRuntimeSupport._scope_for(event), source_event_id=event.event_id)
    child_key = None
    if phase != "first":
        child_key = json.loads((directory / "pending.json").read_text(encoding="utf-8"))["key"]
    task = None
    original_startup = main._start_population_runtime_on_startup
    original_shutdown = main._stop_population_runtime_on_shutdown
    original_character = CharacterModelGateway.complete_prepared_request
    original_freeze = CharacterCognitionCoordinator.freeze_l2
    original_resume = CharacterCognitionCoordinator.resume_l2

    def wait_release():
        deadline = monotonic() + 45
        while not (directory / "release").exists():
            if monotonic() >= deadline:
                raise TimeoutError("crash_probe_not_released")
            sleep(.02)

    def provider_wait(request):
        marker = directory / (phase + "-provider.json")
        if marker.exists():
            return
        write_json(marker, dict(request_digest=_hash(request), provider_thread=[os.getpid(), get_ident()]))
        if family != "character_commit":
            wait_release()

    def siming_provider(provider, **kwargs):
        if family == "siming":
            provider_wait(kwargs)
            return []
        return [make_candidate(target_environment_id=None)]

    def character_provider(gateway, request):
        if family.startswith("character") and json.loads(request)["task_kind"] == "l2_reasoning":
            provider_wait(request)
        return original_character(gateway, request)

    def freeze_l2(coordinator, *args, **kwargs):
        value = original_freeze(coordinator, *args, **kwargs)
        if family == "character_commit" and phase == "first":
            assert value.status == "commit_started" and value.plan is not None
            write_json(directory / "pending.json", snapshot())
            wait_release()
        return value

    def resume_l2(coordinator, *args, **kwargs):
        if family == "character_commit" and phase == "resume" and not (directory / "restored.json").exists():
            value = snapshot()
            assert value["status"] == "commit_started"
            write_json(directory / "restored.json", value)
            wait_release()
        return original_resume(coordinator, *args, **kwargs)

    def snapshot():
        nonlocal child_key
        rt = main.character_agent_runtime
        if family == "siming":
            admissions = main._siming_cognition_driver.coordinator.admissions
            receipt = admissions.read(key)
            if receipt is None or receipt.entry.provider_revision is None:
                return None
            entry = receipt.entry
            admission = entry.model_dump(mode="json", include={"key", "source", "source_digest", "source_outbox_ref",
                "source_transaction_ref", "admitted_at", "expires_at", "policy_version", "room_sequence"})
            provider = admissions.read(key, revision=entry.provider_revision).entry.transition.provider
            progress = dict(status=entry.state, revision=entry.revision, request_json=provider.request_json)
            identity = key.model_dump(mode="json")
        else:
            admissions = main._character_cognition_driver.coordinator.admissions
            if child_key is None:
                entries = [row for row in admissions.list_pending() if row.actor_id == "char_b"
                    and row.source_kind == "ingest_siming_output"]
                if not entries:
                    return None
                assert len(entries) == 1
                child_key = entries[0].child_key
            entry, current = admissions.read(child_key), admissions.read_progress(child_key)
            if current is None:
                return None
            admission = entry.model_dump(mode="json")
            # 最终阶段的 request 可能已变为 L3；保留当前真实进度，不回填旧摘要。
            progress = dict(status=current.status, revision=current.revision, request_json=current.request_json)
            identity = child_key
        return dict(owner_pid=os.getpid(), owner_thread=[os.getpid(), get_ident()], key=identity,
            admission=admission, timeline=rt.get_session_timeline("char_b"),
            authority_head=main.gameplay_event_store.get_last_global_sequence(), **progress)

    async def observe():
        try:
            if phase == "first":
                await asyncio.wrap_future(main.runtime_execution.submit(lambda: main.authority_event_bus.publish(event)))
            async with asyncio.timeout(22):
                while True:
                    value = await asyncio.wrap_future(main.runtime_execution.submit(snapshot))
                    if phase == "stable":
                        assert value is not None and value["status"] == "completed"
                        await asyncio.sleep(.2)
                        write_json(directory / "stable.json", await asyncio.wrap_future(main.runtime_execution.submit(snapshot)))
                        return
                    target = directory / ("pending.json" if phase == "first" else "restored.json")
                    if (family != "character_commit" and not target.exists() and value is not None
                            and value["status"] == "provider_pending" and (directory / (phase + "-provider.json")).exists()):
                        write_json(target, value)
                        if phase == "first":
                            return
                    if phase == "resume" and value is not None and value["status"] in {"completed", "stale", "failed", "cancelled"}:
                        write_json(directory / "completed.json", value)
                        return
                    await asyncio.sleep(.02)
        except BaseException as error:
            write_json(directory / "probe-error.json", dict(type=type(error).__name__, message=str(error)))
            raise

    async def startup():
        nonlocal task
        await original_startup()
        task = asyncio.create_task(observe())

    async def shutdown():
        try:
            if task is not None and not task.done():
                task.cancel()
            if task is not None:
                await asyncio.gather(task, return_exceptions=True)
        finally:
            await original_shutdown()

    with ExitStack() as stack:
        stack.enter_context(patch.object(main, "start_population_runtime", lambda: None))
        stack.enter_context(patch.object(main, "_start_population_runtime_on_startup", startup))
        stack.enter_context(patch.object(main, "_stop_population_runtime_on_shutdown", shutdown))
        stack.enter_context(patch.object(DisabledSimingLlmCandidateProvider, "generate_candidates", siming_provider))
        stack.enter_context(patch.object(CharacterModelGateway, "complete_prepared_request", character_provider))
        stack.enter_context(patch.object(CharacterCognitionCoordinator, "freeze_l2", freeze_l2))
        stack.enter_context(patch.object(CharacterCognitionCoordinator, "resume_l2", resume_l2))
        runtime_child_main(commands, controls, results, notifications, settings_json)


@pytest.mark.parametrize("family", ["siming", "character", "character_commit"])
def test_original_owner_provider_pending_survives_hard_kill_without_reingest(tmp_path, monkeypatch, family):
    from app.config import Settings
    from app.services import runtime_process
    from scripts.verification.population_godot_runner import write_json

    monkeypatch.setenv("PARALLS_COGNITION_CRASH_PROBE", str(tmp_path))
    monkeypatch.setattr(runtime_process, "CHILD_TARGET", crash_recovery_child)
    settings = Settings(heavenly_graph_path=str(tmp_path / "state" / "graph.sqlite3"),
        character_model_provider_kind="local", siming_llm_mode="disabled")

    async def file_for(name, host):
        async with asyncio.timeout(25):
            while not (tmp_path / name).exists():
                assert host.process.is_alive()
                if (tmp_path / "probe-error.json").exists():
                    pytest.fail((tmp_path / "probe-error.json").read_text(encoding="utf-8"))
                await asyncio.sleep(.02)
        return json.loads((tmp_path / name).read_text(encoding="utf-8"))

    async def run():
        write_json(tmp_path / "probe.json", dict(family=family, phase="first"))
        first = runtime_process.RuntimeProcess(settings.model_dump_json())
        try:
            await first.start()
            pending = await file_for("pending.json", first)
            assert pending["owner_pid"] == first.process.pid != os.getpid()
            assert pending["status"] == ("commit_started" if family == "character_commit" else "provider_pending")
            first.process.terminate()
            await asyncio.to_thread(first.process.join, 5)
            assert not first.process.is_alive() and first.process.exitcode != 0
            assert first.snapshot()["status"] == "unhealthy"
        finally:
            if first.process.is_alive():
                first.process.terminate()
                await asyncio.to_thread(first.process.join, 5)
            await first.close()
        write_json(tmp_path / "probe.json", dict(family=family, phase="resume"))
        second = runtime_process.RuntimeProcess(settings.model_dump_json())
        try:
            await second.start()
            restored = await file_for("restored.json", second)
            assert restored["owner_pid"] == second.process.pid != pending["owner_pid"]
            assert restored["status"] == pending["status"]
            assert restored["key"] == pending["key"]
            assert restored["admission"] == pending["admission"]
            assert restored["request_json"] == pending["request_json"]
            assert restored["timeline"][:len(pending["timeline"])] == pending["timeline"]
            (tmp_path / "release").touch()
            completed = await file_for("completed.json", second)
            assert completed["status"] == "completed" and completed["key"] == pending["key"]
            if family != "siming":
                assert [row for row in completed["timeline"] if row["event_type"] in {"siming_output_event", "l2_reasoning_request"}] == [
                    row for row in pending["timeline"] if row["event_type"] in {"siming_output_event", "l2_reasoning_request"}]
                assert sum(row["event_type"] == "siming_output_event" for row in completed["timeline"]) == 1
            else:
                assert completed["authority_head"] == pending["authority_head"]
        finally:
            (tmp_path / "release").touch()
            await second.close()
        assert second.process.exitcode == 0
        write_json(tmp_path / "probe.json", dict(family=family, phase="stable"))
        third = runtime_process.RuntimeProcess(settings.model_dump_json())
        try:
            await third.start()
            stable = await file_for("stable.json", third)
            assert {k:v for k,v in stable.items() if k not in {"owner_pid", "owner_thread"}} == {k:v for k,v in completed.items() if k not in {"owner_pid", "owner_thread"}}
            assert not (tmp_path / "stable-provider.json").exists()
        finally:
            await third.close()
        assert third.process.exitcode == 0
        first_call = json.loads((tmp_path / "first-provider.json").read_text(encoding="utf-8"))
        assert first_call["provider_thread"] != pending["owner_thread"]
        if family == "character_commit":
            assert not (tmp_path / "resume-provider.json").exists()
        else:
            resumed_call = json.loads((tmp_path / "resume-provider.json").read_text(encoding="utf-8"))
            assert first_call["request_digest"] == resumed_call["request_digest"]
            assert resumed_call["provider_thread"] != restored["owner_thread"]

    asyncio.run(run())
