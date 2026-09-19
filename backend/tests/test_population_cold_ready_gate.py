import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from scripts.verification import verify_population_long_session_recovery as recovery


@pytest.mark.parametrize("large_steps, passed", [(100000, False), (1500, True), (1501, False)])
def test_resource_gate_limits_vm_work_even_when_returned_rows_are_fixed(large_steps, passed):
    def sample(steps):
        return {"ready": {"sql": {"vm_interval": 100, "databases": {"graph.sqlite3": {
            "rows": 100, "payload_bytes": 1000, "vm_steps_sampled": steps,
        }}}, "calls": {"decode:Example.model_validate": 20}}}

    result = recovery.resource_bounds({1000: [sample(1000)], 10000: [sample(large_steps)]})
    assert result["passed"] is passed, result
    assert result["sql_vm_steps_sampled"] == {1000: 1000, 10000: large_steps}
    assert result["sql_vm_step_limit"] == 1500


def test_resource_gate_allows_only_one_sampling_interval_per_database():
    def sample(steps):
        return {"ready": {"sql": {"vm_interval": 100, "databases": {
            name: {"rows": 1, "payload_bytes": 10, "vm_steps_sampled": steps}
            for name in ("graph.sqlite3", "gameplay.sqlite3")
        }}, "calls": {}}}

    assert recovery.resource_bounds({1000: [sample(0)], 10000: [sample(100)]})["passed"]
    assert not recovery.resource_bounds({1000: [sample(0)], 10000: [sample(200)]})["passed"]


def test_cold_ready(tmp_path):
    root = Path(__file__).resolve().parents[2]
    output = tmp_path / "gate"
    result = subprocess.run([
        sys.executable, str(root / "scripts/verification/verify_population_long_session_recovery.py"),
        "--population", "2", "--histories", "32", "64", "--repeats", "1", "--output", str(output),
    ], cwd=root, env=dict(os.environ, PYTHONUTF8="1"), capture_output=True, text=True, timeout=150)
    # 通用 correctness 环境不强制性能比值；真实验收仍由 CLI 按原阈值返回非零。
    assert result.returncode in (0, 1), result.stdout + result.stderr
    assert (output / "report.json").exists(), result.stdout + result.stderr
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    assert report["resource_bounds"]["passed"], report["resource_bounds"]
    assert not report["formal_acceptance_configuration"]
    for samples in report["cases"].values():
        assert samples[0]["oracle_matches"] and samples[0]["ready"]["replayed_windows"] == [8]
        assert samples[0]["ready"]["caches"]["session_events"] == 0
        assert samples[0]["pending_before"] == samples[0]["pending_after"]
        for pending in samples[0]["pending_after"].values():
            assert pending["count"] == 0
    small = json.loads((output / "fixture-32/manifest.json").read_text(encoding="utf-8"))
    large = json.loads((output / "fixture-64/manifest.json").read_text(encoding="utf-8"))
    for table in ("graph_nodes", "graph_relations", "character_session_events", "character_session_candidates", "character_session_receipts"):
        assert large["graph_history_rows"][table] > small["graph_history_rows"][table]
