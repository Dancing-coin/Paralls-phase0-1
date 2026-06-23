from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common
import harness
from common import get_health

from harness import _write_harness_report


def test_write_harness_report_outputs_json_and_markdown(tmp_path: Path) -> None:
    report_paths = _write_harness_report(
        tmp_path,
        [
            {
                "profile": "boundaries",
                "command": ["python", "scripts/verification/check_boundaries.py"],
                "exit_code": 0,
            }
        ],
        overall_passed=True,
    )

    payload = json.loads(report_paths["json"].read_text(encoding="utf-8"))
    assert payload["overall_harness_passed"] is True
    assert payload["profiles"][0]["profile"] == "boundaries"
    assert payload["profiles"][0]["exit_code"] == 0
    assert report_paths["markdown"].read_text(encoding="utf-8").startswith("# Harness Run Report")
    assert report_paths["manifest"].exists()
    assert report_paths["baseline"].exists()
    assert report_paths["diff"].exists()


def test_write_harness_report_records_previous_run_diff(tmp_path: Path) -> None:
    _write_harness_report(
        tmp_path,
        [
            {
                "profile": "docs",
                "command": ["python", "scripts/verification/check_docs.py"],
                "exit_code": 0,
            }
        ],
        overall_passed=True,
        run_id="run_previous",
    )

    report_paths = _write_harness_report(
        tmp_path,
        [
            {
                "profile": "docs",
                "command": ["python", "scripts/verification/check_docs.py"],
                "exit_code": 1,
            }
        ],
        overall_passed=False,
        run_id="run_current",
    )

    diff = json.loads(report_paths["diff"].read_text(encoding="utf-8"))

    assert diff["previous_run_id"] == "run_previous"
    assert diff["current_run_id"] == "run_current"
    assert diff["overall_changed"] is True
    assert diff["profile_exit_code_changes"] == [
        {
            "profile": "docs",
            "previous_exit_code": 0,
            "current_exit_code": 1,
        }
    ]


def test_write_harness_report_default_run_ids_do_not_collide(tmp_path: Path) -> None:
    first_paths = _write_harness_report(
        tmp_path,
        [{"profile": "docs", "command": ["python", "check_docs.py"], "exit_code": 0}],
        overall_passed=True,
    )
    second_paths = _write_harness_report(
        tmp_path,
        [{"profile": "drift", "command": ["python", "check_drift.py"], "exit_code": 0}],
        overall_passed=True,
    )

    assert first_paths["run_dir"] != second_paths["run_dir"]


def test_write_harness_report_preserves_attempt_count_when_present(tmp_path: Path) -> None:
    report_paths = _write_harness_report(
        tmp_path,
        [
            {
                "profile": "phase0",
                "command": ["python", "scripts/verification/verify_phase0.py"],
                "exit_code": 0,
                "attempts": 2,
                "max_attempts": 2,
            }
        ],
        overall_passed=True,
        run_id="run_retry",
    )

    payload = json.loads(report_paths["json"].read_text(encoding="utf-8"))

    assert payload["profiles"][0]["attempts"] == 2
    assert payload["profiles"][0]["max_attempts"] == 2


def test_harness_runner_retries_profile_up_to_max_attempts(monkeypatch, tmp_path: Path) -> None:
    calls = {"count": 0}

    def fake_repo_root() -> Path:
        return tmp_path

    def fake_resolve_python_exe(_explicit: str | None) -> str:
        return "python"

    def fake_resolve_godot_exe(_explicit: str | None) -> str:
        return "godot"

    def fake_load_profile_registry(_project_root: Path):
        return SimpleNamespace(
            profiles={
                "phase0": {
                    "name": "phase0",
                    "script": "scripts/verification/verify_phase0.py",
                    "requires_godot": True,
                    "max_attempts": 2,
                }
            },
            profile_order=["phase0"],
        )

    def fake_run(_args: list[str], _cwd: Path) -> int:
        calls["count"] += 1
        return 1 if calls["count"] == 1 else 0

    monkeypatch.setattr(harness, "repo_root", fake_repo_root)
    monkeypatch.setattr(harness, "resolve_python_exe", fake_resolve_python_exe)
    monkeypatch.setattr(harness, "_resolve_godot_exe", fake_resolve_godot_exe)
    monkeypatch.setattr(harness, "load_profile_registry", fake_load_profile_registry)
    monkeypatch.setattr(harness, "_run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        ["harness.py", "--profile", "phase0"],
    )

    exit_code = harness.main()
    report = json.loads((tmp_path / ".harness" / "verification" / "harness-run-report.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert calls["count"] == 2
    assert report["profiles"][0]["attempts"] == 2
    assert report["profiles"][0]["max_attempts"] == 2


def test_harness_runner_does_not_retry_when_report_artifact_exists_after_failure(monkeypatch, tmp_path: Path) -> None:
    calls = {"count": 0}
    verification_dir = tmp_path / ".harness" / "verification"
    phase0_report = verification_dir / "phase0-report.json"

    def fake_repo_root() -> Path:
        return tmp_path

    def fake_resolve_python_exe(_explicit: str | None) -> str:
        return "python"

    def fake_resolve_godot_exe(_explicit: str | None) -> str:
        return "godot"

    def fake_load_profile_registry(_project_root: Path):
        return SimpleNamespace(
            profiles={
                "phase0": {
                    "name": "phase0",
                    "script": "scripts/verification/verify_phase0.py",
                    "requires_godot": True,
                    "max_attempts": 2,
                    "result_artifact": ".harness/verification/phase0-report.json",
                }
            },
            profile_order=["phase0"],
        )

    def fake_run(_args: list[str], _cwd: Path) -> int:
        calls["count"] += 1
        verification_dir.mkdir(parents=True, exist_ok=True)
        phase0_report.write_text("{\"overall_strict_phase0_passed\": false}", encoding="utf-8")
        return 1

    monkeypatch.setattr(harness, "repo_root", fake_repo_root)
    monkeypatch.setattr(harness, "resolve_python_exe", fake_resolve_python_exe)
    monkeypatch.setattr(harness, "_resolve_godot_exe", fake_resolve_godot_exe)
    monkeypatch.setattr(harness, "load_profile_registry", fake_load_profile_registry)
    monkeypatch.setattr(harness, "_run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        ["harness.py", "--profile", "phase0"],
    )

    exit_code = harness.main()
    report = json.loads((tmp_path / ".harness" / "verification" / "harness-run-report.json").read_text(encoding="utf-8"))

    assert exit_code == 1
    assert calls["count"] == 1
    assert report["profiles"][0]["attempts"] == 1
    assert report["profiles"][0]["max_attempts"] == 2


def test_get_health_treats_connection_reset_as_unhealthy(monkeypatch) -> None:
    def fake_urlopen(_url: str, timeout: float = 1.0):
        raise ConnectionResetError(10054, "connection reset")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    assert get_health() is None


def test_ensure_backend_can_restart_same_worktree_backend_when_fresh_backend_requested(monkeypatch, tmp_path: Path) -> None:
    health_state = {"calls": 0}
    terminated = {"pid": None}
    popen_calls = {"count": 0}
    listener_calls = {"count": 0}

    class _FakePopen:
        def __init__(self, *_args, **_kwargs) -> None:
            popen_calls["count"] += 1

        def terminate(self) -> None:
            return None

    def fake_get_health():
        health_state["calls"] += 1
        if health_state["calls"] == 1:
            return {"status": "ok", "worktree_root": str(tmp_path)}
        if health_state["calls"] == 2:
            return None
        return {"status": "ok", "worktree_root": str(tmp_path)}

    def fake_find_listener_pid(_port: int):
        listener_calls["count"] += 1
        return 4242 if listener_calls["count"] == 1 else None

    monkeypatch.setattr(common, "get_health", fake_get_health)
    monkeypatch.setattr(common, "_find_listener_pid", fake_find_listener_pid)
    monkeypatch.setattr(common, "_terminate_listener_pid", lambda pid: terminated.__setitem__("pid", pid))
    monkeypatch.setattr(common.subprocess, "Popen", _FakePopen)
    monkeypatch.setattr(common.time, "sleep", lambda _seconds: None)

    health, process = common.ensure_backend(tmp_path, "python", prefer_fresh_backend=True)

    assert health["worktree_root"] == str(tmp_path)
    assert terminated["pid"] == 4242
    assert popen_calls["count"] == 1
    assert process is not None


def test_run_command_until_markers_terminates_once_marker_is_seen(tmp_path: Path) -> None:
    script = tmp_path / "emit_marker.py"
    script.write_text(
        "import time\n"
        "print('before', flush=True)\n"
        "print('MARKER_OK', flush=True)\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )
    log_path = tmp_path / "marker.log"

    result = common.run_command_until_markers(
        ["C:/Anaconda3/python.exe", str(script)],
        tmp_path,
        log_path,
        success_markers=["MARKER_OK"],
        timeout_seconds=5.0,
    )

    assert result.returncode == 0
    assert result.marker_found is True
    assert "MARKER_OK" in log_path.read_text(encoding="utf-8")
