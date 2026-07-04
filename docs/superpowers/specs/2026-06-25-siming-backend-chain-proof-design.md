# Siming Backend Chain Proof Design

Status: approved

## Problem

The current project can verify Siming through focused backend tests and the `phase1-slice` runtime profile, but the strongest runtime evidence still mixes backend truth with Godot-facing projection evidence.

We need an architecture-level proof that Siming is genuinely operating inside the backend authority-event chain, without relying on Godot, scene probes, frontend projection, or `siming_output` consumption.

The proof must be readable from a console because this is meant to answer a direct engineering question: did the backend Siming chain really run, where did it run, and which stage failed if it did not?

## Goal

Add a backend-only Siming verification surface that proves both:

- the Siming backend component chain behaves correctly when assembled directly
- the real `backend/app/main.py` app wiring can call real DeepSeek and complete the same backend authority-event chain
- additive live provider proofs for Qwen and Seed/Doubao can run through the same app-wiring chain without replacing the DeepSeek proof

The proof chain is:

```text
AuthorityEvent
-> SimingEventConsumer
-> SimingRuntime.tick()
-> DeepSeek, Qwen, Seed/Doubao, or deterministic LLM candidate provider
-> policy / feasibility
-> SimingEventProducer
-> InMemoryAuthorityEventBus
-> audit / read model / debug evidence
```

Console output is bilingual Chinese / English. JSON report keys stay stable English for harness processing.

## Non-Goals

- Do not start Godot.
- Do not depend on WebSocket client behavior.
- Do not use frontend `siming_output` projection as proof.
- Do not treat a successful HTTP call to DeepSeek as sufficient proof.
- Do not print API keys, full prompts, full responses, or full candidate explanations.
- Do not include this live proof in `harness.py --profile all`.
- Do not let the verification script create an alternate Siming runtime path for the app-wiring proof.
- Do not replace the DeepSeek live proof when adding Qwen or Seed/Doubao; multi-provider proof is additive.

## Existing Context

Relevant existing components:

- `backend/app/main.py`
- `backend/app/config.py`
- `backend/app/services/siming_event_consumer.py`
- `backend/app/services/siming_runtime.py`
- `backend/app/services/siming_event_producer.py`
- `backend/app/services/siming_event_pipeline.py`
- `backend/app/services/authority_event_bus.py`
- `backend/app/services/siming_llm_provider.py`
- `scripts/verification/harness.py`
- `.harness/profiles/phase1-slice.json`

Related existing tests:

- `backend/tests/test_siming_event_pipeline.py`
- `backend/tests/test_siming_llm_runtime.py`
- `backend/tests/test_siming_llm_provider_config.py`
- `backend/tests/test_siming_llm_boundary_static.py`

There is already local draft implementation from the interrupted implementation attempt:

- `.harness/profiles/siming-backend-chain.json`
- `scripts/verification/verify_siming_backend_chain.py`
- `scripts/verification/tests/test_siming_backend_chain_verify.py`

Those files are implementation draft until this design is reviewed. Future implementation should adjust them to this spec rather than assuming the draft is final.

## Verification Entry

Add a direct script:

```powershell
python scripts/verification/verify_siming_backend_chain.py
```

Add a harness profile:

```powershell
python scripts/verification/harness.py --profile siming-backend-chain
```

The profile must be explicit-only:

```json
{
  "name": "siming-backend-chain",
  "include_in_all": false
}
```

`harness.py --profile all` must not run profiles with `include_in_all=false`.

## Configuration

The live app-wiring proof uses the real app settings loaded by `backend/app/config.py`; it must not read only `os.environ` because project `.env` values are loaded into `settings`.

Required project configuration:

```env
SIMING_LLM_MODE=http
SIMING_LLM_PROVIDER_ORDER=deepseek_chat
SIMING_LLM_API_KEY=<real DeepSeek key>
SIMING_LLM_ENDPOINT=https://api.deepseek.com/chat/completions
SIMING_LLM_MODEL=deepseek-chat
SIMING_LLM_TIMEOUT_SECONDS=8.0
```

`SIMING_LLM_API_KEY` is the only accepted credential variable for this proof. Do not fall back to `DEEPSEEK_API_KEY`; that belongs to other model surfaces and would blur the Siming configuration boundary.

`SIMING_LLM_PROVIDER_ORDER` is a comma-separated list:

```env
SIMING_LLM_PROVIDER_ORDER=deepseek_chat,openai_responses
```

For this proof, the first provider must be `deepseek_chat`. Missing key, disabled mode, wrong provider order, or non-DeepSeek endpoint is a failed credential/configuration check.

## Architecture

### Component-Chain Proof

The deterministic component-chain proof directly assembles:

```text
InMemoryAuthorityEventBus
-> SimingEventPipeline
   -> SimingEventConsumer
   -> SimingRuntime
   -> SimingEventProducer
   -> SimingAuditWriter
```

It publishes real `AuthorityEvent` objects to the bus. It must not call private helper methods on `SimingRuntime`.

This layer proves component behavior with disabled or fake providers.

### App-Wiring Live Proof

The app-wiring proof imports `backend/app/main.py`, calls `reset_runtime_state()`, and uses the real globals assembled by the app:

```text
app.main.authority_event_bus
app.main.siming_event_pipeline
app.main.siming_audit_writer
app.main.settings
```

It publishes the proof `AuthorityEvent` through `app.main.authority_event_bus`.

The real DeepSeek call must happen in this app-wiring proof, not only in a hand-built test pipeline. A passing live proof means:

```text
real app config
-> real app wiring
-> real DeepSeek provider
-> SimingRuntime
-> policy / feasibility
-> SimingEventProducer
-> AuthorityEventBus
-> audit / read model
```

## Output Contract

Console output is bilingual and stage-oriented:

```text
[司命后端主链证明 / Siming Backend Chain Proof] scenario=app_wiring_live_deepseek_chain provider=deepseek_chat model=deepseek-chat

[1/8] 权威事件已接收 / authority event accepted
event_type=visual_fact_event correlation_id=visual_fact:300

[2/8] 真实应用装配已确认 / app wiring confirmed
provider_order=deepseek_chat endpoint=https://api.deepseek.com/chat/completions

[3/8] DeepSeek 请求已发送 / DeepSeek request sent
endpoint=https://api.deepseek.com/chat/completions timeout=8.0

[4/8] DeepSeek 响应已通过结构校验 / DeepSeek response validated
candidate_count=1 source=llm confidence=0.72 latency_ms=842

[5/8] 司命决策已生成 / Siming decision emitted
selected_path=visual_fact_path intervention_band=fact_reveal

[6/8] 事件生产者已发布 / producer published authority event
event_type=siming.visual_observability_request

[7/8] 审计与读模型已生成 / audit and read model present
audit_status=recorded read_model=present

[8/8] 结果=通过 / result=PASS
```

Failure output identifies the architecture stage:

```text
[司命后端主链证明 / Siming Backend Chain Proof] scenario=app_wiring_live_deepseek_chain result=FAIL
失败阶段 / failed_stage=deepseek_response_validation
期望 / expected=JSON object with explicit LLM candidates array
实际 / actual=missing field: source
提示 / hint=DeepSeek returned a non-candidate shape or did not follow the Siming candidate contract
```

When key or configuration is missing, the result is `FAIL`, not `SKIP`:

```text
[司命后端主链证明 / Siming Backend Chain Proof] scenario=app_wiring_live_deepseek_chain result=FAIL
失败阶段 / failed_stage=credential_check
期望 / expected=SIMING_LLM_API_KEY is set and provider_order starts with deepseek_chat
实际 / actual=missing SIMING_LLM_API_KEY
提示 / hint=This architecture proof requires a real DeepSeek call through app wiring
```

## Scenarios

### `component_fallback_visual_fact_chain`

Purpose: prove the backend Siming component chain works without model assistance.

Expected evidence:

- `visual_fact_event` enters `InMemoryAuthorityEventBus`
- `SimingEventConsumer` produces one `SimingInput`
- `SimingRuntime` emits fairness, candidate, decision, and dispatch outputs
- `SimingEventProducer` publishes concrete `siming.*` authority events
- `SimingAuditWriter` records audit evidence
- read model evidence is present

### `component_fake_llm_candidate_chain`

Purpose: prove a deterministic fake LLM candidate flows through the real Siming component chain.

Expected evidence:

- fake provider returns canonical `InterventionCandidate`
- runtime emits candidate / decision / dispatch
- output is published by `SimingEventProducer`
- no direct provider-to-bus path exists

### `component_fake_llm_rejection_chain`

Purpose: prove unsafe LLM candidates do not bypass policy.

Expected evidence:

- fake provider returns a candidate referencing an unknown fact
- policy rejects it
- audit contains `policy_rejected`
- no unsafe downstream authority action is published

### `component_fake_llm_timeout_chain`

Purpose: prove provider timeout degrades into auditable no-action behavior.

Expected evidence:

- provider raises timeout
- audit contains `llm_timeout`
- no unvalidated authority action is published

### `component_input_family_guard`

Purpose: prove the proof covers the important backend input boundaries without becoming a full behavior matrix.

Minimum evidence:

- unsupported event is ignored
- object-only `conversation_resolution_event` reaches current visual observability behavior
- accepted Siming event families still go through `SimingEventConsumer`

This is a guard, not a full semantic regression suite for every allowed input family.

### `app_wiring_live_deepseek_chain`

Purpose: prove the real app wiring can call real DeepSeek and complete the backend authority-event chain.

Expected evidence:

- `app.main.settings.siming_llm_mode == "http"`
- `app.main.settings.siming_llm_provider_order[0] == "deepseek_chat"`
- `app.main.settings.siming_llm_api_key` exists
- real app `authority_event_bus` receives the proof `visual_fact_event`
- real DeepSeek returns JSON that validates into explicit canonical LLM candidates
- accepted candidate passes policy and feasibility
- `SimingEventProducer` publishes a concrete `siming.*` authority event
- audit and read model evidence are present

Live DeepSeek success is not HTTP 200. It is success only if the full app-wiring backend chain produces valid authority-event and audit evidence.

## DeepSeek Candidate Contract

The `deepseek_chat` provider prompt should explicitly request a JSON object with a `candidates` array. Each candidate must explicitly include:

```text
candidate_id
room_id
scene_id
zone_id
causation_id
correlation_id
proposed_band
target_actor_id or target_environment_id
established_fact_ids
explanation
confidence
reason_tags
source="llm"
```

The production `deepseek_chat` provider should reject missing key fields before candidates enter `SimingRuntime`. This strictness is scoped to `deepseek_chat` provider output. It prevents Pydantic defaults from silently converting missing model output into apparently valid candidates.

The live proof should print only candidate summaries:

```text
candidate_id
candidate_count
source
proposed_band
target_actor_id / target_environment_id
established_fact_ids_count
confidence
latency_ms
```

It must not print full prompt text, full response text, full explanation, or API key.

## Retry Policy

The live DeepSeek proof does not retry.

One malformed response, timeout, policy rejection, feasibility rejection, missing authority event, or missing audit/read-model evidence fails the live proof. Retry behavior belongs in production provider design, not in this proof.

## Artifacts

Generated files:

```text
.harness/verification/siming-backend-chain-report.json
.harness/verification/siming-backend-chain-report.md
```

Suggested JSON shape:

```json
{
  "overall_siming_backend_chain_passed": true,
  "results": [
    {
      "id": "app_wiring_live_deepseek_chain",
      "status": "passed",
      "title": "App wiring live DeepSeek backend chain",
      "notes": "published_events=..."
    }
  ],
  "artifacts": {
    "json": ".harness/verification/siming-backend-chain-report.json",
    "markdown": ".harness/verification/siming-backend-chain-report.md"
  }
}
```

Stable English keys are intentional. The console and Markdown report may include bilingual labels.

## Error Handling

The script returns non-zero when any required scenario fails.

Required failure examples:

- missing `SIMING_LLM_API_KEY`
- `SIMING_LLM_MODE` is not `http`
- `SIMING_LLM_PROVIDER_ORDER` does not start with `deepseek_chat`
- DeepSeek request timeout
- malformed DeepSeek JSON
- DeepSeek candidate missing explicit key fields
- DeepSeek candidate `source` is not `llm`
- policy rejection in the live success scenario
- feasibility rejection in the live success scenario
- missing `siming.*` authority event
- missing audit or read model evidence

## Test Strategy

Use TDD for implementation.

Script-level tests should prove:

- profile `siming-backend-chain` is registered
- profile has `include_in_all=false`
- `harness.py --profile all` excludes `siming-backend-chain`
- direct script emits bilingual console output
- deterministic component-chain scenarios write JSON report
- missing live DeepSeek credentials fail with bilingual `credential_check`
- app-wiring proof uses real app settings rather than raw `os.environ`
- DeepSeek output missing explicit fields is rejected

Verification commands:

```powershell
python -m pytest -q scripts/verification/tests/test_siming_backend_chain_verify.py
python -m pytest -q backend/tests/test_siming_llm_provider_config.py
python scripts/verification/verify_siming_backend_chain.py
python scripts/verification/harness.py --profile siming-backend-chain
```

## Acceptance Criteria

- `siming-backend-chain` profile exists and is loadable by harness registry.
- `siming-backend-chain` does not run under `harness.py --profile all`.
- Direct script works without Godot.
- Direct script produces bilingual console proof.
- Deterministic component scenarios prove backend authority-event chain behavior.
- App-wiring live DeepSeek scenario is mandatory for profile success.
- Missing credentials are failure, not skip.
- DeepSeek output must include explicit LLM candidate fields.
- No secret or full prompt/response is printed.
- JSON and Markdown evidence are written under `.harness/verification/`.
- Existing `phase1-slice` remains the Godot-inclusive runtime proof and is not replaced by this profile.

## Review Notes

This spec intentionally separates backend architecture proof from Godot runtime proof. The backend proof answers whether Siming is structurally alive in the backend authority-event chain and whether the real app wiring can call DeepSeek through that chain. It does not claim that Godot consumed or displayed the result.
