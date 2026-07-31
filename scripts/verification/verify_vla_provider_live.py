from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.world_runtime.intelligence_upgrade import (
    AttentionContext,
    CanonicalPerceptBundle,
    PerceptionQueryFrame,
    SampleInputRef,
    SpatialReference,
    TimeWindow,
)
from app.world_runtime.vla_percept_bridge import merge_vla_advisory_into_bundle, vla_result_to_modality_result
from app.world_runtime.vla_provider import HTTPVLAProviderAdapter, VLAProviderStatus
from app.world_runtime.vla_slow_path import VLAAdvisorySlowPath
from app.config import settings
from common import repo_root, verification_dir, write_json, write_markdown
from vla_live_proof_artifact import redact_inline_image_payloads, resolve_annotation_sample_capture, resolve_live_proof_image


def _live_frame(
    image_source: str,
    artifact_ref: str,
    *,
    route: str,
    scope: dict[str, str],
    grounding_catalog: dict[str, list[str]],
) -> PerceptionQueryFrame:
    return PerceptionQueryFrame(
        query_id="pqf:vla-live-proof:1",
        consumer_kind="character",
        subject_id=scope.get("subject_id") or "char_b",
        time_window=TimeWindow(started_at=1, ended_at=2),
        spatial_reference=SpatialReference(
            room_id=scope.get("room_id") or "room_demo",
            scene_id=scope.get("scene_id") or "scene_demo",
            zone_id=scope.get("zone_id") or "zone_focus",
        ),
        target_ref=scope.get("target_ref", ""),
        attention_context=AttentionContext(reason_tags=["vla_deep"] if route == "advisory-deep" else []),
        visual_inputs=[
            SampleInputRef(
                provider_kind="visual_patch",
                ref_id=artifact_ref,
                stable_source_ref=image_source,
                retention="debug_artifact",
            )
        ],
        structured_fact_refs=[f"l1_fact:{artifact_ref}:known-scene-anchor"],
        grounding_entity_refs=list(grounding_catalog.get("entity_refs", [])),
        grounding_collider_refs=list(grounding_catalog.get("collider_refs", [])),
        grounding_anchor_refs=list(grounding_catalog.get("anchor_refs", [])),
        grounding_affordance_refs=list(grounding_catalog.get("affordance_refs", [])),
        multimodal_context_id="character_mm:char_b",
        cache_namespace="character_mm:char_b:vla_cache",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an explicit live VLA advisory-provider proof.")
    parser.add_argument("--allow-live-call", action="store_true", help="required before the script may contact a provider")
    parser.add_argument("--run-id", default=settings.vla_provider_live_proof_run_id)
    parser.add_argument("--route", choices=["advisory-fast", "advisory-deep"], default="advisory-fast")
    parser.add_argument(
        "--use-godot-runtime-capture",
        action="store_true",
        help="require the current Godot sampling probe capture and its matching runtime report",
    )
    parser.add_argument(
        "--annotation-sample-id",
        default="",
        help="derive PQF scope and a matching Godot runtime capture from the reviewed annotation manifest",
    )
    parser.add_argument(
        "--max-godot-capture-age-seconds",
        type=float,
        default=300.0,
        help="maximum accepted age for --use-godot-runtime-capture (default: 300)",
    )
    args = parser.parse_args()

    root = repo_root()
    evidence_dir = verification_dir(root)
    image = (
        resolve_annotation_sample_capture(
            root,
            sample_id=args.annotation_sample_id,
            max_age_seconds=args.max_godot_capture_age_seconds,
        )
        if args.annotation_sample_id
        else resolve_live_proof_image(
            root,
            configured_url=settings.vla_live_proof_image_url,
            configured_path=settings.vla_live_proof_image_path,
            use_godot_runtime_capture=args.use_godot_runtime_capture,
            max_godot_capture_age_seconds=args.max_godot_capture_age_seconds,
        )
    )
    artifact_ref = settings.vla_live_proof_artifact_ref
    adapter = HTTPVLAProviderAdapter.from_runtime_settings()
    slow_path = VLAAdvisorySlowPath.from_runtime_settings()
    status = "not_attempted"
    reason = "explicit_opt_in_required"
    result_payload: dict[str, object] = {}
    bridge_ok = False
    end_to_end_started_at: float | None = None

    if args.allow_live_call:
        if settings.vla_provider_mode != "http":
            status = "blocked_by_mode"
            reason = "VLA_PROVIDER_MODE=http is required for a live HTTP proof"
        elif not args.run_id:
            status = "blocked_missing_run_id"
            reason = "VLA_PROVIDER_LIVE_PROOF_RUN_ID or --run-id is required for readiness promotion"
        elif not image.source:
            status = VLAProviderStatus.BLOCKED_MISSING_ARTIFACTS.value
            reason = image.failure_reason or "VLA_LIVE_PROOF_IMAGE_URL or VLA_LIVE_PROOF_IMAGE_PATH is required"
        else:
            end_to_end_started_at = time.monotonic()
            frame = _live_frame(
                image.source,
                artifact_ref,
                route=args.route,
                scope=image.sample_scope,
                grounding_catalog=image.grounding_catalog,
            )
            submission = slow_path.submit_frame(
                frame,
                owner_kind="character",
                owner_id=frame.subject_id,
            )
            request = submission.request
            result = submission.cached_result or slow_path.consume_next(
                owner_kind=frame.consumer_kind,
                owner_id=frame.subject_id,
            )
            if result is None:
                raise RuntimeError("live VLA request was not available for slow-path consumption")
            status = result.status.value
            reason = result.fallback_reason or result.status.value
            modality = vla_result_to_modality_result(result)
            bundle = CanonicalPerceptBundle(
                bundle_id="bundle:vla-live-proof",
                consumer_kind="character",
                subject_id=frame.subject_id,
                query_id=frame.query_id,
                percept_context_id=frame.multimodal_context_id,
                structured_fact_refs=list(frame.structured_fact_refs),
            )
            consumed = merge_vla_advisory_into_bundle(bundle, result)
            bridge_ok = (
                modality.modality == "visual_spatial"
                and consumed.uncertainty["vla_advisory"]["advisory"] is True
                and consumed.structured_fact_refs == frame.structured_fact_refs
            )
            result_payload = {
                "request_id": request.request_id,
                "artifact_ref_ids": request.artifact_refs,
                "structured_fact_refs": request.structured_fact_refs,
                "grounding_reference_catalog": {
                    "entity_refs": request.grounding_entity_refs,
                    "collider_refs": request.grounding_collider_refs,
                    "anchor_refs": request.grounding_anchor_refs,
                    "affordance_refs": request.grounding_affordance_refs,
                },
                "result": redact_inline_image_payloads(result.model_dump(mode="json")),
                "bridge_ok": bridge_ok,
            }

    end_to_end_seconds = (
        round(time.monotonic() - end_to_end_started_at, 3) if end_to_end_started_at is not None else None
    )

    report = {
        "run_id": args.run_id,
        "real_provider_status": status,
        "reason": reason,
        "provider_id": adapter.provider_id,
        "model_id": result_payload.get("result", {}).get("model_id", settings.vla_advisory_fast_model) if result_payload else settings.vla_advisory_fast_model,
        "model_version": result_payload.get("result", {}).get("model_version", settings.vla_advisory_fast_model_version) if result_payload else settings.vla_advisory_fast_model_version,
        "endpoint_host": _endpoint_host(adapter.endpoint),
        "live_call_opted_in": args.allow_live_call,
        "requested_route": args.route,
        "bridge_ok": bridge_ok,
        "end_to_end_seconds": end_to_end_seconds,
        "artifact_origin": image.origin,
        "artifact_ref": artifact_ref,
        "godot_runtime_capture_requested": args.use_godot_runtime_capture,
        "annotation_sample_id": args.annotation_sample_id,
        "pqf_scope": image.sample_scope,
        "grounding_reference_catalog": image.grounding_catalog,
        "godot_runtime_capture_evidence_refs": image.evidence_refs,
        "provider_http_status": result_payload.get("result", {}).get("provider_http_status") if result_payload else None,
        "provider_error_code": result_payload.get("result", {}).get("provider_error_code", "") if result_payload else "",
        "provider_error_param": result_payload.get("result", {}).get("provider_error_param", "") if result_payload else "",
        "provider_error_category": result_payload.get("result", {}).get("provider_error_category", "") if result_payload else "",
        "failure_phase": result_payload.get("result", {}).get("failure_phase", "") if result_payload else "",
        "provider_thinking_enabled": result_payload.get("result", {}).get("provider_thinking_enabled") if result_payload else None,
        "advisory_boundary": {
            "writes_world_truth": result_payload.get("result", {}).get("writes_world_truth") if result_payload else None,
            "writes_esm_authority": result_payload.get("result", {}).get("writes_esm_authority") if result_payload else None,
            "controls_actor": result_payload.get("result", {}).get("controls_actor") if result_payload else None,
        },
        "proof": result_payload,
    }
    report_stem = "vla-provider-live-report" if args.route == "advisory-fast" else "vla-provider-live-deep-report"
    json_path = evidence_dir / f"{report_stem}.json"
    markdown_path = evidence_dir / f"{report_stem}.md"
    write_json(json_path, report)
    write_markdown(markdown_path, "VLA Provider Live Proof", report, "real_provider_status")
    print(f"vla_provider_live_report_json={json_path}")
    print(f"vla_provider_live_report_md={markdown_path}")
    print(f"real_provider_status={status}")
    return 0 if status == VLAProviderStatus.REAL_PROVIDER_VERIFIED.value and bridge_ok else 1


def _endpoint_host(endpoint: str) -> str:
    from urllib.parse import urlparse

    parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
    return parsed.hostname or "not_configured"


if __name__ == "__main__":
    raise SystemExit(main())
