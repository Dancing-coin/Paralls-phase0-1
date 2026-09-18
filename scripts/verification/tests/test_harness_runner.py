from __future__ import annotations

import json
import sys
import threading
import time
import urllib.request
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import common
import pytest
from run_context import run_scope
from common import verification_dir


@pytest.fixture(autouse=True)
def run_context(tmp_path):
    with run_scope(tmp_path):
        yield

import harness
from common import get_health

from evidence import (
    build_failure_digest,
    collect_harness_changes,
    extract_failed_checks,
)
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
    assert not (report_paths["run_dir"] / "baseline.json").exists()
    assert not (report_paths["run_dir"] / "runs").exists()






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




def test_collect_harness_changes_reads_only_active_manifests(tmp_path: Path) -> None:
    changes_dir = tmp_path / ".harness" / "changes"
    changes_dir.mkdir(parents=True)
    active_path = changes_dir / "chg-active.json"
    superseded_path = changes_dir / "chg-superseded.json"
    rejected_path = changes_dir / "chg-rejected.json"

    active_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "chg-active",
                "title": "Active change",
                "status": "active",
                "verification_profiles": ["docs", "harness-lifecycle"],
            }
        ),
        encoding="utf-8",
    )
    superseded_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "chg-superseded",
                "title": "Old change",
                "status": "superseded",
                "verification_profiles": ["docs"],
            }
        ),
        encoding="utf-8",
    )
    rejected_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "chg-rejected",
                "title": "Rejected change",
                "status": "rejected",
                "verification_profiles": ["docs"],
            }
        ),
        encoding="utf-8",
    )

    result = collect_harness_changes(tmp_path)

    assert result["harness_change_errors"] == []
    assert result["harness_changes"] == [
        {
            "id": "chg-active",
            "title": "Active change",
            "status": "active",
            "path": ".harness/changes/chg-active.json",
            "verification_profiles": ["docs", "harness-lifecycle"],
        }
    ]


def test_collect_harness_changes_reports_invalid_manifest_without_raising(tmp_path: Path) -> None:
    changes_dir = tmp_path / ".harness" / "changes"
    changes_dir.mkdir(parents=True)
    (changes_dir / "broken.json").write_text("{not-json", encoding="utf-8")

    result = collect_harness_changes(tmp_path)

    assert result["harness_changes"] == []
    assert result["harness_change_errors"] == [
        {
            "path": ".harness/changes/broken.json",
            "error": "invalid_json",
        }
    ]


def test_collect_harness_changes_reports_invalid_text_without_raising(tmp_path: Path) -> None:
    changes_dir = tmp_path / ".harness" / "changes"
    changes_dir.mkdir(parents=True)
    (changes_dir / "invalid-text.json").write_bytes(b"\xff\xfe\xfa")

    result = collect_harness_changes(tmp_path)

    assert result["harness_changes"] == []
    assert result["harness_change_errors"] == [
        {
            "path": ".harness/changes/invalid-text.json",
            "error": "invalid_text",
        }
    ]


def test_collect_harness_changes_rejects_missing_or_unsupported_schema_version(tmp_path: Path) -> None:
    changes_dir = tmp_path / ".harness" / "changes"
    changes_dir.mkdir(parents=True)
    (changes_dir / "missing-schema.json").write_text(
        json.dumps(
            {
                "id": "chg-missing-schema",
                "title": "Missing schema",
                "status": "active",
                "verification_profiles": ["docs"],
            }
        ),
        encoding="utf-8",
    )
    (changes_dir / "unsupported-schema.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "id": "chg-unsupported-schema",
                "title": "Unsupported schema",
                "status": "active",
                "verification_profiles": ["docs"],
            }
        ),
        encoding="utf-8",
    )

    result = collect_harness_changes(tmp_path)

    assert result["harness_changes"] == []
    assert result["harness_change_errors"] == [
        {
            "path": ".harness/changes/missing-schema.json",
            "error": "invalid_schema_version",
        },
        {
            "path": ".harness/changes/unsupported-schema.json",
            "error": "invalid_schema_version",
        },
    ]


def test_collect_harness_changes_rejects_mixed_verification_profile_types(tmp_path: Path) -> None:
    changes_dir = tmp_path / ".harness" / "changes"
    changes_dir.mkdir(parents=True)
    (changes_dir / "mixed-profiles.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "chg-mixed",
                "title": "Mixed profiles",
                "status": "active",
                "verification_profiles": ["docs", 3],
            }
        ),
        encoding="utf-8",
    )

    result = collect_harness_changes(tmp_path)

    assert result["harness_changes"] == []
    assert result["harness_change_errors"] == [
        {
            "path": ".harness/changes/mixed-profiles.json",
            "error": "invalid_verification_profiles",
        }
    ]


def test_extract_failed_checks_reads_missing_result_entries() -> None:
    report = {
        "results": [
            {"id": "docs_index_paths_exist", "status": "proved", "evidence": ["docs/INDEX.md"]},
            {"id": "runtime_trace_exists", "status": "missing", "evidence": []},
            {"id": "phase0_loop", "status": "failed", "evidence": ["phase0-report.json"]},
        ]
    }

    assert extract_failed_checks(report) == [
        {"id": "runtime_trace_exists", "status": "missing", "evidence": []},
        {"id": "phase0_loop", "status": "failed", "evidence": ["phase0-report.json"]},
    ]


def test_build_failure_digest_degrades_when_report_has_no_structured_checks(tmp_path: Path) -> None:
    report_path = verification_dir(tmp_path) / "custom-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps({"overall_custom_passed": False}), encoding="utf-8")

    digest = build_failure_digest(
        project_root=tmp_path,
        run_id="run_digest",
        profile_result={
            "profile": "custom",
            "command": ["python", "scripts/verification/custom.py"],
            "exit_code": 1,
        },
        profile_config={
            "result_artifact": ".harness/verification/custom-report.json",
        },
    )

    assert digest["schema_version"] == 1
    assert digest["run_id"] == "run_digest"
    assert digest["profile"] == "custom"
    assert digest["status"] == "failed"
    assert digest["exit_code"] == 1
    assert digest["command"] == ["python", "scripts/verification/custom.py"]
    assert digest["summary_status"] == "profile_failed_without_structured_checks"
    assert digest["primary_report"] == ".harness/verification/custom-report.json"
    assert digest["failed_checks"] == []
    assert digest["runtime_trace_refs"] == []
    assert digest["source_artifacts"] == [".harness/verification/custom-report.json"]


def test_build_failure_digest_degrades_when_report_json_is_invalid(tmp_path: Path) -> None:
    report_path = verification_dir(tmp_path) / "custom-report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("{not-json", encoding="utf-8")

    digest = build_failure_digest(
        project_root=tmp_path,
        run_id="run_digest",
        profile_result={
            "profile": "custom",
            "command": ["python", "scripts/verification/custom.py"],
            "exit_code": 1,
        },
        profile_config={
            "result_artifact": ".harness/verification/custom-report.json",
        },
    )

    assert digest["summary_status"] == "profile_failed_without_structured_checks"
    assert digest["primary_report"] == ".harness/verification/custom-report.json"
    assert digest["failed_checks"] == []
    assert digest["source_artifacts"] == [".harness/verification/custom-report.json"]


def test_build_failure_digest_preserves_command_when_profile_has_no_report(tmp_path: Path) -> None:
    digest = build_failure_digest(
        project_root=tmp_path,
        run_id="run_no_report",
        profile_result={
            "profile": "custom",
            "command": ["python", "scripts/verification/custom.py", "--flag"],
            "exit_code": 7,
        },
        profile_config={},
    )

    assert digest["summary_status"] == "profile_failed_without_report"
    assert digest["primary_report"] is None
    assert digest["command"] == ["python", "scripts/verification/custom.py", "--flag"]
    assert digest["exit_code"] == 7








def test_get_health_treats_connection_reset_as_unhealthy(monkeypatch) -> None:
    def fake_urlopen(_url: str, timeout: float = 1.0):
        raise ConnectionResetError(10054, "connection reset")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    assert get_health() is None




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
        [sys.executable, str(script)],
        tmp_path,
        log_path,
        success_markers=["MARKER_OK"],
        timeout_seconds=5.0,
    )

    assert result.returncode == 0
    assert result.marker_found is True
    assert "MARKER_OK" in log_path.read_text(encoding="utf-8")


def test_run_command_times_out_and_preserves_streamed_output(tmp_path: Path) -> None:
    script = tmp_path / "hang.py"
    script.write_text(
        "import time\n"
        "print('before-timeout', flush=True)\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )
    log_path = tmp_path / "hang.log"

    started_at = time.monotonic()
    result = common.run_command(
        [sys.executable, str(script)],
        tmp_path,
        log_path,
        timeout_seconds=0.5,
    )

    assert time.monotonic() - started_at < 5.0
    assert result.returncode == 124
    assert "before-timeout" in result.stdout
    assert "before-timeout" in log_path.read_text(encoding="utf-8")
    assert "timed out after 0.5 seconds" in log_path.read_text(encoding="utf-8")


def test_run_command_flushes_log_while_process_is_running(tmp_path: Path) -> None:
    script = tmp_path / "stream.py"
    script.write_text(
        "import time\n"
        "print('streamed-before-exit', flush=True)\n"
        "time.sleep(1)\n",
        encoding="utf-8",
    )
    log_path = tmp_path / "stream.log"
    result_holder: list[object] = []
    runner = threading.Thread(
        target=lambda: result_holder.append(
            common.run_command([sys.executable, str(script)], tmp_path, log_path)
        ),
        daemon=True,
    )

    runner.start()
    deadline = time.monotonic() + 0.8
    while time.monotonic() < deadline:
        if log_path.exists() and "streamed-before-exit" in log_path.read_text(encoding="utf-8"):
            break
        time.sleep(0.02)

    assert runner.is_alive()
    assert "streamed-before-exit" in log_path.read_text(encoding="utf-8")
    runner.join(timeout=3.0)
    assert result_holder[0].returncode == 0


def test_run_command_until_markers_can_wait_for_all_markers(tmp_path: Path) -> None:
    script = tmp_path / "emit_markers.py"
    script.write_text(
        "import time\n"
        "print('FIRST_OK', flush=True)\n"
        "time.sleep(0.2)\n"
        "print('SECOND_OK', flush=True)\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )
    log_path = tmp_path / "markers.log"

    result = common.run_command_until_markers(
        [sys.executable, str(script)],
        tmp_path,
        log_path,
        success_markers=["FIRST_OK", "SECOND_OK"],
        timeout_seconds=5.0,
        require_all_markers=True,
    )

    log_text = log_path.read_text(encoding="utf-8")
    assert result.returncode == 0
    assert result.marker_found is True
    assert "FIRST_OK" in log_text
    assert "SECOND_OK" in log_text
