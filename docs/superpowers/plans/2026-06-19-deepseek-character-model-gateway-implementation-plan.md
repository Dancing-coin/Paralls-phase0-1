# DeepSeek Character Model Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Connect the character-agent runtime to DeepSeek as the first live online provider while upgrading the gateway/provider/router seam into a router-ready provider-aware boundary with local fallback preserved.

**Architecture:** Keep `CharacterModelGateway` as the only business-facing entry point, upgrade `CharacterModelRouter` to return explicit DeepSeek-aware provider metadata, and upgrade `CharacterModelProvider` to translate current gateway requests into DeepSeek chat-completions requests and normalize JSON responses back into task-shaped outputs. Preserve offline fallback for `local` and `hybrid` routes without introducing a full multi-provider runtime.

**Tech Stack:** Python 3.13, current FastAPI backend, urllib-based HTTP client, pytest, current character-agent gateway contracts, DeepSeek OpenAI-compatible chat-completions API.

---

### Task 1: Freeze Router-Ready Provider Expectations In Tests

**Files:**
- Modify: `backend/tests/test_character_model_router.py`
- Modify: `backend/tests/test_character_model_gateway.py`

- [ ] **Step 1: Write failing router tests for explicit DeepSeek provider identity**

```python
def test_model_router_defaults_to_deepseek_online_route() -> None:
    router = CharacterModelRouter()
    route = router.resolve_route()
    assert route["route_mode"] == "online_default"
    assert route["provider_kind"] == "deepseek"
```

- [ ] **Step 2: Write failing hybrid/local tests that keep fallback semantics explicit**

```python
def test_model_router_supports_local_and_hybrid_routes() -> None:
    router = CharacterModelRouter()
    assert router.resolve_route("local_only")["provider_kind"] == "local"
    assert router.resolve_route("hybrid_ready")["provider_kind"] == "hybrid"
```

- [ ] **Step 3: Write failing gateway tests for provider-aware policy metadata**

```python
assert request["route"]["provider_kind"] == "deepseek"
assert request["policy"]["provider_kind"] == "deepseek"
assert request["policy"]["fallback_mode"] == "hybrid"
```

- [ ] **Step 4: Run the focused tests to verify they fail for the expected reason**

Run:

```powershell
python -m pytest -q backend/tests/test_character_model_router.py backend/tests/test_character_model_gateway.py
```

Expected: failures showing the router still returns `online` instead of `deepseek`, or policy metadata is still too generic.

---

### Task 2: Add Provider Translation Tests For DeepSeek Chat Completions

**Files:**
- Modify: `backend/tests/test_character_model_gateway.py`
- Create or modify: `backend/tests/test_character_model_provider.py`

- [ ] **Step 1: Write a failing test for DeepSeek request translation**

```python
def test_model_provider_builds_deepseek_chat_completion_request() -> None:
    provider = CharacterModelProvider(
        provider_kind="deepseek",
        endpoint_url="https://api.deepseek.com/chat/completions",
        api_key="test-key",
    )
    payload = provider._build_deepseek_request(
        {
            "task_kind": "dialogue_generation",
            "prompt": {
                "system_instruction": "system",
                "user_instruction": "user",
                "required_output_keys": ["content", "tone"],
                "response_format": "json_object",
            },
            "policy": {"temperature": 0.2},
        }
    )
    assert payload["model"]
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1]["role"] == "user"
```

- [ ] **Step 2: Write a failing test for DeepSeek response normalization**

```python
def test_model_provider_normalizes_deepseek_chat_completion_response() -> None:
    provider = CharacterModelProvider(provider_kind="deepseek")
    output = provider._normalize_deepseek_response(
        {
            "choices": [
                {
                    "message": {
                        "content": "{\"content\": \"I am here.\", \"tone\": \"neutral\"}"
                    }
                }
            ]
        }
    )
    assert output["content"] == "I am here."
    assert output["tone"] == "neutral"
```

- [ ] **Step 3: Write a failing test for hybrid fallback on provider failure**

```python
def test_model_provider_hybrid_falls_back_to_offline_on_provider_error() -> None:
    provider = CharacterModelProvider(provider_kind="hybrid", endpoint_url="https://api.deepseek.com/chat/completions")
    output = provider.complete({...})
    assert isinstance(output, dict)
```

- [ ] **Step 4: Run the focused tests to verify they fail correctly**

Run:

```powershell
python -m pytest -q backend/tests/test_character_model_provider.py backend/tests/test_character_model_gateway.py
```

Expected: failures showing the provider lacks DeepSeek request/response translation helpers.

---

### Task 3: Implement Router-Ready DeepSeek Provider Support

**Files:**
- Modify: `backend/app/character_agent/gateway/model_router.py`
- Modify: `backend/app/character_agent/gateway/model_provider.py`
- Modify if needed: `backend/app/character_agent/gateway/model_gateway.py`
- Modify if needed: `backend/app/character_agent/gateway/prompt_policy.py`

- [ ] **Step 1: Update router defaults to explicit DeepSeek provider identity**

```python
if route_override == "local_only":
    return {"route_mode": "local_only", "provider_kind": "local"}
if route_override == "hybrid_ready":
    return {"route_mode": "hybrid_ready", "provider_kind": "hybrid"}
return {"route_mode": "online_default", "provider_kind": "deepseek"}
```

- [ ] **Step 2: Extend provider initialization to read provider-aware env vars**

```python
self._provider_kind = provider_kind or "deepseek"
self._endpoint_url = endpoint_url or os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
self._api_key = api_key or os.getenv("DEEPSEEK_API_KEY", "") or os.getenv("CHARACTER_MODEL_API_KEY", "")
self._model_name = model_name or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
```

- [ ] **Step 3: Implement DeepSeek chat-completions request translation**

```python
payload = {
    "model": self._model_name,
    "messages": [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_instruction},
    ],
    "response_format": {"type": "json_object"},
}
```

- [ ] **Step 4: Implement DeepSeek response normalization**

```python
message = payload["choices"][0]["message"]["content"]
parsed = json.loads(message)
if not isinstance(parsed, dict):
    raise ValueError("deepseek response content must decode to a JSON object")
return parsed
```

- [ ] **Step 5: Preserve route-based behavior**

```python
if provider_kind == "local":
    return self._offline_complete(request)
if provider_kind in {"deepseek", "hybrid"}:
    try:
        return self._complete_via_deepseek(request)
    except (...):
        if provider_kind == "hybrid":
            return self._offline_complete(request)
        raise
```

- [ ] **Step 6: Keep gateway and prompt policy compatible with the new provider kind without changing business entry points**

- [ ] **Step 7: Run focused tests to verify the provider path passes**

Run:

```powershell
python -m pytest -q backend/tests/test_character_model_router.py backend/tests/test_character_model_provider.py backend/tests/test_character_model_gateway.py
```

Expected: PASS.

---

### Task 4: Wire Local Runtime Configuration And Verify Character-Agent Consumers

**Files:**
- Modify if present: local env docs or runbook files that mention model config
- Modify if needed: `backend/tests/test_character_agent_l2_reasoning.py`
- Modify if needed: `backend/tests/test_character_agent_l3_planning.py`
- Modify if needed: `backend/tests/test_character_service.py`

- [ ] **Step 1: Add or update focused tests proving `L2`, `L3`, and dialogue generation still consume the gateway unchanged**

```python
assert gateway.requests[0]["task_kind"] == "l2_reasoning"
assert gateway.requests[0]["task_kind"] == "l3_planning"
assert gateway.calls[0]["task_kind"] == "dialogue_generation"
```

- [ ] **Step 2: Verify the new provider-aware route does not change current business-facing gateway usage**

- [ ] **Step 3: Document local runtime env setup with untracked env vars only**

Use:

```text
DEEPSEEK_API_KEY
DEEPSEEK_MODEL
DEEPSEEK_BASE_URL
```

- [ ] **Step 4: Run focused integration tests**

Run:

```powershell
python -m pytest -q backend/tests/test_character_agent_l2_reasoning.py backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_service.py
```

Expected: PASS.

---

### Task 5: Final Verification

**Files:**
- Modify if needed: `docs/current-project-implementation-summary.md`
- Modify if needed: related gateway docs if runtime truth changed

- [ ] **Step 1: Run backend verification**

Run:

```powershell
python -m pytest -v
```

Expected: PASS.

- [ ] **Step 2: If docs changed, run docs verification**

Run:

```powershell
python scripts/verification/harness.py --profile docs
```

Expected: `overall_docs_passed=True`

- [ ] **Step 3: Confirm no tracked file contains the DeepSeek secret**

Run:

```powershell
rg -n "sk-[a-zA-Z0-9]+" .
```

Expected: no matches in tracked repo files for the live secret.
