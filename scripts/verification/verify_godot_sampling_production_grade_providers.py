from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.world_runtime.intelligence_upgrade import PerceptionQueryFrame
from common import read_text, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


REQUIRED_KEYS = {
    "visual_inputs",
    "spatial_inputs",
    "auditory_inputs",
    "embodied_inputs",
    "skeletal_inputs",
    "environment_inputs",
}
REQUIRED_SAMPLE_FIELDS = {
    "provider_kind",
    "ref_id",
    "retention",
    "sample_status",
    "freshness",
    "throttle_state",
    "stable_source_ref",
    "runtime_source_refs",
    "failure_status",
}
REQUIRED_GROUNDING_KEYS = {
    "grounding_entity_refs",
    "grounding_collider_refs",
    "grounding_anchor_refs",
    "grounding_affordance_refs",
}


def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def _resolve_optional_godot(project_root: Path, explicit: str | None) -> Path | None:
    candidates = [
        explicit,
        str(project_root / "Godot.exe"),
        r"D:\godot\Godot_v4.6.3-stable_win64.exe",
        r"E:\下载\Godot_v4.6.3-stable_win64.exe\Godot_v4.6.3-stable_win64_console.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return Path(candidate)
    return None


def _load_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _provider_refs_have_required_fields(provider_refs: object) -> bool:
    if not isinstance(provider_refs, dict) or not REQUIRED_KEYS.issubset(set(provider_refs)):
        return False
    for key in REQUIRED_KEYS:
        entries = provider_refs.get(key)
        if not isinstance(entries, list) or not entries:
            return False
        for entry in entries:
            if not isinstance(entry, dict):
                return False
            if not REQUIRED_SAMPLE_FIELDS.issubset(set(entry)):
                return False
            if entry.get("sample_status") not in {"ok", "stub_artifact", "throttled", "stale", "failed"}:
                return False
            if not isinstance(entry.get("runtime_source_refs"), list) or not entry.get("runtime_source_refs"):
                return False
    return True


def _pqf_schema_valid(payload: dict[str, object]) -> bool:
    frame = payload.get("perception_query_frame")
    if not isinstance(frame, dict):
        return False
    try:
        PerceptionQueryFrame(**frame)
    except Exception:
        return False
    return all(isinstance(frame.get(key), list) and frame.get(key) for key in REQUIRED_KEYS)


def _pqf_has_grounding_catalog(payload: dict[str, object]) -> bool:
    frame = payload.get("perception_query_frame")
    return isinstance(frame, dict) and all(
        isinstance(frame.get(key), list) and frame[key] and all(isinstance(ref, str) and ref for ref in frame[key])
        for key in REQUIRED_GROUNDING_KEYS
    )


def _no_heavy_work(payload: dict[str, object]) -> bool:
    fields = payload.get("no_heavy_work")
    return isinstance(fields, dict) and all(value is False for value in fields.values())


def _scripts_have_boundary_markers(project_root: Path) -> bool:
    paths = [
        "scripts/character/VisualPatchProvider.gd",
        "scripts/character/SpatialPatchProvider.gd",
        "scripts/character/AuditoryContextProvider.gd",
        "scripts/character/EmbodiedStateProvider.gd",
        "scripts/character/SkeletalStateProviderRefEmitter.gd",
        "scripts/character/EnvironmentFieldProvider.gd",
    ]
    for relative in paths:
        text = read_text(project_root / relative)
        if "feeds_query_frame" not in text or "runtime_source_refs" not in text:
            return False
        if "world_truth" in text or "ESM" in text:
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)

    pytest_log = log_dir / "godot-sampling-production-grade-providers-pytest.log"
    pytest_result = run_command(
        [python_exe, "-m", "pytest", "-q", "backend/tests/test_godot_sampling_production_grade_providers.py"],
        project_root,
        pytest_log,
    )

    godot_exe = _resolve_optional_godot(project_root, args.godot_exe)
    godot_log = log_dir / "godot-sampling-production-grade-providers-godot.log"
    runtime_artifact = log_dir / "godot-sampling-production-grade-providers-runtime.json"
    godot_status = "godot-runtime-unverified"
    godot_ok = False
    if godot_exe is not None:
        godot_result = run_command(
            [
                str(godot_exe),
                "--path",
                str(project_root),
                "--scene",
                "res://scenes/phase0/GodotSamplingProvidersProbe.tscn",
                "--quit-after",
                "600",
                "--render-thread",
                "safe",
            ],
            project_root,
            godot_log,
        )
        godot_text = read_text(godot_log)
        godot_ok = (
            godot_result.returncode == 0
            and "godot_sampling_providers_probe:six_provider_refs=true" in godot_text
            and runtime_artifact.exists()
        )
        godot_status = "godot-runtime-sampling-verified" if godot_ok else "godot-runtime-unverified"

    runtime_payload = _load_json(runtime_artifact)
    provider_refs_ok = _provider_refs_have_required_fields(runtime_payload.get("provider_refs"))
    pqf_ok = _pqf_schema_valid(runtime_payload)
    grounding_catalog_ok = _pqf_has_grounding_catalog(runtime_payload)
    no_heavy_work_ok = _no_heavy_work(runtime_payload)
    boundary_ok = _scripts_have_boundary_markers(project_root)
    backend_ok = pytest_result.returncode == 0

    results = [
        _result(
            "backend_contract_verified",
            "Backend provider refs and PQF schema tests pass",
            backend_ok,
            [str(pytest_log)],
        ),
        _result(
            "six_provider_runtime_refs_present",
            "Visual, spatial, auditory, embodied, skeletal and environment provider refs are present",
            provider_refs_ok,
            [str(runtime_artifact)],
        ),
        _result(
            "provider_status_fields_present",
            "Every provider ref carries status, freshness, throttle, retention and failure fields",
            provider_refs_ok,
            [str(runtime_artifact)],
        ),
        _result(
            "backend_pqf_consumes_provider_refs",
            "Runtime provider refs assemble into a schema-valid PerceptionQueryFrame",
            pqf_ok,
            [str(runtime_artifact)],
        ),
        _result(
            "godot_runtime_grounding_catalog_present",
            "Godot runtime PQF carries known entity, collider, anchor, and affordance refs",
            grounding_catalog_ok,
            [str(runtime_artifact)],
        ),
        _result(
            "no_heavy_work_boundary_verified",
            "Providers do not declare heavy inference, heavy voxelization, or full-scene runtime rescan",
            no_heavy_work_ok and boundary_ok,
            [
                "scripts/character/VisualPatchProvider.gd",
                "scripts/character/SpatialPatchProvider.gd",
                "scripts/character/EnvironmentFieldProvider.gd",
            ],
        ),
        {
            "id": "godot_runtime_probe",
            "title": "Godot sampling providers runtime probe completed",
            "status": "proved" if godot_ok else godot_status,
            "evidence": [str(godot_log), str(runtime_artifact)] if godot_exe is not None else [],
            "notes": "" if godot_ok else "Godot unavailable or sampling probe did not produce a schema-valid runtime artifact.",
        },
    ]
    overall = backend_ok and provider_refs_ok and pqf_ok and grounding_catalog_ok and no_heavy_work_ok and boundary_ok and godot_ok
    report = {
        "overall_godot_sampling_production_grade_providers_passed": overall,
        "godot_runtime_status": godot_status,
        "results": results,
        "artifacts": {
            "pytest_log": str(pytest_log),
            "godot_log": str(godot_log),
            "runtime_artifact": str(runtime_artifact),
        },
    }
    json_path = log_dir / "godot-sampling-production-grade-providers-report.json"
    md_path = log_dir / "godot-sampling-production-grade-providers-report.md"
    write_json(json_path, report)
    write_markdown(
        md_path,
        "Godot Sampling Production-Grade Providers Verification Report",
        report,
        "overall_godot_sampling_production_grade_providers_passed",
    )

    print(f"godot_sampling_production_grade_providers_report_json={json_path}")
    print(f"godot_sampling_production_grade_providers_report_md={md_path}")
    print(f"overall_godot_sampling_production_grade_providers_passed={overall}")
    print(f"godot_runtime_status={godot_status}")
    for entry in results:
        print(f"{entry['id']}={entry['status']}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
