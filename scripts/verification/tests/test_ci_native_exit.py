"""本地CI遇到native失败应停下，不能让后续绿命令覆盖退出码。"""
import os
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml


@pytest.mark.skipif(os.name != "nt", reason="仓库PowerShell本地CI入口")
def test_first_python_failure_stops_local_gate(tmp_path):
    root = Path(__file__).resolve().parents[3]
    python_stub = tmp_path / "python.cmd"
    python_stub.write_text('@echo off\necho invoked>> "%CI_TEST_CALLS%"\nexit /b 23\n', encoding="utf-8")
    calls = tmp_path / "calls.txt"
    env = {**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"], "CI_TEST_CALLS": str(calls)}
    result = subprocess.run([shutil.which("powershell"), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                             "-File", str(root / ".harness/ci/local-ci-gate.ps1")],
                            cwd=tmp_path, env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 23
    assert calls.read_text(encoding="utf-8").splitlines() == ["invoked"]


def test_hosted_harness_installs_pinned_engine_and_preserves_separate_gates():
    root = Path(__file__).resolve().parents[3]
    job = yaml.safe_load((root / ".github/workflows/harness.yml").read_text(encoding="utf-8"))["jobs"]["harness"]
    assert "GODOT_EXE" not in job.get("env", {})
    assert next(step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout@"))["with"]["lfs"] is True
    install = next(step["run"] for step in job["steps"] if "Get-FileHash" in step.get("run", ""))
    assert "https://github.com/godotengine/godot-builds/releases/download/4.6.3-stable/Godot_v4.6.3-stable_win64.exe.zip" in install
    assert "e39986a178d585ce7ac198fb8de6ea436366dc0cc00e594810c2e3e104c04b90" in install
    runs = [step["run"] for step in job["steps"] if "verify_population_harness_evidence.py" in step.get("run", "")]
    assert len(runs) == 3
    assert {command.split("--profile ", 1)[1].split()[0] for command in runs} == {"all", "mainline-unified-runtime", "change-lifecycle"}
    assert all(command.count("python ") == 1 for command in runs)
    upload = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/upload-artifact@"))
    assert upload["if"] == "always()"
    assert upload["with"]["include-hidden-files"] is True


def test_performance_job_is_explicit_fixed_machine_and_retains_all_raw_runs():
    root = Path(__file__).resolve().parents[3]
    job = yaml.safe_load((root / '.github/workflows/harness.yml').read_text(encoding='utf-8'))['jobs']['population-performance-fixed-runner']
    assert job['runs-on'] == ['self-hosted', 'Windows', 'X64', 'paralls-population-performance']
    assert job['if'] == "github.event_name == 'workflow_dispatch' && inputs.run_population_performance"
    runs = [step for step in job['steps'] if 'scripts/verification/' in step.get('run', '')]
    assert len(runs) == 6 and all(step['run'].count('python ') == 1 for step in runs)
    commands = '\n'.join(step['run'] for step in runs)
    assert 'population_mixed_matrix.py --kind soak' in commands and 'population_mixed_matrix.py --kind short' in commands
    assert 'verify_population_multi_game_capacity.py' in commands
    assert 'verify_population_long_session_recovery.py' in commands
    assert 'verify_population_service_isolation.py' in commands and 'verify_population_transport_cost.py' in commands
    assert all(step['if'] == '${{ !cancelled() }}' for step in runs)
    assert 'godot' not in commands.lower()
    upload = next(step for step in job['steps'] if step.get('uses', '').startswith('actions/upload-artifact@'))
    assert upload['if'] == 'always()' and upload['with']['include-hidden-files'] is True
    paths = upload['with']['path'].splitlines()
    assert paths[0] == '.harness/verification/ci-performance/'
    assert '!.harness/verification/ci-performance/**/state/**' in paths
    assert '!.harness/verification/ci-performance/recovery/run-*/**' in paths
