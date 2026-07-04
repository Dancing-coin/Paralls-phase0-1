from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.world_runtime.intelligence_upgrade import CanonicalPerceptBundle, PerceptionQueryFrame, SpatialReference, TimeWindow
from app.world_runtime.vla_cache import VLACache
from app.world_runtime.vla_model_registry import default_vla_model_registry
from app.world_runtime.vla_percept_bridge import merge_vla_advisory_into_bundle, vla_result_to_modality_result
from app.world_runtime.vla_provider import (
    DeterministicMockVLAProvider,
    HTTPVLAProviderAdapter,
    LocalVLAProviderAdapter,
    VLAProviderRequest,
    VLAProviderStatus,
)
from app.world_runtime.vla_slow_path_scheduler import VLASlowPathScheduler
from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = [
    "backend/tests/test_vla_provider_backend_contract.py",
    "backend/tests/test_vla_provider_backend_adapter.py",
    "backend/tests/test_vla_slow_path_scheduler.py",
    "backend/tests/test_vla_provider_cache_isolation.py",
    "backend/tests/test_vla_percept_bridge.py",
    "backend/tests/test_vla_runtime_consumption.py",
]


def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def _load_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _build_siming_request(frame: PerceptionQueryFrame) -> VLAProviderRequest:
    siming_frame = PerceptionQueryFrame(
        query_id="pqf:siming:vla-provider-backend",
        consumer_kind="siming",
        subject_id="siming",
        time_window=TimeWindow(
            started_at=frame.time_window.started_at,
            ended_at=frame.time_window.ended_at,
            cadence=frame.time_window.cadence,
        ),
        spatial_reference=SpatialReference(
            room_id=frame.spatial_reference.room_id,
            scene_id=frame.spatial_reference.scene_id,
            zone_id=frame.spatial_reference.zone_id,
            coordinate_space="siming_global",
        ),
        visual_inputs=list(frame.visual_inputs),
        spatial_inputs=list(frame.spatial_inputs),
        environment_inputs=list(frame.environment_inputs),
        structured_fact_refs=list(frame.structured_fact_refs),
        multimodal_context_id="siming_mm:room_demo",
        cache_namespace="siming_mm:room_demo:vla_cache",
        inference_history_ref="siming_mm:room_demo:vla_history",
    )
    return VLAProviderRequest.from_pqf(siming_frame, owner_kind="siming", owner_id="siming", model_id="qwen3-vl-plus")


def _real_provider_status(env: dict[str, str], request: VLAProviderRequest):
    mode = env.get("VLA_PROVIDER_MODE", "blocked")
    endpoint = env.get("VLA_PROVIDER_ENDPOINT", "")
    api_key = env.get("VLA_PROVIDER_API_KEY", "")
    model = env.get("VLA_PROVIDER_MODEL", "qwen3-vl-plus")
    if mode == "disabled":
        return VLAProviderStatus.DISABLED, "disabled"
    if mode == "local":
        result = LocalVLAProviderAdapter(model_id=model, endpoint=endpoint).interpret(request)
        return result.status, result.fallback_reason or result.status.value
    if mode == "http":
        result = HTTPVLAProviderAdapter(endpoint=endpoint, api_key=api_key, model_id=model).interpret(request)
        return result.status, result.fallback_reason or result.status.value
    if endpoint == "" or api_key == "":
        result = HTTPVLAProviderAdapter(endpoint=endpoint, api_key=api_key, model_id=model).interpret(request)
        return result.status, result.fallback_reason or result.status.value
    result = HTTPVLAProviderAdapter(endpoint=endpoint, api_key=api_key, model_id=model).interpret(request)
    return result.status, result.fallback_reason or result.status.value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)

    pytest_log = log_dir / "vla-provider-backend-pytest.log"
    pytest_result = run_command([python_exe, "-m", "pytest", "-q", *TEST_FILES], project_root, pytest_log)

    sampling_artifact = log_dir / "godot-sampling-production-grade-providers-runtime.json"
    sampling_payload = _load_json(sampling_artifact)
    artifact_status = "available" if sampling_payload else "blocked_missing_artifacts"
    frame_payload = sampling_payload.get("perception_query_frame", {}) if sampling_payload else {}
    request_ok = False
    mock_ok = False
    scheduler_ok = False
    cache_ok = False
    bridge_ok = False
    consumed_bundle_id = ""
    trace: dict[str, object] = {}
    real_status = VLAProviderStatus.BLOCKED_MISSING_ARTIFACTS
    real_reason = "blocked_missing_artifacts"

    if isinstance(frame_payload, dict) and frame_payload:
        frame = PerceptionQueryFrame(**frame_payload)
        request = VLAProviderRequest.from_pqf(
            frame,
            owner_kind="character",
            owner_id=frame.subject_id,
            model_id=os.environ.get("VLA_PROVIDER_MODEL", "qwen3-vl-plus"),
            timeout_seconds=float(os.environ.get("VLA_PROVIDER_TIMEOUT_SECONDS", "8.0")),
        )
        siming_request = _build_siming_request(frame)
        request_ok = bool(request.artifact_refs) and request.context_namespace.startswith("character_mm:")

        provider = DeterministicMockVLAProvider()
        mock_result = provider.interpret(request)
        mock_ok = mock_result.status == VLAProviderStatus.MOCK_PROVIDER_VERIFIED and mock_result.advisory
        modality = vla_result_to_modality_result(mock_result)
        bundle = CanonicalPerceptBundle(
            bundle_id="bundle:character:char_b:vla-provider-backend",
            consumer_kind="character",
            subject_id=frame.subject_id,
            query_id=frame.query_id,
            percept_context_id=frame.multimodal_context_id,
            local_spatial_state={"source": "L1", "passability": "passable"},
            structured_fact_refs=list(frame.structured_fact_refs),
        )
        consumed = merge_vla_advisory_into_bundle(bundle, mock_result)
        consumed_bundle_id = consumed.bundle_id
        bridge_ok = (
            modality.modality == "visual_spatial"
            and consumed.uncertainty["vla_advisory"]["advisory"] is True
            and consumed.local_spatial_state["source"] == "L1"
        )

        scheduler = VLASlowPathScheduler(max_queue_size=int(os.environ.get("VLA_PROVIDER_MAX_QUEUE_SIZE", "8")))
        scheduler_status = scheduler.enqueue(request, now=float(frame.time_window.ended_at))
        timeout_result = scheduler.timeout_result(request)
        scheduler_ok = scheduler_status == "enqueued" and timeout_result.status == VLAProviderStatus.TIMEOUT and timeout_result.advisory

        cache = VLACache(ttl_seconds=float(os.environ.get("VLA_PROVIDER_CACHE_TTL_SECONDS", "30.0")))
        cache.put(request, mock_result, now=1.0)
        cache_hit = cache.get(request, now=2.0)
        cache_siming_miss = cache.get(siming_request, now=2.0)
        cache_ok = cache_hit == mock_result and cache_siming_miss is None and request.cache_namespace != siming_request.cache_namespace

        real_status, real_reason = _real_provider_status(os.environ, request)
        trace = {
            "request_id": request.request_id,
            "artifact_refs": request.artifact_refs,
            "mock_result": mock_result.model_dump(mode="json"),
            "scheduler_trace": scheduler.trace_dicts(),
            "cache_trace": cache.trace,
            "consumed_bundle_id": consumed_bundle_id,
            "real_provider_status": real_status.value,
            "real_provider_reason": real_reason,
        }

    registry = default_vla_model_registry()
    registry_ok = {
        "qwen3-vl-plus",
        "qwen3-vl-local",
        "seed-vl-advisor",
        "openvla-action-head-research-only",
    }.issubset(set(registry))
    real_provider_acceptable = real_status in {
        VLAProviderStatus.BLOCKED_MISSING_CREDENTIALS,
        VLAProviderStatus.CONFIGURED_UNVERIFIED,
        VLAProviderStatus.REAL_PROVIDER_VERIFIED,
        VLAProviderStatus.DISABLED,
    }

    trace_path = log_dir / "vla-provider-backend-trace.json"
    write_json(trace_path, trace)
    results = [
        _result("backend-contract-verified", "VLA backend focused pytest suite passes", pytest_result.returncode == 0, [str(pytest_log)]),
        _result("godot-runtime-artifact-available", "Godot sampling provider artifact is available for PQF input", artifact_status == "available", [str(sampling_artifact)], artifact_status),
        _result("pqf-to-request-verified", "PQF converts to VLAProviderRequest with artifact refs and private context/cache", request_ok, [str(trace_path)]),
        _result("mock-provider-verified", "Deterministic provider returns schema-valid advisory findings", mock_ok, [str(trace_path)], "Mock proof is contract-only and not reported as real provider verification."),
        _result("scheduler-timeout-degrade-verified", "Slow path scheduler enqueues, traces and degrades on timeout without current tick blocking", scheduler_ok, [str(trace_path)]),
        _result("cache-isolation-verified", "Character and Siming cache namespaces do not cross-hit", cache_ok, [str(trace_path)]),
        _result("percept-bridge-verified", "VLAProviderResult converts to visual_spatial modality and advisory bundle fields", bridge_ok, [str(trace_path)]),
        _result("model-registry-verified", "Qwen3-VL and Seed candidates are registered with runtime boundaries", registry_ok, ["backend/app/world_runtime/vla_model_registry.py"]),
        {
            "id": "real-provider-readiness",
            "title": "Real Qwen3-VL/Seed provider readiness is explicit",
            "status": real_status.value,
            "evidence": [str(trace_path)],
            "notes": real_reason,
        },
    ]
    overall = (
        pytest_result.returncode == 0
        and artifact_status == "available"
        and request_ok
        and mock_ok
        and scheduler_ok
        and cache_ok
        and bridge_ok
        and registry_ok
        and real_provider_acceptable
    )
    report = {
        "overall_vla_provider_backend_passed": overall,
        "real_provider_status": real_status.value,
        "artifact_status": artifact_status,
        "consumed_bundle_id": consumed_bundle_id,
        "results": results,
        "artifacts": {
            "pytest_log": str(pytest_log),
            "sampling_artifact": str(sampling_artifact),
            "trace": str(trace_path),
        },
    }
    json_path = log_dir / "vla-provider-backend-report.json"
    md_path = log_dir / "vla-provider-backend-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "VLA Provider Backend Verification Report", report, "overall_vla_provider_backend_passed")

    print(f"vla_provider_backend_report_json={json_path}")
    print(f"vla_provider_backend_report_md={md_path}")
    print(f"overall_vla_provider_backend_passed={overall}")
    print(f"real_provider_status={real_status.value}")
    print(f"artifact_status={artifact_status}")
    for entry in results:
        print(f"{entry['id']}={entry['status']}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
