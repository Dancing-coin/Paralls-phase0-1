# Siming Backend Chain Proof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a backend-only Siming proof surface that verifies deterministic component-chain behavior and a mandatory live DeepSeek app-wiring chain without Godot or frontend projection.

**Architecture:** Add one explicit-only harness profile and one verification script. The script runs component scenarios through a directly assembled `InMemoryAuthorityEventBus -> SimingEventPipeline -> SimingRuntime -> SimingEventProducer -> SimingAuditWriter` chain, then runs the live proof through `backend/app/main.py` globals after `reset_runtime_state()`.

**Tech Stack:** Python 3, pytest, Pydantic settings/models, existing FastAPI backend services, `httpx` via the existing Siming LLM provider.

---

## File Structure

- Modify: `backend/app/config.py` to parse `SIMING_LLM_PROVIDER_ORDER` from env and project `.env`.
- Modify: `backend/app/services/siming_llm_provider.py` to strengthen the DeepSeek prompt and reject missing explicit LLM candidate fields before Pydantic defaults apply.
- Modify: `scripts/verification/harness.py` so `include_in_all=false` profiles remain explicit-only.
- Create/modify: `.harness/profiles/siming-backend-chain.json` for the explicit-only profile.
- Create/modify: `scripts/verification/verify_siming_backend_chain.py` for component and app-wiring proof logic.
- Modify: `scripts/verification/tests/test_siming_backend_chain_verify.py`, `backend/tests/test_config_runtime_modes.py`, and `backend/tests/test_siming_llm_provider_config.py` for TDD coverage.
- Modify: `.env.example` and `docs/harness.md` for operator-facing configuration.

## Task 1: Lock Profile And Config Behavior

**Files:**
- Modify: `scripts/verification/tests/test_siming_backend_chain_verify.py`
- Modify: `backend/tests/test_config_runtime_modes.py`
- Modify: `scripts/verification/harness.py`
- Modify: `.harness/profiles/siming-backend-chain.json`
- Modify: `backend/app/config.py`

- [x] **Step 1: Write failing profile/config tests**

Required assertions:

```python
assert profile["include_in_all"] is False
assert "siming-backend-chain" not in harness._profiles_for_selection("all", registry)
assert reloaded.settings.siming_llm_provider_order == ["deepseek_chat", "openai_responses"]
```

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_siming_backend_chain_verify.py
python -m pytest -q backend/tests/test_config_runtime_modes.py backend/tests/test_siming_llm_provider_config.py
```

Expected: failures for missing `include_in_all`, missing `_profiles_for_selection`, and missing provider-order env parsing.

- [x] **Step 3: Implement minimal config and harness changes**

Add `_env_list()` in `backend/app/config.py`:

```python
def _env_list(name: str, default: list[str]) -> list[str]:
    value = _env_value(name)
    if value is None:
        return list(default)
    parsed = [item.strip() for item in value.split(",") if item.strip()]
    return parsed or list(default)
```

Add `_profiles_for_selection()` in `scripts/verification/harness.py`:

```python
def _profiles_for_selection(selection: str, registry: object) -> list[str]:
    if selection != "all":
        return [selection]
    profile_order = list(getattr(registry, "profile_order"))
    profiles = getattr(registry, "profiles")
    return [
        profile
        for profile in profile_order
        if bool(profiles[profile].get("include_in_all", True))
    ]
```

- [x] **Step 4: Verify GREEN for this task**

Run the same focused tests. Expected: profile/config failures are gone.

## Task 2: Enforce DeepSeek Candidate Contract

**Files:**
- Modify: `backend/tests/test_siming_llm_provider_config.py`
- Modify: `backend/app/services/siming_llm_provider.py`

- [x] **Step 1: Write failing DeepSeek provider tests**

Required assertions:

```python
assert "candidate_id" in system_prompt
assert "established_fact_ids" in system_prompt
assert 'source="llm"' in system_prompt

with pytest.raises(SimingLlmProviderInvalidOutput, match=missing_field):
    provider.generate_candidates(snapshot=make_snapshot(), recent_events=[make_event()], recent_audit=[])
```

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest -q backend/tests/test_siming_llm_provider_config.py
```

Expected: failures for weak DeepSeek prompt and missing explicit-field validation.

- [x] **Step 3: Implement strict DeepSeek validation**

Add a `DEEPSEEK_REQUIRED_CANDIDATE_FIELDS` set and validate each `deepseek_chat` candidate before `InterventionCandidate.model_validate()`. Reject missing `source`, `explanation`, `confidence`, `reason_tags`, and non-`llm` source.

- [x] **Step 4: Verify GREEN for this task**

Run:

```powershell
python -m pytest -q backend/tests/test_siming_llm_provider_config.py
```

Expected: provider tests pass.

## Task 3: Build Backend Chain Proof Script

**Files:**
- Modify: `scripts/verification/tests/test_siming_backend_chain_verify.py`
- Create/modify: `scripts/verification/verify_siming_backend_chain.py`

- [x] **Step 1: Write failing script tests**

Required assertions:

```python
assert result.returncode == 0
assert "司命后端主链证明 / Siming Backend Chain Proof" in result.stdout
assert "scenario=app_wiring_live_deepseek_chain result=FAIL" in result.stdout
assert "失败阶段 / failed_stage=credential_check" in result.stdout
```

- [x] **Step 2: Run tests to verify RED**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_siming_backend_chain_verify.py
```

Expected: failures for missing `--component-only`, old scenario names, and old SKIP behavior.

- [x] **Step 3: Implement component-chain scenarios**

Implement these scenario IDs in `verify_siming_backend_chain.py`:

```text
component_fallback_visual_fact_chain
component_fake_llm_candidate_chain
component_fake_llm_rejection_chain
component_fake_llm_timeout_chain
component_input_family_guard
```

Each scenario publishes real `AuthorityEvent` objects through `InMemoryAuthorityEventBus` and inspects published `siming.*` events, audit records, and read models.

- [x] **Step 4: Implement app-wiring live DeepSeek scenario**

Implement `app_wiring_live_deepseek_chain` by importing `app.main`, reading `app.main.settings`, calling `app.main.reset_runtime_state()`, publishing through `app.main.authority_event_bus`, and inspecting `app.main.siming_audit_writer` plus app-wired pipeline evidence.

- [x] **Step 5: Verify GREEN for script tests**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_siming_backend_chain_verify.py
```

Expected: script tests pass with missing-key live proof returning exit code `1` and `credential_check`.

## Task 4: Documentation And Final Verification

**Files:**
- Modify: `.env.example`
- Modify: `docs/harness.md`
- Modify: `docs/superpowers/specs/2026-06-25-siming-backend-chain-proof-design.md`

- [x] **Step 1: Document explicit-only profile**

Add `siming-backend-chain` to `docs/harness.md`, explicitly stating it is excluded from `all` and requires real DeepSeek configuration.

- [x] **Step 2: Run focused verification**

Run:

```powershell
python -m pytest -q scripts/verification/tests/test_siming_backend_chain_verify.py
python -m pytest -q backend/tests/test_config_runtime_modes.py backend/tests/test_siming_llm_provider_config.py
python scripts/verification/verify_siming_backend_chain.py --component-only
python scripts/verification/check_docs.py
```

Expected: all commands exit `0`.

- [x] **Step 3: Run broader Siming regression verification**

Run:

```powershell
python -m pytest -q backend/tests/test_siming_llm_provider.py backend/tests/test_siming_llm_runtime.py backend/tests/test_siming_llm_boundary_static.py backend/tests/test_siming_event_pipeline.py backend/tests/test_siming_authority_bus_provenance.py
```

Expected: all selected tests pass.

- [x] **Step 4: Run live proof only when configured**

Run:

```powershell
python scripts/verification/harness.py --profile siming-backend-chain
```

Expected with valid DeepSeek config: exit `0`, `overall_siming_backend_chain_passed=True`, and `app_wiring_live_deepseek_chain` status `passed`.

Expected without `SIMING_LLM_API_KEY`: exit non-zero with `failed_stage=credential_check`.
## 2026-07-23 Closure Status

The active proof path is `scripts/verification/verify_siming_backend_chain.py` plus the explicit `siming-backend-chain` profile. The proof must not borrow Character credentials and must not mutate `app_main.settings`; live DeepSeek success is represented only by `app_wiring_live_deepseek_chain=passed`.
