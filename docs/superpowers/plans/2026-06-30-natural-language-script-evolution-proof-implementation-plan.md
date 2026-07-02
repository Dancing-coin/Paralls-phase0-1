# Natural Language Script Choice Evolution Proof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a backend-only verification profile that accepts a natural-language script and a natural-language group of player choices, proves which choices can evolve the mainline, and verifies Siming observation or enhanced intervention evidence.

**Architecture:** Add a focused verification script with small internal units for normalization, baseline validation, independent branch execution, Siming evidence capture, reporting, and CLI/harness integration. Live DeepSeek is used only for the explicit `--live-deepseek` path; deterministic tests use fixture normalizer outputs so the test suite does not depend on network access or secrets.

**Tech Stack:** Python 3, Pydantic-style backend models already in `backend/app`, existing `scripts/verification/common.py`, existing harness profile registry, `pytest`, DeepSeek Chat Completions over HTTPS for live normalization.

## Global Constraints

- The script input is natural language and may be Markdown or plain text.
- The player input is a group of natural-language choices, not a single event.
- Each choice is independently evaluated from the same baseline state.
- DeepSeek must be called for real in live proof mode.
- DeepSeek is a normalizer, not the world-truth authority.
- Backend authority chain and ESM decide whether world impact is legal.
- Siming is not the primary judge of legality; it observes, audits, and may assist with intervention/catalyst suggestions.
- The proof is backend-only and does not depend on frontend or Godot runtime.
- Generated evidence must stay under `.harness/verification/`.
- New harness profiles must be documented in `docs/harness.md`.
- Do not include API keys or full sensitive environment values in reports.

---

## File Structure

- Create `.harness/fixtures/script-evolution/demo-script.md`: natural-language lamp-letter mainline fixture.
- Create `.harness/fixtures/script-evolution/demo-choices.txt`: natural-language choice group fixture with impact, no-impact, and needs-prior-event choices.
- Create `.harness/profiles/script-evolution-proof.json`: explicit-only backend harness profile excluded from `all` because live DeepSeek requires credentials.
- Create `scripts/verification/verify_script_evolution.py`: CLI, data models, deterministic fixture normalization, live DeepSeek normalization, validation, branch execution, Siming evidence, console output, JSON/Markdown report.
- Create `scripts/verification/tests/test_script_evolution_verify.py`: unit and integration-style tests for the verification script.
- Modify `docs/harness.md`: document the new profile, required environment, command, and artifacts.

The first implementation keeps all proof-specific code in `verify_script_evolution.py`. If the file grows beyond this proof's narrow scope, split pure model/validation helpers into `scripts/verification/script_evolution.py` in a later refactor. Do not move code into `backend/app` for this proof unless a later runtime feature needs it.

---

### Task 1: Fixtures, Models, And Choice Classification

**Files:**
- Create: `.harness/fixtures/script-evolution/demo-script.md`
- Create: `.harness/fixtures/script-evolution/demo-choices.txt`
- Create: `scripts/verification/verify_script_evolution.py`
- Create: `scripts/verification/tests/test_script_evolution_verify.py`

**Interfaces:**
- Produces: `BaselineModel`, `CandidateChoice`, `ChoiceResult`, `ChoiceClassification`
- Produces: `fixture_baseline_model() -> dict[str, object]`
- Produces: `fixture_candidate_choices() -> list[dict[str, object]]`
- Produces: `classify_choice(baseline: dict[str, object], candidate: dict[str, object]) -> ChoiceResult`
- Consumes: no prior task code

- [ ] **Step 1: Add natural-language fixtures**

Create `.harness/fixtures/script-evolution/demo-script.md`:

```markdown
# 灯下信件

深夜，书房里只有一盏台灯亮着。桌上放着一封旧信，信封泛黄，半压在一本黑色笔记本下。

角色 A 站在书桌旁，已经注意到桌上有一封信，但还没有打开。角色 B 在门外，并不知道信里的内容。

当前主线中，角色 A 只是看见了旧信，尚未检查、打开或带走它。
```

Create `.harness/fixtures/script-evolution/demo-choices.txt`:

```text
A. 玩家拿起旧信仔细查看。
B. 玩家直接离开书房。
C. 玩家把信交给门外的角色 B。
```

- [ ] **Step 2: Write failing tests for fixture normalization and classifications**

Create `scripts/verification/tests/test_script_evolution_verify.py`:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = PROJECT_ROOT / "scripts" / "verification" / "verify_script_evolution.py"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_script_evolution", MODULE_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_fixture_baseline_has_mainline_contract() -> None:
    module = load_module()

    baseline = module.fixture_baseline_model()

    assert baseline["script_id"] == "lamp_letter"
    assert baseline["objects"][0]["object_id"] == "obj_letter"
    assert baseline["objects"][0]["state"]["interaction_state"] == "unopened"
    assert {fact["fact_id"] for fact in baseline["locked_facts"]} == {
        "fact_letter_exists",
        "fact_char_b_does_not_know_letter_content",
    }


def test_fixture_choices_cover_impact_no_impact_and_prior_event() -> None:
    module = load_module()

    choices = module.fixture_candidate_choices()

    assert [choice["choice_id"] for choice in choices] == ["A", "B", "C"]
    assert choices[0]["interaction_type"] == "inspect"
    assert choices[1]["interaction_type"] == "leave"
    assert choices[2]["interaction_type"] == "handoff"


def test_classify_choice_before_backend_execution() -> None:
    module = load_module()
    baseline = module.fixture_baseline_model()
    choices = module.fixture_candidate_choices()

    result_a = module.classify_choice(baseline, choices[0])
    result_b = module.classify_choice(baseline, choices[1])
    result_c = module.classify_choice(baseline, choices[2])

    assert result_a.classification == "PENDING_AUTHORITY_EXECUTION"
    assert result_a.matched_deviation_id == "player_inspects_letter"
    assert result_b.classification == "EVOLVABLE_NO_IMPACT"
    assert result_c.classification == "NEEDS_PRIOR_EVENT"
    assert "obj_letter.possession" in result_c.notes
```

- [ ] **Step 3: Run tests to verify they fail**

Run:

```powershell
python -m pytest scripts/verification/tests/test_script_evolution_verify.py -v
```

Expected: FAIL because `verify_script_evolution.py` does not exist or required functions are missing.

- [ ] **Step 4: Implement minimal models and classification**

Create `scripts/verification/verify_script_evolution.py` with this initial content:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


ChoiceClassification = Literal[
    "PENDING_AUTHORITY_EXECUTION",
    "SIMING_INTERVENTION_PROPOSED",
    "MAINLINE_IMPACT_DETECTED",
    "EVOLVABLE_NO_IMPACT",
    "REJECTED_BY_BASELINE",
    "NEEDS_PRIOR_EVENT",
    "NORMALIZATION_FAILED",
]


@dataclass
class ChoiceResult:
    choice_id: str
    source_text: str
    classification: ChoiceClassification
    matched_deviation_id: str = ""
    notes: str = ""
    branch_diff: list[dict[str, object]] = field(default_factory=list)
    authority_events: list[dict[str, object]] = field(default_factory=list)
    esm_results: list[dict[str, object]] = field(default_factory=list)
    siming_evidence: dict[str, object] = field(default_factory=dict)


def fixture_baseline_model() -> dict[str, object]:
    return {
        "script_id": "lamp_letter",
        "mainline_summary": "深夜书房中，角色 A 注意到桌上的旧信，但尚未打开或检查。",
        "actors": [
            {"actor_id": "char_a", "summary": "站在书桌旁，知道旧信存在。"},
            {"actor_id": "char_b", "summary": "在门外，不知道信件内容。"},
        ],
        "objects": [
            {
                "object_id": "obj_letter",
                "summary": "桌上的旧信，半压在黑色笔记本下。",
                "state": {
                    "location": "desk",
                    "visibility_state": "partially_visible",
                    "interaction_state": "unopened",
                    "possession": "desk",
                },
            }
        ],
        "locked_facts": [
            {"fact_id": "fact_letter_exists", "summary": "桌上存在一封旧信。"},
            {
                "fact_id": "fact_char_b_does_not_know_letter_content",
                "summary": "角色 B 尚不知道信件内容。",
            },
        ],
        "allowed_deviations": [
            {
                "deviation_id": "player_inspects_letter",
                "trigger_family": "player_interaction",
                "target_object_id": "obj_letter",
                "interaction_type": "inspect",
                "may_change": [
                    {
                        "path": "objects.obj_letter.visibility_state",
                        "from": "partially_visible",
                        "to": "visible",
                    },
                    {
                        "path": "objects.obj_letter.interaction_state",
                        "from": "unopened",
                        "to": "inspected",
                    },
                ],
                "must_preserve_locked_facts": [
                    "fact_letter_exists",
                    "fact_char_b_does_not_know_letter_content",
                ],
            },
            {
                "deviation_id": "player_takes_letter",
                "trigger_family": "player_interaction",
                "target_object_id": "obj_letter",
                "interaction_type": "take",
                "may_change": [
                    {
                        "path": "objects.obj_letter.possession",
                        "from": "desk",
                        "to": "char_a",
                    }
                ],
                "must_preserve_locked_facts": [
                    "fact_letter_exists",
                    "fact_char_b_does_not_know_letter_content",
                ],
            },
        ],
        "prior_event_requirements": [
            {
                "requirement_id": "letter_must_be_held_before_handing_to_b",
                "summary": "角色 A 必须先拿起旧信，才能把旧信交给角色 B。",
                "interaction_type": "handoff",
                "target_object_id": "obj_letter",
                "required_state": {"objects.obj_letter.possession": "char_a"},
            }
        ],
    }


def fixture_candidate_choices() -> list[dict[str, object]]:
    return [
        {
            "choice_id": "A",
            "source_text": "玩家拿起旧信仔细查看。",
            "event_type": "player_interaction",
            "actor_ref": "char_a",
            "intent_type": "interact_intent",
            "target_ref": "obj_letter",
            "interaction_type": "inspect",
            "confidence": 0.91,
            "evidence": ["旧信", "仔细查看"],
            "normalization_notes": "该选择表达的是检查旧信。",
        },
        {
            "choice_id": "B",
            "source_text": "玩家直接离开书房。",
            "event_type": "player_navigation",
            "actor_ref": "char_a",
            "intent_type": "move_intent",
            "target_ref": "room_exit",
            "interaction_type": "leave",
            "confidence": 0.86,
            "evidence": ["离开书房"],
            "normalization_notes": "该选择可能合法，但不影响当前主线关键对象。",
        },
        {
            "choice_id": "C",
            "source_text": "玩家把信交给门外的角色 B。",
            "event_type": "player_interaction",
            "actor_ref": "char_a",
            "intent_type": "interact_intent",
            "target_ref": "obj_letter",
            "secondary_target_ref": "char_b",
            "interaction_type": "handoff",
            "confidence": 0.88,
            "evidence": ["把信交给角色 B"],
            "normalization_notes": "该选择需要先满足旧信由角色 A 持有的前置状态。",
        },
    ]


def _object_ids(baseline: dict[str, object]) -> set[str]:
    objects = baseline.get("objects", [])
    if not isinstance(objects, list):
        return set()
    return {str(item.get("object_id")) for item in objects if isinstance(item, dict)}


def _actor_ids(baseline: dict[str, object]) -> set[str]:
    actors = baseline.get("actors", [])
    if not isinstance(actors, list):
        return set()
    return {str(item.get("actor_id")) for item in actors if isinstance(item, dict)}


def _allowed_deviations(baseline: dict[str, object]) -> list[dict[str, object]]:
    deviations = baseline.get("allowed_deviations", [])
    return [item for item in deviations if isinstance(item, dict)] if isinstance(deviations, list) else []


def _prior_requirements(baseline: dict[str, object]) -> list[dict[str, object]]:
    requirements = baseline.get("prior_event_requirements", [])
    return [item for item in requirements if isinstance(item, dict)] if isinstance(requirements, list) else []


def classify_choice(baseline: dict[str, object], candidate: dict[str, object]) -> ChoiceResult:
    choice_id = str(candidate.get("choice_id", ""))
    source_text = str(candidate.get("source_text", ""))
    actor_ref = str(candidate.get("actor_ref", ""))
    target_ref = str(candidate.get("target_ref", ""))
    interaction_type = str(candidate.get("interaction_type", ""))

    if actor_ref and actor_ref not in _actor_ids(baseline):
        return ChoiceResult(choice_id, source_text, "NORMALIZATION_FAILED", notes=f"unknown actor_ref={actor_ref}")

    for requirement in _prior_requirements(baseline):
        if (
            str(requirement.get("interaction_type")) == interaction_type
            and str(requirement.get("target_object_id")) == target_ref
        ):
            required_state = requirement.get("required_state", {})
            return ChoiceResult(
                choice_id,
                source_text,
                "NEEDS_PRIOR_EVENT",
                notes=f"requires prior state {required_state}",
            )

    if target_ref not in _object_ids(baseline):
        return ChoiceResult(choice_id, source_text, "EVOLVABLE_NO_IMPACT", notes=f"non-mainline target={target_ref}")

    for deviation in _allowed_deviations(baseline):
        if (
            str(deviation.get("target_object_id")) == target_ref
            and str(deviation.get("interaction_type")) == interaction_type
        ):
            return ChoiceResult(
                choice_id,
                source_text,
                "PENDING_AUTHORITY_EXECUTION",
                matched_deviation_id=str(deviation.get("deviation_id", "")),
                notes="matched allowed deviation; authority execution required",
            )

    return ChoiceResult(choice_id, source_text, "REJECTED_BY_BASELINE", notes="no allowed deviation matched")
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```powershell
python -m pytest scripts/verification/tests/test_script_evolution_verify.py -v
```

Expected: PASS for the three tests in this task.

- [ ] **Step 6: Commit**

```powershell
git add -- .harness/fixtures/script-evolution/demo-script.md .harness/fixtures/script-evolution/demo-choices.txt scripts/verification/verify_script_evolution.py scripts/verification/tests/test_script_evolution_verify.py
git commit -m "feat: add script evolution proof classifications"
```

---

### Task 2: Backend Authority And ESM Branch Execution

**Files:**
- Modify: `scripts/verification/verify_script_evolution.py`
- Modify: `scripts/verification/tests/test_script_evolution_verify.py`

**Interfaces:**
- Consumes: `classify_choice(baseline, candidate) -> ChoiceResult`
- Produces: `execute_choice_branch(baseline: dict[str, object], candidate: dict[str, object]) -> ChoiceResult`
- Produces: `apply_deviation_diff(baseline: dict[str, object], deviation_id: str) -> list[dict[str, object]]`

- [ ] **Step 1: Write failing branch execution test**

Append to `scripts/verification/tests/test_script_evolution_verify.py`:

```python
def test_execute_choice_branch_produces_authority_esm_and_diff() -> None:
    module = load_module()
    baseline = module.fixture_baseline_model()
    candidate = module.fixture_candidate_choices()[0]

    result = module.execute_choice_branch(baseline, candidate)

    assert result.classification in {"MAINLINE_IMPACT_DETECTED", "PENDING_SIMING_OBSERVATION"}
    assert result.matched_deviation_id == "player_inspects_letter"
    assert any(event["event_type"] == "player.interaction.requested" for event in result.authority_events)
    assert any(event["event_type"] == "esm_result_event" for event in result.authority_events)
    assert any(event["event_type"] == "world.object_state.changed" for event in result.authority_events)
    assert any(item["result_type"] == "action_resolution_result" for item in result.esm_results)
    assert {
        (diff["path"], diff["from"], diff["to"])
        for diff in result.branch_diff
    } == {
        ("objects.obj_letter.visibility_state", "partially_visible", "visible"),
        ("objects.obj_letter.interaction_state", "unopened", "inspected"),
    }
```

Also update the `ChoiceClassification` assertion type expectation if needed by allowing `"PENDING_SIMING_OBSERVATION"` in the module implementation.

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest scripts/verification/tests/test_script_evolution_verify.py::test_execute_choice_branch_produces_authority_esm_and_diff -v
```

Expected: FAIL because `execute_choice_branch` is not defined.

- [ ] **Step 3: Implement branch execution through existing backend models**

Modify `scripts/verification/verify_script_evolution.py`:

```python
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.models.authority_event import AuthorityEvent
from app.models.player_input import InteractIntent
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.esm_service import ESMService
from app.services.phase0_authority_event_adapter import Phase0AuthorityEventAdapter
```

Extend `ChoiceClassification` with:

```python
    "PENDING_SIMING_OBSERVATION",
```

Add these helpers:

```python
def _deviation_by_id(baseline: dict[str, object], deviation_id: str) -> dict[str, object] | None:
    for deviation in _allowed_deviations(baseline):
        if str(deviation.get("deviation_id")) == deviation_id:
            return deviation
    return None


def apply_deviation_diff(baseline: dict[str, object], deviation_id: str) -> list[dict[str, object]]:
    deviation = _deviation_by_id(baseline, deviation_id)
    if deviation is None:
        return []
    changes = deviation.get("may_change", [])
    if not isinstance(changes, list):
        return []
    diff: list[dict[str, object]] = []
    for item in changes:
        if not isinstance(item, dict):
            continue
        diff.append(
            {
                "path": str(item.get("path", "")),
                "from": item.get("from"),
                "to": item.get("to"),
            }
        )
    return diff


def _authority_event(
    *,
    event_id: str,
    event_type: str,
    producer_ts: int,
    actor_id: str,
    payload: dict[str, object],
    causation_id: str,
    correlation_id: str,
) -> AuthorityEvent:
    return AuthorityEvent(
        event_id=event_id,
        event_type=event_type,
        producer_ts=producer_ts,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L1", "system": "script_evolution_proof", "actor_id": actor_id},
        routing={"audience_mode": "room", "routing_mode": "broadcast", "target_ids": []},
        priority="p1",
        durability="replayable",
        causation_id=causation_id,
        correlation_id=correlation_id,
        payload=payload,
    )


def _candidate_to_interact_intent(candidate: dict[str, object], producer_ts: int) -> InteractIntent:
    return InteractIntent(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        actor_id=str(candidate["actor_ref"]),
        intent_type=str(candidate.get("intent_type", "interact_intent")),
        target_object_id=str(candidate["target_ref"]),
        interaction_type=str(candidate["interaction_type"]),
        producer_ts=producer_ts,
    )


def execute_choice_branch(baseline: dict[str, object], candidate: dict[str, object]) -> ChoiceResult:
    classified = classify_choice(baseline, candidate)
    if classified.classification != "PENDING_AUTHORITY_EXECUTION":
        return classified

    bus = InMemoryAuthorityEventBus()
    esm = ESMService()
    adapter = Phase0AuthorityEventAdapter()
    choice_id = str(candidate["choice_id"])
    producer_ts = 100 + ord(choice_id[0])
    causation_id = f"choice:{choice_id}"
    correlation_id = f"script-evolution:{choice_id}"

    incoming = _authority_event(
        event_id=f"choice:{choice_id}:player_interaction",
        event_type="player.interaction.requested",
        producer_ts=producer_ts,
        actor_id=str(candidate["actor_ref"]),
        causation_id=causation_id,
        correlation_id=correlation_id,
        payload={"choice": candidate},
    )
    bus.publish(incoming)

    intent = _candidate_to_interact_intent(candidate, producer_ts)
    resolution = esm.resolve_interaction(intent, is_in_range=True)
    esm_results = [resolution.model_dump()]

    branch_diff = apply_deviation_diff(baseline, classified.matched_deviation_id)
    for index, diff in enumerate(branch_diff, start=1):
        object_result = esm.emit_object_state_result(
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            actor_id=str(candidate["actor_ref"]),
            target_object_id=str(candidate["target_ref"]),
            previous_state=str(diff["from"]),
            current_state=str(diff["to"]),
            producer_ts=producer_ts + index,
            request_ref=getattr(resolution, "request_ref", None),
            causation_id=causation_id,
            correlation_id=correlation_id,
        )
        esm_results.append(object_result.model_dump())
        siming_event = adapter.world_result_event(object_result, source_event=intent)
        bus.publish(siming_event)
        bus.publish(
            _authority_event(
                event_id=f"choice:{choice_id}:world_change:{index}",
                event_type="world.object_state.changed",
                producer_ts=producer_ts + index,
                actor_id=str(candidate["actor_ref"]),
                causation_id=causation_id,
                correlation_id=correlation_id,
                payload={
                    "choice_id": choice_id,
                    "target_object_id": str(candidate["target_ref"]),
                    "path": str(diff["path"]),
                    "from": diff["from"],
                    "to": diff["to"],
                    "esm_result": object_result.model_dump(),
                    "siming_observable_event_id": siming_event.event_id,
                },
            )
        )

    return ChoiceResult(
        choice_id=choice_id,
        source_text=str(candidate["source_text"]),
        classification="PENDING_SIMING_OBSERVATION",
        matched_deviation_id=classified.matched_deviation_id,
        notes="authority and ESM produced branch diff; Siming observation required",
        branch_diff=branch_diff,
        authority_events=[event.model_dump() for event in bus.list_events()],
        esm_results=esm_results,
    )
```

- [ ] **Step 4: Run branch execution test**

Run:

```powershell
python -m pytest scripts/verification/tests/test_script_evolution_verify.py::test_execute_choice_branch_produces_authority_esm_and_diff -v
```

Expected: PASS.

- [ ] **Step 5: Run all script evolution tests**

Run:

```powershell
python -m pytest scripts/verification/tests/test_script_evolution_verify.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add -- scripts/verification/verify_script_evolution.py scripts/verification/tests/test_script_evolution_verify.py
git commit -m "feat: execute script choice branches through backend authority"
```

---

### Task 3: Siming Observation And Enhanced Intervention Evidence

**Files:**
- Modify: `scripts/verification/verify_script_evolution.py`
- Modify: `scripts/verification/tests/test_script_evolution_verify.py`

**Interfaces:**
- Consumes: `execute_choice_branch(...) -> ChoiceResult`
- Produces: `attach_siming_evidence(result: ChoiceResult) -> ChoiceResult`
- Produces: `run_choice_pipeline(baseline: dict[str, object], candidate: dict[str, object]) -> ChoiceResult`

- [ ] **Step 1: Write failing Siming observation test**

Append:

```python
def test_run_choice_pipeline_requires_siming_observation_for_mainline_impact() -> None:
    module = load_module()
    baseline = module.fixture_baseline_model()
    candidate = module.fixture_candidate_choices()[0]

    result = module.run_choice_pipeline(baseline, candidate)

    assert result.classification in {"MAINLINE_IMPACT_DETECTED", "SIMING_INTERVENTION_PROPOSED"}
    assert result.siming_evidence["observed"] is True
    assert int(result.siming_evidence["audit_count"]) >= 1
    assert int(result.siming_evidence["output_count"]) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest scripts/verification/tests/test_script_evolution_verify.py::test_run_choice_pipeline_requires_siming_observation_for_mainline_impact -v
```

Expected: FAIL because `run_choice_pipeline` is not defined.

- [ ] **Step 3: Implement Siming observation adapter**

Add imports:

```python
from app.models.siming_event import SimingInput
from app.services.siming_runtime import SimingRuntime
```

Add helpers:

```python
def _siming_source_event(result: ChoiceResult) -> AuthorityEvent | None:
    for event_payload in result.authority_events:
        if event_payload.get("event_type") == "esm_result_event":
            return AuthorityEvent.model_validate(event_payload)
    return None


def _is_intervention_like(output: object) -> bool:
    output_type = str(getattr(output, "output_type", "") or "")
    selected_path = str(getattr(output, "selected_path", "") or "")
    intervention_band = str(getattr(output, "intervention_band", "") or "")
    return any(
        token in " ".join([output_type, selected_path, intervention_band]).lower()
        for token in ["candidate", "decision", "dispatch", "catalyst", "intervention", "fact_reveal"]
    )


def attach_siming_evidence(result: ChoiceResult) -> ChoiceResult:
    if result.classification != "PENDING_SIMING_OBSERVATION":
        return result
    source_event = _siming_source_event(result)
    if source_event is None:
        result.classification = "REJECTED_BY_BASELINE"
        result.notes = "world divergence missing authority event for Siming"
        return result

    runtime = SimingRuntime()
    tick_result = runtime.tick([SimingInput(source_event=source_event)])
    output_count = len(tick_result.outputs)
    audit_count = len(tick_result.audit_records)
    intervention_count = sum(1 for output in tick_result.outputs if _is_intervention_like(output))
    result.siming_evidence = {
        "observed": output_count > 0 or audit_count > 0,
        "output_count": output_count,
        "audit_count": audit_count,
        "intervention_like_output_count": intervention_count,
        "outputs": [output.model_dump() for output in tick_result.outputs],
        "audit_records": [record.model_dump() for record in tick_result.audit_records],
    }
    if intervention_count > 0:
        result.classification = "SIMING_INTERVENTION_PROPOSED"
        result.notes = "world divergence observed by Siming with intervention-like output"
    elif output_count > 0 or audit_count > 0:
        result.classification = "MAINLINE_IMPACT_DETECTED"
        result.notes = "world divergence observed or audited by Siming"
    else:
        result.classification = "PENDING_SIMING_OBSERVATION"
        result.notes = "world divergence produced but Siming evidence missing"
    return result


def run_choice_pipeline(baseline: dict[str, object], candidate: dict[str, object]) -> ChoiceResult:
    return attach_siming_evidence(execute_choice_branch(baseline, candidate))
```

- [ ] **Step 4: Run Siming observation test**

Run:

```powershell
python -m pytest scripts/verification/tests/test_script_evolution_verify.py::test_run_choice_pipeline_requires_siming_observation_for_mainline_impact -v
```

Expected: PASS because `Phase0AuthorityEventAdapter.world_result_event()` publishes `esm_result_event`, which `SimingObservePipeline` accepts when routed to `siming`.

- [ ] **Step 5: Add no-impact and prior-event pipeline regression test**

Append:

```python
def test_run_choice_pipeline_keeps_no_impact_and_prior_event_classifications() -> None:
    module = load_module()
    baseline = module.fixture_baseline_model()
    choices = module.fixture_candidate_choices()

    result_b = module.run_choice_pipeline(baseline, choices[1])
    result_c = module.run_choice_pipeline(baseline, choices[2])

    assert result_b.classification == "EVOLVABLE_NO_IMPACT"
    assert result_b.siming_evidence == {}
    assert result_c.classification == "NEEDS_PRIOR_EVENT"
    assert result_c.siming_evidence == {}
```

- [ ] **Step 6: Run all script evolution tests**

Run:

```powershell
python -m pytest scripts/verification/tests/test_script_evolution_verify.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add -- scripts/verification/verify_script_evolution.py scripts/verification/tests/test_script_evolution_verify.py
git commit -m "feat: verify Siming observation for script evolution"
```

---

### Task 4: CLI, Reports, Console Output, And Live DeepSeek Normalization

**Files:**
- Modify: `scripts/verification/verify_script_evolution.py`
- Modify: `scripts/verification/tests/test_script_evolution_verify.py`

**Interfaces:**
- Consumes: `fixture_baseline_model()`, `fixture_candidate_choices()`, `run_choice_pipeline(...)`
- Produces: `run_proof(script_path: Path, choices_path: Path, live_deepseek: bool) -> dict[str, object]`
- Produces: `normalize_with_deepseek(script_text: str, choices_text: str) -> tuple[dict[str, object], list[dict[str, object]], dict[str, object]]`
- Produces: `main() -> int`

- [ ] **Step 1: Write failing CLI/report test for deterministic mode**

Append:

```python
import json
import subprocess
import sys


def test_cli_component_mode_writes_bilingual_reports() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/verification/verify_script_evolution.py",
            "--script",
            ".harness/fixtures/script-evolution/demo-script.md",
            "--choices",
            ".harness/fixtures/script-evolution/demo-choices.txt",
            "--component-only",
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0
    assert "自然语言剧本选择演化证明 / Natural Language Script Choice Evolution Proof" in result.stdout
    assert "[CHOICE A]" in result.stdout
    assert "MAINLINE_IMPACT_DETECTED" in result.stdout or "SIMING_INTERVENTION_PROPOSED" in result.stdout
    assert "EVOLVABLE_NO_IMPACT" in result.stdout
    assert "NEEDS_PRIOR_EVENT" in result.stdout

    report_path = PROJECT_ROOT / ".harness" / "verification" / "script-evolution-proof-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overall_script_evolution_passed"] is True
    assert report["mainline_evolvable"] is True
    assert len(report["choices"]) == 3
```

- [ ] **Step 2: Run CLI test to verify it fails**

Run:

```powershell
python -m pytest scripts/verification/tests/test_script_evolution_verify.py::test_cli_component_mode_writes_bilingual_reports -v
```

Expected: FAIL because CLI/report code is missing.

- [ ] **Step 3: Implement deterministic CLI and reports**

Add imports:

```python
import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from common import repo_root, verification_dir, write_json
```

Add constants and report helpers:

```python
REPORT_JSON = "script-evolution-proof-report.json"
REPORT_MD = "script-evolution-proof-report.md"


def _choice_to_report(result: ChoiceResult) -> dict[str, object]:
    return {
        "choice_id": result.choice_id,
        "source_text": result.source_text,
        "classification": result.classification,
        "matched_deviation_id": result.matched_deviation_id,
        "notes": result.notes,
        "branch_diff": result.branch_diff,
        "authority_events": result.authority_events,
        "esm_results": result.esm_results,
        "siming_evidence": result.siming_evidence,
    }


def _write_script_evolution_markdown(path: Path, report: dict[str, object]) -> None:
    lines = ["# Natural Language Script Choice Evolution Proof / 自然语言剧本选择演化证明", ""]
    lines.append(f"- Overall: `{report['overall_script_evolution_passed']}`")
    lines.append(f"- Mainline Evolvable: `{report['mainline_evolvable']}`")
    lines.append("")
    lines.append("| Choice | Classification | Notes |")
    lines.append("| --- | --- | --- |")
    for choice in report["choices"]:
        notes = str(choice.get("notes", "")).replace("\n", " ")
        lines.append(f"| `{choice['choice_id']}` | `{choice['classification']}` | {notes} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _print_console(report: dict[str, object]) -> None:
    print("自然语言剧本选择演化证明 / Natural Language Script Choice Evolution Proof")
    print(f"script_normalize={report['normalization']['script_normalize']}")
    print(f"choices_normalize={report['normalization']['choices_normalize']}")
    for choice in report["choices"]:
        print(f"[CHOICE {choice['choice_id']}] {choice['source_text']}")
        print(f"result={choice['classification']}")
        print(f"notes={choice['notes']}")
    print(f"mainline_evolvable={report['mainline_evolvable']}")
    print("结果=通过 / result=PASS" if report["overall_script_evolution_passed"] else "结果=失败 / result=FAIL")


def _write_report(report: dict[str, object]) -> None:
    project_root = repo_root()
    log_dir = verification_dir(project_root)
    write_json(log_dir / REPORT_JSON, report)
    _write_script_evolution_markdown(log_dir / REPORT_MD, report)
```

Add deterministic proof runner:

```python
def run_proof(script_path: Path, choices_path: Path, live_deepseek: bool) -> dict[str, object]:
    script_text = script_path.read_text(encoding="utf-8")
    choices_text = choices_path.read_text(encoding="utf-8")
    normalization_meta: dict[str, object] = {
        "script_normalize": "fixture",
        "choices_normalize": "fixture",
        "live_deepseek": live_deepseek,
    }
    if live_deepseek:
        baseline, choices, deepseek_meta = normalize_with_deepseek(script_text, choices_text)
        normalization_meta.update(deepseek_meta)
    else:
        baseline = fixture_baseline_model()
        choices = fixture_candidate_choices()

    results = [run_choice_pipeline(baseline, candidate) for candidate in choices]
    impact_classifications = {"MAINLINE_IMPACT_DETECTED", "SIMING_INTERVENTION_PROPOSED"}
    mainline_evolvable = any(result.classification in impact_classifications for result in results)
    report: dict[str, object] = {
        "overall_script_evolution_passed": mainline_evolvable,
        "mainline_evolvable": mainline_evolvable,
        "script_path": str(script_path),
        "choices_path": str(choices_path),
        "normalization": normalization_meta,
        "baseline_model": baseline,
        "candidate_choices": choices,
        "choices": [_choice_to_report(result) for result in results],
        "artifacts": {
            "json": ".harness/verification/script-evolution-proof-report.json",
            "markdown": ".harness/verification/script-evolution-proof-report.md",
        },
    }
    _write_report(report)
    return report
```

Add live DeepSeek normalizer:

```python
def _deepseek_request(messages: list[dict[str, str]]) -> dict[str, object]:
    api_key = os.environ.get("SIMING_LLM_API_KEY", "").strip()
    endpoint = os.environ.get("SIMING_LLM_ENDPOINT", "https://api.deepseek.com/chat/completions").strip()
    model = os.environ.get("SIMING_LLM_MODEL", "deepseek-chat").strip()
    timeout = float(os.environ.get("SIMING_LLM_TIMEOUT_SECONDS", "8.0"))
    if not api_key:
        raise RuntimeError("DEEPSEEK_UNAVAILABLE: missing SIMING_LLM_API_KEY")
    payload = {
        "model": model,
        "messages": messages,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"DEEPSEEK_UNAVAILABLE: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("DEEPSEEK_UNAVAILABLE: response JSON is not an object")
    return data


def _deepseek_content(data: dict[str, object]) -> dict[str, object]:
    choices = data.get("choices")
    if not isinstance(choices, list):
        raise RuntimeError("CHOICES_NORMALIZE_FAILED: DeepSeek response missing choices")
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            parsed = json.loads(content)
            if isinstance(parsed, dict):
                return parsed
    raise RuntimeError("CHOICES_NORMALIZE_FAILED: DeepSeek response missing JSON content")


def normalize_with_deepseek(script_text: str, choices_text: str) -> tuple[dict[str, object], list[dict[str, object]], dict[str, object]]:
    script_response = _deepseek_request(
        [
            {
                "role": "system",
                "content": (
                    "Return only JSON. Normalize the script into the exact keys: "
                    "script_id, mainline_summary, actors, objects, locked_facts, "
                    "allowed_deviations, prior_event_requirements. Do not create events from the script."
                ),
            },
            {"role": "user", "content": script_text},
        ]
    )
    baseline = _deepseek_content(script_response)
    choices_response = _deepseek_request(
        [
            {
                "role": "system",
                "content": (
                    "Return only JSON with top-level key choices. Normalize each player choice "
                    "against the supplied baseline. Do not claim world mutation."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"script": script_text, "baseline_model": baseline, "choices": choices_text},
                    ensure_ascii=False,
                ),
            },
        ]
    )
    choices_payload = _deepseek_content(choices_response)
    raw_choices = choices_payload.get("choices")
    if not isinstance(raw_choices, list):
        raise RuntimeError("CHOICES_NORMALIZE_FAILED: normalized choices missing choices list")
    candidate_choices = [choice for choice in raw_choices if isinstance(choice, dict)]
    return baseline, candidate_choices, {
        "script_normalize": "deepseek_chat",
        "choices_normalize": "deepseek_chat",
        "deepseek_model": os.environ.get("SIMING_LLM_MODEL", "deepseek-chat"),
        "deepseek_endpoint_host": os.environ.get("SIMING_LLM_ENDPOINT", "https://api.deepseek.com/chat/completions").split("/")[2],
    }
```

Add CLI:

```python
def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", required=True)
    parser.add_argument("--choices", required=True)
    parser.add_argument("--live-deepseek", action="store_true")
    parser.add_argument("--component-only", action="store_true")
    args = parser.parse_args()

    try:
        report = run_proof(
            Path(args.script),
            Path(args.choices),
            live_deepseek=bool(args.live_deepseek and not args.component_only),
        )
    except RuntimeError as exc:
        report = {
            "overall_script_evolution_passed": False,
            "mainline_evolvable": False,
            "normalization": {"error": str(exc)},
            "choices": [],
            "artifacts": {
                "json": ".harness/verification/script-evolution-proof-report.json",
                "markdown": ".harness/verification/script-evolution-proof-report.md",
            },
        }
        _write_report(report)
        _print_console(report)
        return 1
    _print_console(report)
    return 0 if report["overall_script_evolution_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run deterministic CLI test**

Run:

```powershell
python -m pytest scripts/verification/tests/test_script_evolution_verify.py::test_cli_component_mode_writes_bilingual_reports -v
```

Expected: PASS.

- [ ] **Step 5: Write and run missing-key live DeepSeek test**

Append:

```python
def test_live_deepseek_without_key_fails_bilingually() -> None:
    env = dict(os.environ)
    env["SIMING_LLM_API_KEY"] = ""
    env["SIMING_LLM_ENDPOINT"] = "https://api.deepseek.com/chat/completions"
    env["SIMING_LLM_MODEL"] = "deepseek-chat"
    result = subprocess.run(
        [
            sys.executable,
            "scripts/verification/verify_script_evolution.py",
            "--script",
            ".harness/fixtures/script-evolution/demo-script.md",
            "--choices",
            ".harness/fixtures/script-evolution/demo-choices.txt",
            "--live-deepseek",
        ],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )

    assert result.returncode == 1
    assert "DEEPSEEK_UNAVAILABLE" in result.stdout
    report_path = PROJECT_ROOT / ".harness" / "verification" / "script-evolution-proof-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overall_script_evolution_passed"] is False
    assert "SIMING_LLM_API_KEY" in report["normalization"]["error"]
```

Run:

```powershell
python -m pytest scripts/verification/tests/test_script_evolution_verify.py::test_live_deepseek_without_key_fails_bilingually -v
```

Expected: PASS.

- [ ] **Step 6: Run all script evolution tests**

Run:

```powershell
python -m pytest scripts/verification/tests/test_script_evolution_verify.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add -- scripts/verification/verify_script_evolution.py scripts/verification/tests/test_script_evolution_verify.py
git commit -m "feat: add script evolution proof CLI and reports"
```

---

### Task 5: Harness Profile, Documentation, And Verification

**Files:**
- Create: `.harness/profiles/script-evolution-proof.json`
- Modify: `docs/harness.md`
- Modify: `scripts/verification/tests/test_script_evolution_verify.py`

**Interfaces:**
- Consumes: `scripts/verification/verify_script_evolution.py` CLI
- Produces: harness profile `script-evolution-proof`

- [ ] **Step 1: Write failing profile registration test**

Append:

```python
def test_script_evolution_profile_is_registered() -> None:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "verification"))
    import harness
    from registry import load_profile_registry

    registry = load_profile_registry(PROJECT_ROOT)

    assert "script-evolution-proof" in registry.profiles
    profile = registry.profiles["script-evolution-proof"]
    assert profile["script"] == "scripts/verification/verify_script_evolution.py"
    assert profile["requires_godot"] is False
    assert profile["include_in_all"] is False
    assert profile["result_artifact"] == ".harness/verification/script-evolution-proof-report.json"
    assert "script-evolution-proof" not in harness._profiles_for_selection("all", registry)
    assert harness._profiles_for_selection("script-evolution-proof", registry) == ["script-evolution-proof"]
```

- [ ] **Step 2: Run profile test to verify it fails**

Run:

```powershell
python -m pytest scripts/verification/tests/test_script_evolution_verify.py::test_script_evolution_profile_is_registered -v
```

Expected: FAIL because the profile manifest does not exist.

- [ ] **Step 3: Add profile manifest**

Create `.harness/profiles/script-evolution-proof.json`:

```json
{
  "schema_version": 1,
  "name": "script-evolution-proof",
  "order": 59,
  "script": "scripts/verification/verify_script_evolution.py",
  "requires_godot": false,
  "include_in_all": false,
  "result_artifact": ".harness/verification/script-evolution-proof-report.json",
  "description": "Explicit-only backend proof for natural-language script choice evolution with live DeepSeek normalization and Siming observation evidence"
}
```

- [ ] **Step 4: Modify profile command to pass fixtures by default**

Because `harness.py` invokes profile scripts without custom arguments, modify `main()` in `scripts/verification/verify_script_evolution.py` so `--script` and `--choices` default to the demo fixtures:

```python
    project_root = repo_root()
    parser.add_argument(
        "--script",
        default=str(project_root / ".harness" / "fixtures" / "script-evolution" / "demo-script.md"),
    )
    parser.add_argument(
        "--choices",
        default=str(project_root / ".harness" / "fixtures" / "script-evolution" / "demo-choices.txt"),
    )
```

Keep `--live-deepseek` optional for direct CLI runs. Add profile behavior so harness runs live mode by default unless `--component-only` is explicitly passed:

```python
    live_deepseek = bool(args.live_deepseek or not args.component_only)
```

Then direct test commands can still use `--component-only` for deterministic mode.

- [ ] **Step 5: Document profile in docs/harness.md**

Add `script-evolution-proof` to the command list near `siming-backend-chain`:

```powershell
python scripts/verification/harness.py --profile script-evolution-proof
```

Add a profile section after `siming-backend-chain`:

```markdown
### `script-evolution-proof`

Explicit-only backend proof for natural-language script choice evolution. This profile does not start Godot and does not rely on frontend projection. It accepts a natural-language script mainline plus a group of natural-language player choices, uses live DeepSeek normalization, executes each choice as an independent backend branch, and verifies Siming observation evidence for mainline impact.

This profile is intentionally excluded from `all` by `include_in_all=false` because it requires a real `SIMING_LLM_API_KEY` and live DeepSeek requests:

```powershell
python scripts/verification/harness.py --profile script-evolution-proof
```

Required configuration:

```env
SIMING_LLM_API_KEY=<real DeepSeek key>
SIMING_LLM_ENDPOINT=https://api.deepseek.com/chat/completions
SIMING_LLM_MODEL=deepseek-chat
SIMING_LLM_TIMEOUT_SECONDS=8.0
```

Output:

- `.harness/verification/script-evolution-proof-report.json`
- `.harness/verification/script-evolution-proof-report.md`
```

Update the `all` section sentence so it remains true and does not include `script-evolution-proof`.

- [ ] **Step 6: Run profile and deterministic CLI tests**

Run:

```powershell
python -m pytest scripts/verification/tests/test_script_evolution_verify.py -v
```

Expected: PASS.

Run deterministic CLI:

```powershell
python scripts/verification/verify_script_evolution.py --component-only
```

Expected: exit code 0 and console includes `结果=通过 / result=PASS`.

- [ ] **Step 7: Run docs/profile checks**

Run:

```powershell
python -m pytest scripts/verification/tests/test_harness_registry.py scripts/verification/tests/test_docs_checks.py scripts/verification/tests/test_script_evolution_verify.py -v
```

Expected: PASS.

Run:

```powershell
python scripts/verification/harness.py --profile docs
```

Expected: exit code 0.

- [ ] **Step 8: Run live DeepSeek profile when credentials are available**

Only run this when `SIMING_LLM_API_KEY` is set to a real DeepSeek key:

```powershell
python scripts/verification/harness.py --profile script-evolution-proof
```

Expected: exit code 0, report `.harness/verification/script-evolution-proof-report.json` has:

```json
{
  "overall_script_evolution_passed": true,
  "mainline_evolvable": true
}
```

If the key is not available, run the explicit failure proof instead:

```powershell
$env:SIMING_LLM_API_KEY=""
python scripts/verification/verify_script_evolution.py --live-deepseek
```

Expected: exit code 1, console and report include `DEEPSEEK_UNAVAILABLE`.

- [ ] **Step 9: Commit**

```powershell
git add -- .harness/profiles/script-evolution-proof.json docs/harness.md scripts/verification/verify_script_evolution.py scripts/verification/tests/test_script_evolution_verify.py
git commit -m "feat: register script evolution proof harness profile"
```

---

## Final Verification

Run focused tests:

```powershell
python -m pytest scripts/verification/tests/test_script_evolution_verify.py -v
```

Run harness docs check:

```powershell
python scripts/verification/harness.py --profile docs
```

Run deterministic proof:

```powershell
python scripts/verification/verify_script_evolution.py --component-only
```

Run live proof when a real DeepSeek key is configured:

```powershell
python scripts/verification/harness.py --profile script-evolution-proof
```

Do not claim live DeepSeek success unless the live profile exits 0 and `.harness/verification/script-evolution-proof-report.json` shows `overall_script_evolution_passed=true`.
