# Complete LLM Integration Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** close real-provider execution for character dialogue, character `L2`, character `L3`, and Siming DeepSeek while preserving existing gateway, validator, runtime, event-bus, fallback, and readiness boundaries.

**Architecture:** make `CHARACTER_MODEL_*` the sole character runtime configuration contract, keep Siming on unmodified `SIMING_LLM_*` settings, and add separate explicit-only live proofs. A closure aggregator accepts readiness plus fresh Character and Siming artifacts from one run ID; it never upgrades readiness evidence into live evidence.

**Tech Stack:** Python 3.13, FastAPI backend services, Pydantic settings/models, `urllib` character transport, `httpx` Siming transport, pytest, repository harness profiles, JSON/Markdown verification artifacts.

Status: completed and verified on 2026-07-23

## 2026-07-23 Closure Execution Evidence

Run ID: `5ff195c7-f448-4f58-bffc-a768e0a13d00`

Implemented closure surfaces:

- Character runtime configuration is canonicalized to `CHARACTER_MODEL_*`; provider aliases are not consumed by the Character runtime.
- Character calls continue through `CharacterModelGateway -> CharacterModelProvider -> CharacterStructuredOutputValidator`.
- Character dialogue, `L2`, and `L3` live proof is explicit-only and records redacted transport evidence.
- Siming live proof validates loaded `app.main.settings`, resets the real app runtime state, and publishes through `SimingRuntime.tick() -> SimingEventProducer -> AuthorityEventBus`.
- Readiness evidence is run-ID-tagged but remains non-live evidence; closure aggregation requires separate live artifacts.
- Tracked secret guard checks configured Character and Siming secrets without printing secret values.

Verification evidence:

- `python -m pytest -q backend/tests/test_config_runtime_modes.py backend/tests/test_character_model_provider.py backend/tests/test_character_model_provider_readiness.py backend/tests/test_character_model_gateway.py` -> `70 passed`
- `python -m pytest -q backend/tests/test_character_agent_l2_reasoning.py backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_dialogue_mind_core_integration.py backend/tests/test_character_service.py` -> `79 passed`
- `python -m pytest -q backend/tests/test_siming_llm_provider_config.py backend/tests/test_siming_llm_runtime.py backend/tests/test_siming_event_pipeline.py backend/tests/test_siming_event_producer.py` -> `55 passed`
- `python -m pytest -q scripts/verification/tests/test_character_model_live_verify.py scripts/verification/tests/test_siming_backend_chain_verify.py scripts/verification/tests/test_llm_integration_closure_verify.py scripts/verification/tests/test_tracked_model_secrets.py` -> `16 passed`
- `python -m pytest -q scripts/verification/tests/test_harness_registry.py scripts/verification/tests/test_harness_runner.py` -> `27 passed`
- `python -m pytest -v` -> `1485 passed`
- `python scripts/verification/harness.py --profile all` -> archived `overall_harness_passed=true` in `.harness/verification/runs/run-20260723-195922-642353/harness-run-report.json`; `phase1-slice` and `mainline-unified-runtime` each passed on harness retry after a transient Godot probe attempt.
- `$env:LLM_CLOSURE_RUN_ID='5ff195c7-f448-4f58-bffc-a768e0a13d00'; python scripts/verification/harness.py --profile model-provider-readiness` -> `model_provider_readiness_overall_passed=True`; Character and Siming rows are `http_configured_unverified`.
- `$env:LLM_CLOSURE_RUN_ID='5ff195c7-f448-4f58-bffc-a768e0a13d00'; python scripts/verification/harness.py --profile character-model-live` -> `overall_character_model_live_passed=True`; `dialogue_live_deepseek`, `l2_live_deepseek`, and `l3_live_deepseek` passed with `fallback_used=false`.
- `$env:LLM_CLOSURE_RUN_ID='5ff195c7-f448-4f58-bffc-a768e0a13d00'; python scripts/verification/harness.py --profile siming-backend-chain` -> `overall_siming_backend_chain_passed=True`; `app_wiring_live_deepseek_chain` passed with `endpoint_host=api.deepseek.com`, `timeout_seconds=60.0`, `retry_count=0`, `latency_ms=7341`.
- `$env:LLM_CLOSURE_RUN_ID='5ff195c7-f448-4f58-bffc-a768e0a13d00'; python scripts/verification/harness.py --profile llm-integration-closure` -> `overall_llm_integration_closure_passed=True`; all four live closure claims passed and `readiness_is_live_proof=false`.
- `python scripts/verification/check_tracked_model_secrets.py` -> `tracked_model_secret_offender_count=0`
- `python scripts/verification/harness.py --profile docs` -> `overall_docs_passed=True`

Primary artifacts:

- `.harness/verification/model-provider-readiness-report.json`
- `.harness/verification/character-model-live-report.json`
- `.harness/verification/siming-backend-chain-report.json`
- `.harness/verification/llm-integration-closure-report.json`
- `.harness/verification/runs/run-20260723-195922-642353/harness-run-report.json`

Completion matrix status:

| Claim | Status | Evidence |
| --- | --- | --- |
| Character dialogue real provider | completed and verified | `character-model-live-report.json`: `dialogue_live_deepseek=passed`, `fallback_used=false` |
| Character L2 real provider | completed and verified | `character-model-live-report.json`: `l2_live_deepseek=passed`, typed consumer passed |
| Character L3 real provider | completed and verified | `character-model-live-report.json`: `l3_live_deepseek=passed`, local viability/consumer passed |
| Siming DeepSeek app wiring | completed and verified | `siming-backend-chain-report.json`: `app_wiring_live_deepseek_chain=passed` |
| Readiness/live separation | completed and verified | `model-provider-readiness-report.json` plus closure report; `readiness_is_live_proof=false` |
| Aggregate closure | completed and verified | `llm-integration-closure-report.json`: all four claims passed under the same run ID |
| Regression | completed and verified | full pytest `1485 passed`; harness all archived green |
| Secret safety | completed and verified | `tracked_model_secret_offender_count=0` |

Remaining risks:

- Explicit live profiles depend on external DeepSeek availability, account access, and network latency.
- The Godot `phase1-slice` and `mainline-unified-runtime` profiles can have transient first-attempt probe timing failures in full `all`; the harness now records retry attempts and requires a successful retry before passing.

---

## File Structure

Create:

- `scripts/verification/verify_character_model_live.py`: three-scenario Character real-provider proof.
- `scripts/verification/tests/test_character_model_live_verify.py`: verifier and explicit-profile regression tests.
- `.harness/profiles/character-model-live.json`: explicit-only Character live profile.
- `scripts/verification/verify_llm_integration_closure.py`: fresh-evidence closure aggregator.
- `scripts/verification/tests/test_llm_integration_closure_verify.py`: aggregator false-green regressions.
- `.harness/profiles/llm-integration-closure.json`: explicit-only aggregation profile.
- `scripts/verification/check_tracked_model_secrets.py`: tracked-file credential leak guard.
- `scripts/verification/tests/test_tracked_model_secrets.py`: leak-guard tests.

Modify:

- `backend/app/config.py`: strict provider-correlated configuration and route-mode semantics.
- `backend/app/character_agent/gateway/model_provider.py`: no implicit provider aliases and redacted call evidence.
- `backend/app/character_agent/gateway/prompt_policy.py`: task-specific token budgets and strict output instructions.
- `backend/app/character_agent/gateway/output_validator.py`: executable dialogue/L2/L3 semantic validation.
- `backend/app/world_runtime/model_provider_readiness.py`: route-aware, run-ID-tagged readiness evidence.
- `scripts/verification/verify_model_provider_readiness.py`: validate and emit the run ID.
- `scripts/verification/verify_siming_backend_chain.py`: use unmodified real app settings.
- `scripts/verification/tests/test_siming_backend_chain_verify.py`: prevent synthesized-settings regression.
- `backend/tests/test_config_runtime_modes.py`
- `backend/tests/test_character_model_provider.py`
- `backend/tests/test_character_model_provider_readiness.py`
- `backend/tests/test_character_model_gateway.py`
- `backend/tests/test_siming_llm_provider_config.py`
- `backend/tests/test_siming_llm_runtime.py`
- `.env.example`
- `docs/harness.md`
- `docs/INDEX.md`
- historical LLM specs/plans named by the approved closure spec.

No task may add a second Character model entry point, call a Siming provider outside `SimingRuntime.tick()`, or publish Siming authority events outside `SimingEventProducer`.

---

## Task 0: Record External Inputs And Start One Closure Run

This task changes no tracked file.

### 中文要求清单

执行本计划前，你需要先提供或确认下面这些信息。不要把真实 `API key` 直接写进文档；你可以在对话里说明“已提供”，或者只给变量名和是否可用。

#### 一、角色大模型接入

- [ ] 本轮角色链路最终使用哪家 provider
  - `DeepSeek`
  - `Qwen`
  - `Seed / Doubao`
- [ ] 本轮是否以 `DeepSeek` 作为角色链路的首个闭环目标
- [ ] 是否已有可用的角色模型 `API key`
- [ ] 角色模型 `endpoint`
- [ ] 角色模型 `model` 名称
- [ ] 角色模型超时时间是否接受先按 `30.0` 秒执行
- [ ] 是否要求默认运行时直接走在线模型，而不是继续使用 `stub/local`
- [ ] 是否允许把当前机器已有的 `DEEPSEEK_*` 迁移或映射成 `CHARACTER_MODEL_*`

如果角色链路使用 DeepSeek，至少要确认以下变量能否提供：

- [ ] `CHARACTER_MODEL_PROVIDER_KIND`
- [ ] `CHARACTER_MODEL_API_KEY`
- [ ] `CHARACTER_MODEL_ENDPOINT`
- [ ] `CHARACTER_MODEL_MODEL`
- [ ] `CHARACTER_MODEL_TIMEOUT_SECONDS`
- [ ] `DIALOGUE_MODE`

#### 二、司命大模型接入

- [ ] 本轮司命链路是否也使用 `DeepSeek`
- [ ] 是否允许司命本轮先只做 `deepseek_chat` 单路由闭环
- [ ] 是否已有可用的 `SIMING_LLM_API_KEY`
- [ ] 司命模型 `endpoint`
- [ ] 司命模型 `model` 名称
- [ ] 司命 live proof 的超时时间是否接受先按 `60.0` 秒执行
- [ ] 是否计划本轮同时做 `Qwen` / `Seed / Doubao`，还是先只做 DeepSeek
- [ ] 是否使用 `SIMING_LLM_ROUTES_JSON`
- [ ] 如果不用 route mode，是否接受先走单一 `SIMING_LLM_*` 配置

如果司命链路使用 DeepSeek，至少要确认以下变量能否提供：

- [ ] `SIMING_LLM_MODE`
- [ ] `SIMING_LLM_PROVIDER_ORDER`
- [ ] `SIMING_LLM_API_KEY`
- [ ] `SIMING_LLM_ENDPOINT`
- [ ] `SIMING_LLM_MODEL`
- [ ] `SIMING_LLM_TIMEOUT_SECONDS`

#### 三、验证与执行约束

- [ ] 当前环境是否允许真实联网调用模型
- [ ] 是否允许在执行过程中通过进程环境变量或未跟踪 `.env` 补齐配置
- [ ] 是否要求本轮必须同时完成这四项
  - `dialogue`
  - `L2`
  - `L3`
  - `Siming live proof`
- [ ] 如果 `L3` 输出与当前 contract 不稳定，是否接受通过 `prompt / normalization / validator-compatible shaping` 来收口
- [ ] 是否要求所有完成证明都必须通过现有 `pytest / verification / harness` 命令
- [ ] 是否有成本、速率、网络地区、账号权限或 provider 访问限制需要提前说明

#### 四、建议回复模板

你可以直接按下面格式提供：

```text
角色 provider：
角色 API key：已提供 / 未提供
角色 endpoint：
角色 model：
角色 timeout：
角色默认是否走在线：
是否允许 DEEPSEEK_* -> CHARACTER_MODEL_*：是 / 否

司命 provider：
司命 API key：已提供 / 未提供
司命 endpoint：
司命 model：
司命 timeout：
是否先只做 deepseek_chat：是 / 否
是否使用 SIMING_LLM_ROUTES_JSON：是 / 否

联网调用：允许 / 不允许
本轮必须完成项：
其他限制：
```

- [ ] **Step 0.1: supply Character configuration outside tracked files**

Required non-secret values:

```powershell
$env:CHARACTER_MODEL_PROVIDER_KIND = "deepseek"
$env:CHARACTER_MODEL_ENDPOINT = "https://api.deepseek.com"
$env:CHARACTER_MODEL_MODEL = "deepseek-chat"
$env:CHARACTER_MODEL_TIMEOUT_SECONDS = "30.0"
$env:DIALOGUE_MODE = "online"
Remove-Item Env:CHARACTER_MODEL_ROUTE_OVERRIDE -ErrorAction SilentlyContinue
```

Set `CHARACTER_MODEL_API_KEY` in the process environment or ignored project `.env`. Do not paste it into a shell-history-producing command, tracked file, plan, test, report, or log.

- [ ] **Step 0.2: select exactly one Siming configuration form**

Legacy global route:

```powershell
$env:SIMING_LLM_MODE = "http"
$env:SIMING_LLM_PROVIDER_ORDER = "deepseek_chat"
$env:SIMING_LLM_ENDPOINT = "https://api.deepseek.com/chat/completions"
$env:SIMING_LLM_MODEL = "deepseek-chat"
$env:SIMING_LLM_TIMEOUT_SECONDS = "60.0"
Remove-Item Env:SIMING_LLM_ROUTES_JSON -ErrorAction SilentlyContinue
```

Set `SIMING_LLM_API_KEY` outside tracked files. Do not use `DEEPSEEK_API_KEY` as a Siming credential.

Route mode is an alternative, not an additive configuration. When route mode is selected, remove `SIMING_LLM_PROVIDER_ORDER` and provide one enabled `deepseek_chat` route containing `route_id`, `provider`, `endpoint`, `model`, `api_key`, `timeout_seconds`, and `enabled`.

- [ ] **Step 0.3: establish evidence freshness**

```powershell
$env:LLM_CLOSURE_RUN_ID = [guid]::NewGuid().ToString()
```

Every readiness/live/closure artifact in this execution must carry this exact run ID. Missing or mismatched IDs fail closure.

- [ ] **Step 0.4: confirm external conditions**

Record outside the repository that:

- network access to the selected endpoints is available
- the account can call the selected model
- paid calls for three Character scenarios and one Siming scenario are authorized
- `30.0` seconds is accepted for Character and `60.0` seconds is accepted for the no-retry Siming proof

Do not start implementation until all four confirmations exist.

---

## Task 1: Freeze Character Configuration And Redacted Transport Evidence

**Files:**

- Modify: `backend/app/config.py`
- Modify: `backend/app/character_agent/gateway/model_provider.py`
- Modify: `backend/tests/test_config_runtime_modes.py`
- Modify: `backend/tests/test_character_model_provider.py`
- Modify: `backend/tests/test_character_model_provider_readiness.py`
- Modify: `.env.example`

- [ ] **Step 1.1: write failing configuration-precedence tests**

Add tests equivalent to:

```python
def test_deepseek_aliases_do_not_feed_character_settings(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "legacy-key")
    monkeypatch.setenv("DEEPSEEK_MODEL", "legacy-model")
    monkeypatch.delenv("CHARACTER_MODEL_API_KEY", raising=False)
    monkeypatch.delenv("CHARACTER_MODEL_MODEL", raising=False)
    reloaded = importlib.reload(config_module)
    assert reloaded.settings.character_model_api_key is None
    assert reloaded.settings.character_model_model is None


def test_character_timeout_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        Settings(character_model_timeout_seconds=0)
```

Add provider tests asserting:

- DeepSeek with no explicit Character model resolves to `deepseek-chat`.
- Qwen with no explicit Character model resolves to `qwen3.7-plus`.
- A `DEEPSEEK_MODEL` environment variable does not affect either result.
- A blank Character key causes strict DeepSeek calls to fail before transport.

- [ ] **Step 1.2: run RED**

Run:

```powershell
python -m pytest -q backend/tests/test_config_runtime_modes.py backend/tests/test_character_model_provider.py backend/tests/test_character_model_provider_readiness.py
```

Expected: failures show the current fixed Qwen model default and implicit provider aliases.

- [ ] **Step 1.3: implement the canonical Character contract**

In `Settings`:

```python
character_model_provider_kind: str = "qwen"
character_model_endpoint: str | None = None
character_model_api_key: str | None = Field(default=None, repr=False, exclude=True)
character_model_model: str | None = None
character_model_timeout_seconds: float = Field(default=20.0, gt=0)
```

Load only `CHARACTER_MODEL_*` into those fields. In `CharacterModelProvider`, remove direct reads of `DEEPSEEK_*`, `QWEN_*`, and `SEED_DOUBAO_*`. Resolve safe endpoint/model defaults from the selected provider only:

```python
_DEFAULT_ENDPOINTS = {
    "deepseek": "https://api.deepseek.com",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
}
_DEFAULT_MODELS = {
    "deepseek": "deepseek-chat",
    "qwen": "qwen3.7-plus",
    "seed_doubao": "doubao-seed-2.0-pro",
}
```

Do not add a default key.

- [ ] **Step 1.4: add redacted call evidence**

Add an immutable evidence object beside `CharacterModelProvider`:

```python
@dataclass(frozen=True)
class CharacterModelCallEvidence:
    task_kind: str
    provider_kind: str
    model_name: str
    endpoint_host: str
    transport_attempted: bool
    transport_succeeded: bool
    fallback_used: bool
    error_type: str | None = None
```

Expose only a copy through `last_call_evidence`. Populate it on strict HTTP success, HTTP failure, and local/hybrid fallback. Never record keys, prompts, response bodies, query strings, or private context.

- [ ] **Step 1.5: update `.env.example`**

Keep safe defaults and document the canonical surface:

```env
DIALOGUE_MODE=stub
CHARACTER_MODEL_PROVIDER_KIND=qwen
CHARACTER_MODEL_ENDPOINT=https://dashscope.aliyuncs.com/compatible-mode/v1
CHARACTER_MODEL_API_KEY=
CHARACTER_MODEL_MODEL=qwen3.7-plus
CHARACTER_MODEL_TIMEOUT_SECONDS=20.0
```

Add a comment that provider-specific aliases are operator conveniences only and are not consumed by Character runtime.

- [ ] **Step 1.6: run GREEN**

Run:

```powershell
python -m pytest -q backend/tests/test_config_runtime_modes.py backend/tests/test_character_model_provider.py backend/tests/test_character_model_provider_readiness.py backend/tests/test_character_model_gateway.py
```

Expected: PASS, with local/hybrid regression behavior unchanged.

- [ ] **Step 1.7: commit with Lore metadata**

```powershell
git add backend/app/config.py backend/app/character_agent/gateway/model_provider.py backend/tests/test_config_runtime_modes.py backend/tests/test_character_model_provider.py backend/tests/test_character_model_provider_readiness.py .env.example
git commit -m "Prevent provider aliases from crossing character runtime boundaries" -m "Character configuration now resolves endpoint and model from one canonical provider identity while exposing redacted transport evidence for live verification." -m "Constraint: CharacterModelGateway remains the only business-facing entry point" -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: focused config, provider, readiness, and gateway tests"
```

---

## Task 2: Make Character Output Contracts Executable

**Files:**

- Modify: `backend/app/character_agent/gateway/prompt_policy.py`
- Modify: `backend/app/character_agent/gateway/output_validator.py`
- Modify: `backend/tests/test_character_model_gateway.py`
- Modify: `backend/tests/test_character_agent_l2_reasoning.py`
- Modify: `backend/tests/test_character_agent_l3_planning.py`

- [ ] **Step 2.1: write failing semantic-validator tests**

Add tests proving:

```python
with pytest.raises(ValueError, match="content must not be empty"):
    validator.validate(
        task_kind="dialogue_generation",
        output={"content": "", "tone": "neutral"},
    )

with pytest.raises(ValueError, match="salience_score"):
    validator.validate(
        task_kind="l2_reasoning",
        output=complete_l2_output(salience_score=1.5),
    )

with pytest.raises(ValueError, match="selected_intent"):
    validator.validate(
        task_kind="l3_planning",
        output=complete_l3_output(
            candidate_intents=["observe"],
            selected_intent="share_info",
        ),
    )
```

Also keep the existing failure for empty `active_goal_frame.primary_goal`.

- [ ] **Step 2.2: run RED**

Run:

```powershell
python -m pytest -q backend/tests/test_character_model_gateway.py backend/tests/test_character_agent_l2_reasoning.py backend/tests/test_character_agent_l3_planning.py
```

Expected: new semantic checks fail while existing contract tests remain green.

- [ ] **Step 2.3: implement strict validators**

Require:

- dialogue `content` and `tone` are non-empty
- L2 contains every key listed by `CharacterPromptPolicy._required_output_keys("l2_reasoning")`
- L2 `salience_score` is finite and within `0.0..1.0`
- L2 ambiguity, risk, and opportunity values belong to their declared model enums
- L3 candidate and recommended lists are non-empty
- L3 selected intent belongs to candidate intents
- L3 `why_this_now` and `active_goal_frame.primary_goal` are non-empty

Do not synthesize missing semantic values. Preserve syntactic list and numeric normalization only where the contract already permits it.

- [ ] **Step 2.4: strengthen prompt policy without changing ownership**

Use task-specific budgets:

```python
max_tokens = {
    "dialogue_generation": 400,
    "l2_reasoning": 1200,
    "l3_planning": 1800,
}[task_kind]
```

For L3, state that all required fields must be explicit, `planning_status` must be `model`, `fallback_mode` must be JSON `null` on live success, and `primary_goal` cannot be empty. Do not add planner-side pre-validation shaping.

- [ ] **Step 2.5: run GREEN**

Run:

```powershell
python -m pytest -q backend/tests/test_character_model_gateway.py backend/tests/test_character_model_provider.py backend/tests/test_character_agent_l2_reasoning.py backend/tests/test_character_agent_l3_planning.py
```

Expected: PASS. Invalid raw output fails at the gateway; local continuity output remains valid and explicitly marked as fallback.

- [ ] **Step 2.6: commit with Lore metadata**

```powershell
git add backend/app/character_agent/gateway/prompt_policy.py backend/app/character_agent/gateway/output_validator.py backend/tests/test_character_model_gateway.py backend/tests/test_character_agent_l2_reasoning.py backend/tests/test_character_agent_l3_planning.py
git commit -m "Reject schema-shaped character outputs that lack usable semantics" -m "Dialogue, L2, and L3 validators now enforce the live closure oracle while keeping fallback status explicit." -m "Rejected: Planner-side goal hydration | gateway validation occurs before planner consumption and hydration would hide provider failure" -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: gateway, provider, L2, and L3 tests"
```

---

## Task 3: Add Character Dialogue, L2, And L3 Live Proof

**Files:**

- Create: `scripts/verification/verify_character_model_live.py`
- Create: `scripts/verification/tests/test_character_model_live_verify.py`
- Create: `.harness/profiles/character-model-live.json`
- Modify: `scripts/verification/tests/test_harness_runner.py`
- Modify: `docs/harness.md`

- [ ] **Step 3.1: write failing profile and config-guard tests**

Require this profile:

```json
{
  "schema_version": 1,
  "name": "character-model-live",
  "order": 59,
  "script": "scripts/verification/verify_character_model_live.py",
  "requires_godot": false,
  "include_in_all": false,
  "result_artifact": ".harness/verification/character-model-live-report.json",
  "description": "Explicit-only real-provider proof for character dialogue, L2, and L3"
}
```

Tests must prove the verifier returns `credential_check` without `CHARACTER_MODEL_API_KEY`, rejects non-DeepSeek provider identity, rejects `DIALOGUE_MODE=stub`, and rejects any `CHARACTER_MODEL_ROUTE_OVERRIDE`.

- [ ] **Step 3.2: run RED**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_character_model_live_verify.py scripts/verification/tests/test_harness_runner.py
```

Expected: FAIL because the script/profile do not exist.

- [ ] **Step 3.3: implement shared live-proof evidence helpers**

The report top level must be:

```json
{
  "schema_version": "character-model-live.v1",
  "verification_run_id": "fixture-run",
  "overall_character_model_live_passed": true,
  "provider": {
    "provider_kind": "deepseek",
    "model": "deepseek-chat",
    "endpoint_host": "api.deepseek.com"
  },
  "results": []
}
```

Use stable result IDs:

- `dialogue_live_deepseek`
- `l2_live_deepseek`
- `l3_live_deepseek`

Each result records `status`, `transport_attempted`, `transport_succeeded`, `fallback_used`, validator/consumer status, latency, and a redacted error type. It never records prompt, response body, key, Authorization header, or private context.

- [ ] **Step 3.4: implement the dialogue scenario**

Construct:

```python
provider = CharacterModelProvider()
gateway = CharacterModelGateway(provider=provider)
service = DialogueService(gateway=gateway)
content, tone = service.generate_reply("char_a", "Acknowledge the visible lamp change.")
```

Pass only when content/tone are non-empty and `provider.last_call_evidence` reports DeepSeek, transport success, and no fallback.

- [ ] **Step 3.5: implement the L2 scenario**

Use the real `CharacterAgentL2Service` with a schema-valid `CharacterPrivateWorldSnapshot` and `CharacterPerceivedEvent` fixture. Pass only when:

- call evidence says `task_kind=l2_reasoning` and no fallback
- gateway validation succeeds
- the service returns a typed `CharacterInterpretation`
- required interpretation text is non-empty
- score/enums satisfy Task 2

- [ ] **Step 3.6: implement the L3 scenario**

Feed the validated live L2 interpretation into the real `CharacterAgentL3Service`. Pass only when:

- call evidence says `task_kind=l3_planning` and no fallback
- `planning_status=model`
- primary goal and candidate/recommended lists are non-empty
- selected intent is model-produced and locally viable
- the triple-filter result for that intent exists and satisfies the current local policy

- [ ] **Step 3.7: test successful orchestration without network**

Inject a fake transport only in verifier unit tests. The production CLI path must always instantiate the real provider. Assert three passed results, stable IDs, matching run ID, redaction, and a non-zero exit when any one scenario fails.

- [ ] **Step 3.8: run GREEN**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_character_model_live_verify.py scripts/verification/tests/test_harness_runner.py
python scripts/verification/harness.py --profile docs
```

Expected: unit/profile/docs checks pass without making a live call.

- [ ] **Step 3.9: commit with Lore metadata**

```powershell
git add scripts/verification/verify_character_model_live.py scripts/verification/tests/test_character_model_live_verify.py .harness/profiles/character-model-live.json scripts/verification/tests/test_harness_runner.py docs/harness.md
git commit -m "Require durable live evidence for every character model surface" -m "One explicit-only verifier exercises actual Dialogue, L2, and L3 services through the existing gateway and records redacted no-fallback evidence." -m "Constraint: Live profile remains excluded from harness all because it requires credentials and paid network calls" -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: verifier unit tests, harness registration, docs profile"
```

---

## Task 4: Restore Config-Faithful Siming DeepSeek Proof

**Files:**

- Modify: `backend/app/config.py`
- Modify: `scripts/verification/verify_siming_backend_chain.py`
- Modify: `scripts/verification/tests/test_siming_backend_chain_verify.py`
- Modify: `backend/tests/test_config_runtime_modes.py`
- Modify: `backend/tests/test_siming_llm_provider_config.py`
- Modify: `backend/tests/test_siming_llm_runtime.py`
- Modify: `docs/harness.md`

- [ ] **Step 4.1: write failing anti-bypass tests**

Add tests asserting:

```python
def test_live_deepseek_does_not_accept_character_key(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "character-only")
    monkeypatch.delenv("SIMING_LLM_API_KEY", raising=False)
    result = run_script("--live-provider", "deepseek_chat")
    assert result.returncode == 1
    assert "failed_stage=credential_check" in result.stdout


def test_live_deepseek_does_not_replace_app_settings() -> None:
    source = SCRIPT.read_text(encoding="utf-8")
    assert "_live_settings_for_provider" not in source
    assert "app_main.settings =" not in source
    assert '"siming_llm_mode": "http"' not in source
```

Add route tests proving legacy and `SIMING_LLM_ROUTES_JSON` modes are mutually exclusive for the proof.

- [ ] **Step 4.2: run RED**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_siming_backend_chain_verify.py backend/tests/test_config_runtime_modes.py backend/tests/test_siming_llm_provider_config.py backend/tests/test_siming_llm_runtime.py
```

Expected: failures identify the current `DEEPSEEK_API_KEY` fallback and synthesized settings.

- [ ] **Step 4.3: make route-mode loading unambiguous**

When `SIMING_LLM_ROUTES_JSON` is present and `SIMING_LLM_PROVIDER_ORDER` is absent, load an empty legacy order. Reject a configured route list plus a non-empty legacy order for closure proof. Validate both Character and Siming timeouts as positive values.

- [ ] **Step 4.4: delete synthesized live settings**

Remove `_live_settings_for_provider` and provider-specific Character-key aliases from the DeepSeek proof. Resolve the selected provider from the already-loaded `app_main.settings`:

```python
settings = app_main.settings
config_failure = _settings_failure(settings, config)
if config_failure is not None:
    return _failed_credential_entry(config_failure)
app_main.reset_runtime_state()
app_main.authority_event_bus.publish(_make_visual_fact_event())
```

For route mode, read the selected enabled route without copying it into global legacy fields. Redact endpoint to hostname before printing or reporting.

- [ ] **Step 4.5: preserve the authority chain oracle**

Keep all existing checks for:

- `source="llm"`
- explicit canonical candidate fields
- policy and feasibility acceptance
- concrete downstream `siming.*` event
- audit/read-model evidence
- proof correlation id
- no retry

Add `verification_run_id` to the JSON/Markdown reports.

- [ ] **Step 4.6: run GREEN**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_siming_backend_chain_verify.py backend/tests/test_config_runtime_modes.py backend/tests/test_siming_llm_provider_config.py backend/tests/test_siming_llm_runtime.py backend/tests/test_siming_event_pipeline.py backend/tests/test_siming_event_producer.py
python scripts/verification/harness.py --profile boundaries
```

Expected: PASS with `siming_llm_stays_inside_runtime=proved`.

- [ ] **Step 4.7: commit with Lore metadata**

```powershell
git add backend/app/config.py scripts/verification/verify_siming_backend_chain.py scripts/verification/tests/test_siming_backend_chain_verify.py backend/tests/test_config_runtime_modes.py backend/tests/test_siming_llm_provider_config.py backend/tests/test_siming_llm_runtime.py docs/harness.md
git commit -m "Prevent Siming proof from manufacturing runnable settings" -m "The live verifier now validates the loaded Siming configuration and runs the existing app event-bus chain without borrowing Character credentials." -m "Constraint: Approved 2026-06-25 backend-chain proof requires real app settings and no retry" -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: verifier, config, provider, runtime, pipeline, producer, and boundary tests"
```

---

## Task 5: Add Fresh-Evidence Closure Aggregation

**Files:**

- Modify: `backend/app/world_runtime/model_provider_readiness.py`
- Modify: `scripts/verification/verify_model_provider_readiness.py`
- Modify: `backend/tests/test_model_provider_readiness.py`
- Create: `scripts/verification/verify_llm_integration_closure.py`
- Create: `scripts/verification/tests/test_llm_integration_closure_verify.py`
- Create: `.harness/profiles/llm-integration-closure.json`
- Modify: `scripts/verification/tests/test_harness_runner.py`
- Modify: `docs/harness.md`

- [ ] **Step 5.1: write failing readiness identity tests**

Require the report to carry `verification_run_id` and make the Siming row understand the selected route from `SIMING_LLM_ROUTES_JSON`. Readiness remains `http_configured_unverified` unless a real checker is supplied.

```python
assert report.verification_run_id == "fixture-run"
assert siming_row.provider_id == "deepseek_chat"
assert siming_row.model_id == "deepseek-chat"
assert siming_row.readiness_status == "http_configured_unverified"
```

- [ ] **Step 5.2: write failing aggregator tests**

The aggregator must fail for:

- missing readiness, Character, or Siming artifact
- mismatched run IDs
- any failed Character scenario
- failed `app_wiring_live_deepseek_chain`
- readiness provider/model identity inconsistent with live reports
- readiness-only success with missing live artifacts

It passes only with all four live scenarios from one run ID.

- [ ] **Step 5.3: run RED**

Run:

```powershell
python -m pytest -q backend/tests/test_model_provider_readiness.py scripts/verification/tests/test_llm_integration_closure_verify.py scripts/verification/tests/test_harness_runner.py
```

Expected: FAIL for missing run identity, route-aware readiness, aggregator, and profile.

- [ ] **Step 5.4: implement run-ID-tagged readiness**

Add `verification_run_id` to `ModelProviderReadinessReport` and its serialized output. Read it from `LLM_CLOSURE_RUN_ID` without changing row readiness semantics. Parse the selected Siming route using structured JSON validation; do not expose route keys.

- [ ] **Step 5.5: implement the aggregator**

The output contract is:

```json
{
  "schema_version": "llm-integration-closure.v1",
  "verification_run_id": "fixture-run",
  "overall_llm_integration_closure_passed": true,
  "claims": {
    "character_dialogue_live": "passed",
    "character_l2_live": "passed",
    "character_l3_live": "passed",
    "siming_deepseek_live": "passed"
  },
  "readiness_is_live_proof": false,
  "source_artifacts": []
}
```

The script reads existing reports and never makes provider calls or rewrites readiness status.

- [ ] **Step 5.6: register an explicit-only aggregation profile**

Use:

```json
{
  "schema_version": 1,
  "name": "llm-integration-closure",
  "order": 60,
  "script": "scripts/verification/verify_llm_integration_closure.py",
  "requires_godot": false,
  "include_in_all": false,
  "result_artifact": ".harness/verification/llm-integration-closure-report.json",
  "description": "Aggregates fresh readiness and live-provider evidence for the four approved closure claims"
}
```

- [ ] **Step 5.7: run GREEN**

Run:

```powershell
python -m pytest -q backend/tests/test_model_provider_readiness.py scripts/verification/tests/test_llm_integration_closure_verify.py scripts/verification/tests/test_harness_runner.py
python scripts/verification/harness.py --profile model-provider-readiness
```

Expected: tests and readiness profile pass; the closure profile still fails until fresh live artifacts exist.

- [ ] **Step 5.8: commit with Lore metadata**

```powershell
git add backend/app/world_runtime/model_provider_readiness.py scripts/verification/verify_model_provider_readiness.py backend/tests/test_model_provider_readiness.py scripts/verification/verify_llm_integration_closure.py scripts/verification/tests/test_llm_integration_closure_verify.py .harness/profiles/llm-integration-closure.json scripts/verification/tests/test_harness_runner.py docs/harness.md
git commit -m "Make LLM closure depend on fresh live artifacts" -m "A run-ID-bound aggregator combines readiness with three Character and one Siming live result without changing readiness semantics." -m "Rejected: Promote readiness rows after a live call | readiness and live proof are separate evidence classes" -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: readiness, aggregator, and harness registry tests"
```

---

## Task 6: Converge Documentation And Protect Secrets

**Files:**

- Create: `scripts/verification/check_tracked_model_secrets.py`
- Create: `scripts/verification/tests/test_tracked_model_secrets.py`
- Modify: `docs/harness.md`
- Modify: `docs/INDEX.md`
- Modify: `docs/superpowers/specs/2026-06-19-deepseek-character-model-gateway-design.md`
- Modify: `docs/superpowers/specs/2026-06-15-full-character-agent-runtime-with-llm-design.md`
- Modify: `docs/superpowers/specs/2026-06-15-siming-phase1-llm-authority-bus-runtime-design.md`
- Modify: `docs/superpowers/specs/2026-06-25-siming-backend-chain-proof-design.md`
- Modify: `docs/superpowers/plans/2026-06-19-deepseek-character-model-gateway-implementation-plan.md`
- Modify: `docs/superpowers/plans/2026-06-15-full-character-agent-runtime-with-llm-implementation-plan.md`
- Modify: `docs/superpowers/plans/2026-06-15-siming-phase1-llm-authority-bus-runtime-implementation-plan.md`
- Modify: `docs/superpowers/plans/2026-06-25-siming-backend-chain-proof-implementation-plan.md`
- Modify: `docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-03-current-project-model-provider-readiness-implementation-plan.md`
- Modify: `docs/superpowers/plans/current-project-intelligence-upgrade/README.md`

- [ ] **Step 6.1: write failing secret-guard tests**

The guard obtains tracked paths from `git ls-files`, reads Character and Siming key values from environment, and scans file bytes without printing the values. It returns non-zero and prints only offending tracked paths.

Test with a temporary git repository containing one tracked leak and one ignored `.env`; only the tracked leak must fail.

- [ ] **Step 6.2: implement the minimal secret guard**

Required environment names:

- `CHARACTER_MODEL_API_KEY`
- `SIMING_LLM_API_KEY`

Also inspect route-level keys from `SIMING_LLM_ROUTES_JSON`. Empty values are ignored. Never accept key-like regex matching as the only check; compare exact configured secret bytes.

- [ ] **Step 6.3: update docs and historical status**

Document:

- `CHARACTER_MODEL_*` as the only Character runtime contract
- Siming dedicated-key and unmodified-settings proof
- three explicit-only profiles and their artifacts
- the carry-forward matrix status vocabulary
- readiness as non-live evidence
- broad character tasks remain owned by the broad plan

Do not mark old unchecked tasks complete without cited code/test evidence.

- [ ] **Step 6.4: run docs and secret checks**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_tracked_model_secrets.py
python scripts/verification/check_tracked_model_secrets.py
python scripts/verification/harness.py --profile docs
```

Expected: tests pass, no tracked secret paths are reported, and `overall_docs_passed=True`.

- [ ] **Step 6.5: commit with Lore metadata**

```powershell
git add scripts/verification/check_tracked_model_secrets.py scripts/verification/tests/test_tracked_model_secrets.py docs/harness.md docs/INDEX.md docs/superpowers/specs/2026-06-19-deepseek-character-model-gateway-design.md docs/superpowers/specs/2026-06-15-full-character-agent-runtime-with-llm-design.md docs/superpowers/specs/2026-06-15-siming-phase1-llm-authority-bus-runtime-design.md docs/superpowers/specs/2026-06-25-siming-backend-chain-proof-design.md docs/superpowers/plans/2026-06-19-deepseek-character-model-gateway-implementation-plan.md docs/superpowers/plans/2026-06-15-full-character-agent-runtime-with-llm-implementation-plan.md docs/superpowers/plans/2026-06-15-siming-phase1-llm-authority-bus-runtime-implementation-plan.md docs/superpowers/plans/2026-06-25-siming-backend-chain-proof-implementation-plan.md docs/superpowers/plans/current-project-intelligence-upgrade/2026-07-03-current-project-model-provider-readiness-implementation-plan.md docs/superpowers/plans/current-project-intelligence-upgrade/README.md
git commit -m "Keep LLM status and credential evidence auditable" -m "Historical plans now point to one strict closure source while a tracked-file guard prevents configured model keys from entering commits." -m "Constraint: Broad non-provider character work remains outside this closure" -m "Confidence: high" -m "Scope-risk: narrow" -m "Tested: secret guard and docs profile"
```

---

## Task 7: Run Focused, Full, Live, And Aggregated Verification

This task modifies only generated evidence under `.harness/verification/` and plan status/evidence notes.

- [ ] **Step 7.1: run focused non-live tests**

```powershell
python -m pytest -q backend/tests/test_config_runtime_modes.py backend/tests/test_character_model_provider.py backend/tests/test_character_model_provider_readiness.py backend/tests/test_character_model_gateway.py
python -m pytest -q backend/tests/test_character_agent_l2_reasoning.py backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_dialogue_mind_core_integration.py backend/tests/test_character_service.py
python -m pytest -q backend/tests/test_siming_llm_provider_config.py backend/tests/test_siming_llm_runtime.py backend/tests/test_siming_event_pipeline.py backend/tests/test_siming_event_producer.py
python -m pytest -q scripts/verification/tests/test_character_model_live_verify.py scripts/verification/tests/test_siming_backend_chain_verify.py scripts/verification/tests/test_llm_integration_closure_verify.py scripts/verification/tests/test_tracked_model_secrets.py
```

Expected: all commands pass with no live network calls.

- [ ] **Step 7.2: run full backend and static/runtime harness regression**

```powershell
python -m pytest -v
python scripts/verification/harness.py --profile all
```

Expected: full pytest passes and `overall_harness_passed=True`. This does not count as live-provider proof because explicit-only profiles are excluded from `all`.

- [ ] **Step 7.3: regenerate readiness for this run**

```powershell
python scripts/verification/verify_model_provider_readiness.py
```

Expected: report run ID equals `LLM_CLOSURE_RUN_ID`. Character and Siming rows identify the configured DeepSeek provider/model and remain readiness evidence.

- [ ] **Step 7.4: run Character live proof**

```powershell
python scripts/verification/harness.py --profile character-model-live
```

Expected:

- `overall_character_model_live_passed=True`
- `dialogue_live_deepseek=passed`
- `l2_live_deepseek=passed`
- `l3_live_deepseek=passed`
- every result has `fallback_used=false`

- [ ] **Step 7.5: run Siming live proof**

```powershell
python scripts/verification/harness.py --profile siming-backend-chain
```

Expected:

- `overall_siming_backend_chain_passed=True`
- `app_wiring_live_deepseek_chain=passed`
- evidence shows the actual configured timeout and no retry

Do not accept a timeout followed by fallback, a verifier-created setting, or an HTTP-only result.

- [ ] **Step 7.6: aggregate the four live claims**

```powershell
python scripts/verification/harness.py --profile llm-integration-closure
```

Expected:

- `overall_llm_integration_closure_passed=True`
- all reports share `LLM_CLOSURE_RUN_ID`
- readiness/live provider and model identities agree
- `readiness_is_live_proof=false`

- [ ] **Step 7.7: run the tracked-secret guard after all reports exist**

```powershell
python scripts/verification/check_tracked_model_secrets.py
```

Expected: exit code `0` and no offending tracked paths.

- [ ] **Step 7.8: update plan evidence without changing claim scope**

Record command, exit code, report path, run ID, provider/model, redacted endpoint host, latency, and exact failed stage when applicable. Never record keys, prompts, full responses, or private context.

If any live scenario fails, leave this plan open and record the blocker. Do not convert missing credentials, timeout, invalid output, fallback, policy rejection, feasibility rejection, or stale evidence into completion.

- [ ] **Step 7.9: commit final evidence with Lore metadata**

```powershell
git add docs/superpowers/plans/2026-07-23-complete-llm-integration-closure-implementation-plan.md
git commit -m "Close LLM integration only on fresh end-to-end evidence" -m "The closure record now binds readiness, Character dialogue/L2/L3, Siming authority-chain proof, full regression, and secret safety to one run ID." -m "Constraint: Readiness remains separate from live-provider proof" -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: full pytest, harness all, Character live, Siming live, closure aggregation, tracked-secret guard"
```

---

## Completion Matrix

| Claim | Required artifact | Required result |
| --- | --- | --- |
| Character dialogue real provider | `character-model-live-report.json` | `dialogue_live_deepseek=passed` and no fallback |
| Character L2 real provider | `character-model-live-report.json` | `l2_live_deepseek=passed` and typed consumer success |
| Character L3 real provider | `character-model-live-report.json` | `l3_live_deepseek=passed` and local viability success |
| Siming DeepSeek | `siming-backend-chain-report.json` | `app_wiring_live_deepseek_chain=passed` |
| Readiness separation | `model-provider-readiness-report.json` | matching identity; no readiness-only promotion |
| Aggregate closure | `llm-integration-closure-report.json` | all four claims passed under one run ID |
| Regression | `harness-run-report.json` and pytest output | full green |
| Secret safety | secret guard output | no tracked configured secret |

## Not Acceptable As Completion

- readiness-only success
- fake, recording, or local provider output
- manual route forcing
- provider HTTP success without validator and consumer success
- dialogue success used to imply L2/L3 success
- planner/provider synthesis of missing L3 semantic fields
- Siming proof built from verifier-created settings
- Character credentials reused for Siming
- retrying the no-retry Siming proof until it happens to pass
- timeout increase without measured evidence and the approved ceiling
- stale or mismatched run IDs
- focused tests without full pytest and `harness --profile all`
- live success without tracked-secret verification
