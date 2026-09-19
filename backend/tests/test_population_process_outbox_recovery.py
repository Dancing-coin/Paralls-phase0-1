"""原 main owner 被强杀后，由原启动和窗口链恢复持久 outbox。"""
import asyncio
import json
import os

import pytest


def outbox_recovery_child(commands, controls, results, notifications, settings_json):
    from contextlib import ExitStack
    from pathlib import Path
    from threading import get_ident
    from time import monotonic, sleep
    from unittest.mock import patch
    from app import main
    from app.gameplay.event_store import DurableGameplayEventStore
    from app.gameplay.organization_government_runtime import OrganizationAuthority
    from app.services.authority_event_bus import InMemoryAuthorityEventBus
    from app.services.runtime_process import runtime_child_main
    from scripts.verification.population_godot_runner import write_json
    from test_population_organization_due_source import schedule, window

    directory = Path(os.environ["PARALLS_OUTBOX_CRASH_PROBE"])
    options = json.loads((directory / "probe.json").read_text(encoding="utf-8"))
    cut, phase = options["cut"], options["phase"]
    target_tx = "tx:mirror-source" if cut == "before_done" else "transaction:schedule:process-crash"
    domain_topic = "population_domain_cadence_event"
    task = None
    observed = dict(published=[], refresh_completed=[])
    original_startup = main._start_population_runtime_on_startup
    original_shutdown = main._stop_population_runtime_on_shutdown
    original_publish = InMemoryAuthorityEventBus.publish
    original_delivered = DurableGameplayEventStore.mark_outbox_delivered
    original_done = DurableGameplayEventStore.mark_projection_refreshed

    def snapshot():
        store = main.gameplay_event_store
        if cut == "domain":
            entries = store.list_outbox(topic=domain_topic)
            assert len(entries) == 1
            transaction = store.get_transaction(entries[0].transaction_id)
            record = store.get_event(entries[0].event_id).payload
            facts = [row.model_dump(mode="json") for row in store.read_events()
                     if row.event_type == "gameplay.organization.operating_window_due_recorded"]
            driver = main._population_runtime_driver
            extra = dict(domain_record=record, owner_facts=facts,
                         confirmed_tick=driver.world_runtime.latest_confirmation.window_end,
                         window_size=driver.window_size,
                         recovery_state=driver.world_runtime.export_recovery_state(),
                         due=list(driver.world_runtime.due_population_work(86400)))
        else:
            transaction = store.get_transaction(target_tx)
            assert transaction is not None
            entries = [store.get_outbox(row.outbox_id) for row in transaction.outbox_entries]
            extra = {}
            if cut == "before_done":
                publisher = main.gameplay_godot_projection_publisher
                source = publisher.actor_source(actor_ref="actor:configured")
                from app.gameplay.godot_mirror_delivery import GameplayMirrorDeliveryError
                try:
                    view = main.gameplay_godot_projection_repository.view_for("actor:configured")
                except GameplayMirrorDeliveryError:
                    if phase != "stable":
                        raise
                    view = None
                from dataclasses import fields, is_dataclass
                from collections.abc import Mapping
                def plain(value):
                    if is_dataclass(value):
                        return {field.name: plain(getattr(value, field.name)) for field in fields(value)}
                    if isinstance(value, Mapping):
                        return {key: plain(item) for key, item in value.items()}
                    if isinstance(value, (tuple, list)):
                        return [plain(item) for item in value]
                    return value
                extra = dict(source_view=plain(source()), published_view=plain(view))
        refresh = store._rows("SELECT refresh_state FROM transactions WHERE transaction_id=?",
                              (transaction.transaction_id,))[0][0]
        key = transaction.idempotency_record
        return dict(owner_pid=os.getpid(), owner_thread=[os.getpid(), get_ident()],
                    transaction=transaction.model_dump(mode="json"),
                    receipt=store.get_by_idempotency(key.principal_ref, key.idempotency_key).model_dump(mode="json"),
                    outboxes=[row.model_dump(mode="json") for row in entries], refresh_state=refresh,
                    observed=observed.copy(), **extra)

    def block_at_cut():
        write_json(directory / "pending.json", snapshot())
        deadline = monotonic() + 35
        while not (directory / "release").exists():
            if monotonic() >= deadline:
                raise TimeoutError("outbox_crash_probe_not_released")
            sleep(.02)

    def publish(bus, event):
        selected = event.payload.get("transaction_id") == target_tx
        if selected and phase == "first" and cut == "before_publish":
            block_at_cut()
        result = original_publish(bus, event)
        if selected:
            observed["published"].append(event.event_id)
        return result

    def delivered(store, outbox_id):
        if cut == "domain" and phase == "first" and store.get_outbox(outbox_id).topic == domain_topic:
            # 原 publish、Owner 提交和 delivery validator 已返回，delivery 标记尚未写入。
            block_at_cut()
        return original_delivered(store, outbox_id)

    def done(store, transaction_id):
        if transaction_id == target_tx:
            # 原 dispatcher 只有在其整个 refresh 回调成功返回后才调用这里。
            observed["refresh_completed"].append(transaction_id)
            if phase == "first" and cut == "before_done":
                block_at_cut()
        return original_done(store, transaction_id)

    def first_work():
        authority = OrganizationAuthority(store=main.gameplay_event_store)
        if cut == "before_done":
            from app.gameplay.event_store import GameplayEventStore
            from test_phase3_mirror_source import _append_resource_state
            # 复用原真实来源事件；仅为该测试事务增加明确的原刷新提示。
            source_store = GameplayEventStore()
            _append_resource_state(source_store, actor_ref="actor:configured")
            batch = source_store.get_transaction(target_tx).model_dump(mode="json")
            from test_gameplay_event_store_contract import _outbox
            batch["outbox_entries"] = [_outbox(event["event_id"], tx=target_tx) for event in batch["events"]]
            batch["projection_refresh_hints"] = [dict(
                projection_id="godot_mirror", stream_id="gameplay:resources:actor:configured",
                reason="committed_resource", actor_refs=["actor:configured"])]
            assert main.gameplay_event_store.append_batch(batch).committed
        else:
            schedule(authority, "process-crash", "char_b")
        if cut == "domain":
            window(authority, "process-crash")
            driver = main._population_runtime_driver
            result = driver.tick(driver.current_tick + driver.window_size)
            assert not result.rejected_windows, result.rejected_windows
        else:
            main.gameplay_outbox_dispatcher.dispatch_pending()
        if phase != "baseline":
            raise AssertionError("outbox_crash_cut_not_reached")

    async def observe():
        try:
            if phase in {"first", "baseline"}:
                await asyncio.wrap_future(main.runtime_execution.submit(first_work))
                if phase == "first":
                    return
            if cut == "domain" and phase == "resume":
                write_json(directory / "restored.json", await asyncio.wrap_future(main.runtime_execution.submit(snapshot)))
                driver = main._population_runtime_driver
                # 下一次原窗口自行泵送持久域待办；不手工改状态或调用替代 dispatcher。
                await asyncio.wrap_future(main.runtime_execution.submit(
                    lambda: driver.tick(driver.current_tick + driver.window_size)))
            output = "baseline.json" if phase == "baseline" else "completed.json" if phase == "resume" else "stable.json"
            write_json(directory / output,
                       await asyncio.wrap_future(main.runtime_execution.submit(snapshot)))
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
        stack.enter_context(patch.object(InMemoryAuthorityEventBus, "publish", publish))
        stack.enter_context(patch.object(DurableGameplayEventStore, "mark_outbox_delivered", delivered))
        stack.enter_context(patch.object(DurableGameplayEventStore, "mark_projection_refreshed", done))
        runtime_child_main(commands, controls, results, notifications, settings_json)


@pytest.mark.parametrize("cut", ["before_publish", "before_done", "domain"])
def test_original_owner_outbox_recovers_after_hard_kill(tmp_path, monkeypatch, cut):
    from app.config import Settings
    from app.services import runtime_process
    from scripts.verification.population_godot_runner import write_json

    monkeypatch.setenv("PARALLS_OUTBOX_CRASH_PROBE", str(tmp_path))
    monkeypatch.setattr(runtime_process, "CHILD_TARGET", outbox_recovery_child)
    from test_phase3_mirror_source import _configuration
    settings = Settings(gameplay_mirror_phase3_actor_configs=[_configuration().model_dump(mode="json")]
                        if cut == "before_done" else [], heavenly_graph_path=str(tmp_path / "state" / "graph.sqlite3"),
                        character_model_provider_kind="local", siming_llm_mode="disabled")

    async def read(name, host):
        async with asyncio.timeout(25):
            while not (tmp_path / name).exists():
                assert host.process.is_alive()
                if (tmp_path / "probe-error.json").exists():
                    pytest.fail((tmp_path / "probe-error.json").read_text(encoding="utf-8"))
                await asyncio.sleep(.02)
        value = json.loads((tmp_path / name).read_text(encoding="utf-8"))
        assert value["owner_pid"] == host.process.pid != os.getpid()
        return value

    async def run():
        baseline = None
        if cut == "before_done":
            write_json(tmp_path / "probe.json", dict(cut=cut, phase="baseline"))
            baseline_settings = settings.model_copy(update={"heavenly_graph_path": str(tmp_path / "baseline" / "graph.sqlite3")})
            no_fault = runtime_process.RuntimeProcess(baseline_settings.model_dump_json())
            try:
                await no_fault.start()
                baseline = await read("baseline.json", no_fault)
            finally:
                await no_fault.close()
            assert no_fault.process.exitcode == 0
        write_json(tmp_path / "probe.json", dict(cut=cut, phase="first"))
        first = runtime_process.RuntimeProcess(settings.model_dump_json())
        try:
            await first.start()
            pending = await read("pending.json", first)
            assert pending["refresh_state"] == "pending"
            assert all(row["delivery_state"] == ("delivered" if cut == "before_done" else "pending")
                       for row in pending["outboxes"])
            if cut == "domain":
                assert len(pending["owner_facts"]) == 1
            else:
                assert pending["observed"]["published"] == (
                    [row["event_id"] for row in pending["outboxes"]] if cut == "before_done" else [])
                assert len(pending["observed"]["refresh_completed"]) == (1 if cut == "before_done" else 0)
            if cut == "before_done":
                assert pending["transaction"]["projection_refresh_hints"]
                assert len(pending["outboxes"]) == 3
                assert baseline["observed"]["published"] == pending["observed"]["published"]
                assert pending["published_view"] == pending["source_view"] == baseline["published_view"]
                assert pending["published_view"]["groups"]["core.resources"]["payload"]["entries"]["core.stamina"]["current"] == 7
                assert pending["published_view"]["source_revision_vector"]
            first.process.terminate()
            await asyncio.to_thread(first.process.join, 5)
            assert not first.process.is_alive() and first.process.exitcode != 0
        finally:
            if first.process.is_alive():
                first.process.terminate()
                await asyncio.to_thread(first.process.join, 5)
            await first.close()
        write_json(tmp_path / "probe.json", dict(cut=cut, phase="resume"))
        second = runtime_process.RuntimeProcess(settings.model_dump_json())
        try:
            await second.start()
            completed = await read("completed.json", second)
            assert completed["owner_pid"] != pending["owner_pid"]
            assert completed["transaction"] == pending["transaction"]
            assert completed["receipt"] == pending["receipt"]
            assert all(row["delivery_state"] == "delivered" for row in completed["outboxes"]), [
                (row["delivery_state"], row["last_error"]) for row in completed["outboxes"]]
            assert completed["refresh_state"] == "done"
            for before, after in zip(pending["outboxes"], completed["outboxes"], strict=True):
                assert {k:v for k,v in before.items() if k != "delivery_state"} == {
                    k:v for k,v in after.items() if k != "delivery_state"}
            if cut == "before_done":
                assert completed["published_view"] == completed["source_view"] == baseline["published_view"]
                assert completed["transaction"] == baseline["transaction"]
            if cut == "domain":
                restored = await read("restored.json", second)
                assert restored["domain_record"] == completed["domain_record"] == pending["domain_record"]
                assert restored["owner_facts"] == completed["owner_facts"] == pending["owner_facts"]
                assert restored["confirmed_tick"] == pending["confirmed_tick"]
                assert completed["confirmed_tick"] == restored["confirmed_tick"] + restored["window_size"]
                assert not any(row[1].startswith("projection:organization-window-due:") for row in completed["due"])
            else:
                assert completed["observed"]["published"] == (
                    [row["event_id"] for row in pending["outboxes"]] if cut == "before_publish" else [])
                assert completed["observed"]["refresh_completed"] == [pending["transaction"]["transaction_id"]]
        finally:
            await second.close()
        assert second.process.exitcode == 0
        write_json(tmp_path / "probe.json", dict(cut=cut, phase="stable"))
        third = runtime_process.RuntimeProcess(settings.model_dump_json())
        try:
            await third.start()
            stable = await read("stable.json", third)
            assert stable["owner_pid"] not in (pending["owner_pid"], completed["owner_pid"])
            assert stable["observed"] == dict(published=[], refresh_completed=[])
            if cut == "before_done":
                assert stable["published_view"] is None
                assert stable["source_view"] == baseline["source_view"]
            assert {k:v for k,v in stable.items() if k not in {"owner_pid", "owner_thread", "observed", "published_view"}} == {
                k:v for k,v in completed.items() if k not in {"owner_pid", "owner_thread", "observed", "published_view"}}
        finally:
            await third.close()
        assert third.process.exitcode == 0

    asyncio.run(run())
