from __future__ import annotations

import argparse
import importlib
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.config import Settings
from app.models.authority_event import AuthorityEvent
from app.models.siming_event import InterventionCandidate
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_pipeline import SimingEventPipeline
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_llm_provider import FakeSimingLlmCandidateProvider
from app.services.siming_runtime import SimingRuntime

from common import repo_root, verification_dir, write_json, write_markdown


REPORT_JSON = "siming-backend-chain-report.json"
REPORT_MD = "siming-backend-chain-report.md"
ROOM_ID = "room_demo"
VISUAL_CORRELATION_ID = "visual_fact:300"
VISUAL_EVENT_ID = "visual_fact:300:char_c:light_level_drop"
ESTABLISHED_FACT_ID = VISUAL_EVENT_ID
SIMING_NON_DISPATCH_EVENT_TYPES = {
    "siming.fairness_snapshot",
    "siming.intervention_candidate",
    "siming.intervention_decision",
    "siming.audit_recorded",
    "siming.no_action_recorded",
}


@dataclass(frozen=True)
class LiveProviderProofConfig:
    provider: str
    display_name: str
    scenario: str
    title: str
    default_endpoint: str
    default_model: str
    api_key_envs: tuple[str, ...]
    endpoint_envs: tuple[str, ...]
    model_envs: tuple[str, ...]
    required_endpoint_marker: str | None = None


LIVE_PROVIDER_CONFIGS: dict[str, LiveProviderProofConfig] = {
    "deepseek_chat": LiveProviderProofConfig(
        provider="deepseek_chat",
        display_name="DeepSeek",
        scenario="app_wiring_live_deepseek_chain",
        title="App wiring live DeepSeek backend chain",
        default_endpoint="https://api.deepseek.com/chat/completions",
        default_model="deepseek-chat",
        api_key_envs=("SIMING_LLM_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY"),
        endpoint_envs=("SIMING_LLM_DEEPSEEK_ENDPOINT", "DEEPSEEK_CHAT_COMPLETIONS_ENDPOINT"),
        model_envs=("SIMING_LLM_DEEPSEEK_MODEL", "DEEPSEEK_MODEL"),
        required_endpoint_marker="deepseek.com",
    ),
    "qwen": LiveProviderProofConfig(
        provider="qwen",
        display_name="Qwen",
        scenario="app_wiring_live_qwen_chain",
        title="App wiring live Qwen backend chain",
        default_endpoint="https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        default_model="qwen3.7-plus",
        api_key_envs=("SIMING_LLM_QWEN_API_KEY", "QWEN_API_KEY"),
        endpoint_envs=("SIMING_LLM_QWEN_ENDPOINT", "QWEN_CHAT_COMPLETIONS_ENDPOINT", "QWEN_BASE_URL"),
        model_envs=("SIMING_LLM_QWEN_MODEL", "QWEN_MODEL"),
    ),
    "seed_doubao": LiveProviderProofConfig(
        provider="seed_doubao",
        display_name="Seed/Doubao",
        scenario="app_wiring_live_seed_doubao_chain",
        title="App wiring live Seed/Doubao backend chain",
        default_endpoint="",
        default_model="doubao-seed-2.0-pro",
        api_key_envs=("SIMING_LLM_SEED_DOUBAO_API_KEY", "SEED_DOUBAO_API_KEY"),
        endpoint_envs=("SIMING_LLM_SEED_DOUBAO_ENDPOINT", "SEED_DOUBAO_CHAT_COMPLETIONS_ENDPOINT", "SEED_DOUBAO_BASE_URL"),
        model_envs=("SIMING_LLM_SEED_DOUBAO_MODEL", "SEED_DOUBAO_MODEL"),
    ),
}


def _print(line: str) -> None:
    print(line, flush=True)


def _header(scenario: str, *, provider: str, model: str | None = None) -> None:
    suffix = f" provider={provider}" + (f" model={model}" if model else "")
    _print(f"[司命后端主链证明 / Siming Backend Chain Proof] scenario={scenario}{suffix}")


def _print_failure(*, scenario: str, stage: str, expected: str, actual: str, hint: str) -> None:
    _print(f"[司命后端主链证明 / Siming Backend Chain Proof] scenario={scenario} result=FAIL")
    _print(f"失败阶段 / failed_stage={stage}")
    _print(f"期望 / expected={expected}")
    _print(f"实际 / actual={actual}")
    _print(f"提示 / hint={hint}")


def _make_visual_fact_event() -> AuthorityEvent:
    return AuthorityEvent.model_validate(
        {
            "event_id": VISUAL_EVENT_ID,
            "event_type": "visual_fact_event",
            "producer_ts": 300,
            "room_id": ROOM_ID,
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "source": {"layer": "L1", "system": "visual_fact", "actor_id": "char_c"},
            "routing": {"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["siming"]},
            "priority": "p2",
            "ttl": 5000,
            "durability": "replayable",
            "causation_id": VISUAL_CORRELATION_ID,
            "correlation_id": VISUAL_CORRELATION_ID,
            "payload": {
                "fact_type": "light_level_drop",
                "established_fact_id": ESTABLISHED_FACT_ID,
                "target_environment_id": "env_lamp",
            },
        }
    )


def _make_conversation_object_event() -> AuthorityEvent:
    return AuthorityEvent.model_validate(
        {
            "event_id": "conversation_candidate:310:char_a",
            "event_type": "conversation_resolution_event",
            "producer_ts": 310,
            "room_id": ROOM_ID,
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "source": {"layer": "L2", "system": "conversation_relation", "actor_id": "char_a"},
            "routing": {"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["siming"]},
            "priority": "p2",
            "ttl": 5000,
            "durability": "replayable",
            "causation_id": "conversation:310",
            "correlation_id": "conversation:310",
            "payload": {
                "actor_id": "char_a",
                "candidate_object_ids": ["obj_box"],
                "candidate_ref": "conversation:object:obj_box",
            },
        }
    )


def _make_unsupported_event() -> AuthorityEvent:
    return AuthorityEvent.model_validate(
        {
            "event_id": "state_machine_transition:ignored:1",
            "event_type": "state_machine_transition_event",
            "producer_ts": 305,
            "room_id": ROOM_ID,
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "source": {"layer": "L1", "system": "esm", "actor_id": None},
            "routing": {"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["presentation"]},
            "priority": "p2",
            "ttl": 5000,
            "durability": "replayable",
            "causation_id": "unsupported:305",
            "correlation_id": "unsupported:305",
            "payload": {"transition_type": "ignored_by_siming"},
        }
    )


def _make_candidate(**overrides: object) -> InterventionCandidate:
    payload: dict[str, object] = {
        "candidate_id": "cand:proof:1",
        "room_id": ROOM_ID,
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "causation_id": VISUAL_EVENT_ID,
        "correlation_id": VISUAL_CORRELATION_ID,
        "proposed_band": "fact_reveal",
        "target_actor_id": "char_b",
        "target_environment_id": "env_lamp",
        "established_fact_ids": [ESTABLISHED_FACT_ID],
        "explanation": "Reveal the established light drop.",
        "confidence": 0.72,
        "reason_tags": ["visibility_imbalance"],
        "source": "llm",
    }
    payload.update(overrides)
    return InterventionCandidate.model_validate(payload)


def _build_pipeline(
    llm_provider: object | None = None,
) -> tuple[InMemoryAuthorityEventBus, SimingAuditWriter, SimingEventPipeline]:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    pipeline = SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=SimingRuntime(llm_provider=llm_provider),  # type: ignore[arg-type]
        producer=SimingEventProducer(bus),
        audit_writer=audit_writer,
    )
    for event_type in SimingEventConsumer.ALLOWED_EVENT_TYPES:
        bus.subscribe(event_type, pipeline.handle_event)
    return bus, audit_writer, pipeline


def _event_types(bus: Any, *, room_id: str = ROOM_ID) -> list[str]:
    return [event.event_type for event in bus.list_events(room_id=room_id)]


def _dispatch_events(bus: Any, *, room_id: str = ROOM_ID) -> list[AuthorityEvent]:
    return [
        event
        for event in bus.list_events(room_id=room_id)
        if event.event_type.startswith("siming.") and event.event_type not in SIMING_NON_DISPATCH_EVENT_TYPES
    ]


def _chain_evidence(
    *,
    bus: Any,
    audit_writer: Any,
    pipeline: Any,
    correlation_id: str,
) -> dict[str, object]:
    events = bus.list_events(room_id=ROOM_ID)
    records = audit_writer.find_by_correlation(room_id=ROOM_ID, correlation_id=correlation_id)
    read_models = audit_writer.list_read_models(room_id=ROOM_ID)
    candidate_events = [
        event for event in events if event.correlation_id == correlation_id and event.event_type == "siming.intervention_candidate"
    ]
    decision_events = [
        event for event in events if event.correlation_id == correlation_id and event.event_type == "siming.intervention_decision"
    ]
    dispatch_events = [
        event for event in _dispatch_events(bus) if event.correlation_id == correlation_id
    ]
    observatory_messages = (
        pipeline.drain_observatory_messages()
        if hasattr(pipeline, "drain_observatory_messages")
        else []
    )
    stages = [
        str(message.get("payload", {}).get("stage"))
        for message in observatory_messages
        if message.get("message_type") == "siming_debug_event"
    ]
    return {
        "event_types": [event.event_type for event in events if event.room_id == ROOM_ID],
        "audit_records": records,
        "audit_statuses": [record.status for record in records],
        "read_models": read_models,
        "candidate_events": candidate_events,
        "decision_events": decision_events,
        "dispatch_events": dispatch_events,
        "debug_stages": stages,
    }


def _audit_reason(evidence: dict[str, object], status: str) -> str:
    records = list(evidence["audit_records"])  # type: ignore[arg-type]
    for record in records:
        if record.status != status:
            continue
        reason = " ".join(str(record.reason).split())
        return reason[:180] + ("..." if len(reason) > 180 else "")
    return ""


def _pass_entry(scenario: str, title: str, notes: str) -> dict[str, object]:
    return {"id": scenario, "status": "passed", "title": title, "notes": notes}


def _fail_entry(
    scenario: str,
    title: str,
    stage: str,
    expected: str,
    actual: str,
    hint: str,
) -> dict[str, object]:
    return {
        "id": scenario,
        "status": "failed",
        "title": title,
        "failed_stage": stage,
        "expected": expected,
        "actual": actual,
        "hint": hint,
        "notes": f"failed_stage={stage}; expected={expected}; actual={actual}; hint={hint}",
    }


def _validate_chain_success(
    *,
    scenario: str,
    title: str,
    evidence: dict[str, object],
    required_events: set[str],
) -> dict[str, object] | None:
    event_types = list(evidence["event_types"])  # type: ignore[arg-type]
    missing = sorted(required_events.difference(event_types))
    if missing:
        stage = "authority_event_publication"
        expected = ",".join(sorted(required_events))
        actual = ",".join(str(event_type) for event_type in event_types)
        hint = "SimingEventProducer did not publish the expected authority event family"
        _print_failure(scenario=scenario, stage=stage, expected=expected, actual=actual, hint=hint)
        return _fail_entry(scenario, title, stage, expected, actual, hint)

    audit_records = list(evidence["audit_records"])  # type: ignore[arg-type]
    read_models = list(evidence["read_models"])  # type: ignore[arg-type]
    if not audit_records or not read_models:
        stage = "audit_read_model"
        expected = "audit records and read model are present"
        actual = f"audit_count={len(audit_records)} read_model_count={len(read_models)}"
        hint = "SimingEventPipeline did not persist runtime evidence"
        _print_failure(scenario=scenario, stage=stage, expected=expected, actual=actual, hint=hint)
        return _fail_entry(scenario, title, stage, expected, actual, hint)
    return None


def _prove_component_success_scenario(
    *,
    scenario: str,
    title: str,
    llm_provider: object | None,
    provider_label: str,
) -> dict[str, object]:
    _header(scenario, provider=provider_label)
    started = time.perf_counter()
    bus, audit_writer, pipeline = _build_pipeline(llm_provider)
    event = _make_visual_fact_event()
    _print("[1/7] 权威事件已接收 / authority event accepted")
    _print(f"event_type={event.event_type} correlation_id={event.correlation_id}")

    try:
        bus.publish(event)
    except Exception as exc:
        stage = "runtime_pipeline"
        expected = "Siming backend chain completes"
        actual = str(exc)
        hint = "Inspect SimingEventConsumer, SimingRuntime, and SimingEventProducer"
        _print_failure(scenario=scenario, stage=stage, expected=expected, actual=actual, hint=hint)
        return _fail_entry(scenario, title, stage, expected, actual, hint)

    evidence = _chain_evidence(
        bus=bus,
        audit_writer=audit_writer,
        pipeline=pipeline,
        correlation_id=VISUAL_CORRELATION_ID,
    )
    event_types = list(evidence["event_types"])  # type: ignore[arg-type]
    audit_records = list(evidence["audit_records"])  # type: ignore[arg-type]
    read_models = list(evidence["read_models"])  # type: ignore[arg-type]
    debug_stages = list(evidence["debug_stages"])  # type: ignore[arg-type]

    _print("[2/7] 事件消费者已生成司命输入 / consumer produced Siming input")
    _print("input_count=1")
    _print("[3/7] 司命运行时已生成公平快照 / runtime emitted fairness snapshot")
    _print(f"fairness_snapshot={'siming.fairness_snapshot' in event_types} debug_stage={'fairness_snapshot' in debug_stages}")
    _print("[4/7] 司命候选与决策已生成 / Siming candidate and decision emitted")
    _print(f"candidate={'siming.intervention_candidate' in event_types} decision={'siming.intervention_decision' in event_types}")
    _print("[5/7] 事件生产者已发布 / producer published authority event")
    _print(f"published_events={','.join(str(event_type) for event_type in event_types)}")
    _print("[6/7] 审计与读模型已生成 / audit and read model present")
    _print(f"audit_count={len(audit_records)} read_model={'present' if read_models else 'missing'} latency_ms={int((time.perf_counter() - started) * 1000)}")

    required_events = {
        "visual_fact_event",
        "siming.fairness_snapshot",
        "siming.intervention_candidate",
        "siming.intervention_decision",
        "siming.visual_observability_request",
    }
    failure = _validate_chain_success(
        scenario=scenario,
        title=title,
        evidence=evidence,
        required_events=required_events,
    )
    if failure is not None:
        return failure

    _print("[7/7] 结果=通过 / result=PASS")
    return _pass_entry(
        scenario,
        title,
        f"published_events={','.join(str(event_type) for event_type in event_types)}; "
        f"audit_count={len(audit_records)}; read_model_count={len(read_models)}",
    )


def _prove_rejection_scenario() -> dict[str, object]:
    scenario = "component_fake_llm_rejection_chain"
    title = "Component fake LLM unsafe candidate rejection chain"
    _header(scenario, provider="fake")
    bus, audit_writer, pipeline = _build_pipeline(
        FakeSimingLlmCandidateProvider(
            [_make_candidate(candidate_id="cand:unsafe", established_fact_ids=["visual_fact:unknown"])]
        )
    )
    bus.publish(_make_visual_fact_event())
    evidence = _chain_evidence(
        bus=bus,
        audit_writer=audit_writer,
        pipeline=pipeline,
        correlation_id=VISUAL_CORRELATION_ID,
    )
    audit_statuses = list(evidence["audit_statuses"])  # type: ignore[arg-type]
    dispatch_events = list(evidence["dispatch_events"])  # type: ignore[arg-type]
    if "policy_rejected" in audit_statuses and not dispatch_events:
        _print("[1/1] 非法候选已被拒绝 / unsafe candidate rejected")
        _print("audit_status=policy_rejected unsafe_dispatch_published=False")
        _print("结果=通过 / result=PASS")
        return _pass_entry(scenario, title, "policy_rejected audit was recorded; unsafe dispatch was not published")

    stage = "policy_rejection"
    expected = "policy_rejected audit and no unsafe dispatch"
    actual = f"audit_statuses={audit_statuses} dispatch_count={len(dispatch_events)}"
    hint = "Unsafe LLM candidates must not publish authority actions"
    _print_failure(scenario=scenario, stage=stage, expected=expected, actual=actual, hint=hint)
    return _fail_entry(scenario, title, stage, expected, actual, hint)


def _prove_timeout_scenario() -> dict[str, object]:
    scenario = "component_fake_llm_timeout_chain"
    title = "Component fake LLM timeout degradation chain"
    _header(scenario, provider="fake")
    bus, audit_writer, pipeline = _build_pipeline(FakeSimingLlmCandidateProvider([], timeout=True))
    bus.publish(_make_visual_fact_event())
    evidence = _chain_evidence(
        bus=bus,
        audit_writer=audit_writer,
        pipeline=pipeline,
        correlation_id=VISUAL_CORRELATION_ID,
    )
    audit_statuses = list(evidence["audit_statuses"])  # type: ignore[arg-type]
    dispatch_events = list(evidence["dispatch_events"])  # type: ignore[arg-type]
    if "llm_timeout" in audit_statuses and not dispatch_events:
        _print("[1/1] 模型超时已降级 / provider timeout degraded")
        _print("audit_status=llm_timeout unsafe_dispatch_published=False")
        _print("结果=通过 / result=PASS")
        return _pass_entry(scenario, title, "llm_timeout audit was recorded; dispatch was not published")

    stage = "timeout_degradation"
    expected = "llm_timeout audit and no unvalidated authority action"
    actual = f"audit_statuses={audit_statuses} dispatch_count={len(dispatch_events)}"
    hint = "Provider timeout should produce auditable no-action behavior"
    _print_failure(scenario=scenario, stage=stage, expected=expected, actual=actual, hint=hint)
    return _fail_entry(scenario, title, stage, expected, actual, hint)


def _prove_input_family_guard() -> dict[str, object]:
    scenario = "component_input_family_guard"
    title = "Component input family guard"
    _header(scenario, provider="disabled")
    bus, audit_writer, pipeline = _build_pipeline()

    unsupported_event = _make_unsupported_event()
    bus.publish(unsupported_event)
    unsupported_siming_events = [
        event_type
        for event_type in _event_types(bus)
        if event_type.startswith("siming.")
    ]

    conversation_event = _make_conversation_object_event()
    bus.publish(conversation_event)
    evidence = _chain_evidence(
        bus=bus,
        audit_writer=audit_writer,
        pipeline=pipeline,
        correlation_id="conversation:310",
    )
    event_types = list(evidence["event_types"])  # type: ignore[arg-type]
    audit_records = list(evidence["audit_records"])  # type: ignore[arg-type]
    read_models = list(evidence["read_models"])  # type: ignore[arg-type]

    if unsupported_siming_events:
        stage = "unsupported_event_guard"
        expected = "unsupported event is ignored by SimingEventConsumer"
        actual = ",".join(unsupported_siming_events)
        hint = "SimingEventConsumer should only accept declared event families"
        _print_failure(scenario=scenario, stage=stage, expected=expected, actual=actual, hint=hint)
        return _fail_entry(scenario, title, stage, expected, actual, hint)

    required_events = {
        "conversation_resolution_event",
        "siming.fairness_snapshot",
        "siming.visual_observability_request",
    }
    failure = _validate_chain_success(
        scenario=scenario,
        title=title,
        evidence=evidence,
        required_events=required_events,
    )
    if failure is not None:
        return failure

    _print("[1/3] 非支持事件已忽略 / unsupported event ignored")
    _print(f"unsupported_event_type={unsupported_event.event_type}")
    _print("[2/3] 对象候选会话事件已进入司命 / object-only conversation event reached Siming")
    _print("event_type=conversation_resolution_event candidate_object_ids=1")
    _print("[3/3] 结果=通过 / result=PASS")
    return _pass_entry(
        scenario,
        title,
        f"published_events={','.join(str(event_type) for event_type in event_types)}; "
        f"audit_count={len(audit_records)}; read_model_count={len(read_models)}",
    )


def _first_env(*names: str) -> str | None:
    for name in names:
        value = os.getenv(name)
        if value:
            return value.strip()
    return None


def _matching_route(settings: Settings, provider: str) -> Any | None:
    for route in settings.siming_llm_routes:
        if route.enabled and route.provider == provider:
            return route
    return None


def _live_settings_for_provider(base_settings: Settings, config: LiveProviderProofConfig) -> Settings:
    route = _matching_route(base_settings, config.provider)
    uses_legacy_global = (
        bool(base_settings.siming_llm_provider_order)
        and base_settings.siming_llm_provider_order[0] == config.provider
    )
    api_key = _first_env(*config.api_key_envs)
    endpoint = _first_env(*config.endpoint_envs)
    model = _first_env(*config.model_envs)
    if route is not None:
        api_key = api_key or route.api_key
        endpoint = endpoint or route.endpoint
        model = model or route.model
    if uses_legacy_global:
        api_key = api_key or base_settings.siming_llm_api_key
        endpoint = endpoint or base_settings.siming_llm_endpoint
        model = model or base_settings.siming_llm_model
    return base_settings.model_copy(
        update={
            "siming_llm_mode": "http",
            "siming_llm_api_key": api_key,
            "siming_llm_endpoint": endpoint or config.default_endpoint,
            "siming_llm_model": model or config.default_model,
            "siming_llm_provider_order": [config.provider],
            "siming_llm_routes": [],
        }
    )


def _settings_failure(settings: Settings, config: LiveProviderProofConfig) -> tuple[str, str] | None:
    if settings.siming_llm_mode != "http":
        return "credential_check", f"SIMING_LLM_MODE={settings.siming_llm_mode}"
    if not settings.siming_llm_api_key:
        return "credential_check", f"missing API key for {config.provider}"
    provider_order = list(settings.siming_llm_provider_order)
    if not provider_order or provider_order[0] != config.provider:
        return "credential_check", f"provider_order={','.join(provider_order) or '<empty>'}"
    if not settings.siming_llm_endpoint:
        return "credential_check", f"missing endpoint for {config.provider}"
    if config.required_endpoint_marker and config.required_endpoint_marker not in settings.siming_llm_endpoint:
        return "credential_check", f"endpoint={settings.siming_llm_endpoint}"
    return None


def _import_app_main() -> Any:
    return importlib.import_module("app.main")


def _prove_app_wiring_live_provider_chain(config: LiveProviderProofConfig) -> dict[str, object]:
    scenario = config.scenario
    title = config.title
    app_main = _import_app_main()
    original_settings: Settings = app_main.settings
    settings = _live_settings_for_provider(original_settings, config)
    _header(scenario, provider=config.provider, model=settings.siming_llm_model)

    config_failure = _settings_failure(settings, config)
    if config_failure is not None:
        stage, actual = config_failure
        expected = f"API key, endpoint, and provider_order are configured for {config.provider}"
        hint = f"This architecture proof requires a real {config.display_name} call through app wiring"
        _print_failure(scenario=scenario, stage=stage, expected=expected, actual=actual, hint=hint)
        return _fail_entry(scenario, title, stage, expected, actual, hint)

    app_main.settings = settings
    app_main.reset_runtime_state()
    event = _make_visual_fact_event()
    _print("[1/8] 权威事件已接收 / authority event accepted")
    _print(f"event_type={event.event_type} correlation_id={event.correlation_id}")
    _print("[2/8] 真实应用装配已确认 / app wiring confirmed")
    _print(
        "provider_order=%s endpoint=%s"
        % (",".join(settings.siming_llm_provider_order), settings.siming_llm_endpoint)
    )
    _print(f"[3/8] {config.display_name} 请求已发送 / {config.display_name} request sent")
    _print(f"endpoint={settings.siming_llm_endpoint} timeout={settings.siming_llm_timeout_seconds}")

    started = time.perf_counter()
    try:
        app_main.authority_event_bus.publish(event)
    except Exception as exc:
        stage = f"{config.provider}_request"
        expected = f"{config.display_name} request completes through app-wired SimingRuntime"
        message = " ".join(str(exc).split())
        actual = exc.__class__.__name__ + (f": {message[:180]}" if message else "")
        hint = f"Check {config.display_name} endpoint, key validity, network, and provider error handling"
        _print_failure(scenario=scenario, stage=stage, expected=expected, actual=actual, hint=hint)
        app_main.settings = original_settings
        app_main.reset_runtime_state()
        return _fail_entry(scenario, title, stage, expected, actual, hint)

    latency_ms = int((time.perf_counter() - started) * 1000)
    evidence = _chain_evidence(
        bus=app_main.authority_event_bus,
        audit_writer=app_main.siming_audit_writer,
        pipeline=app_main.siming_event_pipeline,
        correlation_id=VISUAL_CORRELATION_ID,
    )
    audit_statuses = list(evidence["audit_statuses"])  # type: ignore[arg-type]
    candidate_events = list(evidence["candidate_events"])  # type: ignore[arg-type]
    decision_events = list(evidence["decision_events"])  # type: ignore[arg-type]
    dispatch_events = list(evidence["dispatch_events"])  # type: ignore[arg-type]
    audit_records = list(evidence["audit_records"])  # type: ignore[arg-type]
    read_models = list(evidence["read_models"])  # type: ignore[arg-type]

    if "llm_timeout" in audit_statuses:
        stage = f"{config.provider}_request_timeout"
        expected = f"{config.display_name} returns before timeout"
        reason = _audit_reason(evidence, "llm_timeout")
        actual = "audit_status=llm_timeout" + (f" reason={reason}" if reason else "")
        hint = "The live proof has no retry; increase timeout only if the model path is otherwise healthy"
        _print_failure(scenario=scenario, stage=stage, expected=expected, actual=actual, hint=hint)
        app_main.settings = original_settings
        app_main.reset_runtime_state()
        return _fail_entry(scenario, title, stage, expected, actual, hint)
    if "llm_invalid_output" in audit_statuses:
        stage = f"{config.provider}_response_validation"
        expected = "JSON object with explicit LLM candidates array"
        reason = _audit_reason(evidence, "llm_invalid_output")
        actual = "audit_status=llm_invalid_output" + (f" reason={reason}" if reason else "")
        hint = f"{config.display_name} returned a non-candidate shape or did not follow the Siming candidate contract"
        _print_failure(scenario=scenario, stage=stage, expected=expected, actual=actual, hint=hint)
        app_main.settings = original_settings
        app_main.reset_runtime_state()
        return _fail_entry(scenario, title, stage, expected, actual, hint)
    if "policy_rejected" in audit_statuses or "feasibility_rejected" in audit_statuses:
        stage = "policy_feasibility"
        expected = "candidate passes policy and feasibility"
        reason = _audit_reason(evidence, "policy_rejected") or _audit_reason(evidence, "feasibility_rejected")
        actual = f"audit_statuses={audit_statuses}" + (f" reason={reason}" if reason else "")
        hint = "The live candidate reached SimingRuntime but was not executable"
        _print_failure(scenario=scenario, stage=stage, expected=expected, actual=actual, hint=hint)
        app_main.settings = original_settings
        app_main.reset_runtime_state()
        return _fail_entry(scenario, title, stage, expected, actual, hint)
    if not candidate_events:
        stage = f"{config.provider}_response_validation"
        expected = "at least one validated LLM candidate event"
        actual = "candidate_count=0"
        hint = f"{config.display_name} did not produce a candidate that entered SimingRuntime"
        _print_failure(scenario=scenario, stage=stage, expected=expected, actual=actual, hint=hint)
        app_main.settings = original_settings
        app_main.reset_runtime_state()
        return _fail_entry(scenario, title, stage, expected, actual, hint)

    candidate_payload = candidate_events[0].payload
    source = str(candidate_payload.get("source", ""))
    if source != "llm":
        stage = f"{config.provider}_response_validation"
        expected = 'candidate source="llm"'
        actual = f"source={source or '<missing>'}"
        hint = f"{config.display_name} candidates must not rely on Pydantic defaults"
        _print_failure(scenario=scenario, stage=stage, expected=expected, actual=actual, hint=hint)
        app_main.settings = original_settings
        app_main.reset_runtime_state()
        return _fail_entry(scenario, title, stage, expected, actual, hint)

    _print(f"[4/8] {config.display_name} 响应已通过结构校验 / {config.display_name} response validated")
    _print(
        "candidate_count=%s candidate_id=%s source=%s confidence=%s established_fact_ids_count=%s latency_ms=%s"
        % (
            len(candidate_events),
            candidate_payload.get("candidate_id", ""),
            source,
            candidate_payload.get("confidence", ""),
            len(candidate_payload.get("established_fact_ids", []) or []),
            latency_ms,
        )
    )
    if not decision_events:
        stage = "siming_decision"
        expected = "Siming decision event is emitted"
        actual = "decision_count=0"
        hint = "Candidate validation passed but runtime did not emit a decision"
        _print_failure(scenario=scenario, stage=stage, expected=expected, actual=actual, hint=hint)
        app_main.settings = original_settings
        app_main.reset_runtime_state()
        return _fail_entry(scenario, title, stage, expected, actual, hint)

    _print("[5/8] 司命决策已生成 / Siming decision emitted")
    _print(f"selected_path=visual_fact_path intervention_band={candidate_payload.get('proposed_band', '')}")
    if not dispatch_events:
        stage = "authority_event_publication"
        expected = "SimingEventProducer publishes concrete siming.* dispatch authority event"
        actual = "dispatch_count=0"
        hint = "Producer did not publish the accepted candidate downstream"
        _print_failure(scenario=scenario, stage=stage, expected=expected, actual=actual, hint=hint)
        app_main.settings = original_settings
        app_main.reset_runtime_state()
        return _fail_entry(scenario, title, stage, expected, actual, hint)

    _print("[6/8] 事件生产者已发布 / producer published authority event")
    _print(f"event_type={dispatch_events[0].event_type}")
    if not audit_records or not read_models:
        stage = "audit_read_model"
        expected = "audit records and read model are present"
        actual = f"audit_count={len(audit_records)} read_model_count={len(read_models)}"
        hint = "SimingEventPipeline did not persist live proof evidence"
        _print_failure(scenario=scenario, stage=stage, expected=expected, actual=actual, hint=hint)
        app_main.settings = original_settings
        app_main.reset_runtime_state()
        return _fail_entry(scenario, title, stage, expected, actual, hint)

    _print("[7/8] 审计与读模型已生成 / audit and read model present")
    _print(f"audit_status={audit_records[0].status} read_model=present")
    _print("[8/8] 结果=通过 / result=PASS")
    app_main.settings = original_settings
    app_main.reset_runtime_state()
    return _pass_entry(
        scenario,
        title,
        f"candidate_count={len(candidate_events)}; dispatch_event_type={dispatch_events[0].event_type}; "
        f"audit_count={len(audit_records)}; read_model_count={len(read_models)}; latency_ms={latency_ms}",
    )


def _parse_live_providers(raw_values: list[str]) -> list[str]:
    values = raw_values or [os.getenv("SIMING_BACKEND_CHAIN_LIVE_PROVIDERS", "deepseek_chat")]
    providers: list[str] = []
    for raw_value in values:
        for provider in raw_value.split(","):
            normalized = provider.strip()
            if normalized:
                providers.append(normalized)
    return providers or ["deepseek_chat"]


def _write_report(entries: list[dict[str, object]]) -> dict[str, object]:
    project_root = repo_root()
    log_dir = verification_dir(project_root)
    overall = all(entry["status"] == "passed" for entry in entries)
    report: dict[str, object] = {
        "overall_siming_backend_chain_passed": overall,
        "results": entries,
        "artifacts": {
            "json": ".harness/verification/" + REPORT_JSON,
            "markdown": ".harness/verification/" + REPORT_MD,
        },
    }
    write_json(log_dir / REPORT_JSON, report)
    write_markdown(log_dir / REPORT_MD, "Siming Backend Chain Proof / 司命后端主链证明", report, "overall_siming_backend_chain_passed")
    return report


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--component-only",
        action="store_true",
        help="Run deterministic component-chain scenarios only; this is not the full live architecture proof.",
    )
    parser.add_argument("--live-deepseek", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument(
        "--live-provider",
        action="append",
        default=[],
        help=(
            "Require a live app-wiring proof for a provider. May be repeated or comma-separated. "
            "Supported: deepseek_chat, qwen, seed_doubao. Defaults to deepseek_chat."
        ),
    )
    args = parser.parse_args()

    entries = [
        _prove_component_success_scenario(
            scenario="component_fallback_visual_fact_chain",
            title="Component fallback visual fact backend chain",
            llm_provider=None,
            provider_label="disabled",
        ),
        _prove_component_success_scenario(
            scenario="component_fake_llm_candidate_chain",
            title="Component fake LLM candidate backend chain",
            llm_provider=FakeSimingLlmCandidateProvider([_make_candidate()]),
            provider_label="fake",
        ),
        _prove_rejection_scenario(),
        _prove_timeout_scenario(),
        _prove_input_family_guard(),
    ]
    if args.live_deepseek and "deepseek_chat" not in args.live_provider:
        args.live_provider.append("deepseek_chat")
    if not args.component_only or args.live_provider:
        for provider in _parse_live_providers(args.live_provider):
            config = LIVE_PROVIDER_CONFIGS.get(provider)
            if config is None:
                entries.append(
                    _fail_entry(
                        f"app_wiring_live_{provider}_chain",
                        f"App wiring live {provider} backend chain",
                        "provider_selection",
                        "provider is one of deepseek_chat,qwen,seed_doubao",
                        f"provider={provider}",
                        "Use --live-provider with a registered Siming live provider",
                    )
                )
                continue
            entries.append(_prove_app_wiring_live_provider_chain(config))

    report = _write_report(entries)
    _print(f"siming_backend_chain_report_json={report['artifacts']['json']}")  # type: ignore[index]
    _print(f"siming_backend_chain_report_md={report['artifacts']['markdown']}")  # type: ignore[index]
    _print(f"overall_siming_backend_chain_passed={report['overall_siming_backend_chain_passed']}")
    return 0 if report["overall_siming_backend_chain_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
