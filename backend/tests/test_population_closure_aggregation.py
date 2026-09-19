"""聚合器控制测试；专用复验器替身不构成六项真实验收证据。"""
import json
import xml.etree.ElementTree as ET

import pytest

from scripts.verification import aggregate_population_closure as gate


@pytest.mark.parametrize("fault", [None, "missing", "old_commit", "source", "not_run", "blocked", "static_only",
    "godot_unverified", "raw_csv_missing", "threshold_changed", "identity_changed", "outside", "reused", "unknown"])
def test_aggregation_requires_every_fresh_verified_profile(tmp_path, monkeypatch, fault):
    revision = "a" * 40
    source = {"source_sha256": "test-source", "files": {}}
    identities = []

    def identity(_):
        identities.append(1)
        if fault == "identity_changed" and len(identities) > 1:
            raise ValueError("changed_during_verification")
        return source, source

    monkeypatch.setattr(gate, "_identity", identity)
    locations = {}
    for names in gate.REQUIRED.values():
        for name in names:
            path = tmp_path / name
            path.mkdir()
            manifest = dict(schema_version=2 if name == "recovery" else 1, base_commit=revision, source=source, status="passed")
            if name == "godot":
                if fault in {"not_run", "blocked", "static_only", "godot_unverified"}:
                    manifest["status"] = fault
                if fault == "old_commit":
                    manifest["base_commit"] = "b" * 40
                if fault == "source":
                    manifest["source"] = {"source_sha256": "old"}
            (path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            locations[name] = name
    if fault == "missing":
        del locations["godot"]
    if fault == "outside":
        locations["godot"] = "../outside"
    if fault == "reused":
        locations["godot"] = "service-100"
    if fault == "unknown":
        locations["skip-real-godot"] = "godot"
    (tmp_path / "evidence.json").write_text(json.dumps(dict(schema_version=1, profiles=locations)), encoding="utf-8")
    verified = []

    def verify(name, directory, commit):
        assert directory.is_relative_to(tmp_path) and commit == revision
        verified.append(name)
        if name == "godot" and fault in {"raw_csv_missing", "threshold_changed"}:
            raise ValueError(fault)
        return {"passed": True}

    monkeypatch.setattr(gate, "_verify_profile", verify)
    result = gate.aggregate(tmp_path, expected_commit=revision)
    assert result["status"] == ("passed" if fault is None else "incomplete")
    assert result["godot_status"] == ("runtime_verified" if fault is None else "godot_unverified")
    assert len(result["profiles"]) == 12
    assert set(result["items"]) == set("123456")
    assert (tmp_path / "closure-report.md").is_file()
    junit = ET.parse(tmp_path / "closure-report.xml").getroot()
    assert len(junit.findall("testcase")) == 12
    assert bool(junit.findall("testcase/failure")) == (fault is not None)
    if fault is None:
        assert set(verified) == set(locations)


def test_aggregation_current_population_requirement_excludes_service_10000():
    assert gate.REQUIRED["1"] == ("service-100", "service-1000")


def test_real_service_verifier_cannot_accept_manifest_only(tmp_path, monkeypatch):
    from scripts.verification import verify_population_service_isolation as service
    source = {"source_sha256": "test", "files": {}}
    monkeypatch.setattr(service, "source_manifest", lambda: source)
    manifest = dict(schema_version=1, base_commit="a" * 40, source=source,
                    profile="population-service-isolation", passed=True)
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="raw_artifacts"):
        gate._verify_profile("service-100", tmp_path, "a" * 40)


def test_dedicated_missing_verifier_is_not_a_pass(tmp_path, monkeypatch):
    import types
    monkeypatch.setattr(gate.importlib, "import_module", lambda _: types.SimpleNamespace())
    with pytest.raises(ValueError, match="offline_verifier_missing"):
        gate._verify_profile("recovery", tmp_path, "a" * 40)


@pytest.mark.parametrize('changed', ['backend/app/deleted.py', 'assets/characters/profiles/deleted.yaml', 'backend/tests/renamed_old.py', 'docs/superpowers/local-only.md'])
def test_identity_rejects_deleted_or_renamed_source_even_when_absent_from_snapshot(monkeypatch, changed):
    revision = 'a'*40
    monkeypatch.setattr(gate, 'source_manifest', lambda: {'files': {'backend/app/kept.py': 'x'}})
    monkeypatch.setattr(gate, 'source_snapshot', lambda _: {'files': {'backend/app/kept.py': 'x'}})
    def git(command, **kwargs):
        if 'rev-parse' in command: return revision
        if 'diff' in command: return changed
        return 'backend/app/kept.py\0' + changed
    monkeypatch.setattr(gate.subprocess, 'check_output', git)
    if changed.startswith('docs/'):
        gate._identity(revision)
    else:
        with pytest.raises(ValueError, match='uncommitted_verification_source'):
            gate._identity(revision)


@pytest.mark.parametrize("profile,version,dispatched", [
    ("recovery", 2, True), ("recovery", 1, False), ("recovery", 3, False),
    *[(name, 2, False) for names in gate.REQUIRED.values() for name in names if name != "recovery"],
])
def test_profile_schema_dispatch_preserves_real_recovery_verifier(tmp_path, monkeypatch, profile, version, dispatched):
    from scripts.verification import verify_population_long_session_recovery as recovery
    revision = "a" * 40
    source = {"files": {}}
    monkeypatch.setattr(gate, "_identity", lambda _: (source, source))
    # 不替换专用复验器；它拒绝缺少原始证据的 manifest，证明真实分发已到达。
    calls = []
    def identity():
        calls.append(1)
        return {"base_commit": revision, "source": source}
    monkeypatch.setattr(recovery, "_source_identity", identity)
    path = tmp_path / profile
    path.mkdir()
    (path / "manifest.json").write_text(json.dumps(dict(
        schema_version=version, base_commit=revision, source=source, status="passed")), encoding="utf-8")
    (tmp_path / "evidence.json").write_text(json.dumps(dict(
        schema_version=1, profiles={profile: profile})), encoding="utf-8")
    result = gate.aggregate(tmp_path, expected_commit=revision)
    row = next(row for row in result["profiles"] if row["profile"] == profile)
    assert row["status"] == "incomplete"
    assert bool(calls) is dispatched
    assert ("recovery_evidence_identity_or_status_invalid" if dispatched else
            "evidence_schema_or_commit_mismatch") in row["error"]
