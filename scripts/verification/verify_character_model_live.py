from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Callable

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.gateway.model_provider import CharacterModelCallEvidence, CharacterModelProvider
from app.models.character_agent_runtime import CharacterInterpretation, CharacterPrivateWorldSnapshot
from app.models.character_perceived import CharacterPerceivedEvent
from app.services.character_agent_l2 import CharacterAgentL2Service
from app.services.character_agent_l3 import CharacterAgentL3Service
from app.services.dialogue_service import DialogueService
from app.config import settings

from common import repo_root, verification_dir, write_json, write_markdown


REPORT_JSON = "character-model-live-report.json"
REPORT_MD = "character-model-live-report.md"
SCHEMA_VERSION = "character-model-live.v1"
RESULT_IDS = {
    "dialogue": "dialogue_live_deepseek",
    "l2": "l2_live_deepseek",
    "l3": "l3_live_deepseek",
}


def _provider() -> CharacterModelProvider:
    return CharacterModelProvider()


def _gateway(provider: CharacterModelProvider) -> CharacterModelGateway:
    return CharacterModelGateway(provider=provider)


def _credential_failure(message: str) -> dict[str, object]:
    return _result(
        result_id="credential_check",
        status="failed",
        evidence=None,
        latency_ms=0,
        validator_status="not_run",
        consumer_status="not_run",
        error_type="credential_check",
        notes=message,
    )


def _config_guard() -> dict[str, object] | None:
    if settings.character_model_provider_kind != "deepseek":
        return _credential_failure(f"provider_kind={settings.character_model_provider_kind}")
    if settings.dialogue_mode == "stub":
        return _credential_failure("DIALOGUE_MODE=stub")
    if os.getenv("CHARACTER_MODEL_ROUTE_OVERRIDE"):
        return _credential_failure("CHARACTER_MODEL_ROUTE_OVERRIDE must be unset")
    if not settings.character_model_api_key:
        return _credential_failure("missing CHARACTER_MODEL_API_KEY")
    if not settings.character_model_endpoint:
        return _credential_failure("missing CHARACTER_MODEL_ENDPOINT")
    if not settings.character_model_model:
        return _credential_failure("missing CHARACTER_MODEL_MODEL")
    return None


def _result(
    *,
    result_id: str,
    status: str,
    evidence: CharacterModelCallEvidence | None,
    latency_ms: int,
    validator_status: str,
    consumer_status: str,
    error_type: str | None = None,
    notes: str = "",
) -> dict[str, object]:
    return {
        "id": result_id,
        "status": status,
        "transport_attempted": evidence.transport_attempted if evidence is not None else False,
        "transport_succeeded": evidence.transport_succeeded if evidence is not None else False,
        "fallback_used": evidence.fallback_used if evidence is not None else False,
        "validator_status": validator_status,
        "consumer_status": consumer_status,
        "latency_ms": latency_ms,
        "provider_kind": evidence.provider_kind if evidence is not None else settings.character_model_provider_kind,
        "model": evidence.model_name if evidence is not None else settings.character_model_model,
        "endpoint_host": evidence.endpoint_host if evidence is not None else "not_configured",
        "error_type": error_type or (evidence.error_type if evidence is not None else None),
        "notes": notes,
    }


def _passes_evidence(evidence: CharacterModelCallEvidence | None, *, task_kind: str) -> bool:
    return (
        evidence is not None
        and evidence.task_kind == task_kind
        and evidence.provider_kind == "deepseek"
        and evidence.transport_attempted
        and evidence.transport_succeeded
        and not evidence.fallback_used
    )


def _run_scenario(result_id: str, task_kind: str, call: Callable[[CharacterModelProvider], object]) -> dict[str, object]:
    provider = _provider()
    started = time.perf_counter()
    try:
        consumer_output = call(provider)
        latency_ms = int((time.perf_counter() - started) * 1000)
        evidence = provider.last_call_evidence
        status = "passed" if _passes_evidence(evidence, task_kind=task_kind) else "failed"
        return _result(
            result_id=result_id,
            status=status,
            evidence=evidence,
            latency_ms=latency_ms,
            validator_status="passed" if status == "passed" else "failed",
            consumer_status="passed" if consumer_output is not None and status == "passed" else "failed",
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        return _result(
            result_id=result_id,
            status="failed",
            evidence=provider.last_call_evidence,
            latency_ms=latency_ms,
            validator_status="failed",
            consumer_status="failed",
            error_type=exc.__class__.__name__,
            notes=str(exc)[:240],
        )


def _dialogue(provider: CharacterModelProvider) -> tuple[str, str]:
    service = DialogueService(gateway=_gateway(provider))
    content, tone = service.generate_reply("char_a", "Acknowledge the visible lamp change.")
    if not content or not tone:
        raise ValueError("dialogue content/tone must be non-empty")
    return content, tone


def _snapshot() -> CharacterPrivateWorldSnapshot:
    return CharacterPrivateWorldSnapshot(
        actor_id="char_a",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=1300,
        updated_at=1300,
        visible_entities=["visual_fact/light_level_drop"],
        attention_targets=["env_lamp"],
        recent_world_changes=["env_lamp light level changed visibly"],
        clarity_score=0.9,
        certainty_score=0.9,
    )


def _event() -> CharacterPerceivedEvent:
    return CharacterPerceivedEvent(
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=1301,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="visual_fact/light_level_drop at env_lamp",
        source_candidate_event_id="visual_fact:1301:char_a:env_lamp",
        target_environment_id="env_lamp",
        clarity_score=0.9,
        certainty_score=0.9,
    )


def _l2(provider: CharacterModelProvider) -> CharacterInterpretation:
    service = CharacterAgentL2Service(gateway=_gateway(provider))
    interpretation = service.interpret_perceived_event(
        _snapshot(),
        _event(),
        memory_bundle={
            "working_memory": [],
            "event_memories": [],
            "observation_memories": [],
            "knowledge_memories": [],
            "social_memories": [],
            "higher_order_memories": [],
        },
    )
    if not interpretation.interpreted_summary:
        raise ValueError("typed L2 interpretation must include interpreted_summary")
    return interpretation


def _l3(provider: CharacterModelProvider) -> dict[str, object]:
    planner = CharacterAgentL3Service(gateway=_gateway(provider))
    decision = planner.select_intent(
        CharacterInterpretation(
            actor_id="char_a",
            interpreted_summary="env_lamp changed visibly",
            interpretation_type="state_change",
            salience_score=0.82,
            ambiguity_level="low",
            risk_level="low",
            opportunity_level="medium",
            attention_target="env_lamp",
            inner_prompt_candidate="notice the lamp change",
        ),
        control_mode="agent_full_auto",
        snapshot={"recent_world_changes": ["env_lamp light level changed visibly"], "attention_targets": ["env_lamp"]},
        memory_bundle={
            "working_memory": [],
            "event_memories": [],
            "observation_memories": [],
            "knowledge_memories": [],
            "social_memories": [],
            "higher_order_memories": [],
        },
    )
    if not decision.primary_goal:
        raise ValueError("typed L3 decision must include primary_goal")
    return decision.model_dump()


def build_report() -> dict[str, object]:
    guard = _config_guard()
    if guard is not None:
        results = [guard]
    else:
        results = [
            _run_scenario(RESULT_IDS["dialogue"], "dialogue_generation", _dialogue),
            _run_scenario(RESULT_IDS["l2"], "l2_reasoning", _l2),
            _run_scenario(RESULT_IDS["l3"], "l3_planning", _l3),
        ]
    provider = _provider()
    return {
        "schema_version": SCHEMA_VERSION,
        "verification_run_id": os.getenv("LLM_CLOSURE_RUN_ID", ""),
        "overall_character_model_live_passed": all(result["status"] == "passed" for result in results),
        "provider": {
            "provider_kind": provider._provider_kind,
            "model": provider._model_name,
            "endpoint_host": provider.last_call_evidence.endpoint_host if provider.last_call_evidence else _redacted_provider_host(provider),
        },
        "results": results,
    }


def _redacted_provider_host(provider: CharacterModelProvider) -> str:
    from urllib.parse import urlparse

    endpoint = provider._endpoint_url
    if not endpoint:
        return "not_configured"
    parsed = urlparse(endpoint if "://" in endpoint else f"https://{endpoint}")
    return parsed.hostname or "redacted_endpoint"


def main() -> int:
    report = build_report()
    root = repo_root()
    log_dir = verification_dir(root)
    write_json(log_dir / REPORT_JSON, report)
    write_markdown(log_dir / REPORT_MD, "Character Model Live Proof", report, "overall_character_model_live_passed")
    print(f"character_model_live_report_json=.harness/verification/{REPORT_JSON}")
    print(f"overall_character_model_live_passed={report['overall_character_model_live_passed']}")
    for result in report["results"]:
        print(f"result_id={result['id']} status={result['status']} fallback_used={result['fallback_used']}")
        if result["status"] != "passed":
            print(f"failed_stage={result['id']} error_type={result.get('error_type')}")
    return 0 if report["overall_character_model_live_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
