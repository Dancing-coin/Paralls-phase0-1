from __future__ import annotations

import base64
import json
import mimetypes
import time
from dataclasses import dataclass, field
from pathlib import Path


GODOT_RUNTIME_REPORT = Path(".harness/verification/godot-sampling-production-grade-providers-runtime.json")
GODOT_RUNTIME_CAPTURE = Path(".harness/verification/godot-sampling-visual-capture.png")
ANNOTATION_MANIFEST = Path("docs/verification/vla-advisory-replay-annotation-manifest.json")
SUPPORTED_IMAGE_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class LiveProofImage:
    source: str
    origin: str
    evidence_refs: list[str] = field(default_factory=list)
    failure_reason: str = ""
    sample_scope: dict[str, str] = field(default_factory=dict)
    grounding_catalog: dict[str, list[str]] = field(default_factory=dict)


def redact_inline_image_payloads(value: object) -> object:
    if isinstance(value, str):
        return "redacted_data_image" if value.startswith("data:image/") else value
    if isinstance(value, list):
        return [redact_inline_image_payloads(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_inline_image_payloads(item) for key, item in value.items()}
    return value


def resolve_live_proof_image(
    root: Path,
    *,
    configured_url: str,
    configured_path: str,
    use_godot_runtime_capture: bool,
    max_godot_capture_age_seconds: float,
    now: float | None = None,
) -> LiveProofImage:
    if use_godot_runtime_capture:
        return _resolve_godot_runtime_capture(root, max_age_seconds=max_godot_capture_age_seconds, now=now)
    if configured_url.strip():
        return LiveProofImage(source=configured_url.strip(), origin="configured_url")
    if not configured_path.strip():
        return LiveProofImage(source="", origin="missing", failure_reason="missing_live_proof_image")
    return _resolve_local_image(root, root / configured_path.strip(), origin="repo_local_file")


def resolve_annotation_sample_capture(
    root: Path,
    *,
    sample_id: str,
    max_age_seconds: float,
    now: float | None = None,
) -> LiveProofImage:
    try:
        manifest = json.loads((root / ANNOTATION_MANIFEST).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return LiveProofImage(source="", origin="annotation_runtime_capture", failure_reason="missing_annotation_manifest")
    samples = manifest.get("samples") if isinstance(manifest, dict) else None
    sample = next(
        (candidate for candidate in samples if isinstance(candidate, dict) and candidate.get("sample_id") == sample_id),
        None,
    ) if isinstance(samples, list) else None
    if not isinstance(sample, dict):
        return LiveProofImage(source="", origin="annotation_runtime_capture", failure_reason="unknown_annotation_sample")
    runtime_capture = sample.get("runtime_capture")
    if not isinstance(runtime_capture, dict):
        return LiveProofImage(source="", origin="annotation_runtime_capture", failure_reason="missing_annotation_runtime_capture")
    return _resolve_runtime_capture(
        root,
        report_relative_path=str(runtime_capture.get("report_path", "")),
        capture_relative_path=str(runtime_capture.get("capture_path", "")),
        expected_status=str(runtime_capture.get("expected_status", "")),
        max_age_seconds=max_age_seconds,
        now=now,
        origin="annotation_runtime_capture",
        sample_scope={
            key: str(sample.get(key, ""))
            for key in ("sample_id", "room_id", "scene_id", "zone_id", "subject_id", "target_ref")
        },
        grounding_catalog=_annotation_grounding_catalog(sample.get("advisory_grounding")),
    )


def _resolve_godot_runtime_capture(root: Path, *, max_age_seconds: float, now: float | None) -> LiveProofImage:
    return _resolve_runtime_capture(
        root,
        report_relative_path=str(GODOT_RUNTIME_REPORT),
        capture_relative_path=str(GODOT_RUNTIME_CAPTURE),
        expected_status="godot-runtime-sampling-verified",
        max_age_seconds=max_age_seconds,
        now=now,
        origin="godot_runtime_capture",
        sample_scope={},
        grounding_catalog={},
    )


def _resolve_runtime_capture(
    root: Path,
    *,
    report_relative_path: str,
    capture_relative_path: str,
    expected_status: str,
    max_age_seconds: float,
    now: float | None,
    origin: str,
    sample_scope: dict[str, str],
    grounding_catalog: dict[str, list[str]],
) -> LiveProofImage:
    report_path = root / report_relative_path
    capture_path = root / capture_relative_path
    if max_age_seconds <= 0:
        return LiveProofImage(source="", origin=origin, failure_reason="invalid_capture_age_budget")
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return LiveProofImage(source="", origin=origin, failure_reason="missing_or_invalid_godot_runtime_report")
    if not isinstance(payload, dict) or payload.get("status") != expected_status:
        return LiveProofImage(source="", origin=origin, failure_reason="godot_runtime_probe_not_verified")
    visual_refs = payload.get("provider_refs", {}).get("visual_inputs", []) if isinstance(payload.get("provider_refs"), dict) else []
    visual_ref = visual_refs[0] if isinstance(visual_refs, list) and visual_refs and isinstance(visual_refs[0], dict) else {}
    artifact_ref = str(visual_ref.get("artifact_ref", "") or payload.get("artifact_ref", ""))
    expected_artifact_ref = "runtime://artifact/" + capture_path.resolve().as_posix()
    if artifact_ref != expected_artifact_ref:
        return LiveProofImage(source="", origin=origin, failure_reason="godot_capture_artifact_ref_mismatch")
    try:
        capture_mtime = capture_path.stat().st_mtime
        report_mtime = report_path.stat().st_mtime
    except OSError:
        return LiveProofImage(source="", origin=origin, failure_reason="missing_godot_runtime_capture")
    current_time = time.time() if now is None else now
    if current_time - capture_mtime > max_age_seconds:
        return LiveProofImage(source="", origin=origin, failure_reason="stale_godot_runtime_capture")
    if capture_mtime > report_mtime + 1:
        return LiveProofImage(source="", origin=origin, failure_reason="godot_capture_newer_than_matching_report")
    resolved = _resolve_local_image(root, capture_path, origin=origin)
    if not resolved.source:
        return resolved
    return LiveProofImage(
        source=resolved.source,
        origin=resolved.origin,
        evidence_refs=[report_relative_path, artifact_ref, str(visual_ref.get("ref_id", ""))],
        sample_scope=sample_scope,
        grounding_catalog=grounding_catalog,
    )


def _resolve_local_image(root: Path, candidate: Path, *, origin: str) -> LiveProofImage:
    try:
        candidate = candidate.resolve()
        candidate.relative_to(root.resolve())
    except ValueError:
        return LiveProofImage(source="", origin=origin, failure_reason="invalid_outside_repo_path")
    media_type, _ = mimetypes.guess_type(candidate.name)
    if not candidate.is_file() or media_type not in SUPPORTED_IMAGE_MEDIA_TYPES:
        return LiveProofImage(source="", origin=origin, failure_reason="invalid_local_image_path")
    if candidate.stat().st_size > MAX_IMAGE_BYTES:
        return LiveProofImage(source="", origin=origin, failure_reason="local_image_exceeds_10mb")
    encoded = base64.b64encode(candidate.read_bytes()).decode("ascii")
    return LiveProofImage(source=f"data:{media_type};base64,{encoded}", origin=origin)


def _annotation_grounding_catalog(value: object) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    return {
        key: [str(ref) for ref in refs if isinstance(ref, str) and ref]
        for key in ("entity_refs", "collider_refs", "anchor_refs", "affordance_refs")
        if isinstance((refs := value.get(key)), list)
    }
