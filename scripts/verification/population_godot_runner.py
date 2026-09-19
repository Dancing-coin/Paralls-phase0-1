"""外机 probe 进程管理；只启动/停止本次拥有的进程，不复用现存后端。"""
from __future__ import annotations

import asyncio
from contextlib import suppress
from dataclasses import asdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import secrets
import socket
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

from scripts.verification.verify_population_godot_runtime import ROOT, digest, read_json


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def object_digest(value) -> str:
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode())


def _runtime_resource_paths() -> list[str]:
    from app.gameplay.production_package_registry import _APPROVED_MANIFESTS
    return ["assets/characters/profiles", *[
        "docs/superpowers/specs/world-character-siming-authority-mainline/" + name
        for name in _APPROVED_MANIFESTS]]


def source_manifest(root: Path = ROOT) -> dict:
    paths = [root / "project.godot", root / "scenes/phase0/PopulationProbe.tscn"]
    for directory in ("backend/app", "backend/assets", "scripts", "addons", "assets/characters/profiles"):
        paths.extend(path for path in (root / directory).rglob("*")
                     if path.suffix in {".py", ".gd", ".json", ".yaml", ".yml", ".cfg", ".tres"}
                     and "__pycache__" not in path.parts)
    paths.extend(root / name for name in _runtime_resource_paths()[1:])
    files = {path.relative_to(root).as_posix(): digest(path.read_text(encoding="utf-8").encode("utf-8"))
             for path in sorted(set(paths)) if path.is_file()}
    return dict(source_sha256=object_digest(files), files=files)


def child_environment(parent=None) -> dict[str, str]:
    # 白名单保留系统/GPU必需变量；provider和任意Python启动钩子不进入渲染进程。
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "HOME", "APPDATA", "LOCALAPPDATA",
               "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "HOMEDRIVE", "HOMEPATH", "DISPLAY",
               "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "XDG_SESSION_TYPE", "LD_LIBRARY_PATH", "LANG", "LC_ALL", "TZ"}
    return {**{key: value for key, value in (os.environ if parent is None else parent).items() if key.upper() in allowed},
            "PYTHONPATH": os.pathsep.join((str(ROOT), str(ROOT / "backend"))), "PYTHONUTF8": "1", "PYTHONHASHSEED": "0",
            "CHARACTER_GRAPH_REQUIRE_CONTINUITY": "0"}


def memory_bytes() -> int:
    if sys.platform == "win32":
        import ctypes
        class MemoryStatus(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (name, ctypes.c_ulonglong) for name in ("physical", "available", "page", "available_page", "virtual", "available_virtual", "extended")]
        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError("physical_memory_query_failed")
        return status.physical
    return os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")


def authority_boundary(main) -> dict:
    """仅在采样后停调度的 owner 截面读取；全扫描不计入运行/帧性能。"""
    from app.population_continuity.presentation import _confirmed_population_state
    driver = main._population_runtime_driver
    world = driver.world_runtime
    confirmed = _confirmed_population_state(world)
    if confirmed is None or main.get_population_runtime_failure() is not None:
        raise ValueError("population_confirmation_missing")
    state = world.export_recovery_state()
    runtime = main.character_agent_runtime
    revisions = {actor: dict(event_count=runtime._session_store.event_count(actor),
                            current=runtime._session_store.read_runtime_state(actor))
                 for actor in runtime._session_store.actor_ids()}
    store = main.gameplay_event_store
    # 历史receipts与事件本体分别摘要，不用内存cache充当账本。
    receipts = store._rows("SELECT transaction_id, result FROM transactions ORDER BY sequence")
    events = [event.model_dump(mode="json") for event in store.read_events()]
    full_hash, tail_hash = world.replay_equivalence()
    if full_hash != tail_hash:
        raise ValueError("gameplay_replay_mismatch")
    return dict(authority=dict(driver_id=id(driver), world_id=id(world), confirmed_tick=driver.current_tick,
        population=len(world.roster.actor_ids), advanced_count=confirmed.receipt.advanced_count,
        receipt_digest=object_digest(asdict(confirmed.receipt)), checkpoint_digest=object_digest(confirmed.model_dump(mode="json")),
        character_revision_digest=object_digest(revisions), population_state_digest=state["state_digest"],
        gameplay_events_digest=object_digest(events), gameplay_replay_digest=full_hash,
        hot_revision_digest=object_digest([(row["actor_id"], row["revision"], row["last_update_tick"]) for row in state["actors"]]),
        authority_head=store.get_last_global_sequence(), stream_revision_digest=object_digest(store.get_stream_heads()),
        owner_receipt_digest=object_digest(receipts)),
        subscriptions=list(main.gameplay_mirror_subscription_registry.subscribed_actor_refs()), scheduling_paused=True)


def render_owner_child(commands, controls, results, notifications, settings_json):
    """外机渲染探针仍通过原 spawn owner 读取、暂停和恢复同一个 driver。"""
    from contextlib import ExitStack
    from unittest.mock import patch
    from app import main
    from app.services.runtime_process import runtime_child_main
    directory = Path(sys.argv[sys.argv.index('--backend-child') + 1])
    state_directory = Path(sys.argv[sys.argv.index('--state-directory') + 1])
    observed = dict(owner_pid=os.getpid(), errors=[])
    task = None
    original_startup = main._start_population_runtime_on_startup
    original_shutdown = main._stop_population_runtime_on_shutdown

    async def observe():
        before = None
        try:
            driver = main._population_runtime_driver
            if (driver is None or driver.window_size != 1 or driver.wall_period_seconds != 1
                    or main._population_mirror_source.world is not driver.world_runtime):
                raise RuntimeError('production_population_driver_missing')
            write_json(directory / 'owner-ready.json', dict(owner_pid=os.getpid(),
                population=len(driver.world_runtime.roster.actor_ids), clock_profile='benchmark_1x'))
            while not (state_directory / 'stop').exists():
                stage_path = directory / 'stage.json'
                try:
                    stage = read_json(stage_path.read_text(encoding='utf-8')).get('stage') if stage_path.exists() else None
                except (json.JSONDecodeError, PermissionError):
                    await asyncio.sleep(.05)
                    continue  # 外机 Godot 写 stage 不是原子替换；保持原控制协议。
                if stage == 'awaiting_lod_boundary' and before is None:
                    main._population_runtime_stop_event.set()
                    await asyncio.wait_for(asyncio.shield(main._population_runtime_task), 30)
                    before = await asyncio.wrap_future(main.runtime_execution.submit(lambda: authority_boundary(main)))
                    before['owner_pid'] = os.getpid()
                    write_json(directory / 'authority-before.json', before)
                elif stage == 'lod_rotated' and before is not None and not (directory / 'authority-after.json').exists():
                    after = await asyncio.wrap_future(main.runtime_execution.submit(lambda: authority_boundary(main)))
                    after['owner_pid'] = os.getpid()
                    if before['authority'] != after['authority']:
                        raise ValueError('lod_authority_changed')
                    main.start_population_runtime()
                    if main._population_runtime_driver is not driver or main._population_runtime_task.done():
                        raise RuntimeError('population_resume_failed')
                    after['resumed_same_driver'] = True
                    write_json(directory / 'authority-after.json', after)
                await asyncio.sleep(.05)
        except asyncio.CancelledError:
            observed['errors'].append('render_owner_observation_cancelled')
            raise
        except Exception as error:
            observed['errors'].append(type(error).__name__)
        finally:
            write_json(directory / 'owner-observed.json', observed)

    async def startup():
        nonlocal task
        await original_startup()
        task = asyncio.create_task(observe())

    async def shutdown():
        if task is not None and not task.done():
            task.cancel()
        if task is not None:
            await asyncio.gather(task, return_exceptions=True)
        await original_shutdown()

    with ExitStack() as stack:
        stack.enter_context(patch.object(main, '_start_population_runtime_on_startup', startup))
        stack.enter_context(patch.object(main, '_stop_population_runtime_on_shutdown', shutdown))
        try:
            runtime_child_main(commands, controls, results, notifications, settings_json)
        finally:
            from app.services.process_qos import process_qos_snapshot
            write_json(directory / 'owner-qos.json', process_qos_snapshot())


async def _wait_for_render_stop(directory, state_directory, serving, process):
    while not (state_directory / "stop").exists():
        if serving.done() or not process.is_alive():
            raise RuntimeError('render_backend_exited')
        if (directory / 'owner-observed.json').exists() and not (state_directory / 'stop').exists():
            raise RuntimeError('render_owner_observation_ended_early')
        await asyncio.sleep(.05)


async def backend_child(directory: Path, state_directory: Path) -> None:
    """同一 app.main 的启动期 fixture 配置；不复制 runtime，不提供调试 HTTP 写入口。"""
    import uvicorn
    from app import config
    actors = read_json((directory / "roster.json").read_text(encoding="utf-8"))["actor_ids"]
    config.settings = config.Settings(
        heavenly_graph_path=str(state_directory / "graph.sqlite3"), population_roster_path=str(directory / "roster.json"),
        population_runtime_profile="benchmark_1x", character_model_provider_kind="local", siming_llm_mode="disabled",
        gameplay_mirror_live_probe_drop_first_delivery=True,
        gameplay_mirror_launcher_bootstrap_secret=os.environ["GAMEPLAY_MIRROR_LAUNCHER_BOOTSTRAP_SECRET"],
        gameplay_mirror_trusted_local_launch_profiles=[config.GameplayMirrorTrustedLocalLaunchProfileSettings(
            profile_ref="population-render-probe", principal_ref="population-render-probe",
            allowed_actor_refs=tuple(f"character:{actor}" for actor in actors), credential_ttl_seconds=300)],
    )
    from app import main
    from app.services import runtime_process
    from unittest.mock import patch
    observed = dict(parent_pid=os.getpid(), owner_pid=None, child_exit_code=None, errors=[])
    with patch.object(runtime_process, 'CHILD_TARGET', render_owner_child), socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        listener.setblocking(False)
        server = uvicorn.Server(uvicorn.Config(main.app, ws=main.RUNTIME_WEBSOCKET_PROTOCOL, host="127.0.0.1", port=listener.getsockname()[1],
            ws_per_message_deflate=False, access_log=False, log_level="warning"))
        serving = asyncio.create_task(server.serve(sockets=[listener]))
        host = None
        try:
            while not server.started:
                if serving.done():
                    await serving
                    raise RuntimeError("backend_start_failed")
                await asyncio.sleep(.05)
            host = main.app.state.runtime_process
            observed['owner_pid'] = host.process.pid
            async with asyncio.timeout(90):
                while not (directory / 'owner-ready.json').exists():
                    if not host.process.is_alive():
                        raise RuntimeError('render_owner_exited')
                    await asyncio.sleep(.05)
            from scripts.verification.verify_population_mixed_soak import read_control
            ready = await read_control(directory / 'owner-ready.json', loader=read_json)
            if (ready['owner_pid'] != host.process.pid or ready['population'] != len(actors)
                    or ready['clock_profile'] != 'benchmark_1x'):
                raise RuntimeError('production_population_driver_missing')
            write_json(directory / "backend-ready.json", dict(port=listener.getsockname()[1],
                parent_pid=os.getpid(), owner_pid=host.process.pid,
                clock_profile="benchmark_1x", model_mode="local_fixture", population=len(actors), compression="disabled"))
            await _wait_for_render_stop(directory, state_directory, serving, host.process)
            async with asyncio.timeout(35):
                while not (directory / 'owner-observed.json').exists():
                    if not host.process.is_alive():
                        raise RuntimeError('render_owner_exited')
                    await asyncio.sleep(.05)
                owner = await read_control(directory / 'owner-observed.json', loader=read_json)
            if owner['owner_pid'] != host.process.pid or owner['errors']:
                raise RuntimeError('render_owner_observation_failed')
        except Exception as error:
            observed['errors'].append(type(error).__name__)
            raise
        finally:
            server.should_exit = True
            try:
                await asyncio.wait_for(serving, 40)
            except Exception as error:
                observed['errors'].append(type(error).__name__)
                raise
            finally:
                lifecycle = getattr(server, 'lifespan', None)
                observed['asgi_lifecycle'] = {name: getattr(lifecycle, name, None) for name in
                    ('startup_failed', 'shutdown_failed', 'error_occurred')}
                if any(value is not False for value in observed['asgi_lifecycle'].values()):
                    observed['errors'].append('render_asgi_lifecycle_failed')
                observed['child_exit_code'] = host.process.exitcode if host is not None else None
                write_json(directory / 'parent-qos.json', main.app.state.process_qos)
                write_json(directory / 'backend-observed.json', observed)
            if observed['errors'] or observed['child_exit_code'] != 0:
                raise RuntimeError('render_backend_shutdown_failed')


def wait_file(path: Path, process: subprocess.Popen, *, timeout: float):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            try:
                return read_json(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, PermissionError):
                pass
        if process.poll() is not None:
            raise RuntimeError(f"owned_process_exited:{process.returncode}:{path.name}")
        time.sleep(.05)
    raise TimeoutError(f"evidence_timeout:{path.name}")


def stop_owned(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(10)


def run_tier(directory: Path, population: int, godot: Path) -> dict:
    from scripts.launch_trusted_local_gameplay_mirror import build_godot_child_environment, request_enrollment
    from scripts.verification.verify_population_godot_runtime import validate_capture, validate_backend_process
    directory.mkdir()
    write_json(directory / "roster.json", dict(actor_ids=["char_a", "char_b", *(
        f"resident_{index:05d}" for index in range(population - 2))]))
    with TemporaryDirectory(prefix="paralls-population-godot-") as temporary:
        state = Path(temporary)
        backend_env = child_environment()
        secret = secrets.token_urlsafe(32)
        backend_env["GAMEPLAY_MIRROR_LAUNCHER_BOOTSTRAP_SECRET"] = secret
        backend_command = [sys.executable, str(ROOT / "scripts/verification/verify_population_godot_runtime.py"),
                           "--backend-child", str(directory), "--state-directory", str(state)]
        with (directory / "backend.log").open("w", encoding="utf-8") as backend_log, (directory / "godot.log").open("w", encoding="utf-8") as godot_log:
            backend = subprocess.Popen(backend_command, cwd=ROOT, env=backend_env, stdout=backend_log, stderr=subprocess.STDOUT)
            render = None
            result = None
            try:
                ready = wait_file(directory / "backend-ready.json", backend, timeout=120)
                url = f"http://127.0.0.1:{ready['port']}"
                enrollment = request_enrollment(backend_http_url=url, launch_profile_ref="population-render-probe", launcher_secret=secret)
                environment = build_godot_child_environment(parent_environment=child_environment(), enrollment=enrollment)
                environment.update(PARALLS_BACKEND_WS_URL=f"ws://127.0.0.1:{ready['port']}/ws",
                    PARALLS_POPULATION_EVIDENCE_DIR=str(directory), PARALLS_POPULATION_EXPECTED_COUNT=str(population),
                    PARALLS_POPULATION_ROSTER_PATH=str(directory / "roster.json"),
                    PARALLS_POPULATION_RECONNECT_ENROLLMENT_PATH=str(state / "enrollment.json"))
                command = [str(godot), "--path", str(ROOT), "--scene", "res://scenes/phase0/PopulationProbe.tscn",
                           "--rendering-method", "forward_plus", "--rendering-driver", "vulkan", "--resolution", "1280x720", "--windowed"]
                write_json(directory / "commands.json", dict(backend=backend_command, godot=command, provider_mode="local_fixture"))
                render = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=godot_log, stderr=subprocess.STDOUT)
                deadline = time.monotonic() + 250
                renewed = False
                while render.poll() is None:
                    if backend.poll() is not None:
                        raise RuntimeError("backend_exited_during_render")
                    if time.monotonic() >= deadline:
                        raise TimeoutError("godot_probe_timeout")
                    with suppress(FileNotFoundError, json.JSONDecodeError):
                        stage = read_json((directory / "stage.json").read_text(encoding="utf-8"))["stage"]
                        if stage == "disconnected" and not renewed:
                            fresh = request_enrollment(backend_http_url=url, launch_profile_ref="population-render-probe", launcher_secret=secret)
                            write_json(state / "enrollment.json", fresh.model_dump(mode="json"))
                            renewed = True
                    time.sleep(.05)
                if render.returncode != 0:
                    raise RuntimeError("godot_probe_failed")
                result = validate_capture(directory, population)
            finally:
                if render is not None:
                    stop_owned(render)
                (state / "stop").touch()
                with suppress(subprocess.TimeoutExpired):
                    backend.wait(15)
                clean_shutdown = backend.poll() == 0
                stop_owned(backend)
                write_json(directory / "processes.json", dict(backend_pid=backend.pid,
                    backend_exit_code=backend.returncode, godot_pid=render.pid if render is not None else None,
                    godot_exit_code=render.returncode if render is not None else None, clean_backend_shutdown=clean_shutdown))
                if result is not None and not clean_shutdown:
                    raise RuntimeError("backend_shutdown_failed")
                if result is not None:
                    validate_backend_process(directory, population, backend.pid)
            write_json(directory / "result.json", result)
            return result


def collect(output: Path, godot: Path) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    from scripts.verification.population_process_qos import recorded_high_qos
    try:
        with recorded_high_qos(output / 'collector-qos.json'):
            _collect_with_policy(output, godot)
    finally:
        path = output / 'manifest.json'
        if path.exists():
            manifest = json.loads(path.read_text(encoding='utf-8'))
            if sys.exc_info()[0] is not None:
                manifest.update(passed=False, status='failed', godot_status='godot_unverified')
                manifest.setdefault('errors', []).append('collection_scope:' + sys.exc_info()[0].__name__)
            try:
                manifest['artifacts'] = {item.relative_to(output).as_posix(): digest(item.read_bytes())
                    for item in sorted(output.rglob('*')) if item.is_file() and item != path}
            except Exception as error:
                manifest.update(passed=False, status="failed", godot_status="godot_unverified",
                                error=f"{type(error).__name__}:{error}")
                write_json(path, manifest)
                raise
            write_json(path, manifest)

    if manifest["status"] == "passed":
        from scripts.verification.verify_population_godot_runtime import verify_artifacts
        try:
            verify_artifacts(output)
        except Exception as error:
            manifest.update(status="failed", godot_status="godot_unverified", error=f"{type(error).__name__}:{error}")
            write_json(output / "manifest.json", manifest)
    return manifest


def _collect_with_policy(output: Path, godot: Path) -> dict:
    manifest = dict(schema_version=1, status="running", godot_status="godot_unverified", seed=0, collector_pid=os.getpid(),
        started_at=datetime.now(timezone.utc).isoformat(), source=source_manifest(),
        base_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        environment=dict(python=platform.python_version(), python_executable=sys.executable, sqlite=sqlite3.sqlite_version,
                         os=platform.platform(), architecture=platform.machine(), memory_bytes=memory_bytes(),
                         cpu=platform.processor() or "unknown", logical_cpus=os.cpu_count()), cases={})
    source_paths = ["backend/app", "backend/assets", "scripts", "addons", "project.godot", "scenes/phase0/PopulationProbe.tscn", *_runtime_resource_paths()]
    manifest["source_dirty_paths"] = sorted(set(subprocess.check_output(
        ["git", "diff", "--name-only", "HEAD", "--", *source_paths], cwd=ROOT, text=True).splitlines()
        + subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "--", *source_paths], cwd=ROOT, text=True).splitlines()))
    write_json(output / "manifest.json", manifest)
    try:
        if platform.python_version() != "3.12.14":
            raise ValueError("fixed_python_3_12_14_required")
        manifest["environment"]["godot_binary_sha256"] = digest(godot.read_bytes())
        version = subprocess.run([str(godot), "--version"], cwd=ROOT, env=child_environment(), capture_output=True, text=True, timeout=30, check=True)
        manifest["environment"]["godot_version"] = version.stdout.strip()
        if not version.stdout.startswith("4.6.3.stable"):
            raise ValueError("fixed_godot_version_required")
        with (output / "dependencies.txt").open("w", encoding="utf-8") as dependencies:
            subprocess.run([sys.executable, "-m", "pip", "freeze"], cwd=ROOT, stdout=dependencies, stderr=subprocess.STDOUT, timeout=30, check=True)
        with (output / "godot-import.log").open("w", encoding="utf-8") as log:
            command = [str(godot), "--headless", "--path", str(ROOT), "--editor", "--quit"]
            manifest["import_command"] = command
            subprocess.run(command, cwd=ROOT, env=child_environment(), stdout=log, stderr=subprocess.STDOUT, timeout=180, check=True)
        for population in (100, 1000):
            print(f"population_godot_collect={population}", flush=True)
            manifest["cases"][str(population)] = run_tier(output / str(population), population, godot)
        if manifest["source"] != source_manifest():
            raise ValueError("source_changed_during_capture")
        manifest.update(status="passed", godot_status="runtime_verified")
    except Exception as error:
        manifest.update(status="failed", godot_status="godot_unverified", error=f"{type(error).__name__}:{error}")
    finally:
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        manifest["artifacts"] = {path.relative_to(output).as_posix(): digest(path.read_bytes())
                                 for path in sorted(output.rglob("*")) if path.is_file() and path != output / "manifest.json"}
        write_json(output / "manifest.json", manifest)
    return manifest
