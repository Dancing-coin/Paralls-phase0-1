"""混合基准的原provider调用证据与单次transport故障，不保存提示词或模型正文。"""
from contextlib import contextmanager
import hashlib
import json
import os
from threading import Lock, get_ident, local
from time import perf_counter
from urllib.parse import urlparse


def _hash(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
            default=lambda item: item.model_dump(mode="json")).encode("utf-8")
    return hashlib.sha256(value).hexdigest()


class MixedProviderProbe:
    def __init__(self, record):
        self.record = record
        self.local, self.lock = local(), Lock()
        self.active = self.peak_active = self.ordinal = 0
        self.timeout_key = None

    def arm_timeout(self, key):
        with self.lock:
            if self.timeout_key is not None:
                raise ValueError("mixed_provider_previous_fault_not_consumed")
            self.timeout_key = key
        self.record(dict(type="provider_timeout_armed", key=key, at=perf_counter()))

    @contextmanager
    def call(self, family, stage, request, *, source_event_ids=()):
        request_hash = _hash(request)
        with self.lock:
            self.ordinal += 1
            ordinal = self.ordinal
            self.active += 1
            self.peak_active = max(self.peak_active, self.active)
        row = dict(type="provider_result", ordinal=ordinal, family=family, stage=stage, thread_id=get_ident(), process_id=os.getpid(),
            started_at=perf_counter(), request_sha256=request_hash, source_event_ids=list(source_event_ids),
            transport_attempted=False, transport_succeeded=False, fallback_used=False, validated=False,
            fault_key=None, error=None)
        previous = getattr(self.local, "call", None)
        self.local.call = row
        try:
            yield row
        except GeneratorExit:
            # 消费者取得completed后关闭生成器是正常结束；取消未完成的流仍留下失败证据。
            if not row["validated"]:
                row["error"] = "GeneratorExit"
            raise
        except BaseException as error:
            row["error"] = type(error).__name__
            raise
        finally:
            self.local.call = previous
            row["finished_at"] = perf_counter()
            row["qualified_success"] = (row["validated"] and row["transport_attempted"] and row["transport_succeeded"]
                and not row["fallback_used"] and row["fault_key"] is None and row["error"] is None)
            with self.lock:
                self.active -= 1
            self.record(row)

    def install(self, stack):
        from unittest.mock import patch
        from app.character_agent.gateway.model_gateway import CharacterModelGateway
        from app.character_agent.gateway import model_provider
        from app.character_agent.gateway.model_provider import CharacterModelProvider
        from app.services.siming_llm_provider import DisabledSimingLlmCandidateProvider, HttpSimingLlmCandidateProvider, SimingLlmProviderTimeout

        complete, stream = CharacterModelGateway.complete_prepared_request, CharacterModelGateway.stream_prepared_request
        evidence = CharacterModelProvider._record_evidence
        def character_complete(gateway, request_json):
            request = gateway._restore_prepared_request(request_json)
            with self.call("character", request["task_kind"], request_json) as row:
                result = complete(gateway, request_json)
                row.update(validated=True, output_sha256=_hash(result))
                return result
        def character_stream(gateway, request_json, *, cancelled):
            with self.call("character", "dialogue_generation", request_json) as row:
                provider = gateway._provider
                request = gateway._restore_prepared_request(request_json)
                row.update(provider_kind=request.get("route", {}).get("provider_kind", provider._provider_kind),
                    model=provider._model_name, endpoint_host=urlparse(provider._endpoint_url).hostname)
                for event in stream(gateway, request_json, cancelled=cancelled):
                    if event["event"] == "completed":
                        row.update(validated=True, output_sha256=_hash(event["output"]))
                    yield event
        def character_evidence(provider, **kwargs):
            evidence(provider, **kwargs)
            row = getattr(self.local, "call", None)
            if row is not None and row["family"] == "character":
                # 从本线程这次实际调用的参数读取，不能读共享provider可能已被别的线程覆盖的last_call_evidence。
                row.update({name: kwargs.get(name, False) for name in ("transport_succeeded", "fallback_used")})
                row["transport_attempted"] = row["transport_attempted"] or kwargs.get("transport_attempted", False)
                row.update(provider_kind=kwargs["provider_kind"], model=provider._model_name,
                    endpoint_host=urlparse(provider._endpoint_url).hostname)
        urlopen = model_provider.urlopen
        def character_transport(*args, **kwargs):
            row = getattr(self.local, "call", None)
            if row is not None and row["family"] == "character":
                # 只观察 Character 实际 HTTP 入口；503/超时/流解析失败也不能记成未尝试。
                row["transport_attempted"] = True
            return urlopen(*args, **kwargs)
        stack.enter_context(patch.object(model_provider, "urlopen", character_transport))
        stack.enter_context(patch.object(CharacterModelGateway, "complete_prepared_request", character_complete))
        stack.enter_context(patch.object(CharacterModelGateway, "stream_prepared_request", character_stream))
        stack.enter_context(patch.object(CharacterModelProvider, "_record_evidence", character_evidence))

        post = HttpSimingLlmCandidateProvider._post_json
        def siming_post(provider, payload):
            row = getattr(self.local, "call", None)
            with self.lock:
                fault, self.timeout_key = self.timeout_key, None
            if row is None or row["family"] != "siming":
                raise ValueError("mixed_siming_transport_without_call")
            row.update(fault_key=fault, transport_request_sha256=_hash(payload),
                provider_kind=provider._provider_name, model=provider._model,
                endpoint_host=urlparse(provider._endpoint).hostname)
            if fault is not None:
                self.record(dict(type="provider_timeout_injected", key=fault, at=perf_counter(), ordinal=row["ordinal"]))
                raise SimingLlmProviderTimeout("mixed controlled transport timeout")
            row["transport_attempted"] = True
            result = post(provider, payload)
            row.update(transport_succeeded=True, transport_response_sha256=result[3])
            return result
        stack.enter_context(patch.object(HttpSimingLlmCandidateProvider, "_post_json", siming_post))
        def wrap_siming(original, stage):
            def invoke(provider, **kwargs):
                events = kwargs.get("recent_events", [])
                with self.call("siming", stage, kwargs, source_event_ids=[event.event_id for event in events]) as row:
                    if isinstance(provider, DisabledSimingLlmCandidateProvider):
                        row['provider_kind'] = 'disabled'
                    result = original(provider, **kwargs)
                    row.update(validated=True, output_sha256=_hash(result))
                    return result
            return invoke
        for provider_type in (HttpSimingLlmCandidateProvider, DisabledSimingLlmCandidateProvider):
            for method, stage in (("generate_candidates", "candidate"), ("generate_adaptive_bridge_proposals", "adaptive")):
                stack.enter_context(patch.object(provider_type, method,
                    wrap_siming(getattr(provider_type, method), stage)))
