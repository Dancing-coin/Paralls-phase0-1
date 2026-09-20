import json

from scripts.verification.ci_failure_summary import failure_summary


def test_summary_selects_failure_location_without_copying_raw_payloads(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({
        "status": "failed", "error": "ValueError: harness_command_or_exit_invalid",
        "command": ["private command"], "source": {"private": "not included"},
        "steps": [{"profile": "focused", "status": "failed", "exit_code": 124,
                   "error": "ValueError: focused_pytest_failed", "request": "private request"}],
    }), encoding="utf-8")
    (tmp_path / "ready.json").write_text('{"secret":"private secret"}', encoding="utf-8")
    (tmp_path / "focused.xml").write_text(
        '<testsuites><testsuite><testcase classname="runtime" name="recovery">'
        '<failure>private failure detail</failure></testcase></testsuite></testsuites>', encoding="utf-8")
    rows = failure_summary(tmp_path)
    assert rows[0]["failures"] == [{"profile": "focused", "status": "failed", "exit_code": 124,
                                    "error": "ValueError: focused_pytest_failed"}]
    assert rows[1] == {"file": "focused.xml", "test": "runtime.recovery", "status": "failure"}
    assert "private" not in json.dumps(rows)


def test_summary_handles_missing_evidence_and_broken_reports(tmp_path):
    assert failure_summary(tmp_path / "missing") == [{"error": "evidence_root_missing"}]
    (tmp_path / "manifest.json").write_text("{", encoding="utf-8")
    (tmp_path / "focused.xml").write_text("<", encoding="utf-8")
    assert {item["error"] for item in failure_summary(tmp_path)} == {"report_unreadable", "junit_unreadable"}


def test_summary_includes_actual_harness_rule_failure_and_cleanup_failure(tmp_path):
    (tmp_path / "profile-result.json").write_text(json.dumps({
        "profile": "sample", "status": "failed", "failure_kind": "evidence",
        "message": "Source inputs changed during verification",
        "failed_checks": [{"id": "source", "status": "missing", "notes": "private note"}],
    }), encoding="utf-8")
    (tmp_path / "harness-run-report.json").write_text(json.dumps({
        "overall_harness_passed": False, "cleanup_status": "failed", "cleanup_errors": ["owned path locked"],
        "profiles": [{"profile": "sample", "status": "passed"}],
    }), encoding="utf-8")
    (tmp_path / "change-lifecycle-report.json").write_text(json.dumps({
        "overall_change_lifecycle_passed": False,
        "results": [{"id": "workflow_doc_exists", "status": "missing", "notes": "private note"}],
    }), encoding="utf-8")
    rows = {row["file"]: row for row in failure_summary(tmp_path)}
    assert rows["profile-result.json"]["message"] == "Source inputs changed during verification"
    assert rows["profile-result.json"]["failed_checks"] == [{"id": "source", "status": "missing"}]
    assert rows["harness-run-report.json"]["cleanup_status"] == "failed"
    assert rows["harness-run-report.json"]["cleanup_errors"] == ["details_omitted"]
    assert rows["change-lifecycle-report.json"]["failures"] == [{"id": "workflow_doc_exists", "status": "missing"}]
    assert "private" not in json.dumps(rows)


def test_invalid_error_container_is_not_published_and_bad_group_does_not_abort(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({
        "status": "failed", "error": {"request": "private request"},
        "errors": ["RuntimeError: request body contains private input"],
    }), encoding="utf-8")
    (tmp_path / "profile-result.json").write_text('{"steps":null}', encoding="utf-8")
    rows = failure_summary(tmp_path)
    assert rows[0]["diagnostic_error"] == "report_invalid_shape"
    assert rows[0]["errors"] == ["RuntimeError: details_omitted"]
    assert rows[1]["error"] == "report_invalid_shape"
    assert "private" not in json.dumps(rows)


def test_ci_exposes_only_filtered_failure_locations_as_escaped_annotations(tmp_path, monkeypatch, capsys):
    from scripts.verification import ci_failure_summary
    (tmp_path / 'manifest.json').write_text(json.dumps({'status': 'failed',
        'error': 'RuntimeError: provider request contains private input',
        'steps': [{'profile': 'focused%0A', 'status': 'failed', 'exit_code': 124}],
        'request': 'private payload'}), encoding='utf-8')
    destination = tmp_path / 'summary.md'
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(destination))
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    monkeypatch.setattr('sys.argv', ['ci_failure_summary.py', str(tmp_path)])
    ci_failure_summary.main()
    output = capsys.readouterr().out
    assert '::warning title=Structured verification failure::' in output
    assert '"exit_code": 124' in output and 'RuntimeError: details_omitted' in output
    assert 'focused%250A' in output
    assert 'private' not in output
    assert 'Structured verification failures' in destination.read_text(encoding='utf-8')


def test_ci_annotation_supports_unicode_test_names_on_windows_stdout(tmp_path, monkeypatch):
    import io
    from scripts.verification import ci_failure_summary
    destination = tmp_path / 'summary.md'
    monkeypatch.setenv('GITHUB_STEP_SUMMARY', str(destination))
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    monkeypatch.setattr('sys.argv', ['ci_failure_summary.py', str(tmp_path)])
    monkeypatch.setattr(ci_failure_summary, 'failure_summary', lambda _: [dict(
        file='focused.xml', test='runtime.test_中文场景', status='failure')])
    buffer = io.BytesIO()
    output = io.TextIOWrapper(buffer, encoding='cp1252')
    monkeypatch.setattr('sys.stdout', output)
    ci_failure_summary.main()
    output.flush()
    assert '::warning' in buffer.getvalue().decode('ascii')
    assert '中文场景' in destination.read_text(encoding='utf-8')
