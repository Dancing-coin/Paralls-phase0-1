"""Production composition coverage for the durable slow-goal path."""
import json
import subprocess
import sys
from pathlib import Path

from scripts.verification.population_godot_runner import child_environment


def test_production_lifespan_runs_triggered_slow_goal_to_terminal_receipt(tmp_path):
    (tmp_path / "roster.json").write_text(
        json.dumps({"actor_ids": ["char_a", "char_b", "char_c", *[f"resident_{i:05d}" for i in range(97)]]}),
        encoding="utf-8",
    )
    code = r'''
import asyncio, sys, time
from contextlib import ExitStack
from pathlib import Path
from threading import Event
from unittest.mock import patch

sys.path.insert(0, str(Path.cwd() / "backend" / "tests"))
from scripts.verification.population_mixed_backend import configure
from test_cognition_completion_revision import source_args


async def run():
    with ExitStack() as stack:
        main, _, _ = configure(Path(sys.argv[1]), stack, mode="one_x", provider_mode="local_probe")
        stack.enter_context(patch.object(main, "start_population_runtime", lambda: None))
        started = Event()
        release = Event()

        class GenerativeProvider:
            def complete(self, request):
                started.set()
                assert release.wait(10)
                frame = {
                    "primary_goal": "persist continuity",
                    "goal_portfolio": [],
                }
                return {"active_goal_frame": frame, "evidence_refs": request["context"]["evidence_refs"]}

        async with main.component_app.router.lifespan_context(main.component_app):
            def prepare():
                rt = main.character_agent_runtime
                payload = source_args(rt, "ingest_siming_output")["payload"].model_dump(mode="json")
                rt._l1.apply_siming_output(rt._plan_siming_entry(payload)["normalized_payload"])
                rt.set_background_mode("char_a", "active")
                rt._refresh_weak_supervision_state(actor_id="char_a", producer_ts=0, reason_summary="private snapshot ready")
                rt.ingest_character_perceived_event(__import__("app.models.character_perceived", fromlist=["CharacterPerceivedEvent"]).CharacterPerceivedEvent(
                    actor_id="char_a", percept_channel="visual", producer_ts=100,
                    room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
                    perceived_summary="a failed task is visible", source_candidate_event_id="percept:100",
                    clarity_score=1.0, certainty_score=1.0,
                ))
                main.character_agent_runtime._l3._gateway._router.resolve_route = lambda route_override=None: {
                    "route_mode": "online_default", "provider_kind": "deepseek"
                }
                main.character_agent_runtime._l3._gateway._provider = GenerativeProvider()
                for index in range(3):
                    rt.record_settlement_result(actor_id="char_a", producer_ts=101 + index, payload={
                        "result_id": f"failure:{index}", "result_type": "constraint_state_result",
                        "settlement_status": "rejected", "action_profile": "open",
                        "constraint_summary": "blocked", "causation_id": f"cause:{index}",
                        "correlation_id": f"cause:{index}",
                    })
                sources = [event for event in rt._session_store.list_events("char_a")
                           if event['event_type'] == 'character_goal_proposal_trigger']
                assert len(sources) == 1
                admissions = main._character_cognition_driver.coordinator.admissions
                key = admissions.key_for(source_event_id=sources[0]['event_id'], actor_id='char_a',
                    delivery_id='goal-proposal:' + sources[0]['event_id'])
                return rt._session_store.event_count("char_a"), key

            before, key = await asyncio.wrap_future(main.runtime_execution.submit(prepare))
            deadline = time.monotonic() + 10
            progress = None
            while time.monotonic() < deadline and not started.is_set():
                await asyncio.sleep(0.02)
            if not started.is_set():
                progress = await asyncio.wrap_future(main.runtime_execution.submit(
                    lambda: main._character_cognition_driver.coordinator.admissions.read_progress(key)))
                raise AssertionError(f'production slow-goal provider was not dispatched: {progress}')
            def read_pending():
                admissions = main._character_cognition_driver.coordinator.admissions
                entries = admissions.list_pending(limit=32)
                entry = next((item for item in entries if item.source_kind == "goal_proposal_trigger"), None)
                return None if entry is None else (entry.child_key, admissions.read_progress(entry.child_key))
            key = progress = None
            while time.monotonic() < deadline:
                pending = await asyncio.wrap_future(main.runtime_execution.submit(read_pending))
                if pending is not None and pending[1] is not None:
                    key, progress = pending
                    break
                await asyncio.sleep(0.02)
            release.set()
            assert progress is not None
            assert progress.status == "provider_pending", progress
            while time.monotonic() < deadline:
                def read_terminal():
                    admissions = main._character_cognition_driver.coordinator.admissions
                    return admissions.read_progress(key), admissions.store.read_receipt("char_a", kind="cognition_goal_terminal", key=key)
                progress, terminal = await asyncio.wrap_future(main.runtime_execution.submit(read_terminal))
                if terminal is not None:
                    break
                await asyncio.sleep(0.02)
            assert terminal is not None
            assert progress.status == "completed", (progress.status, progress.reason, terminal)
            def read_events():
                events = main.character_agent_runtime._session_store.list_events("char_a")
                return [event for event in events if event.get("event_type") == "goal_state_event"
                        and event.get("producer_ts") == 103]
            events = await asyncio.wrap_future(main.runtime_execution.submit(read_events))
            assert len(events) == 1, (events, progress, terminal)
            assert main.character_agent_runtime._session_store.event_count("char_a") >= before

asyncio.run(run())
'''
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[2],
        env=child_environment(), capture_output=True, text=True, encoding="utf-8", timeout=35,
    )
    assert result.returncode == 0, result.stderr


def test_production_fast_turn_completes_while_slow_goal_provider_is_pending(tmp_path):
    (tmp_path / "roster.json").write_text(
        json.dumps({"actor_ids": ["char_a", "char_b", "char_c", *[f"resident_{i:05d}" for i in range(97)]]}),
        encoding="utf-8",
    )
    code = r'''
import asyncio, sys, time
from contextlib import ExitStack
from pathlib import Path
from threading import Event
from unittest.mock import patch

sys.path.insert(0, str(Path.cwd() / "backend" / "tests"))
from scripts.verification.population_mixed_backend import configure
from test_cognition_completion_revision import source_args
from app.character_agent.gateway.model_provider import CharacterModelProvider
from app.models.character_perceived import CharacterPerceivedEvent


async def run():
    with ExitStack() as stack:
        main, _, _ = configure(Path(sys.argv[1]), stack, mode="one_x", provider_mode="local_probe")
        stack.enter_context(patch.object(main, "start_population_runtime", lambda: None))
        slow_started, release_slow = Event(), Event()
        fast_task_kinds = []
        offline = CharacterModelProvider(provider_kind="local")

        class MixedProvider:
            def complete(self, request):
                if request.get("output_contract") == "goal_proposal:v1":
                    slow_started.set()
                    assert release_slow.wait(10)
                    return {
                        "active_goal_frame": {"primary_goal": "persist continuity", "goal_portfolio": []},
                        "evidence_refs": request["context"]["evidence_refs"],
                    }
                fast_task_kinds.append(request["task_kind"])
                return offline._offline_complete(request)

        async with main.component_app.router.lifespan_context(main.component_app):
            try:
                def prepare_slow():
                    rt = main.character_agent_runtime
                    payload = source_args(rt, "ingest_siming_output")["payload"].model_dump(mode="json")
                    rt._l1.apply_siming_output(rt._plan_siming_entry(payload)["normalized_payload"])
                    rt.set_background_mode("char_a", "active")
                    rt._refresh_weak_supervision_state(actor_id="char_a", producer_ts=0, reason_summary="private snapshot ready")
                    rt.ingest_character_perceived_event(CharacterPerceivedEvent(
                        actor_id="char_a", percept_channel="visual", producer_ts=100,
                        room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
                        perceived_summary="a failed task is visible", source_candidate_event_id="percept:100",
                        clarity_score=1.0, certainty_score=1.0,
                    ))
                    rt._l3._gateway._router.resolve_route = lambda route_override=None: {
                        "route_mode": "online_default", "provider_kind": "deepseek"
                    }
                    rt._l2._gateway._provider = MixedProvider()
                    rt._l3._gateway._provider = rt._l2._gateway._provider
                    for index in range(3):
                        rt.record_settlement_result(actor_id="char_a", producer_ts=101 + index, payload={
                            "result_id": f"failure:{index}", "result_type": "constraint_state_result",
                            "settlement_status": "rejected", "action_profile": "open",
                            "constraint_summary": "blocked", "causation_id": f"cause:{index}",
                            "correlation_id": f"cause:{index}",
                        })
                    source = next(event for event in rt._session_store.list_events("char_a")
                        if event["event_type"] == "character_goal_proposal_trigger")
                    admissions = main._character_cognition_driver.coordinator.admissions
                    key = admissions.key_for(source_event_id=source["event_id"], actor_id="char_a",
                        delivery_id="goal-proposal:" + source["event_id"])
                    return key

                key = await asyncio.wrap_future(main.runtime_execution.submit(prepare_slow))
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline and not slow_started.is_set():
                    await asyncio.sleep(0.02)
                assert slow_started.is_set(), "production slow provider was not dispatched"

                def prepare_fast_turn():
                    rt = main.character_agent_runtime
                    event = CharacterPerceivedEvent(
                        actor_id="char_a", percept_channel="visual", producer_ts=200,
                        room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
                        perceived_summary="a new fast-loop fact", source_candidate_event_id="percept:200",
                        clarity_score=1.0, certainty_score=1.0,
                    )
                    return rt.prepare_cognition_job(source_kind="ingest_character_perceived_event",
                        payload=event, deadline_monotonic=time.monotonic() + 20)

                advance = await asyncio.wrap_future(main.runtime_execution.submit(prepare_fast_turn))
                assert advance.status == "pending" and advance.next_job is not None, (advance.status, advance.reason)
                for _ in range(4):
                    job = advance.next_job
                    gateway = main.character_agent_runtime._l2._gateway if job.task_kind == "l2_reasoning" \
                        else main.character_agent_runtime._l3._gateway
                    slot = main._dialogue_provider_slots.acquire()
                    assert slot is not None, "fast turn could not acquire a shared provider slot"
                    try:
                        future = slot.submit(job.request_json, gateway, Event(), None,
                            runner=lambda request, provider, _cancelled, _emit: provider.complete_prepared_request(request))
                        output = await asyncio.wrap_future(future)
                    finally:
                        slot.close()
                    advance = await asyncio.wrap_future(main.runtime_execution.submit(
                        lambda job=job, output=output: main.character_agent_runtime.commit_cognition_result(job, output=output)))
                    if advance.status != "pending":
                        break
                assert advance.status == "completed", (advance.status, advance.reason)
                assert {"l2_reasoning", "l3_planning"}.issubset(fast_task_kinds), fast_task_kinds

                release_slow.set()
                terminal = None
                progress = None
                while time.monotonic() < deadline:
                    def read_terminal():
                        admissions = main._character_cognition_driver.coordinator.admissions
                        return admissions.read_progress(key), admissions.store.read_receipt(
                            "char_a", kind="cognition_goal_terminal", key=key)
                    progress, terminal = await asyncio.wrap_future(main.runtime_execution.submit(read_terminal))
                    if terminal is not None:
                        break
                    await asyncio.sleep(0.02)
                assert terminal is not None, progress
                assert progress.status == "stale", (progress.status, progress.reason, terminal)
                slow_events = await asyncio.wrap_future(main.runtime_execution.submit(lambda: [
                    event for event in main.character_agent_runtime._session_store.list_events("char_a")
                    if event.get("event_type") == "goal_state_event" and event.get("producer_ts") == 103
                ]))
                assert slow_events == [], slow_events
            finally:
                release_slow.set()

asyncio.run(run())
'''
    result = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        cwd=Path(__file__).resolve().parents[2],
        env=child_environment(), capture_output=True, text=True, encoding="utf-8", timeout=35,
    )
    assert result.returncode == 0, result.stderr
