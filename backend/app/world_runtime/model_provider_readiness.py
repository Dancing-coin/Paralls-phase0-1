from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse


SCHEMA_VERSION = "model-provider-readiness.v1"
REPORT_JSON = Path(".harness/verification/model-provider-readiness-report.json")
REPORT_MARKDOWN = Path(".harness/verification/model-provider-readiness-report.md")


class ModelProviderKind(StrEnum):
    CHARACTER_TEXT = "character_text"
    SIMING_CANDIDATE = "siming_candidate"
    VLA_SPATIAL = "vla_spatial"
    PRODUCTION_MULTIMODAL = "production_multimodal"


class ModelProviderMode(StrEnum):
    DISABLED = "disabled"
    HTTP = "http"
    LOCAL = "local"
    BLOCKED = "blocked"


class ModelProviderReadinessStatus(StrEnum):
    DISABLED = "disabled"
    NOT_CONFIGURED = "not_configured"
    CONTRACT_READY = "contract_ready"
    HTTP_CONFIGURED_UNVERIFIED = "http_configured_unverified"
    REAL_PROVIDER_VERIFIED = "real_provider_verified"
    BLOCKED_MISSING_ARTIFACTS = "blocked_missing_artifacts"
    BLOCKED_MISSING_CREDENTIALS = "blocked_missing_credentials"
    BLOCKED_MODEL_UNAVAILABLE = "blocked_model_unavailable"


@dataclass(frozen=True)
class ModelProviderReadinessRow:
    provider_kind: str
    mode: str
    provider_id: str
    model_id: str
    endpoint_host_redacted: str
    readiness_status: str
    schema_version: str
    required_input_refs: list[str]
    output_schema_status: str
    timeout_degrade_status: str
    context_isolation_status: str
    world_truth_write_status: str
    verification_evidence: list[str]
    notes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ModelProviderReadinessReport:
    schema_version: str
    overall_passed: bool
    rows: list[ModelProviderReadinessRow]
    verification_run_id: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "overall_passed": self.overall_passed,
            "verification_run_id": self.verification_run_id,
            "rows": [asdict(row) for row in self.rows],
        }


def build_model_provider_readiness_report(
    *,
    env: dict[str, str] | None = None,
    real_smoke_checker: Callable[[ModelProviderKind, dict[str, str]], bool] | None = None,
) -> ModelProviderReadinessReport:
    values = _merged_env(env)
    rows = [
        _character_text_row(values, real_smoke_checker),
        _siming_candidate_row(values, real_smoke_checker),
        _vla_spatial_row(values, real_smoke_checker),
        _production_multimodal_row(values, real_smoke_checker),
    ]
    blocked_or_clear = {
        ModelProviderReadinessStatus.DISABLED,
        ModelProviderReadinessStatus.CONTRACT_READY,
        ModelProviderReadinessStatus.HTTP_CONFIGURED_UNVERIFIED,
        ModelProviderReadinessStatus.REAL_PROVIDER_VERIFIED,
        ModelProviderReadinessStatus.BLOCKED_MISSING_ARTIFACTS,
        ModelProviderReadinessStatus.BLOCKED_MISSING_CREDENTIALS,
        ModelProviderReadinessStatus.BLOCKED_MODEL_UNAVAILABLE,
    }
    overall_passed = all(ModelProviderReadinessStatus(row.readiness_status) in blocked_or_clear for row in rows)
    return ModelProviderReadinessReport(
        schema_version=SCHEMA_VERSION,
        overall_passed=overall_passed,
        rows=rows,
        verification_run_id=_env(values, "LLM_CLOSURE_RUN_ID", "") or None,
    )


def write_model_provider_readiness_report(
    report: ModelProviderReadinessReport,
    *,
    project_root: Path | None = None,
) -> tuple[Path, Path]:
    root = project_root or Path.cwd()
    json_path = root / REPORT_JSON
    markdown_path = root / REPORT_MARKDOWN
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_render_markdown(report), encoding="utf-8")
    return json_path, markdown_path


def _character_text_row(
    env: dict[str, str],
    real_smoke_checker: Callable[[ModelProviderKind, dict[str, str]], bool] | None,
) -> ModelProviderReadinessRow:
    provider_id = _env(env, "CHARACTER_MODEL_PROVIDER_KIND", "qwen")
    mode = ModelProviderMode.LOCAL if provider_id == "local" else ModelProviderMode.HTTP
    if provider_id == "deepseek":
        endpoint = _env(env, "CHARACTER_MODEL_ENDPOINT", "") or "https://api.deepseek.com"
        api_key = _env(env, "CHARACTER_MODEL_API_KEY", "")
        model = _env(env, "CHARACTER_MODEL_MODEL", "") or "deepseek-chat"
    elif provider_id == "seed_doubao":
        endpoint = _env(env, "CHARACTER_MODEL_ENDPOINT", "")
        api_key = _env(env, "CHARACTER_MODEL_API_KEY", "")
        model = _env(env, "CHARACTER_MODEL_MODEL", "") or "doubao-seed-2.0-pro"
    elif provider_id == "local":
        endpoint = ""
        api_key = ""
        model = "local-continuity-floor"
    else:
        endpoint = _env(env, "CHARACTER_MODEL_ENDPOINT", "") or "https://dashscope.aliyuncs.com/compatible-mode/v1"
        api_key = _env(env, "CHARACTER_MODEL_API_KEY", "")
        model = _env(env, "CHARACTER_MODEL_MODEL", "") or "qwen3.7-plus"
    status = ModelProviderReadinessStatus.CONTRACT_READY if mode == ModelProviderMode.LOCAL else _http_status(
        api_key=api_key,
        endpoint=endpoint,
        kind=ModelProviderKind.CHARACTER_TEXT,
        env=env,
        real_smoke_checker=real_smoke_checker,
    )
    return ModelProviderReadinessRow(
        provider_kind=ModelProviderKind.CHARACTER_TEXT.value,
        mode=mode.value,
        provider_id=provider_id,
        model_id=model,
        endpoint_host_redacted=_redacted_host(endpoint),
        readiness_status=status.value,
        schema_version=SCHEMA_VERSION,
        required_input_refs=["character_private_context", "model_prompt_policy", "task_kind"],
        output_schema_status="character_gateway_output_validator_required",
        timeout_degrade_status=f"timeout_seconds={_env(env, 'CHARACTER_MODEL_TIMEOUT_SECONDS', '20.0')}; local fallback is not real-provider proof",
        context_isolation_status="character_private_context_isolated_from_siming",
        world_truth_write_status="forbidden: dialogue/planning output cannot write world truth or ESM authority",
        verification_evidence=[
            "python -m pytest -q backend/tests/test_character_model_provider_readiness.py",
            "python scripts/verification/verify_model_provider_readiness.py",
        ],
        notes=["CHARACTER_MODEL_* is the only Character runtime provider configuration surface."],
    )


def _siming_candidate_row(
    env: dict[str, str],
    real_smoke_checker: Callable[[ModelProviderKind, dict[str, str]], bool] | None,
) -> ModelProviderReadinessRow:
    mode_value = _env(env, "SIMING_LLM_MODE", "disabled")
    mode = ModelProviderMode.DISABLED if mode_value == "disabled" else ModelProviderMode.HTTP
    route = _selected_siming_route(env)
    provider_order = _env(env, "SIMING_LLM_PROVIDER_ORDER", "seed_doubao,qwen")
    provider_id = str(route.get("provider", "")) if route else (provider_order.split(",", 1)[0].strip() or "seed_doubao")
    endpoint = _env(env, "SIMING_LLM_ENDPOINT", "")
    api_key = _env(env, "SIMING_LLM_API_KEY", "")
    model = _env(env, "SIMING_LLM_MODEL", "doubao-seed-2.0-pro")
    timeout_seconds = _env(env, "SIMING_LLM_TIMEOUT_SECONDS", "8.0")
    if route:
        endpoint = str(route.get("endpoint", "") or "")
        api_key = str(route.get("api_key", "") or "")
        model = str(route.get("model", "") or model)
        timeout_seconds = str(route.get("timeout_seconds", "") or timeout_seconds)
    status = ModelProviderReadinessStatus.DISABLED if mode == ModelProviderMode.DISABLED else _http_status(
        api_key=api_key,
        endpoint=endpoint,
        kind=ModelProviderKind.SIMING_CANDIDATE,
        env=env,
        real_smoke_checker=real_smoke_checker,
    )
    return ModelProviderReadinessRow(
        provider_kind=ModelProviderKind.SIMING_CANDIDATE.value,
        mode=mode.value,
        provider_id=provider_id,
        model_id=model,
        endpoint_host_redacted=_redacted_host(endpoint),
        readiness_status=status.value,
        schema_version=SCHEMA_VERSION,
        required_input_refs=["fairness_state_snapshot", "recent_authority_events", "recent_siming_audit"],
        output_schema_status="InterventionCandidate list only; authority mutations rejected",
        timeout_degrade_status=f"timeout_seconds={timeout_seconds}; router degrades to next provider/empty candidates",
        context_isolation_status="siming_candidate_context_isolated_from_character_private_context",
        world_truth_write_status="forbidden: candidate-level suggestions only",
        verification_evidence=[
            "python -m pytest -q backend/tests/test_siming_llm_provider_config.py backend/tests/test_siming_llm_runtime.py",
            "python scripts/verification/verify_model_provider_readiness.py",
        ],
        notes=["Siming readiness tracks configured identity only; live proof is separate."],
    )


def _vla_spatial_row(
    env: dict[str, str],
    real_smoke_checker: Callable[[ModelProviderKind, dict[str, str]], bool] | None,
) -> ModelProviderReadinessRow:
    mode = ModelProviderMode(_env(env, "VLA_PROVIDER_MODE", "blocked"))
    endpoint = _env(env, "VLA_PROVIDER_ENDPOINT", "")
    api_key = _env(env, "VLA_PROVIDER_API_KEY", "")
    missing_artifacts = not _has_vla_runtime_artifacts(env)
    if mode == ModelProviderMode.DISABLED:
        status = ModelProviderReadinessStatus.DISABLED
    elif missing_artifacts or mode == ModelProviderMode.BLOCKED:
        status = ModelProviderReadinessStatus.BLOCKED_MISSING_ARTIFACTS
    elif mode == ModelProviderMode.LOCAL:
        status = ModelProviderReadinessStatus.CONTRACT_READY
    elif not api_key:
        status = ModelProviderReadinessStatus.BLOCKED_MISSING_CREDENTIALS
    elif not endpoint:
        status = ModelProviderReadinessStatus.NOT_CONFIGURED
    elif _has_matching_vla_live_proof(
        env,
        provider_id=_env(env, "VLA_PROVIDER_KIND", "openai_compatible") + "_vla_provider",
        model_id=_env(env, "VLA_ADVISORY_FAST_MODEL", "qwen3.7-flash"),
        endpoint_host=_redacted_host(endpoint),
    ):
        status = ModelProviderReadinessStatus.REAL_PROVIDER_VERIFIED
    else:
        status = ModelProviderReadinessStatus.HTTP_CONFIGURED_UNVERIFIED
    return ModelProviderReadinessRow(
        provider_kind=ModelProviderKind.VLA_SPATIAL.value,
        mode=mode.value,
        provider_id=_env(env, "VLA_PROVIDER_KIND", "openai_compatible") + "_vla_spatial",
        model_id=_env(env, "VLA_ADVISORY_FAST_MODEL", "qwen3.7-flash"),
        endpoint_host_redacted=_redacted_host(endpoint),
        readiness_status=status.value,
        schema_version=SCHEMA_VERSION,
        required_input_refs=["PerceptionQueryFrame", "visual_artifact_ref", "l1_space_model_ref", "owner_namespace"],
        output_schema_status="advisory spatial findings only; ModalityInterpretationResult bridge required before use",
        timeout_degrade_status=(
            f"fast_timeout_seconds={_env(env, 'VLA_ADVISORY_FAST_TIMEOUT_SECONDS', '12.0')}; "
            f"deep_enabled={_env(env, 'VLA_ADVISORY_DEEP_ENABLED', 'false')}; "
            f"deep_timeout_seconds={_env(env, 'VLA_ADVISORY_DEEP_TIMEOUT_SECONDS', '20.0')}; "
            f"max_queue_size={_env(env, 'VLA_PROVIDER_MAX_QUEUE_SIZE', '8')}; timeout degrades slow path"
        ),
        context_isolation_status="per-owner queue/cache namespace required; no character/siming cache sharing",
        world_truth_write_status="forbidden: advisory findings cannot write L1/world truth/ESM authority",
        verification_evidence=[
            "python -m pytest -q backend/tests/test_model_provider_readiness.py",
            "python scripts/verification/verify_model_provider_readiness.py",
            "python scripts/verification/verify_vla_provider_live.py --allow-live-call (explicit-only live proof)",
            (
                "real adapter call evidence: .harness/verification/vla-provider-live-report.json"
                if status == ModelProviderReadinessStatus.REAL_PROVIDER_VERIFIED
                else "real adapter call evidence pending explicit live proof"
            ),
        ],
        notes=[
            "Real VLA verification requires a PQF with an eligible https:// or data:image/ visual artifact and a schema-valid adapter call.",
            "Production defaults to fast-only. Deep route/model state remains isolated for explicit experiments and stays advisory.",
        ],
    )


def _production_multimodal_row(
    env: dict[str, str],
    real_smoke_checker: Callable[[ModelProviderKind, dict[str, str]], bool] | None,
) -> ModelProviderReadinessRow:
    mode = ModelProviderMode(_env(env, "NON_RUNTIME_MODEL_MODE", "disabled"))
    endpoint = _env(env, "NON_RUNTIME_MODEL_ENDPOINT", "")
    api_key = _env(env, "NON_RUNTIME_MODEL_API_KEY", "")
    if mode == ModelProviderMode.DISABLED:
        status = ModelProviderReadinessStatus.DISABLED
    elif mode == ModelProviderMode.BLOCKED:
        status = ModelProviderReadinessStatus.BLOCKED_MISSING_ARTIFACTS
    elif mode == ModelProviderMode.LOCAL:
        status = ModelProviderReadinessStatus.CONTRACT_READY
    else:
        status = _http_status(
            api_key=api_key,
            endpoint=endpoint,
            kind=ModelProviderKind.PRODUCTION_MULTIMODAL,
            env=env,
            real_smoke_checker=real_smoke_checker,
        )
    return ModelProviderReadinessRow(
        provider_kind=ModelProviderKind.PRODUCTION_MULTIMODAL.value,
        mode=mode.value,
        provider_id="production_review_model",
        model_id=_env(env, "NON_RUNTIME_MODEL_MODEL", "doubao-seed-2.0-lite"),
        endpoint_host_redacted=_redacted_host(endpoint),
        readiness_status=status.value,
        schema_version=SCHEMA_VERSION,
        required_input_refs=["source_artifact_refs", "prompt_schema_version", "review_gate_state"],
        output_schema_status="draft/review artifact only; approved review gate required before L1 seed consumption",
        timeout_degrade_status=f"timeout_seconds={_env(env, 'NON_RUNTIME_MODEL_TIMEOUT_SECONDS', '30.0')}; batch job can fail closed",
        context_isolation_status="non-runtime artifacts stay outside runtime private context/cache/history",
        world_truth_write_status="forbidden: production drafts cannot write runtime truth",
        verification_evidence=[
            "python -m pytest -q backend/tests/test_model_provider_readiness.py",
            "python scripts/verification/verify_model_provider_readiness.py",
        ],
        notes=["Disabled is acceptable until offline production adapters and review workbench are implemented."],
    )


def _http_status(
    *,
    api_key: str,
    endpoint: str,
    kind: ModelProviderKind,
    env: dict[str, str],
    real_smoke_checker: Callable[[ModelProviderKind, dict[str, str]], bool] | None,
) -> ModelProviderReadinessStatus:
    if not api_key:
        return ModelProviderReadinessStatus.BLOCKED_MISSING_CREDENTIALS
    if not endpoint:
        return ModelProviderReadinessStatus.NOT_CONFIGURED
    if _env(env, "MODEL_PROVIDER_READINESS_REAL_SMOKE", "0") != "1":
        return ModelProviderReadinessStatus.HTTP_CONFIGURED_UNVERIFIED
    if real_smoke_checker is None:
        return ModelProviderReadinessStatus.HTTP_CONFIGURED_UNVERIFIED
    try:
        return (
            ModelProviderReadinessStatus.REAL_PROVIDER_VERIFIED
            if real_smoke_checker(kind, env)
            else ModelProviderReadinessStatus.BLOCKED_MODEL_UNAVAILABLE
        )
    except Exception:
        return ModelProviderReadinessStatus.BLOCKED_MODEL_UNAVAILABLE


def _has_vla_runtime_artifacts(env: dict[str, str]) -> bool:
    refs = _env(env, "VLA_PROVIDER_REQUIRED_ARTIFACT_REFS", "")
    return bool(refs)


def _has_matching_vla_live_proof(
    env: dict[str, str],
    *,
    provider_id: str,
    model_id: str,
    endpoint_host: str,
) -> bool:
    expected_run_id = _env(env, "VLA_PROVIDER_LIVE_PROOF_RUN_ID", "")
    report_path = Path(
        _env(env, "VLA_PROVIDER_LIVE_PROOF_REPORT_PATH", ".harness/verification/vla-provider-live-report.json")
    )
    if expected_run_id == "" or not report_path.is_file():
        return False
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    proof = payload.get("proof")
    result = proof.get("result") if isinstance(proof, dict) else None
    required_artifact_refs = {
        ref.strip() for ref in _env(env, "VLA_PROVIDER_REQUIRED_ARTIFACT_REFS", "").split(",") if ref.strip()
    }
    proof_artifact_refs = proof.get("artifact_ref_ids") if isinstance(proof, dict) else None
    return (
        payload.get("run_id") == expected_run_id
        and payload.get("real_provider_status") == ModelProviderReadinessStatus.REAL_PROVIDER_VERIFIED.value
        and payload.get("provider_id") == provider_id
        and payload.get("model_id") == model_id
        and payload.get("endpoint_host") == endpoint_host
        and payload.get("live_call_opted_in") is True
        and payload.get("bridge_ok") is True
        and isinstance(result, dict)
        and result.get("status") == ModelProviderReadinessStatus.REAL_PROVIDER_VERIFIED.value
        and isinstance(proof_artifact_refs, list)
        and required_artifact_refs.issubset({str(ref) for ref in proof_artifact_refs})
    )


def _merged_env(env: dict[str, str] | None) -> dict[str, str]:
    if env is not None:
        return dict(env)
    merged = dict(os.environ)
    process_env_keys = set(merged)
    for env_path in [Path(".env"), Path(".env.vla")]:
        if not env_path.exists():
            continue
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            normalized_key = key.strip()
            if normalized_key not in process_env_keys:
                merged[normalized_key] = value.strip().strip('"').strip("'")
    return merged


def _first_env(env: dict[str, str], *names: str) -> str:
    for name in names:
        value = _env(env, name, "")
        if value:
            return value
    return ""


def _selected_siming_route(env: dict[str, str]) -> dict[str, object] | None:
    raw = _env(env, "SIMING_LLM_ROUTES_JSON", "")
    if raw == "":
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    for item in parsed:
        if not isinstance(item, dict):
            continue
        if item.get("enabled", True) is False:
            continue
        return dict(item)
    return None


def _env(env: dict[str, str], name: str, default: str) -> str:
    return str(env.get(name, default) or default).strip()


def _redacted_host(endpoint: str) -> str:
    if not endpoint:
        return "not_configured"
    parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
    return parsed.hostname or "redacted_endpoint"


def _render_markdown(report: ModelProviderReadinessReport) -> str:
    lines = [
        "# Model Provider Readiness Report",
        "",
        f"- Schema: `{report.schema_version}`",
        f"- Verification run ID: `{report.verification_run_id or ''}`",
        f"- Overall: `{report.overall_passed}`",
        "",
        "| Provider | Mode | Provider ID | Model | Endpoint Host | Status |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in report.rows:
        lines.append(
            "| "
            f"`{row.provider_kind}` | `{row.mode}` | `{row.provider_id}` | `{row.model_id}` | "
            f"`{row.endpoint_host_redacted}` | `{row.readiness_status}` |"
        )
    lines.extend(["", "## Boundary Evidence", ""])
    for row in report.rows:
        lines.extend(
            [
                f"### `{row.provider_kind}`",
                "",
                f"- Required input refs: `{', '.join(row.required_input_refs)}`",
                f"- Output schema: `{row.output_schema_status}`",
                f"- Timeout/degrade: `{row.timeout_degrade_status}`",
                f"- Context isolation: `{row.context_isolation_status}`",
                f"- World-truth writes: `{row.world_truth_write_status}`",
                f"- Verification evidence: `{'; '.join(row.verification_evidence)}`",
                "",
            ]
        )
    return "\n".join(lines)
