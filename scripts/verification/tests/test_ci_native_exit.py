"""本地CI遇到native失败应停下，不能让后续绿命令覆盖退出码。"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import json

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check_release_gate import evaluate_release_gate
from common import collection_output_path, collection_report_path
from run_context import attempt_scope, run_scope
from scripts.verification import verify_population_harness_evidence as broad_gate


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
    assert paths[0] == '${{ env.HARNESS_CI_EVIDENCE }}/'
    assert '!${{ env.HARNESS_CI_EVIDENCE }}/**/state/**' in paths
    assert '!${{ env.HARNESS_CI_EVIDENCE }}/recovery/run-*/**' in paths


def test_release_gate_rejects_duplicate_workflow_job_key(tmp_path):
    root = Path(__file__).resolve().parents[3]
    shutil.copytree(root / '.harness/ci', tmp_path / '.harness/ci')
    (tmp_path / '.github/workflows').mkdir(parents=True)
    workflow = (root / '.github/workflows/harness.yml').read_text(encoding='utf-8')
    workflow = workflow.replace('  population-performance-fixed-runner:\n', '  population-performance-fixed-runner:\n  population-performance-fixed-runner:\n', 1)
    (tmp_path / '.github/workflows/harness.yml').write_text(workflow, encoding='utf-8')
    report = evaluate_release_gate(tmp_path)
    assert next(row for row in report['results'] if row['id'] == 'ci_workflow_yaml_valid')['status'] == 'missing'
    assert next(row for row in evaluate_release_gate(root)['results'] if row['id'] == 'ci_workflow_yaml_valid')['status'] == 'proved'


@pytest.mark.parametrize('scope', ['static-contract-only', 'release-verified'])
def test_release_gate_rejects_stale_or_overclaimed_hosted_scope(tmp_path, scope):
    root = Path(__file__).resolve().parents[3]
    shutil.copytree(root / '.harness/ci', tmp_path / '.harness/ci')
    shutil.copytree(root / '.github/workflows', tmp_path / '.github/workflows')
    metadata_path = tmp_path / '.harness/ci/release-gate.json'
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    metadata['hosted_ci_scope'] = scope
    metadata_path.write_text(json.dumps(metadata), encoding='utf-8')

    report = evaluate_release_gate(tmp_path)

    assert report['overall_release_gate_passed'] is False
    assert next(row for row in report['results'] if row['id'] == 'release_gate_metadata_exists')['status'] == 'missing'
    assert report['runtime_release_verified'] is False


def test_ci_evidence_is_exported_uploaded_and_owned_output_cleaned():
    root = Path(__file__).resolve().parents[3]
    jobs = yaml.safe_load((root / '.github/workflows/harness.yml').read_text(encoding='utf-8'))['jobs']
    for name in ('population-godot-runtime', 'population-correctness'):
        steps = jobs[name]['steps']
        run = next(step['run'] for step in steps if 'harness.py --profile population-' in step.get('run', ''))
        upload = next(step for step in steps if step.get('uses', '').startswith('actions/upload-artifact@'))
        assert '--export-evidence "$env:HARNESS_CI_EVIDENCE"' in run
        assert upload['with']['path'] == '${{ env.HARNESS_CI_EVIDENCE }}/'
        assert upload['if'] == 'always()'
        cleanup = next(step for step in steps if 'Remove-Item' in step.get('run', ''))
        assert cleanup['if'] == "${{ always() && steps." + upload['id'] + ".outcome == 'success' }}"
    for name in ('population-performance-fixed-runner', 'harness'):
        steps = jobs[name]['steps']
        upload = next(step for step in steps if step.get('uses', '').startswith('actions/upload-artifact@'))
        assert '${{ env.HARNESS_CI_EVIDENCE }}' in upload['with']['path']
        cleanup = next(step for step in steps if 'Remove-Item' in step.get('run', ''))
        assert cleanup['if'] == "${{ always() && steps." + upload['id'] + ".outcome == 'success' }}"


def test_collection_report_follows_explicit_output_or_active_attempt(tmp_path):
    root = Path(__file__).resolve().parents[3]
    output = tmp_path / 'performance-case'
    assert collection_report_path(root, output, 'population-service-isolation-report.json') == output / 'population-service-isolation-report.json'
    with run_scope(root) as run:
        assert collection_report_path(root, output, 'population-service-isolation-report.json') == run.evidence_root / 'population-service-isolation-report.json'
        assert collection_output_path(root, 'population-correctness-case') == run.evidence_root / 'population-correctness-case'


def test_broad_capture_commands_export_fresh_owned_evidence(tmp_path):
    command = broad_gate._expected_command('change-lifecycle', tmp_path, 'python', None, tmp_path / 'artifacts')
    assert command[-2:] == ['--export-evidence', str(tmp_path / 'artifacts')]


def test_harness_source_inventory_reads_utf8_git_paths():
    assert broad_gate.harness_inputs()


def test_nested_harness_report_path_is_relative_to_parent_run(tmp_path):
    root = Path(__file__).resolve().parents[3]
    exported = tmp_path / 'export'
    with run_scope(root, export_to=exported) as run:
        with attempt_scope(run, 'parent', 1) as parent:
            child = parent / 'child-authority-graph-projection'
            child.mkdir()
            env = {**os.environ, 'HARNESS_ATTEMPT_ROOT': str(child), 'HARNESS_ATTEMPT_ID': 'child'}
            result = subprocess.run([sys.executable, str(root / 'scripts/verification/harness.py'),
                '--profile', 'authority-graph-projection'], cwd=root, env=env,
                capture_output=True, text=True, encoding='utf-8', timeout=60)
            assert result.returncode == 0, result.stdout[-1000:] + result.stderr[-1000:]
            summary = json.loads((child / 'harness-run-report.json').read_text(encoding='utf-8'))
            relative = summary['profiles'][0]['evidence']['path']
            assert relative.startswith('profiles/parent/1/child-authority-graph-projection/profiles/')
            assert (run.evidence_root / relative).is_file()
    assert (exported / relative).is_file()
    assert not run.evidence_root.exists()
