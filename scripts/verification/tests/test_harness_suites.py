from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import registry


ROOT = Path(__file__).resolve().parents[3]


def _profile(project: Path, filename: str, **overrides: object) -> None:
    directory = project / ".harness" / "profiles"
    directory.mkdir(parents=True, exist_ok=True)
    script = project / "check.py"
    script.write_text("raise SystemExit(0)\n", encoding="utf-8")
    payload = {"schema_version": 1, "name": filename, "script": "check.py", **overrides}
    (directory / f"{filename}.json").write_text(json.dumps(payload), encoding="utf-8")


def _suites(project: Path, payload: object) -> None:
    (project / ".harness" / "suites.json").write_text(json.dumps(payload), encoding="utf-8")


def test_suite_selection_preserves_order_and_deduplicates(tmp_path: Path) -> None:
    _profile(tmp_path, "docs", order=10)
    _profile(tmp_path, "boundaries", order=20)
    _profile(tmp_path, "runtime", order=30)
    _suites(tmp_path, {"schema_version": 1, "suites": {"release": ["docs", "boundaries", "docs", "runtime"]}})

    loaded = registry.load_profile_registry(tmp_path)

    assert registry.select_profiles(loaded, suite="release") == ["docs", "boundaries", "runtime"]
    assert registry.select_profiles(loaded) == ["boundaries"]


def test_all_preserves_legacy_profile_order_and_exclusions(tmp_path: Path) -> None:
    _profile(tmp_path, "docs", order=10)
    _profile(tmp_path, "boundaries", order=20)
    _profile(tmp_path, "live", order=30, include_in_all=False)
    _profile(tmp_path, "hidden", order=0, include_in_profile_order=False, include_in_all=True)
    _profile(tmp_path, "harness-smoke", order=0, include_in_profile_order=False, include_in_all=False)

    loaded = registry.load_profile_registry(tmp_path)

    assert registry.select_profiles(loaded, profile="all") == ["docs", "boundaries"]
    assert registry.select_profiles(loaded, profile="hidden") == ["hidden"]
    assert loaded.suites == {}


@pytest.mark.parametrize("selection", [{"profile": "missing"}, {"suite": "missing"}, {"profile": ""}, {"suite": ""}, {"profile": "docs", "suite": "smoke"}])
def test_invalid_selection_is_rejected(tmp_path: Path, selection: dict[str, str]) -> None:
    _profile(tmp_path, "docs")
    with pytest.raises(ValueError):
        registry.select_profiles(registry.load_profile_registry(tmp_path), **selection)


@pytest.mark.parametrize("payload", [
    [],
    {"schema_version": 2, "suites": {}},
    {"schema_version": 1},
    {"schema_version": 1, "suites": []},
    {"schema_version": 1, "suites": {"smoke": "docs"}},
    {"schema_version": 1, "suites": {"smoke": []}},
    {"schema_version": 1, "suites": {"smoke": ["missing"]}},
    {"schema_version": 1, "suites": {"release": ["smoke"], "smoke": ["docs"]}},
    {"schema_version": 1, "suites": {"smoke": [1]}},
    {"schema_version": 1, "suites": {"": ["docs"]}},
    {"schema_version": 1, "suites": {"smoke": ["docs"]}, "suite": {}},
])
def test_invalid_suite_manifest_is_rejected(tmp_path: Path, payload: object) -> None:
    _profile(tmp_path, "docs")
    _suites(tmp_path, payload)
    with pytest.raises(ValueError):
        registry.load_profile_registry(tmp_path)


def test_duplicate_profile_names_are_rejected(tmp_path: Path) -> None:
    _profile(tmp_path, "first", name="same")
    _profile(tmp_path, "second", name="same")
    with pytest.raises(ValueError, match="Duplicate profile"):
        registry.load_profile_registry(tmp_path)


def test_duplicate_suite_keys_are_rejected(tmp_path: Path) -> None:
    _profile(tmp_path, "docs")
    (tmp_path / ".harness" / "suites.json").write_text(
        '{"schema_version": 1, "suites": {"smoke": ["missing"], "smoke": ["docs"]}}', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="Duplicate"):
        registry.load_profile_registry(tmp_path)


@pytest.mark.parametrize("script", ["../outside.py", "/outside.py", "missing.py", ""])
def test_invalid_profile_script_is_rejected(tmp_path: Path, script: str) -> None:
    _profile(tmp_path, "docs", script=script)
    with pytest.raises(ValueError, match="script"):
        registry.load_profile_registry(tmp_path)


@pytest.mark.parametrize("timeout", [0, -1, True, "30", None, math.inf, math.nan])
def test_invalid_timeout_is_rejected(tmp_path: Path, timeout: object) -> None:
    _profile(tmp_path, "docs", timeout_seconds=timeout)
    with pytest.raises(ValueError, match="timeout_seconds"):
        registry.load_profile_registry(tmp_path)


@pytest.mark.parametrize("members", [[], ["missing"]])
def test_selection_rejects_invalid_constructed_suite(members: list[str]) -> None:
    loaded = registry.ProfileRegistry(profiles={}, profile_order=[], suites={"smoke": members})
    with pytest.raises(ValueError):
        registry.select_profiles(loaded, suite="smoke")


@pytest.mark.parametrize("exit_code", [0, 1])
def test_smoke_runs_offline_tests_and_propagates_failure(monkeypatch, tmp_path: Path, exit_code: int) -> None:
    import check_harness_smoke

    test_script = tmp_path / "test_offline_fixture.py"
    test_script.write_text(
        "import os\n"
        "def test_offline():\n"
        "    assert os.environ['PYTHONDONTWRITEBYTECODE'] == '1'\n"
        f"    assert {exit_code} == 0\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(check_harness_smoke, "SMOKE_TESTS", [str(test_script)])
    assert check_harness_smoke.main() == exit_code
    assert not (tmp_path / "__pycache__").exists()
    assert not (tmp_path / ".pytest_cache").exists()


def test_project_suites_use_reviewed_static_and_runtime_profiles() -> None:
    loaded = registry.load_profile_registry(ROOT)
    assert registry.select_profiles(loaded, suite="smoke") == ["harness-smoke"]
    assert registry.select_profiles(loaded, suite="contract") == ["docs", "boundaries", "backend-contract", "godot-project", "harness-lifecycle"]
    assert registry.select_profiles(loaded, suite="runtime") == ["phase0", "mainline-unified-runtime"]
    assert registry.select_profiles(loaded, suite="release") == ["docs", "boundaries", "backend-contract", "godot-project", "harness-lifecycle", "phase0", "mainline-unified-runtime"]
    assert "harness-smoke" not in registry.select_profiles(loaded, profile="all")


@pytest.mark.skipif(os.name != "nt", reason="验证 Windows 本地 PowerShell 入口")
@pytest.mark.parametrize("failure_position", [1, 2, 3, 4])
def test_local_ci_stops_on_each_native_command_failure(tmp_path: Path, failure_position: int) -> None:
    shell = shutil.which("powershell")
    assert shell is not None
    fake_python = tmp_path / "python.cmd"
    fake_python.write_text(
        "@echo off\n"
        'echo %*>>"%HARNESS_TEST_CALLS%"\n'
        'for /f %%N in (\'find /c /v "" ^< "%HARNESS_TEST_CALLS%"\') do set HARNESS_TEST_COUNT=%%N\n'
        'if "%HARNESS_TEST_COUNT%"=="%HARNESS_TEST_FAIL_AT%" exit /b 17\n'
        "exit /b 0\n",
        encoding="utf-8",
    )
    calls = tmp_path / "calls.txt"
    result = subprocess.run(
        [shell, "-NoProfile", "-File", str(ROOT / ".harness" / "ci" / "local-ci-gate.ps1")],
        cwd=ROOT,
        env={**os.environ, "PATH": f"{tmp_path}{os.pathsep}{os.environ['PATH']}", "HARNESS_TEST_CALLS": str(calls), "HARNESS_TEST_FAIL_AT": str(failure_position)},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 17, result.stdout + result.stderr
    assert len(calls.read_text(encoding="utf-8").splitlines()) == failure_position
