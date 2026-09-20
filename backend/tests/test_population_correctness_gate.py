"""正确性门禁不能把遗留报告、缺失原始结果或运行中变码当作通过。"""
import json
import os
import time
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from scripts.verification import verify_population_runtime_correctness as gate


@pytest.fixture
def short_tmp_path():
    # 此处模拟嵌套仓库，不把外层pytest和长用例名再次叠加到报告路径。
    with TemporaryDirectory(prefix="pc-") as temporary:
        yield Path(temporary)


@pytest.mark.parametrize("fault", [None, "stale", "missing", "false", "skipped", "timeout", "source_changed", "future_stale", "raw_missing", "raw_timeout", "raw_corrupt", "raw_null", "raw_array", "long_temp"])
def test_correctness_gate_requires_fresh_complete_results(short_tmp_path, monkeypatch, fault):
    root = short_tmp_path / "repo"
    latest = root / ".harness/verification/correctness-live"
    latest.mkdir(parents=True)
    output = latest.parent / "run-test"
    calls = []
    owned_temporary = []
    registry = gate.load_profile_registry(gate.ROOT)
    monkeypatch.setattr(gate, "load_profile_registry", lambda _root: registry)
    monkeypatch.setattr(gate, "verification_dir", lambda _root: latest.parent)
    monkeypatch.setattr(gate, "source_snapshot", lambda _root: {"source_sha256": "before" if not calls or fault != "source_changed" else "after", "files": {}})
    monkeypatch.setattr(gate, "environment", lambda: {"python": "3.12.14", "sqlite": "test", "godot": "not_run"})
    monkeypatch.setattr(gate, "git_head", lambda _root: "a" * 40)
    for _, report_name in gate.PROFILES:
        path = latest / report_name
        path.write_text('{"overall_passed":true}', encoding="utf-8")
        os.utime(path, (time.time() + 3600,) * 2 if fault == "future_stale" else (1, 1))

    def run(command, *, cwd, env, log, timeout):
        assert timeout == (gate.FOCUSED_TEST_TIMEOUT_SECONDS if command[1:3] == ['-m', 'pytest'] else gate.TIMEOUT_SECONDS)
        calls.append(command)
        log.write_text("本轮执行\n", encoding="utf-8")
        if command[1:3] == ["-m", "pytest"]:
            temporary_root = Path(command[command.index("--basetemp") + 1])
            # 验收器嵌套执行自身测试时，临时仓库不能叠加在工作树内。
            assert not temporary_root.is_relative_to(root)
            owned_temporary.append(temporary_root)
            if fault == "long_temp":
                temporary = Path(command[command.index("--basetemp") + 1])
                extended = str(temporary.resolve())
                if os.name == "nt" and not extended.startswith("\\\\?\\"):
                    extended = "\\\\?\\" + extended
                temporary = Path(extended)
                owned_temporary.append(temporary)
                deep = temporary / ("a" * 100) / ("b" * 100) / ("c" * 100)
                deep.mkdir(parents=True)
                (deep / "raw.txt").write_text("owned")
                import sqlite3
                from contextlib import closing
                business_db = Path(command[command.index("--basetemp") + 1]) / "readonly.db"
                with closing(sqlite3.connect(business_db)) as connection:
                    connection.execute("CREATE TABLE facts(value)")
                with closing(sqlite3.connect(business_db.as_uri() + "?mode=ro", uri=True)) as connection:
                    assert connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == 0
            xml = Path(next(arg.split("=", 1)[1] for arg in command if arg.startswith("--junitxml=")))
            xml.write_text('<testsuites><testsuite><testcase name="real">' + ('<skipped/>' if fault == "skipped" else '') + '</testcase></testsuite></testsuites>', encoding="utf-8")
        elif fault not in {"stale", "future_stale"}:
            _, report = gate.PROFILES[len(calls) - 1]
            path = latest / report
            if fault in {"raw_missing", "raw_timeout", "raw_corrupt", "raw_null", "raw_array"}:
                prefix = report.removesuffix("-report.json")
                for suffix in ("-tests.log", "-tests.xml"):
                    (latest / (prefix + suffix)).write_text("fresh raw", encoding="utf-8")
            if fault in {"missing", "raw_missing", "raw_timeout"}:
                path.unlink(missing_ok=True)
            elif fault in {"raw_null", "raw_array"}:
                path.write_text("null" if fault == "raw_null" else "[]", encoding="utf-8")
            elif fault == "raw_corrupt":
                path.write_text("{broken", encoding="utf-8")
            else:
                path.write_text(json.dumps({"overall_passed": fault != "false"}), encoding="utf-8")
        return 124 if fault in {"timeout", "raw_timeout"} else 0

    monkeypatch.setattr(gate, "run_logged", run)
    result = gate.run_correctness(root, output)
    # RED 也清理本测试自行创建的长路径，不留下外层pytest无法清理的残留。
    import shutil
    remaining = [path for path in owned_temporary if path.exists()]
    for path in owned_temporary:
        if path.exists():
            shutil.rmtree(path)
    assert not remaining
    assert result["status"] == ("passed" if fault in {None, "long_temp"} else "failed")
    assert result["godot_status"] == "godot_unverified"
    assert result["performance_status"] == "not_run"
    assert len(calls) == 5  # 一个失败也保留其它 profile 的诊断。
    assert len(result["steps"]) == 5
    assert (output / "manifest.json").is_file()
    assert result["raw_artifacts"]["focused.log"]["sha256"]
    if fault in {"raw_missing", "raw_timeout", "raw_corrupt", "raw_null", "raw_array"}:
        names = [name for name in result["raw_artifacts"] if name.endswith(("-tests.log", "-tests.xml"))]
        assert len(names) == 8
        for name in names:
            assert (output / name).read_bytes() == b"fresh raw"
            assert result["raw_artifacts"][name]["sha256"] == gate.digest(b"fresh raw")
    if fault == "future_stale":
        assert not any(name.startswith("legacy/") for name in result["raw_artifacts"])
    if fault in {None, "long_temp"}:
        assert all(step["status"] == "passed" for step in result["steps"])
        assert result["steps"][-1]["test_count"] == 1
    else:
        assert result["errors"] or any(step["status"] == "failed" for step in result["steps"])


def test_correctness_source_pins_tests_and_ci_dependencies(tmp_path, monkeypatch):
    monkeypatch.setattr(gate, "source_manifest", lambda root: {"files": {"project.godot": "runtime"}})
    for name in ("backend/tests/test_case.py", "backend/pyproject.toml", "backend/ci-constraints.txt", ".github/workflows/harness.yml", ".harness/profiles/population-runtime-correctness.json"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("before\n", encoding="utf-8")
    before = gate.source_snapshot(tmp_path)
    assert len(before["files"]) == 6
    (tmp_path / "backend/tests/test_case.py").write_text("after\n", encoding="utf-8")
    assert gate.source_snapshot(tmp_path)["source_sha256"] != before["source_sha256"]


def test_correctness_runner_records_failure_and_timeout(tmp_path):
    import sys
    env = dict(os.environ, PYTHONUTF8="1")
    failed = tmp_path / "failed.log"
    assert gate.run_logged([sys.executable, "-c", "print('failure'); raise SystemExit(3)"], cwd=tmp_path, env=env, log=failed, timeout=5) == 3
    assert "failure" in failed.read_text(encoding="utf-8")
    timed = tmp_path / "timeout.log"
    assert gate.run_logged([sys.executable, "-c", "import time; print('started', flush=True); time.sleep(10)"], cwd=tmp_path, env=env, log=timed, timeout=.2) == 124
    assert "timeout" in timed.read_text(encoding="utf-8")


def test_correctness_outer_deadlines_cover_all_serial_child_budgets():
    import yaml
    registry = gate.load_profile_registry(gate.ROOT)
    profile = registry.profiles[gate.NAME]
    # 四个producer加完整focused回归串行执行；父级不能先于合法子步骤超时。
    assert gate.FOCUSED_TEST_TIMEOUT_SECONDS == 2400
    child_budget = gate.TIMEOUT_SECONDS * len(gate.PROFILES) + gate.FOCUSED_TEST_TIMEOUT_SECONDS
    outer_budget = profile.get("timeout_seconds", 900)
    assert outer_budget >= child_budget + 60
    workflow = yaml.safe_load((gate.ROOT / ".github/workflows/harness.yml").read_text(encoding="utf-8"))
    assert workflow["jobs"]["population-correctness"]["timeout-minutes"] * 60 > outer_budget
