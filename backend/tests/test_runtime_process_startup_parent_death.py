"""真实 spawn/owner 初始化；父进程生存状态由跨进程门精确控制。"""
import asyncio
from contextlib import closing
from functools import partial
from pathlib import Path
import sqlite3

import pytest

from app.config import Settings
from app.services.runtime_process import RuntimeProcess, RuntimeProcessError
from app.world_runtime.storage_lease import RuntimeStorageLease
from test_runtime_process import settings_json


def initializing_child(commands, controls, results, notifications, settings_json,
                       *, entered, parent_dead, release):
    from app import main
    from app.services import runtime_process

    original_parent = runtime_process.multiprocessing.parent_process()
    original_reset = main._reset_runtime_state
    original_put = results.put_nowait
    path = Path(Settings.model_validate_json(settings_json).heavenly_graph_path)
    messages_path = path.with_name(path.name + ".lifecycle-messages")

    class Parent:
        def is_alive(self):
            return not parent_dead.is_set() and original_parent.is_alive()

    def record_message(value):
        kind = runtime_process._decode(value)["kind"]
        if kind in {"ready", "stopped"}:
            with messages_path.open("a", encoding="utf-8") as stream:
                stream.write(kind + "\n")
        return original_put(value)

    def initialize(**kwargs):
        original_reset(**kwargs)
        connection = main.heavenly_graph._connection
        assert connection.execute("PRAGMA journal_mode").fetchone() == ("wal",)
        assert connection.execute("PRAGMA synchronous").fetchone() == (2,)
        connection.execute("CREATE TABLE startup_parent_loss_probe (value TEXT PRIMARY KEY)")
        connection.execute("INSERT INTO startup_parent_loss_probe VALUES ('committed')")
        connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("INSERT INTO startup_parent_loss_probe VALUES ('uncommitted')")
        entered.set()
        release.acquire()
        connection.rollback()

    runtime_process.multiprocessing.parent_process = lambda: Parent()
    main._reset_runtime_state = initialize
    results.put_nowait = record_message
    runtime_process.runtime_child_main(commands, controls, results, notifications, settings_json)


@pytest.mark.parametrize("parent_dies", [True, False], ids=["parent-dead", "parent-alive"])
def test_spawn_startup_parent_death_releases_original_owner_and_atomic_wal(tmp_path, monkeypatch, parent_dies):
    from app.services import runtime_process

    context = runtime_process.multiprocessing.get_context("spawn")
    entered, parent_dead = (context.Event() for _ in range(2))
    # 硬退出可能留下 Event 的 waiter 回执；semaphore release 无需等待已死子进程。
    release = context.Semaphore(0)
    monkeypatch.setattr(runtime_process, "CHILD_TARGET", partial(initializing_child,
        entered=entered, parent_dead=parent_dead, release=release))
    settings = Settings.model_validate_json(settings_json())
    path = tmp_path / "startup.sqlite3"
    settings.heavenly_graph_path = str(path)
    messages_path = path.with_name(path.name + ".lifecycle-messages")

    async def run():
        host = RuntimeProcess(settings.model_dump_json())
        startup = asyncio.create_task(host.start())
        try:
            # 冷导入不计入死亡后的五秒期限；必须先进入真实 owner 初始化。
            assert await asyncio.to_thread(entered.wait, 20), "owner_initialize_not_entered"
            assert not startup.done() and host.process.is_alive()
            with pytest.raises(RuntimeError, match="runtime_storage_in_use"):
                RuntimeStorageLease(path)
            assert not messages_path.exists()
            if parent_dies:
                parent_dead.set()
                await asyncio.to_thread(host.process.join, 5)
                assert not host.process.is_alive(), "父进程已死亡时，初始化中的 owner 不得残留"
                assert host.process.exitcode == 1
                with pytest.raises(RuntimeProcessError):
                    await asyncio.wait_for(startup, 5)
                assert not messages_path.exists(), "终结未完成的初始化不能发送 ready 或 STOPPED"
            else:
                # 活 parent 必须保持同一 owner，释放初始化后仍走正常 ready/STOPPED。
                await asyncio.sleep(.1)
                assert host.process.is_alive() and not startup.done()
                release.release()
                await asyncio.wait_for(startup, 20)
                assert host.snapshot()["status"] == "ok"
        finally:
            release.release()
            if not startup.done():
                startup.cancel()
            await asyncio.gather(startup, return_exceptions=True)
            await host.close()
        assert host.process.exitcode == (1 if parent_dies else 0)

    asyncio.run(run())
    with RuntimeStorageLease(path) as lease:
        assert lease.path.exists()
        with closing(sqlite3.connect(path)) as connection:
            assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
            assert connection.execute("SELECT value FROM startup_parent_loss_probe").fetchall() == [("committed",)]
    if not parent_dies:
        assert messages_path.read_text(encoding="utf-8").splitlines() == ["ready", "stopped"]
