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


def test_write_harness_report_records_active_changes_and_failure_digest(tmp_path: Path) -> None:
    changes_dir = tmp_path / ".harness" / "changes"
    changes_dir.mkdir(parents=True)
    (changes_dir / "chg-active.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "id": "chg-active",
                "title": "Active change",
                "status": "active",
                "verification_profiles": ["docs"],
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / ".harness" / "verification" / "docs-report.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(
        json.dumps(
            {
                "results": [
                    {"id": "docs_index_paths_exist", "status": "missing", "evidence": []}
                ]
            }
        ),
        encoding="utf-8",
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
        run_id="run_observable",
        profile_configs={
            "docs": {
                "result_artifact": ".harness/verification/docs-report.json",
            }
        },
    )

    manifest = json.loads(report_paths["manifest"].read_text(encoding="utf-8"))
    archived_manifest = json.loads((report_paths["run_dir"] / "run-manifest.json").read_text(encoding="utf-8"))
    digest_path = tmp_path / ".harness" / "verification" / "docs-failure-digest.json"
    archived_digest_path = report_paths["run_dir"] / "docs-failure-digest.json"

    assert manifest["harness_changes"] == [
        {
            "id": "chg-active",
            "title": "Active change",
            "status": "active",
            "path": ".harness/changes/chg-active.json",
            "verification_profiles": ["docs"],
        }
    ]
    assert manifest["harness_change_errors"] == []
    assert manifest["failure_digest_artifacts"] == [
        ".harness/verification/docs-failure-digest.json"
    ]
    assert archived_manifest["failure_digest_artifacts"] == [
        ".harness/verification/runs/run_observable/docs-failure-digest.json"
    ]
    assert digest_path.exists()
    assert archived_digest_path.exists()


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
    report_path = tmp_path / ".harness" / "verification" / "custom-report.json"
    report_path.parent.mkdir(parents=True)
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
    report_path = tmp_path / ".harness" / "verification" / "custom-report.json"
    report_path.parent.mkdir(parents=True)
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
        [sys.executable, str(script)],
        tmp_path,
        log_path,
        success_markers=["MARKER_OK"],
        timeout_seconds=5.0,
    )

    assert result.returncode == 0
    assert result.marker_found is True
    assert "MARKER_OK" in log_path.read_text(encoding="utf-8")
