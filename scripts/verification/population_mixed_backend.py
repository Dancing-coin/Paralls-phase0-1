"""混合负载的服务端启动装配与故障；不新增生产 HTTP 写入口。"""
import asyncio
from contextlib import closing
from time import perf_counter, sleep
import sqlite3


def runtime_sample(main, driver, publisher):
    """owner 内的当前计数；不扫描历史账本，不把峰值RSS冒充当前驻留内存。"""
    from time import process_time
    from scripts.verification.population_benchmark_metrics import current_rss_bytes
    from scripts.verification.verify_population_long_session_recovery import ready_caches
    world = driver.world_runtime
    caches = ready_caches(main, driver)
    authority_bus_types = main.authority_event_bus.event_counts()
    caches.update(cadence=len(world._cadence_cache), projection=len(world._projection_cache),
        preview=len(world._preview_results), publisher_records=len(publisher._records),
        authority_bus=sum(authority_bus_types.values()), authority_bus_types=authority_bus_types)
    directory = main.gameplay_event_store._snapshot_path.parent
    files = {path.name: path.stat().st_size for path in directory.iterdir() if path.is_file()}
    return dict(at=perf_counter(), confirmed_tick=driver.current_tick,
        rss_bytes=current_rss_bytes(), cpu_seconds=process_time(), storage_bytes=files,
        caches=caches, execution=main.runtime_execution.snapshot())


class MixedWindowProbe:
    """包住原 owner 的每次 tick；合法fixture写入时间单列，墙钟迟延包含全部工作。"""
    def __init__(self, main, schedule, duration_seconds, record):
        from itertools import groupby
        self.main, self.schedule, self.record = main, schedule, record
        self.events = iter((index, list(rows)) for index, rows in groupby(
            (event for event in schedule.events(duration_seconds) if event.kind in {"regular_due", "due_peak"}),
            key=lambda event: event.window_index))
        self.next_due = next(self.events, None)
        self.publisher = None
        self.latest = None
        self.origin = None
        self.driver_origin = None
        self.driver_monotonic_origin = None

    def install(self, stack):
        from unittest.mock import patch
        from app.population_continuity.runtime_publication import RuntimeCadencePublisher
        from app.world_runtime import population_driver
        original = RuntimeCadencePublisher.__call__
        def publish(publisher, cadence):
            self.publisher = publisher
            return original(publisher, cadence)
        stack.enter_context(patch.object(RuntimeCadencePublisher, "__call__", publish))
        clock = population_driver.monotonic
        self._driver_clock = clock
        def observe_clock():
            value = clock()
            if self.driver_origin is None:
                # 原run_forever第一次真实读时钟位于owner的origin屏障；不替换或压缩时钟值。
                self.driver_origin = perf_counter()
                self.driver_monotonic_origin = value
                self.record(dict(type="driver_clock_origin", monotonic=value, at=self.driver_origin))
            return value
        stack.enter_context(patch.object(population_driver, "monotonic", observe_clock))

    def attach(self):
        from dataclasses import asdict
        from scripts.verification.population_mixed_fixture import prepare_due_fixture
        driver = self.main._population_runtime_driver
        original = driver.tick
        def tick(target):
            if self.origin is None or self.driver_origin is None or target != driver.current_tick + 1:
                raise ValueError("mixed_window_origin_or_stride_invalid")
            started, previous_tick = perf_counter(), driver.current_tick
            driver_started = self._driver_clock()
            fixture_rows = []
            if self.next_due is not None and self.next_due[0] < target:
                raise ValueError("mixed_window_fixture_skipped")
            if self.next_due is not None and self.next_due[0] == target:
                for event in self.next_due[1]:
                    rows = prepare_due_fixture(store=self.main.gameplay_event_store,
                        actors=driver.world_runtime.roster.actor_ids, event=event)
                    fixture_rows.append(dict(key=event.transaction_id, kind=event.kind, rows=rows))
            cadence_started = perf_counter()
            result = original(target)
            driver_finished = self._driver_clock()
            finished = perf_counter()
            if driver.current_tick == target and self.next_due is not None and self.next_due[0] == target:
                self.next_due = next(self.events, None)
            if self.publisher is None:
                raise ValueError("mixed_window_publisher_missing")
            sample = runtime_sample(self.main, driver, self.publisher)
            period = self.schedule.window_ms / 1000
            expected_tick = max(0, int((driver_finished - self.driver_monotonic_origin) / period))
            row = dict(type="window", expected_at=self.driver_origin + target * period,
                driver_started_at=driver_started, driver_finished_at=driver_finished,
                started_at=started, cadence_started_at=cadence_started, finished_at=finished,
                target_tick=target, previous_tick=previous_tick,
                fixture_ms=(cadence_started-started)*1000, cadence_ms=(finished-cadence_started)*1000,
                backlog=max(0, expected_tick-driver.current_tick), advance_lag_windows=max(0., (driver_finished-self.driver_monotonic_origin)/period-driver.current_tick),
                fixtures=fixture_rows, result=asdict(result), sample=sample)
            self.latest = row
            self.record(row)
            return result
        driver.tick = tick


def validate_live_provider_settings(settings):
    from app.services.siming_llm_provider import build_siming_llm_provider, HttpSimingLlmCandidateProvider
    if (settings.dialogue_mode != "online"
            or settings.character_model_provider_kind not in {"deepseek", "qwen", "seed_doubao", "openai_compatible"}
            or not settings.character_model_api_key or not settings.character_model_endpoint or not settings.character_model_model
            or settings.siming_llm_mode != "http"):
        raise ValueError("mixed_live_provider_configuration_required")
    if not any(isinstance(provider, HttpSimingLlmCandidateProvider)
               for provider in build_siming_llm_provider(settings).providers):
        raise ValueError("mixed_live_provider_configuration_required")


def configure(directory, stack, *, mode, provider_mode):
    """仅供全新后端子进程；装包和 mode pins 均先于真实 lifespan 初始化。"""
    import secrets
    import sys
    from unittest.mock import patch
    from app import config
    from app.population_continuity.roster import PopulationRoster

    if "app.main" in sys.modules:
        raise ValueError("mixed_backend_requires_fresh_process")
    if mode not in {"one_x", "ten_x"} or provider_mode not in {"live", "local_probe"}:
        raise ValueError("mixed_backend_profile_invalid")
    actors = PopulationRoster.model_validate_json((directory / "roster.json").read_text(encoding="utf-8")).actor_ids
    if len(actors) not in {100, 1000, 10000} or not {"char_a", "char_b", "char_c"}.issubset(actors):
        raise ValueError("mixed_backend_roster_invalid")
    settings = config.settings if provider_mode == "live" else config.Settings(
        character_model_provider_kind="local", siming_llm_mode="disabled")
    if provider_mode == "live":
        validate_live_provider_settings(settings)
    secret = secrets.token_urlsafe(32)
    configured = settings.model_copy(update=dict(
        heavenly_graph_path=str(directory / "state" / "graph.sqlite3"),
        population_roster_path=str(directory / "roster.json"),
        population_runtime_profile="benchmark_1x" if mode == "one_x" else "benchmark_10x",
        character_model_require_online=provider_mode == "live",
        gameplay_mirror_launcher_bootstrap_secret=secret,
        gameplay_mirror_trusted_local_launch_profiles=[config.GameplayMirrorTrustedLocalLaunchProfileSettings(
            profile_ref="population-mixed", principal_ref="population-mixed",
            allowed_actor_refs=tuple("character:" + actor for actor in actors), credential_ttl_seconds=300)]))
    # 提前导入的模块仍引用原对象；统一更新，防止本地探针沿旧配置调用真实模型。
    for field in config.Settings.model_fields:
        setattr(config.settings, field, getattr(configured, field))
    from app import main
    install_mixed_fixtures(main, stack)
    return main, actors, secret


def install_mixed_fixtures(main, stack):
    """同一装配补丁在真实 child 初始化前安装；不创建替代 runtime。"""
    from unittest.mock import patch
    from scripts.verification.population_mixed_fixture import RECIPE, install_conflict_fixture_package
    original_registry, original_mode = main.build_production_package_registry, main._bakery_population_mode
    def registry(*args, **kwargs):
        result = original_registry(*args, **kwargs)
        install_conflict_fixture_package(result)
        return result
    def world_mode():
        result = original_mode()
        return result.model_copy(update=dict(batch_limit=36, revision=result.revision + ":" + RECIPE))
    stack.enter_context(patch.object(main, "build_production_package_registry", registry))
    stack.enter_context(patch.object(main, "_bakery_population_mode", world_mode))


def merge_process_observations(parent, owner, ready):
    """两方原始记录分别封存；仅同一实际 owner 的正常终态可合并。"""
    if (any(type(parent.get(key)) is not int or parent[key] <= 0 for key in ("parent_pid", "owner_pid"))
            or parent["parent_pid"] == parent["owner_pid"]
            or owner.get("owner_pid") != parent["owner_pid"] or ready.get("owner_pid") != parent["owner_pid"]
            or ready.get("population") != parent.get("population")
            or owner.get("provider_mode") != parent.get("provider_mode")
            or owner.get("interval") != parent.get("interval")
            or type(parent.get("child_exit_code")) is not int or parent["child_exit_code"] != 0
            or owner.get("errors") != [] or parent.get("errors") != []
            or parent.get("asgi_lifecycle") != dict(startup_failed=False, shutdown_failed=False, error_occurred=False)
            or any(value is not False for value in parent["asgi_lifecycle"].values())):
        raise ValueError("mixed_process_observations_invalid")
    return dict(owner, **{key: parent[key] for key in ("parent_pid", "child_exit_code", "population", "asgi_lifecycle")},
        parent_writer_calls=parent["writer_calls"], parent_writer_boundaries=parent["writer_boundaries"])


async def hold_sqlite_busy(path):
    """另一个线程/连接实际占用现有 SQLite writer 两秒，不提交伪造事实。"""
    def hold():
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=rw", uri=True, timeout=5)) as connection:
            connection.execute("BEGIN IMMEDIATE")
            acquired = perf_counter()
            try:
                while (remaining := acquired + 2 - perf_counter()) > 0:
                    sleep(remaining)
            finally:
                connection.rollback()
            return dict(acquired_at=acquired, released_at=perf_counter())
    task = asyncio.create_task(asyncio.to_thread(hold))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        # 线程不能被 asyncio 取消；等待其原定两秒解锁，避免把残留锁带入后续场景。
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
        task.result()
        raise
