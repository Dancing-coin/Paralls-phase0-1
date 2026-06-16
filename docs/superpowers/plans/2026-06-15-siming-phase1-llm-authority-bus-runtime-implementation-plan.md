# Siming Phase 1 LLM Authority Bus Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add LLM-assisted Siming reasoning as an internal `SimingRuntime` collaborator while preserving `AuthorityEventBus` as the only cross-system runtime channel.

**Architecture:** Extend the existing `SimingEventConsumer -> SimingRuntime.tick() -> SimingEventProducer -> AuthorityEventBus` path. The LLM provider returns canonical candidate domain objects only; policy, feasibility, audit, and event production remain deterministic backend-owned layers.

**Tech Stack:** Python 3.11+, Pydantic v2, FastAPI backend, existing in-memory authority bus, pytest, httpx for the optional real provider adapter, harness profiles `docs`, `backend-contract`, `boundaries`, and `phase1-slice`.

---

## File Structure

- Modify: `backend/app/models/siming_event.py`
  - Add `FairnessStateSnapshot`, `InterventionCandidate`, `InterventionDecision`, provider result/error models, and audit statuses needed for LLM-assisted reasoning.
- Create: `backend/app/services/siming_llm_provider.py`
  - Define `SimingLlmCandidateProvider` protocol, deterministic `DisabledSimingLlmCandidateProvider`, fixture `FakeSimingLlmCandidateProvider`, and optional `HttpSimingLlmCandidateProvider`.
- Create: `backend/app/services/siming_policy.py`
  - Normalize and reject unsafe candidates before feasibility.
- Create: `backend/app/services/siming_feasibility.py`
  - Map accepted candidates to executable `SelectedPath` values without trusting the LLM.
- Modify: `backend/app/services/siming_runtime.py`
  - Inject provider, policy, and feasibility. Keep `tick()` as the only place that can call the provider.
- Modify: `backend/app/services/siming_event_producer.py`
  - Keep exclusive mapping from `SimingOutput` to formal `siming.*` authority events and reject forbidden pseudo-events.
- Modify: `backend/app/services/siming_event_consumer.py`
  - Keep allowlist and add tests proving it does not call the provider.
- Modify: `backend/app/services/siming_event_pipeline.py`
  - Preserve pipeline order and audit writing.
- Modify: `backend/app/main.py`
  - Wire default provider configuration without creating an LLM side channel.
- Modify: `backend/app/config.py`
  - Add optional Siming LLM settings with safe disabled defaults.
- Create: `backend/tests/test_siming_llm_models.py`
  - Lock canonical models and forbidden LLM output shapes.
- Create: `backend/tests/test_siming_llm_provider.py`
  - Lock fake/disabled/provider-normalization behavior.
- Create: `backend/tests/test_siming_llm_policy.py`
  - Lock policy rejection of unsafe candidates.
- Create: `backend/tests/test_siming_llm_feasibility.py`
  - Lock feasibility mappings and ESM ownership.
- Create: `backend/tests/test_siming_llm_runtime.py`
  - Lock provider invocation only inside `SimingRuntime.tick()`, fallback behavior, timeout behavior, and audit.
- Modify: `backend/tests/test_siming_event_pipeline.py`
  - Add bus-level proof that LLM-assisted outputs still pass through `SimingEventProducer`.
- Modify: `backend/tests/test_authority_event_bus.py`
  - Keep public envelope fields `world_ts` and `sim_tick_ts` forbidden.
- Modify: `backend/tests/test_siming_authority_bus_provenance.py`
  - Extend provenance proof for LLM-assisted outputs.
- Modify: `scripts/verification/verify_phase1_slice.py`
  - Add the new focused Siming LLM tests to the `phase1-slice` pytest command once they pass independently.

## Implementation Rules

- Do not import an LLM provider from `SimingEventConsumer`, `SimingEventProducer`, `AuthorityEventBus`, `ESM`, Godot scripts, or frontend projection code.
- Do not let provider output contain `AuthorityEvent`, `InterventionDecision`, `selected_path`, physical success results, role belief truth, or ESM mutation fields.
- Do not add an OpenAI SDK dependency in this plan. Use `httpx` for the optional provider adapter because it is already present as a dev dependency and can be promoted only if a later dependency review approves it.
- Default runtime behavior must be deterministic with LLM disabled.
- All real provider configuration must be optional and injectable from `Settings`; missing API key means disabled provider.
- Model/provider selection must be a route router, not a single global provider choice. Each route can declare provider type, model, endpoint, credential source, timeout, and enabled state while preserving `SimingRuntime.tick() -> SimingEventProducer -> AuthorityEventBus` as the only authority path. During migration, route entries run first and an explicitly configured legacy `siming_llm_provider_order` can be appended as fallback; the default legacy order is not appended to route-only configs.

---

### Task 1: Freeze Canonical Siming LLM Domain Models

**Files:**
- Modify: `backend/app/models/siming_event.py`
- Create: `backend/tests/test_siming_llm_models.py`

- [x] **Step 1: Write the failing canonical model tests**

Create `backend/tests/test_siming_llm_models.py`:

```python
import pytest
from pydantic import ValidationError

from app.models.siming_event import (
    FairnessStateSnapshot,
    InterventionCandidate,
    InterventionDecision,
)


def test_intervention_candidate_accepts_only_candidate_level_fields() -> None:
    candidate = InterventionCandidate(
        candidate_id="cand:light:1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300:char_c:light_level_drop",
        correlation_id="visual_fact:300",
        proposed_band="fact_reveal",
        target_actor_id="char_b",
        target_environment_id="env_lamp",
        established_fact_ids=["visual_fact:300:char_c:light_level_drop"],
        explanation="Make the established light drop easier for char_b to notice.",
        confidence=0.74,
        reason_tags=["established_fact", "visibility"],
        source="llm",
    )

    assert candidate.proposed_band == "fact_reveal"
    assert candidate.established_fact_ids == ["visual_fact:300:char_c:light_level_drop"]
    assert candidate.confidence == 0.74


def test_intervention_candidate_rejects_forbidden_llm_control_fields() -> None:
    with pytest.raises(ValidationError, match="forbidden Siming candidate field"):
        InterventionCandidate.model_validate(
            {
                "candidate_id": "cand:bad",
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "causation_id": "visual_fact:300",
                "correlation_id": "visual_fact:300",
                "proposed_band": "fact_reveal",
                "established_fact_ids": ["visual_fact:300"],
                "source": "llm",
                "authority_event": {"event_type": "siming.fact_reveal"},
            }
        )


def test_fairness_snapshot_is_structured_context_without_raw_godot_state() -> None:
    snapshot = FairnessStateSnapshot(
        snapshot_id="fairness:visual_fact:300",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        known_fact_ids=["visual_fact:300:char_c:light_level_drop"],
        eligible_actor_ids=["char_b"],
        blocked_actor_ids=[],
        recent_intervention_ids=[],
    )

    assert snapshot.known_fact_ids == ["visual_fact:300:char_c:light_level_drop"]
    assert not hasattr(snapshot, "raw_godot_state")


def test_intervention_decision_records_policy_and_feasibility_without_being_provider_output() -> None:
    decision = InterventionDecision(
        decision_id="decision:cand:light:1",
        candidate_id="cand:light:1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        selected_path="visual_fact_path",
        intervention_band="fact_reveal",
        accepted=True,
        policy_reasons=["established_fact_visible"],
        feasibility_reasons=["visual_fact_path_available"],
    )

    assert decision.accepted is True
    assert decision.selected_path == "visual_fact_path"
```

- [x] **Step 2: Run the model tests to verify failure**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_llm_models.py
```

Expected before implementation: FAIL because `FairnessStateSnapshot`, `InterventionCandidate`, and `InterventionDecision` do not exist.

- [x] **Step 3: Add the canonical models**

In `backend/app/models/siming_event.py`, add:

```python
from pydantic import BaseModel, ConfigDict, Field, model_validator


CandidateSource = Literal["rule", "llm", "fallback"]


class FairnessStateSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    room_id: str
    scene_id: str
    zone_id: str
    causation_id: str
    correlation_id: str
    known_fact_ids: list[str] = Field(default_factory=list)
    eligible_actor_ids: list[str] = Field(default_factory=list)
    blocked_actor_ids: list[str] = Field(default_factory=list)
    recent_intervention_ids: list[str] = Field(default_factory=list)


class InterventionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    room_id: str
    scene_id: str
    zone_id: str
    causation_id: str
    correlation_id: str
    proposed_band: InterventionBand
    target_actor_id: str | None = None
    target_object_id: str | None = None
    target_environment_id: str | None = None
    established_fact_ids: list[str] = Field(default_factory=list)
    explanation: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason_tags: list[str] = Field(default_factory=list)
    source: CandidateSource = "rule"

    @model_validator(mode="before")
    @classmethod
    def reject_forbidden_candidate_fields(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        forbidden = {
            "authority_event",
            "event_type",
            "intervention_decision",
            "selected_path",
            "physical_success",
            "role_belief_truth",
            "esm_state_mutation",
            "character_low_level_command",
        }
        present = sorted(forbidden.intersection(value.keys()))
        if present:
            raise ValueError(f"forbidden Siming candidate field(s): {', '.join(present)}")
        return value


class InterventionDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str
    candidate_id: str
    room_id: str
    scene_id: str
    zone_id: str
    causation_id: str
    correlation_id: str
    selected_path: SelectedPath
    intervention_band: InterventionBand
    accepted: bool
    policy_reasons: list[str] = Field(default_factory=list)
    feasibility_reasons: list[str] = Field(default_factory=list)
```

Also extend `AuditStatus` with:

```python
"degraded",
"llm_timeout",
"llm_invalid_output",
"policy_rejected",
"feasibility_rejected",
"unknown_effect",
"ack_timeout",
```

- [x] **Step 4: Run the model tests to verify pass**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_llm_models.py
```

Expected: PASS.

- [x] **Step 5: Run existing Siming model users**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_event_pipeline.py tests/test_authority_event_bus.py
```

Expected: PASS.

- [x] **Step 6: Commit**

```bash
git add backend/app/models/siming_event.py backend/tests/test_siming_llm_models.py
git commit -m "Freeze Siming LLM candidate domain models"
```

Evidence:

- RED: `cd backend; python -m pytest -q tests/test_siming_llm_models.py`; expected pre-implementation failure was missing `FairnessStateSnapshot`, `InterventionCandidate`, and `InterventionDecision`.
- GREEN: `a21e17f`; `cd backend; python -m pytest -q tests/test_siming_llm_models.py` and `cd backend; python -m pytest -q tests/test_siming_event_pipeline.py tests/test_authority_event_bus.py`.
- Harness: final 2026-06-16 `python scripts/verification/harness.py --profile phase1-slice` passed with `overall_phase1_slice_passed=True`; final backend suite passed with `327 passed`.

### Task 2: Add Disabled And Fake LLM Candidate Providers

**Files:**
- Create: `backend/app/services/siming_llm_provider.py`
- Create: `backend/tests/test_siming_llm_provider.py`

- [x] **Step 1: Write the failing provider tests**

Create `backend/tests/test_siming_llm_provider.py`:

```python
import pytest

from app.models.authority_event import AuthorityEvent
from app.models.siming_event import FairnessStateSnapshot, InterventionCandidate, SimingAuditRecord
from app.services.siming_llm_provider import (
    DisabledSimingLlmCandidateProvider,
    FakeSimingLlmCandidateProvider,
    SimingLlmProviderTimeout,
)


def make_snapshot() -> FairnessStateSnapshot:
    return FairnessStateSnapshot(
        snapshot_id="fairness:visual_fact:300",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        known_fact_ids=["visual_fact:300:char_c:light_level_drop"],
        eligible_actor_ids=["char_b"],
    )


def make_event() -> AuthorityEvent:
    return AuthorityEvent.model_validate(
        {
            "event_id": "visual_fact:300:char_c:light_level_drop",
            "event_type": "visual_fact_event",
            "producer_ts": 300,
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "source": {"layer": "L1", "system": "visual_fact", "actor_id": "char_c"},
            "routing": {"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["siming"]},
            "priority": "p2",
            "ttl": 5000,
            "durability": "replayable",
            "causation_id": "visual_fact:300",
            "correlation_id": "visual_fact:300",
            "payload": {"fact_type": "light_level_drop", "established_fact_id": "visual_fact:300:char_c:light_level_drop"},
        }
    )


def test_disabled_provider_returns_no_candidates() -> None:
    provider = DisabledSimingLlmCandidateProvider()

    assert provider.generate_candidates(snapshot=make_snapshot(), recent_events=[make_event()], recent_audit=[]) == []


def test_fake_provider_returns_deep_copied_fixture_candidates() -> None:
    fixture = InterventionCandidate(
        candidate_id="cand:fixture",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        proposed_band="fact_reveal",
        target_actor_id="char_b",
        established_fact_ids=["visual_fact:300:char_c:light_level_drop"],
        source="llm",
    )
    provider = FakeSimingLlmCandidateProvider([fixture])

    candidates = provider.generate_candidates(snapshot=make_snapshot(), recent_events=[make_event()], recent_audit=[])
    candidates[0].reason_tags.append("mutated")

    second = provider.generate_candidates(snapshot=make_snapshot(), recent_events=[make_event()], recent_audit=[])
    assert second[0].reason_tags == []


def test_fake_provider_can_raise_timeout() -> None:
    provider = FakeSimingLlmCandidateProvider([], timeout=True)

    with pytest.raises(SimingLlmProviderTimeout):
        provider.generate_candidates(snapshot=make_snapshot(), recent_events=[make_event()], recent_audit=[])
```

- [x] **Step 2: Run the provider tests to verify failure**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_llm_provider.py
```

Expected before implementation: FAIL because `siming_llm_provider.py` does not exist.

- [x] **Step 3: Implement provider protocol, disabled provider, fake provider, and errors**

Create `backend/app/services/siming_llm_provider.py`:

```python
from typing import Protocol

from app.models.authority_event import AuthorityEvent
from app.models.siming_event import FairnessStateSnapshot, InterventionCandidate, SimingAuditRecord


class SimingLlmProviderError(RuntimeError):
    pass


class SimingLlmProviderTimeout(SimingLlmProviderError):
    pass


class SimingLlmProviderInvalidOutput(SimingLlmProviderError):
    pass


class SimingLlmCandidateProvider(Protocol):
    def generate_candidates(
        self,
        *,
        snapshot: FairnessStateSnapshot,
        recent_events: list[AuthorityEvent],
        recent_audit: list[SimingAuditRecord],
    ) -> list[InterventionCandidate]:
        raise NotImplementedError


class DisabledSimingLlmCandidateProvider:
    def generate_candidates(
        self,
        *,
        snapshot: FairnessStateSnapshot,
        recent_events: list[AuthorityEvent],
        recent_audit: list[SimingAuditRecord],
    ) -> list[InterventionCandidate]:
        return []


class FakeSimingLlmCandidateProvider:
    def __init__(self, candidates: list[InterventionCandidate], *, timeout: bool = False) -> None:
        self._candidates = [candidate.model_copy(deep=True) for candidate in candidates]
        self._timeout = timeout

    def generate_candidates(
        self,
        *,
        snapshot: FairnessStateSnapshot,
        recent_events: list[AuthorityEvent],
        recent_audit: list[SimingAuditRecord],
    ) -> list[InterventionCandidate]:
        if self._timeout:
            raise SimingLlmProviderTimeout("Siming LLM provider timed out")
        return [candidate.model_copy(deep=True) for candidate in self._candidates]
```

- [x] **Step 4: Run provider tests to verify pass**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_llm_provider.py
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/app/services/siming_llm_provider.py backend/tests/test_siming_llm_provider.py
git commit -m "Add Siming LLM provider ports and deterministic fakes"
```

Evidence:

- RED: `cd backend; python -m pytest -q tests/test_siming_llm_provider.py`; expected pre-implementation failure was missing `app.services.siming_llm_provider`.
- GREEN: `2e4b41f`; `cd backend; python -m pytest -q tests/test_siming_llm_provider.py` and `cd backend; python -m pytest -q tests/test_siming_llm_models.py tests/test_siming_llm_provider.py`.
- Harness: final 2026-06-16 focused suite passed with `58 passed`; final phase1-slice profile passed with `candidate_and_siming_observed=proved`.

### Task 3: Add Policy Guardrails For LLM Candidates

**Files:**
- Create: `backend/app/services/siming_policy.py`
- Create: `backend/tests/test_siming_llm_policy.py`

- [x] **Step 1: Write the failing policy tests**

Create `backend/tests/test_siming_llm_policy.py`:

```python
from app.models.siming_event import FairnessStateSnapshot, InterventionCandidate
from app.services.siming_policy import SimingInterventionPolicy


def make_snapshot() -> FairnessStateSnapshot:
    return FairnessStateSnapshot(
        snapshot_id="fairness:1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        known_fact_ids=["visual_fact:300:char_c:light_level_drop"],
        eligible_actor_ids=["char_b"],
        blocked_actor_ids=["char_locked"],
    )


def make_candidate(**overrides: object) -> InterventionCandidate:
    payload = {
        "candidate_id": "cand:1",
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "causation_id": "visual_fact:300",
        "correlation_id": "visual_fact:300",
        "proposed_band": "fact_reveal",
        "target_actor_id": "char_b",
        "established_fact_ids": ["visual_fact:300:char_c:light_level_drop"],
        "source": "llm",
    }
    payload.update(overrides)
    return InterventionCandidate.model_validate(payload)


def test_policy_accepts_candidate_grounded_in_established_fact() -> None:
    result = SimingInterventionPolicy().evaluate(make_candidate(), snapshot=make_snapshot())

    assert result.accepted is True
    assert "established_fact_visible" in result.reasons


def test_policy_rejects_unknown_fact_reference() -> None:
    result = SimingInterventionPolicy().evaluate(
        make_candidate(established_fact_ids=["visual_fact:unknown"]),
        snapshot=make_snapshot(),
    )

    assert result.accepted is False
    assert "unknown_fact_reference" in result.reasons


def test_policy_rejects_blocked_actor_reveal() -> None:
    result = SimingInterventionPolicy().evaluate(
        make_candidate(target_actor_id="char_locked"),
        snapshot=make_snapshot(),
    )

    assert result.accepted is False
    assert "actor_not_eligible" in result.reasons


def test_policy_rejects_locked_truth_rewrite_tag() -> None:
    result = SimingInterventionPolicy().evaluate(
        make_candidate(reason_tags=["locked_truth_rewrite"]),
        snapshot=make_snapshot(),
    )

    assert result.accepted is False
    assert "locked_truth_rewrite" in result.reasons
```

- [x] **Step 2: Run policy tests to verify failure**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_llm_policy.py
```

Expected before implementation: FAIL because `SimingInterventionPolicy` does not exist.

- [x] **Step 3: Implement policy result and guardrails**

Create `backend/app/services/siming_policy.py`:

```python
from dataclasses import dataclass

from app.models.siming_event import FairnessStateSnapshot, InterventionCandidate


@dataclass(frozen=True)
class SimingPolicyResult:
    accepted: bool
    reasons: list[str]


class SimingInterventionPolicy:
    UNSAFE_REASON_TAGS = {"locked_truth_rewrite", "skip_role_autonomy", "skip_esm", "phase2_projection_required"}

    def evaluate(self, candidate: InterventionCandidate, *, snapshot: FairnessStateSnapshot) -> SimingPolicyResult:
        reasons: list[str] = []

        unknown_facts = [fact_id for fact_id in candidate.established_fact_ids if fact_id not in snapshot.known_fact_ids]
        if unknown_facts:
            reasons.append("unknown_fact_reference")

        if candidate.target_actor_id and candidate.target_actor_id not in snapshot.eligible_actor_ids:
            reasons.append("actor_not_eligible")

        for tag in candidate.reason_tags:
            if tag in self.UNSAFE_REASON_TAGS:
                reasons.append(tag)

        if candidate.proposed_band == "environment_request" and "esm_validated_request" not in candidate.reason_tags:
            reasons.append("environment_request_requires_esm_path")

        if reasons:
            return SimingPolicyResult(accepted=False, reasons=reasons)
        return SimingPolicyResult(accepted=True, reasons=["established_fact_visible"])
```

- [x] **Step 4: Run policy tests to verify pass**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_llm_policy.py
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/app/services/siming_policy.py backend/tests/test_siming_llm_policy.py
git commit -m "Add Siming intervention policy guardrails"
```

Evidence:

- RED: `cd backend; python -m pytest -q tests/test_siming_llm_policy.py`; expected pre-implementation failure was missing `SimingInterventionPolicy`.
- GREEN: `c685563`; `cd backend; python -m pytest -q tests/test_siming_llm_policy.py` and `cd backend; python -m pytest -q tests/test_siming_llm_models.py tests/test_siming_llm_policy.py`.
- Harness: final 2026-06-16 focused suite passed with `58 passed`; final boundaries profile kept `siming_llm_stays_inside_runtime=proved`.

### Task 4: Add Execution Feasibility Mapping

**Files:**
- Create: `backend/app/services/siming_feasibility.py`
- Create: `backend/tests/test_siming_llm_feasibility.py`

- [x] **Step 1: Write the failing feasibility tests**

Create `backend/tests/test_siming_llm_feasibility.py`:

```python
from app.models.siming_event import InterventionCandidate
from app.services.siming_feasibility import SimingExecutionFeasibility


def make_candidate(**overrides: object) -> InterventionCandidate:
    payload = {
        "candidate_id": "cand:1",
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "causation_id": "visual_fact:300",
        "correlation_id": "visual_fact:300",
        "proposed_band": "fact_reveal",
        "target_actor_id": "char_b",
        "established_fact_ids": ["visual_fact:300:char_c:light_level_drop"],
        "source": "llm",
    }
    payload.update(overrides)
    return InterventionCandidate.model_validate(payload)


def test_visual_fact_candidate_maps_to_visual_fact_path() -> None:
    result = SimingExecutionFeasibility().evaluate(make_candidate(target_environment_id="env_lamp"))

    assert result.accepted is True
    assert result.selected_path == "visual_fact_path"
    assert "visual_fact_path_available" in result.reasons


def test_character_candidate_maps_to_character_input_path() -> None:
    result = SimingExecutionFeasibility().evaluate(make_candidate(target_environment_id=None))

    assert result.accepted is True
    assert result.selected_path == "character_input_path"


def test_environment_request_candidate_requires_environment_target() -> None:
    result = SimingExecutionFeasibility().evaluate(make_candidate(proposed_band="environment_request", target_environment_id=None))

    assert result.accepted is False
    assert result.selected_path == "no_action"
    assert "missing_environment_target" in result.reasons


def test_environment_request_maps_to_environment_change_path_without_claiming_success() -> None:
    result = SimingExecutionFeasibility().evaluate(
        make_candidate(
            proposed_band="environment_request",
            target_environment_id="env_lamp",
            reason_tags=["esm_validated_request"],
        )
    )

    assert result.accepted is True
    assert result.selected_path == "environment_change_path"
    assert "esm_result_required_for_success" in result.reasons
```

- [x] **Step 2: Run feasibility tests to verify failure**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_llm_feasibility.py
```

Expected before implementation: FAIL because `SimingExecutionFeasibility` does not exist.

- [x] **Step 3: Implement feasibility result and deterministic mapping**

Create `backend/app/services/siming_feasibility.py`:

```python
from dataclasses import dataclass

from app.models.siming_event import InterventionCandidate, SelectedPath


@dataclass(frozen=True)
class SimingFeasibilityResult:
    accepted: bool
    selected_path: SelectedPath
    reasons: list[str]


class SimingExecutionFeasibility:
    def evaluate(self, candidate: InterventionCandidate) -> SimingFeasibilityResult:
        if candidate.proposed_band == "environment_request":
            if not candidate.target_environment_id:
                return SimingFeasibilityResult(False, "no_action", ["missing_environment_target"])
            return SimingFeasibilityResult(True, "environment_change_path", ["esm_result_required_for_success"])

        if candidate.proposed_band == "fact_reveal" and candidate.target_environment_id:
            return SimingFeasibilityResult(True, "visual_fact_path", ["visual_fact_path_available"])

        if candidate.proposed_band in {"impulse", "opportunity", "fact_reveal"} and candidate.target_actor_id:
            return SimingFeasibilityResult(True, "character_input_path", ["character_input_path_available"])

        return SimingFeasibilityResult(False, "no_action", ["no_executable_path"])
```

- [x] **Step 4: Run feasibility tests to verify pass**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_llm_feasibility.py
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/app/services/siming_feasibility.py backend/tests/test_siming_llm_feasibility.py
git commit -m "Add Siming execution feasibility mapping"
```

Evidence:

- RED: `cd backend; python -m pytest -q tests/test_siming_llm_feasibility.py`; expected pre-implementation failure was missing `SimingExecutionFeasibility`.
- GREEN: `138fd79`; `cd backend; python -m pytest -q tests/test_siming_llm_feasibility.py`; LSP diagnostics were run on the new feasibility service and tests.
- Harness: final 2026-06-16 focused suite passed with `58 passed`; final backend suite passed with `327 passed`.

### Task 5: Integrate Provider, Policy, And Feasibility Inside `SimingRuntime.tick()`

**Files:**
- Modify: `backend/app/services/siming_runtime.py`
- Create: `backend/tests/test_siming_llm_runtime.py`
- Modify: `backend/tests/test_siming_event_pipeline.py`

- [x] **Step 1: Write failing runtime tests**

Create `backend/tests/test_siming_llm_runtime.py`:

```python
from app.models.authority_event import AuthorityEvent
from app.models.siming_event import InterventionCandidate, SimingInput
from app.services.siming_llm_provider import FakeSimingLlmCandidateProvider
from app.services.siming_runtime import SimingRuntime


def make_visual_fact_event(**payload_overrides: object) -> AuthorityEvent:
    payload = {
        "event_id": "visual_fact:300:char_c:light_level_drop",
        "event_type": "visual_fact_event",
        "producer_ts": 300,
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "source": {"layer": "L1", "system": "visual_fact", "actor_id": "char_c"},
        "routing": {"audience_mode": "room", "routing_mode": "event_type", "target_ids": ["siming"]},
        "priority": "p2",
        "ttl": 5000,
        "durability": "replayable",
        "causation_id": "visual_fact:300",
        "correlation_id": "visual_fact:300",
        "payload": {
            "fact_type": "light_level_drop",
            "established_fact_id": "visual_fact:300:char_c:light_level_drop",
            "target_environment_id": "env_lamp",
        },
    }
    payload["payload"].update(payload_overrides)  # type: ignore[index, union-attr]
    return AuthorityEvent.model_validate(payload)


def make_candidate(**overrides: object) -> InterventionCandidate:
    payload = {
        "candidate_id": "cand:llm:1",
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "causation_id": "visual_fact:300:char_c:light_level_drop",
        "correlation_id": "visual_fact:300",
        "proposed_band": "fact_reveal",
        "target_actor_id": "char_b",
        "target_environment_id": "env_lamp",
        "established_fact_ids": ["visual_fact:300:char_c:light_level_drop"],
        "explanation": "Reveal the established light drop.",
        "confidence": 0.7,
        "source": "llm",
    }
    payload.update(overrides)
    return InterventionCandidate.model_validate(payload)


def test_runtime_invokes_llm_provider_inside_tick_and_emits_canonical_outputs() -> None:
    runtime = SimingRuntime(llm_provider=FakeSimingLlmCandidateProvider([make_candidate()]))
    event = make_visual_fact_event()

    result = runtime.tick([SimingInput(input_type="visual_fact_event", source_event=event)])

    output_types = [output.output_type for output in result.outputs]
    assert "fairness_snapshot" in output_types
    assert "intervention_candidate" in output_types
    assert "intervention_decision" in output_types
    dispatches = [output for output in result.outputs if output.output_type == "dispatch_intent"]
    assert dispatches
    assert dispatches[0].selected_path == "visual_fact_path"
    assert dispatches[0].intervention_band == "fact_reveal"
    assert result.audit_records[0].status == "recorded"


def test_runtime_rejects_unsafe_llm_candidate_and_records_no_action() -> None:
    runtime = SimingRuntime(
        llm_provider=FakeSimingLlmCandidateProvider(
            [make_candidate(established_fact_ids=["visual_fact:unknown"])]
        )
    )

    result = runtime.tick([SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event())])

    assert any(audit.status == "policy_rejected" for audit in result.audit_records)
    assert any(output.output_type == "no_action" for output in result.outputs)


def test_runtime_falls_back_when_llm_provider_times_out() -> None:
    runtime = SimingRuntime(llm_provider=FakeSimingLlmCandidateProvider([], timeout=True))

    result = runtime.tick([SimingInput(input_type="visual_fact_event", source_event=make_visual_fact_event())])

    assert any(audit.status == "llm_timeout" for audit in result.audit_records)
    assert any(output.output_type == "no_action" for output in result.outputs)
```

- [x] **Step 2: Run runtime tests to verify failure**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_llm_runtime.py
```

Expected before implementation: FAIL because `SimingRuntime` does not accept an injected provider and does not build canonical LLM-assisted outputs.

- [x] **Step 3: Refactor `SimingRuntime.__init__` for dependency injection**

In `backend/app/services/siming_runtime.py`, add constructor dependencies:

```python
from app.services.siming_feasibility import SimingExecutionFeasibility
from app.services.siming_llm_provider import (
    DisabledSimingLlmCandidateProvider,
    SimingLlmCandidateProvider,
    SimingLlmProviderInvalidOutput,
    SimingLlmProviderTimeout,
)
from app.services.siming_policy import SimingInterventionPolicy


class SimingRuntime:
    def __init__(
        self,
        *,
        llm_provider: SimingLlmCandidateProvider | None = None,
        policy: SimingInterventionPolicy | None = None,
        feasibility: SimingExecutionFeasibility | None = None,
    ) -> None:
        self._llm_provider = llm_provider or DisabledSimingLlmCandidateProvider()
        self._policy = policy or SimingInterventionPolicy()
        self._feasibility = feasibility or SimingExecutionFeasibility()
```

- [x] **Step 4: Add snapshot construction and provider call inside `tick()`**

Add helper methods:

```python
def _fairness_state_snapshot(self, event: AuthorityEvent) -> FairnessStateSnapshot:
    known_fact_id = str(event.payload.get("established_fact_id", event.event_id))
    target_actor_id = str(event.payload.get("target_actor_id", "char_b") or "char_b")
    return FairnessStateSnapshot(
        snapshot_id=f"fairness:{event.event_id}",
        room_id=event.room_id,
        scene_id=event.scene_id,
        zone_id=event.zone_id,
        causation_id=event.event_id,
        correlation_id=event.correlation_id,
        known_fact_ids=[known_fact_id],
        eligible_actor_ids=[target_actor_id],
        blocked_actor_ids=[],
        recent_intervention_ids=[],
    )


def _llm_candidates_for(self, event: AuthorityEvent, snapshot: FairnessStateSnapshot) -> tuple[list[InterventionCandidate], list[SimingAuditRecord]]:
    try:
        return (
            self._llm_provider.generate_candidates(snapshot=snapshot, recent_events=[event], recent_audit=[]),
            [],
        )
    except SimingLlmProviderTimeout:
        return [], [self._audit(event, status="llm_timeout", reason="LLM provider timed out")]
    except (SimingLlmProviderInvalidOutput, ValueError) as exc:
        return [], [self._audit(event, status="llm_invalid_output", reason=str(exc))]
```

Call `_llm_candidates_for()` only from `tick()` after creating a fairness snapshot. Do not call the provider from consumer, producer, or pipeline code.

- [x] **Step 5: Convert accepted candidates into existing `SimingOutput` shapes**

Add a helper that performs policy and feasibility:

```python
def _outputs_for_candidate(
    self,
    event: AuthorityEvent,
    candidate: InterventionCandidate,
) -> tuple[list[SimingOutput], SimingAuditRecord]:
    policy_result = self._policy.evaluate(candidate, snapshot=self._fairness_state_snapshot(event))
    if not policy_result.accepted:
        return [self._no_action(event)], self._audit(event, status="policy_rejected", reason=";".join(policy_result.reasons))

    feasibility_result = self._feasibility.evaluate(candidate)
    if not feasibility_result.accepted:
        return [self._no_action(event)], self._audit(event, status="feasibility_rejected", reason=";".join(feasibility_result.reasons))

    outputs = [
        self._candidate_output(event, candidate),
        self._decision_output(event, candidate, feasibility_result.selected_path, policy_result.reasons, feasibility_result.reasons),
        self._dispatch_output(event, candidate, feasibility_result.selected_path),
    ]
    return outputs, self._audit(event, status="recorded", reason="LLM-assisted candidate accepted")
```

Preserve the existing rule-based path by using it when provider returns no candidates and there was no provider failure.

- [x] **Step 6: Run runtime and existing pipeline tests**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_llm_runtime.py tests/test_siming_event_pipeline.py
```

Expected: PASS.

- [x] **Step 7: Add pipeline proof for LLM-assisted bus production**

In `backend/tests/test_siming_event_pipeline.py`, add:

```python
from app.models.siming_event import InterventionCandidate
from app.services.siming_llm_provider import FakeSimingLlmCandidateProvider


def test_pipeline_publishes_llm_assisted_output_only_through_siming_event_producer() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    candidate = InterventionCandidate(
        candidate_id="cand:llm:1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300:char_c:light_level_drop",
        correlation_id="visual_fact:300",
        proposed_band="fact_reveal",
        target_actor_id="char_b",
        target_environment_id="env_lamp",
        established_fact_ids=["visual_fact:300:char_c:light_level_drop"],
        source="llm",
    )
    pipeline = SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=SimingRuntime(llm_provider=FakeSimingLlmCandidateProvider([candidate])),
        producer=SimingEventProducer(bus),
        audit_writer=audit_writer,
    )
    bus.subscribe("visual_fact_event", pipeline.handle_event)

    bus.publish(make_visual_fact_event())

    event_types = [event.event_type for event in bus.list_events(room_id="room_demo")]
    assert "siming.intervention_candidate" in event_types
    assert "siming.intervention_decision" in event_types
    assert "siming.visual_observability_request" in event_types
    assert "siming.dispatch_requested" not in event_types
```

- [x] **Step 8: Re-run pipeline tests**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_event_pipeline.py tests/test_siming_llm_runtime.py
```

Expected: PASS.

- [x] **Step 9: Commit**

```bash
git add backend/app/services/siming_runtime.py backend/tests/test_siming_llm_runtime.py backend/tests/test_siming_event_pipeline.py
git commit -m "Run LLM-assisted Siming candidates inside runtime tick"
```

Evidence:

- RED: `cd backend; python -m pytest -q tests/test_siming_llm_runtime.py`; expected pre-implementation failure was missing provider injection and candidate execution inside `SimingRuntime.tick()`.
- GREEN: `f5aa12c` plus review fix `65cdb65`; `cd backend; python -m pytest -q tests/test_siming_llm_runtime.py tests/test_siming_event_pipeline.py` and the model/provider/policy/feasibility/provenance regression set.
- Harness: final 2026-06-16 boundaries profile proved `siming_llm_stays_inside_runtime`; final phase1-slice profile proved `candidate_and_siming_observed`.

### Task 6: Harden `SimingEventProducer` Event Family Mapping

**Files:**
- Modify: `backend/app/services/siming_event_producer.py`
- Create: `backend/tests/test_siming_event_producer.py`

- [x] **Step 1: Write failing producer tests**

Create `backend/tests/test_siming_event_producer.py`:

```python
import pytest

from app.models.siming_event import SimingOutput
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.siming_event_producer import SimingEventProducer


def make_output(**overrides: object) -> SimingOutput:
    payload = {
        "output_type": "dispatch_intent",
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "causation_id": "visual_fact:300",
        "correlation_id": "visual_fact:300",
        "producer_ts": 304,
        "selected_path": "environment_change_path",
        "intervention_band": "environment_request",
        "payload": {"target_environment_id": "env_lamp", "request_kind": "attention_catalyst"},
    }
    payload.update(overrides)
    return SimingOutput.model_validate(payload)


def test_producer_maps_environment_request_without_claiming_success() -> None:
    bus = InMemoryAuthorityEventBus()
    SimingEventProducer(bus).publish_outputs([make_output()])

    event = bus.list_events(event_type="siming.environment_request")[0]
    assert event.routing.target_ids == ["esm"]
    assert "physical_success" not in event.payload


def test_producer_rejects_forbidden_dispatch_requested_event_family() -> None:
    output = make_output(payload={"event_type": "siming.dispatch_requested"})

    with pytest.raises(ValueError, match="forbidden Siming event family"):
        SimingEventProducer(InMemoryAuthorityEventBus()).publish_outputs([output])
```

- [x] **Step 2: Run producer tests to verify failure**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_event_producer.py
```

Expected before implementation: FAIL on forbidden payload event family guard.

- [x] **Step 3: Add explicit forbidden family guard**

In `backend/app/services/siming_event_producer.py`, before creating `AuthorityEvent`, add:

```python
forbidden_event_type = output.payload.get("event_type")
if forbidden_event_type == "siming.dispatch_requested":
    raise ValueError("forbidden Siming event family: siming.dispatch_requested")
if "physical_success" in output.payload:
    raise ValueError("Siming outputs must not claim physical_success")
```

- [x] **Step 4: Run producer tests and existing provenance tests**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_event_producer.py tests/test_siming_authority_bus_provenance.py
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/app/services/siming_event_producer.py backend/tests/test_siming_event_producer.py
git commit -m "Harden Siming event producer authority mappings"
```

Evidence:

- RED: `cd backend; python -m pytest -q tests/test_siming_event_producer.py`; expected pre-implementation failure was missing forbidden family/physical-success producer regressions.
- GREEN: `598a31a` plus review test-only fix `7ffc854`; `cd backend; python -m pytest -q tests/test_siming_event_producer.py tests/test_siming_authority_bus_provenance.py`.
- Harness: final 2026-06-16 focused suite passed with producer/provenance tests included; final phase1-slice profile passed through the producer-owned authority path.

### Task 7: Add Optional Real Provider Route Configuration Without Side Channels

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/services/siming_llm_provider.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_siming_llm_provider_config.py`

- [x] **Step 1: Write failing config/provider tests**

Create `backend/tests/test_siming_llm_provider_config.py`:

```python
from app.config import Settings
from app.services.siming_llm_provider import (
    DisabledSimingLlmCandidateProvider,
    HttpSimingLlmCandidateProvider,
    build_siming_llm_provider,
)


def test_settings_disable_siming_llm_by_default() -> None:
    settings = Settings()

    assert settings.siming_llm_mode == "disabled"
    assert settings.siming_llm_api_key is None


def test_provider_factory_returns_disabled_without_api_key() -> None:
    provider = build_siming_llm_provider(Settings(siming_llm_mode="http", siming_llm_api_key=None))

    assert isinstance(provider, DisabledSimingLlmCandidateProvider)


def test_provider_factory_returns_http_provider_when_configured() -> None:
    provider = build_siming_llm_provider(
        Settings(
            siming_llm_mode="http",
            siming_llm_api_key="test-key",
            siming_llm_endpoint="https://example.invalid/v1/responses",
            siming_llm_model="test-model",
        )
    )

    assert isinstance(provider, HttpSimingLlmCandidateProvider)
```

- [x] **Step 2: Run config tests to verify failure**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_llm_provider_config.py
```

Expected before implementation: FAIL because settings and factory do not exist.

- [x] **Step 3: Extend settings with safe defaults**

Modify `backend/app/config.py`:

```python
from typing import Literal
from pydantic import BaseModel


class Settings(BaseModel):
    dialogue_mode: str = "stub"
    tts_mode: str = "stub"
    siming_llm_mode: Literal["disabled", "http"] = "disabled"
    siming_llm_api_key: str | None = None
    siming_llm_endpoint: str = "https://api.openai.com/v1/responses"
    siming_llm_model: str = "gpt-5.4-mini"
    siming_llm_timeout_seconds: float = 8.0
```

Do not read environment variables yet unless the repo already has an env-loading pattern. This plan keeps config injectable and deterministic.

- [x] **Step 4: Add HTTP provider skeleton and factory**

In `backend/app/services/siming_llm_provider.py`, add:

```python
import httpx
from pydantic import ValidationError

from app.config import Settings


class HttpSimingLlmCandidateProvider:
    def __init__(self, *, api_key: str, endpoint: str, model: str, timeout_seconds: float) -> None:
        self._api_key = api_key
        self._endpoint = endpoint
        self._model = model
        self._timeout_seconds = timeout_seconds

    def generate_candidates(
        self,
        *,
        snapshot: FairnessStateSnapshot,
        recent_events: list[AuthorityEvent],
        recent_audit: list[SimingAuditRecord],
    ) -> list[InterventionCandidate]:
        payload = {
            "model": self._model,
            "input": {
                "snapshot": snapshot.model_dump(),
                "recent_events": [event.model_dump() for event in recent_events],
                "recent_audit": [record.model_dump() for record in recent_audit],
            },
        }
        try:
            response = httpx.post(
                self._endpoint,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise SimingLlmProviderTimeout("Siming LLM provider timed out") from exc
        except httpx.HTTPError as exc:
            raise SimingLlmProviderError(str(exc)) from exc

        try:
            data = response.json()
            raw_candidates = data.get("candidates", [])
            return [InterventionCandidate.model_validate(item) for item in raw_candidates]
        except (ValueError, ValidationError, AttributeError) as exc:
            raise SimingLlmProviderInvalidOutput(str(exc)) from exc


def build_siming_llm_provider(settings: Settings) -> SimingLlmCandidateProvider:
    if settings.siming_llm_mode != "http" or not settings.siming_llm_api_key:
        return DisabledSimingLlmCandidateProvider()
    return HttpSimingLlmCandidateProvider(
        api_key=settings.siming_llm_api_key,
        endpoint=settings.siming_llm_endpoint,
        model=settings.siming_llm_model,
        timeout_seconds=settings.siming_llm_timeout_seconds,
    )
```

- [x] **Step 5: Wire provider factory in app startup**

In `backend/app/main.py`, change:

```python
from app.config import settings
from app.services.siming_llm_provider import build_siming_llm_provider
```

and initialize:

```python
runtime=SimingRuntime(llm_provider=build_siming_llm_provider(settings)),
```

Keep all provider use inside `SimingRuntime`.

- [x] **Step 6: Run config and architecture tests**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_llm_provider_config.py tests/test_architecture_entrypoints.py tests/test_siming_event_pipeline.py
```

Expected: PASS.

- [x] **Step 7: Commit**

```bash
git add backend/app/config.py backend/app/services/siming_llm_provider.py backend/app/main.py backend/tests/test_siming_llm_provider_config.py
git commit -m "Wire optional Siming LLM provider configuration"
```

Evidence:

- RED: `cd backend; python -m pytest -q tests/test_siming_llm_provider_config.py`; expected pre-implementation failure was missing Siming LLM settings and provider factory.
- GREEN: `68bfa4f` plus review hardening `ee1d6c7`; `cd backend; python -m pytest -q tests/test_siming_llm_provider_config.py tests/test_architecture_entrypoints.py tests/test_siming_event_pipeline.py`.
- Harness: final 2026-06-16 focused suite included provider config and runtime tests; final backend suite passed with `327 passed`.
- Route-router correction: User requirement clarified that model choice must be a router able to connect different model/provider routes. RED was `cd backend; python -m pytest -q tests/test_siming_llm_provider_config.py::test_provider_factory_builds_distinct_openai_response_routes`, failing with missing `SimingLlmRouteSettings`. GREEN added `siming_llm_routes`, route-level provider/model/endpoint/api-key/timeout/enabled settings, and tests proving two OpenAI Responses routes stay distinct and route-level request config is used. Review then found mixed `siming_llm_routes` plus `siming_llm_provider_order` precedence was implicit; RED `test_provider_factory_uses_legacy_order_as_route_fallback` proved the gap, and GREEN made explicitly configured legacy order append after routes while keeping route-only configs exact. Verification passed with `tests/test_siming_llm_provider_config.py` (`20 passed`), focused provider/runtime/boundary tests (`32 passed`), focused Siming/authority suite (`65 passed`), and `python scripts/verification/harness.py --profile boundaries` with `siming_llm_stays_inside_runtime=proved`.

### Task 8: Add Static Boundary Audits For LLM Side-Channel Prevention

**Files:**
- Create: `backend/tests/test_siming_llm_boundary_static.py`
- Modify: `scripts/verification/check_boundaries.py`
- Modify: `scripts/verification/tests/test_boundary_checks.py`

- [x] **Step 1: Write failing static boundary tests**

Create `backend/tests/test_siming_llm_boundary_static.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_llm_provider_is_only_invoked_from_siming_runtime() -> None:
    offenders: list[str] = []
    for path in (ROOT / "app").rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        if "generate_candidates(" not in text:
            continue
        if rel not in {"app/services/siming_runtime.py", "app/services/siming_llm_provider.py"}:
            offenders.append(rel)

    assert offenders == []


def test_consumer_producer_and_bus_do_not_import_llm_provider() -> None:
    for rel in [
        "app/services/siming_event_consumer.py",
        "app/services/siming_event_producer.py",
        "app/services/authority_event_bus.py",
    ]:
        assert "siming_llm_provider" not in read(rel)


def test_no_formal_dispatch_requested_event_family_exists() -> None:
    for rel in ["app/services/siming_runtime.py", "app/services/siming_event_producer.py"]:
        assert "siming.dispatch_requested" not in read(rel).replace('"siming.dispatch_requested"', "")
```

- [x] **Step 2: Run static boundary tests to verify failure or pass**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_llm_boundary_static.py
```

Expected: PASS if earlier tasks kept boundaries; FAIL if any side-channel slipped in.

- [x] **Step 3: If boundary tests fail, remove side-channel imports or direct calls**

Fix only the files reported by the static test. Valid provider call sites are:

```text
backend/app/services/siming_runtime.py
backend/app/services/siming_llm_provider.py
```

- [x] **Step 4: Add harness boundary check coverage**

Modify `scripts/verification/check_boundaries.py` with a helper:

```python
def _scan_siming_llm_side_channels(project_root: Path) -> str:
    offenders: list[str] = []
    for path in (project_root / "backend" / "app").rglob("*.py"):
        rel = path.relative_to(project_root).as_posix()
        text = read_text(path)
        if "generate_candidates(" in text and rel not in {
            "backend/app/services/siming_runtime.py",
            "backend/app/services/siming_llm_provider.py",
        }:
            offenders.append(f"{rel}:llm-provider-call")
        if "siming_llm_provider" in text and rel in {
            "backend/app/services/siming_event_consumer.py",
            "backend/app/services/siming_event_producer.py",
            "backend/app/services/authority_event_bus.py",
        }:
            offenders.append(f"{rel}:llm-provider-import")
    return "\n".join(offenders)
```

Add a result:

```python
_result(
    "siming_llm_stays_inside_runtime",
    "Siming LLM provider calls stay inside SimingRuntime and provider adapters",
    not siming_llm_side_channels,
    ["backend/app/services/siming_runtime.py", "backend/app/services/siming_llm_provider.py"],
    siming_llm_side_channels,
)
```

- [x] **Step 5: Add boundary checker test**

Modify `scripts/verification/tests/test_boundary_checks.py`:

```python
def test_boundaries_prove_siming_llm_runtime_containment() -> None:
    report = evaluate_boundaries(repo_root())
    statuses = {entry["id"]: entry["status"] for entry in report["results"]}

    assert statuses["siming_llm_stays_inside_runtime"] == "proved"
```

- [x] **Step 6: Run boundary tests and harness**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_llm_boundary_static.py
cd ..
python -m pytest -q scripts/verification/tests/test_boundary_checks.py
python scripts/verification/harness.py --profile boundaries
```

Expected: PASS.

- [x] **Step 7: Commit**

```bash
git add backend/tests/test_siming_llm_boundary_static.py scripts/verification/check_boundaries.py scripts/verification/tests/test_boundary_checks.py
git commit -m "Guard Siming LLM against authority bus side channels"
```

Evidence:

- RED: `cd backend; python -m pytest -q tests/test_siming_llm_boundary_static.py`; expected outcome was pass only if earlier tasks preserved runtime containment, otherwise offender paths would fail.
- GREEN: `3ff29fb`; `python -m pytest -q backend/tests/test_siming_llm_boundary_static.py`, `python -m pytest -q scripts/verification/tests/test_boundary_checks.py`, and `python scripts/verification/harness.py --profile boundaries`.
- Harness: final 2026-06-16 boundaries profile passed with `siming_llm_stays_inside_runtime=proved`.

### Task 9: Extend Replay, Audit, And Provenance Tests

**Files:**
- Modify: `backend/tests/test_siming_authority_bus_provenance.py`
- Modify: `backend/tests/test_authority_event_bus.py`
- Modify: `backend/tests/test_siming_event_pipeline.py`

- [x] **Step 1: Add LLM-assisted provenance test**

In `backend/tests/test_siming_authority_bus_provenance.py`, add a test that:

```python
from app.models.siming_event import InterventionCandidate
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_pipeline import SimingEventPipeline
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_llm_provider import FakeSimingLlmCandidateProvider
from app.services.siming_runtime import SimingRuntime


def test_llm_assisted_siming_output_preserves_authority_causation_chain() -> None:
    bus = InMemoryAuthorityEventBus()
    candidate = InterventionCandidate(
        candidate_id="cand:llm:1",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300:char_c:light_level_drop",
        correlation_id="visual_fact:300",
        proposed_band="fact_reveal",
        target_actor_id="char_b",
        target_environment_id="env_lamp",
        established_fact_ids=["visual_fact:300:char_c:light_level_drop"],
        source="llm",
    )
    pipeline = SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=SimingRuntime(llm_provider=FakeSimingLlmCandidateProvider([candidate])),
        producer=SimingEventProducer(bus),
        audit_writer=SimingAuditWriter(),
    )
    bus.subscribe("visual_fact_event", pipeline.handle_event)

    source_event = make_visual_fact_event()
    bus.publish(source_event)

    projected = bus.list_events(event_type="siming.visual_observability_request")[0]
    assert projected.event_id.startswith("siming:")
    assert projected.causation_id == source_event.event_id
    assert projected.correlation_id == source_event.correlation_id
```

Use the same event fixture shape as `test_siming_event_pipeline.py`.

- [x] **Step 2: Add public envelope forbidden-field regression**

In `backend/tests/test_authority_event_bus.py`, add:

```python
def test_authority_event_rejects_sim_tick_ts_public_envelope_field() -> None:
    with pytest.raises(ValidationError, match="forbidden authority envelope"):
        make_authority_event(sim_tick_ts=301)
```

- [x] **Step 3: Add audit coverage for timeout, policy rejection, and no action**

In `backend/tests/test_siming_event_pipeline.py`, add concrete audit tests:

```python
def test_pipeline_records_llm_timeout_audit() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    pipeline = SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=SimingRuntime(llm_provider=FakeSimingLlmCandidateProvider([], timeout=True)),
        producer=SimingEventProducer(bus),
        audit_writer=audit_writer,
    )
    bus.subscribe("visual_fact_event", pipeline.handle_event)

    bus.publish(make_visual_fact_event())

    records = audit_writer.find_by_correlation(room_id="room_demo", correlation_id="visual_fact:300")
    assert any(record.status == "llm_timeout" for record in records)


def test_pipeline_records_policy_rejection_audit() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    candidate = InterventionCandidate(
        candidate_id="cand:unsafe",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="visual_fact:300:char_c:light_level_drop",
        correlation_id="visual_fact:300",
        proposed_band="fact_reveal",
        target_actor_id="char_b",
        established_fact_ids=["visual_fact:unknown"],
        source="llm",
    )
    pipeline = SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=SimingRuntime(llm_provider=FakeSimingLlmCandidateProvider([candidate])),
        producer=SimingEventProducer(bus),
        audit_writer=audit_writer,
    )
    bus.subscribe("visual_fact_event", pipeline.handle_event)

    bus.publish(make_visual_fact_event())

    records = audit_writer.find_by_correlation(room_id="room_demo", correlation_id="visual_fact:300")
    assert any(record.status == "policy_rejected" for record in records)


def test_pipeline_preserves_no_action_audit_when_no_candidate_or_rule_applies() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    pipeline = make_pipeline(bus, audit_writer)
    bus.subscribe("world_fact_event", pipeline.handle_event)

    bus.publish(make_visual_fact_event(event_id="world:1", event_type="world_fact_event", payload={"fact_type": "unrelated"}))

    records = audit_writer.find_by_correlation(room_id="room_demo", correlation_id="visual_fact:300")
    assert any(record.status == "no_action" for record in records)
```

- [x] **Step 4: Run provenance and audit tests**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_authority_bus_provenance.py tests/test_authority_event_bus.py tests/test_siming_event_pipeline.py
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add backend/tests/test_siming_authority_bus_provenance.py backend/tests/test_authority_event_bus.py backend/tests/test_siming_event_pipeline.py
git commit -m "Prove Siming LLM audit and authority provenance"
```

Evidence:

- RED: `cd backend; python -m pytest -q tests/test_siming_authority_bus_provenance.py tests/test_authority_event_bus.py tests/test_siming_event_pipeline.py`; expected pre-fix gaps were missing LLM-only provenance, public envelope regression, and audit coverage.
- GREEN: `549af55` plus review strengthening `899abe9`; `cd backend; python -m pytest -q tests/test_siming_authority_bus_provenance.py tests/test_authority_event_bus.py tests/test_siming_event_pipeline.py`.
- Harness: final 2026-06-16 focused suite passed with provenance and pipeline tests included; final backend suite passed with `327 passed`.

### Task 10: Extend Phase1 Slice Verification

**Files:**
- Modify: `scripts/verification/verify_phase1_slice.py`
- Modify: `scripts/verification/tests/test_formal_profile_checks.py` only if the profile evidence list is asserted there
- Modify: `docs/harness.md`

- [x] **Step 1: Update phase1-slice pytest command**

In `scripts/verification/verify_phase1_slice.py`, extend the pytest list:

```python
[
    python_exe,
    "-m",
    "pytest",
    "-v",
    "tests/test_visual_fact_pipeline.py",
    "tests/test_siming_service.py",
    "tests/test_siming_event_pipeline.py",
    "tests/test_siming_llm_models.py",
    "tests/test_siming_llm_provider.py",
    "tests/test_siming_llm_policy.py",
    "tests/test_siming_llm_feasibility.py",
    "tests/test_siming_llm_runtime.py",
    "tests/test_siming_llm_boundary_static.py",
]
```

- [x] **Step 2: Update harness guide**

In `docs/harness.md`, under `phase1-slice`, add:

```markdown
Current mechanical/runtime evidence includes:

- visual fact authority routing remains wired
- Siming event bus pipeline consumes and produces through `AuthorityEventBus`
- LLM-assisted Siming candidate generation is verified with deterministic fake providers
- static boundary audits prove LLM provider calls stay inside `SimingRuntime`
```

- [x] **Step 3: Run focused backend tests**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_llm_models.py tests/test_siming_llm_provider.py tests/test_siming_llm_policy.py tests/test_siming_llm_feasibility.py tests/test_siming_llm_runtime.py tests/test_siming_llm_boundary_static.py tests/test_siming_event_pipeline.py tests/test_siming_authority_bus_provenance.py
```

Expected: PASS.

- [x] **Step 4: Run docs and static harness profiles**

Run:

```powershell
cd ..
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile backend-contract
python scripts/verification/harness.py --profile boundaries
```

Expected: PASS.

- [x] **Step 5: Run runtime harness profile**

Run:

```powershell
python scripts/verification/harness.py --profile phase1-slice
```

Expected: PASS. If Godot executable is unavailable, record the exact failure and run all backend/static commands above as partial evidence.

- [x] **Step 6: Commit**

```bash
git add scripts/verification/verify_phase1_slice.py docs/harness.md scripts/verification/tests/test_formal_profile_checks.py
git commit -m "Add Siming LLM checks to phase1 slice verification"
```

Evidence:

- RED: `python scripts/verification/harness.py --profile phase1-slice`; the initial runtime path failed in a clean workspace because `MainDemo.tscn` depended on ignored generated `.godot/imported` texture cache files.
- GREEN: `392082b`; `python scripts/verification/harness.py --profile phase1-slice` passed with `overall_phase1_slice_passed=True`, `authority_ack_observed=proved`, `runtime_projection_observed=proved`, and `candidate_and_siming_observed=proved`.
- Harness: final 2026-06-16 `docs`, `backend-contract`, `boundaries`, and `phase1-slice` profiles all passed. Task 10 quality re-review by subagent `019ecea9-25ed-7671-ae4b-2013b310d2c1` returned no Critical or Important issues and `Ready to merge? Yes`; the later final-review ack hardening was applied in `56103bc`.

### Task 11: Final Full Verification And Plan Closure

**Files:**
- Modify: `docs/superpowers/plans/2026-06-15-siming-phase1-llm-authority-bus-runtime-implementation-plan.md`

- [x] **Step 1: Run the complete focused test suite**

Run:

```powershell
cd backend
python -m pytest -q tests/test_siming_llm_models.py tests/test_siming_llm_provider.py tests/test_siming_llm_provider_config.py tests/test_siming_llm_policy.py tests/test_siming_llm_feasibility.py tests/test_siming_llm_runtime.py tests/test_siming_llm_boundary_static.py tests/test_siming_event_producer.py tests/test_siming_event_pipeline.py tests/test_siming_authority_bus_provenance.py tests/test_authority_event_bus.py
```

Expected: PASS.

- [x] **Step 2: Run harness profiles**

Run:

```powershell
cd ..
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile backend-contract
python scripts/verification/harness.py --profile boundaries
python scripts/verification/harness.py --profile phase1-slice
```

Expected: PASS.

- [x] **Step 3: Run full backend tests if focused suite is green**

Run:

```powershell
cd backend
python -m pytest -q
```

Expected: PASS.

- [x] **Step 4: Update this plan with final evidence**

Evidence blocks have been appended under Tasks 1-11 with concrete RED, GREEN, and harness results.

- [x] **Step 5: Commit closure evidence**

```bash
git add docs/superpowers/plans/2026-06-15-siming-phase1-llm-authority-bus-runtime-implementation-plan.md
git commit -m "Record Siming LLM authority bus implementation evidence"
```

Evidence:

- RED: `cd backend; python -m pytest -q` initially failed only at `tests/test_health.py::test_health_exposes_current_backend_identity` because the test still accepted the historical `paralls-phase-0-demo` path or `.worktrees\`, while this workspace correctly reported `D:\Paralls-phase0-1`.
- GREEN: `8f7c317` fixed the stale health identity assertion; `cd backend; python -m pytest -q tests/test_health.py` passed with `1 passed`; `cd backend; python -m pytest -q` passed with `327 passed`.
- Review fixes: final code review found two Important issues. `56103bc` fixed the OpenAI Responses structured-output contract, aligned phase1-slice audit with the executed probe scene, and required accepted acks in the probe. Follow-up route-router review identified the global provider-order design as insufficient for different models/providers; the route-router correction added structured per-route settings. Final route-router review found one Important mixed-config precedence gap; the fallback rule was clarified and tested.
- Harness: final 2026-06-16 focused suite passed with `58 passed`; final harness profiles passed with `overall_docs_passed=True`, `overall_backend_contract_passed=True`, `overall_boundaries_passed=True`, and `overall_phase1_slice_passed=True`; final backend suite passed with `328 passed`. Route-router follow-up verification passed `tests/test_siming_llm_provider_config.py` (`20 passed`), focused provider/runtime/boundary tests (`32 passed`), focused Siming/authority suite (`65 passed`), harness profiles `docs`, `backend-contract`, `boundaries`, and `phase1-slice`, and full backend tests with `335 passed, 1 warning`.

---

## Self-Review

- Spec coverage: The plan covers the provider port, structured context, route-based provider/model selection, forbidden LLM outputs, policy rejection, feasibility mapping, audit fallback, SimingEventProducer-only bus publication, optional real provider configuration, public envelope guardrails, and phase1-slice verification.
- Intentional deferral: Full narrative projection, multi-step dramatic chain search, persistent world simulation, new private Siming bus, and direct Godot/ESM mutation are excluded because the spec marks them non-goals.
- Plan hygiene scan: No task contains unresolved placeholder markers or undefined execution steps. Later tasks reference types introduced in earlier tasks.
- Type consistency: The plan consistently uses `FairnessStateSnapshot`, `InterventionCandidate`, `InterventionDecision`, `SimingLlmCandidateProvider`, `SimingInterventionPolicy`, and `SimingExecutionFeasibility`.
