# Current Project Siming L6 Boundary Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the runtime contracts around System L6 routing/replay, Siming-to-character catalyst delivery, player-facing inner prompts, and global situation provenance before adding more Siming director behavior.

**Architecture:** Keep the current in-memory backend runtime. Add explicit contract models and route execution behind existing services instead of replacing transport, frontend projection, character runtime, or the Phase0 smoke path. New director behavior must enter through public evidence and `SimingGlobalSituationSnapshot` provenance, while existing event-specific `SimingRuntime.tick()` branches remain compatibility paths.

**Tech Stack:** Python 3, Pydantic v2, pytest, existing backend service classes, existing harness profiles.

## Global Constraints

- Do not replace the in-memory authority event bus with an external broker.
- Do not introduce distributed ordering, dead-letter queues, persistent databases, or cross-process delivery.
- Do not change existing Godot scene behavior; only define a presentation-only outlet for player-facing `inner_prompt`.
- Siming must not emit `character_agent_execution`, ESM settlement results, world mutation, physical success claims, low-level motion commands, or actor control frames.
- Siming catalyst payloads must not carry private memory patches, selected intent, command type, action request bundles, or private character memory references.
- Character and Siming must not share `character_mm:*`, `character_private`, private patch sessions, inference history, or private cache.
- AI-controlled actors may receive `impulse_hint` through `CharacterAgentRuntime`.
- Player-controlled actors may only receive `inner_prompt` through frontend presentation / narration.
- `impulse_hint` and `inner_prompt` intensity must not exceed `0.35`; over-limit payloads are rejected and audited, not clamped.
- Preserve the existing Phase0 minimal Siming reaction path, `siming-backend-chain`, and mainline runtime proof.

---

## File Structure

- `backend/app/models/siming_catalyst.py`: new Pydantic contract models for `SimingCatalystInput`, `InnerPrompt`, validation errors, forbidden field checks, and AuthorityEvent factory helpers.
- `backend/app/services/siming_character_dispatch_adapter.py`: converts supported `siming.*` authority events into catalyst inputs before runtime ingestion, rejects invalid catalyst payloads with audit summaries, and never dispatches player-facing inner prompts to character runtime.
- `backend/app/services/authority_event_bus.py`: adds consumer identity records, route matching, durability-aware storage, and current-view TTL filtering while preserving existing call compatibility.
- `backend/app/services/frontend_authority_event_projection.py`: remains a projection adapter; adds `inner_prompt` projection shape without taking over route decisions.
- `backend/app/main.py`: subscribes Siming and frontend projector with explicit consumer IDs.
- `backend/app/services/siming_event_pipeline.py`: keeps character dispatch behind the adapter and avoids direct dispatch for presentation-only events.
- `backend/app/services/siming_global_situation.py`: keeps private inputs out and exposes provenance needed by new Siming decisions.
- `backend/app/services/siming_runtime.py`: attaches situation provenance only where new global situation decisions use it; compatibility branches stay in place.
- `backend/tests/test_siming_character_dispatch_adapter.py`: contract tests for catalyst, impulse, rejection, audit, and player prompt routing.
- `backend/tests/test_authority_event_bus.py`: L6 route, durability, replay, and TTL tests.
- `backend/tests/test_siming_event_pipeline.py`: pipeline and projector routing tests.
- `backend/tests/test_siming_global_situation.py` and `backend/tests/test_siming_global_situation_runtime.py`: provenance and private-boundary tests.
- `docs/架构/运行时/模块/SystemL6事件总线.md`: documents executed L6 semantics after implementation.
- `docs/架构/运行时/模块/Siming.md`: documents catalyst, impulse, inner prompt, and situation-backed decision boundaries after implementation.
- `docs/架构/运行时/运行时覆盖矩阵.md`: records owner files and verification coverage.
- `docs/harness.md`: update only if profile evidence wording changes.

---

### Task 1: Catalyst Contract Model And Adapter Gate

**Files:**
- Create: `backend/app/models/siming_catalyst.py`
- Modify: `backend/app/services/siming_character_dispatch_adapter.py`
- Test: `backend/tests/test_siming_character_dispatch_adapter.py`

**Interfaces:**
- Consumes: `AuthorityEvent` from `app.models.authority_event`.
- Produces: `SimingCatalystInput.from_authority_event(event: AuthorityEvent, target_actor_id: str) -> SimingCatalystInput`.
- Produces: `InnerPrompt.from_authority_event(event: AuthorityEvent) -> InnerPrompt`.
- Produces: `SimingCharacterDispatchResult.rejected_catalysts: list[CharacterDeliveryAuditSummary]` by reusing `audit_summaries` with status values `catalyst_rejected`, `expired`, and `target_unavailable`.

- [ ] **Step 1: Write failing catalyst conversion test**

Add this import to `backend/tests/test_siming_character_dispatch_adapter.py`:

```python
from app.models.siming_catalyst import SimingCatalystInput
```

Add this test:

```python
def test_fact_reveal_creates_catalyst_input() -> None:
    runtime = _local_runtime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime)
    event = make_siming_event(event_type="siming.fact_reveal", target_ids=["char_a"])
    event.payload.update(
        {
            "target_actor_id": "char_a",
            "target_environment_id": "env_lamp",
            "presentation_hint": "the lamp flicker is now visible",
            "evidence_refs": ["authority_event:visual_fact:300"],
        }
    )

    result = adapter.dispatch(event)

    assert len(result.delivery_inputs) == 1
    catalyst = SimingCatalystInput.from_authority_event(event, target_actor_id="char_a")
    assert catalyst.catalyst_type == "fact_reveal"
    assert catalyst.target_actor_id == "char_a"
    assert catalyst.target_environment_id == "env_lamp"
    assert catalyst.presentation_hint == "the lamp flicker is now visible"
    assert catalyst.evidence_refs == ["authority_event:visual_fact:300"]
```

Run: `pytest backend/tests/test_siming_character_dispatch_adapter.py::test_fact_reveal_creates_catalyst_input -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.siming_catalyst'`.

- [ ] **Step 2: Write failing AI impulse tests**

Add this helper to the test file:

```python
def make_impulse_event(*, impulse_axis: str = "narrative", intensity: float = 0.2) -> AuthorityEvent:
    event = make_siming_event(event_type="siming.impulse", target_ids=["char_a"])
    event.payload.update(
        {
            "target_actor_id": "char_a",
            "target_object_id": "obj_letter",
            "presentation_hint": "a sudden urge to check the letter",
            "impulse_axis": impulse_axis,
            "impulse_label": "check_letter",
            "intensity": intensity,
            "evidence_refs": ["public_fact:letter_seen"],
        }
    )
    return event
```

Add this test:

```python
def test_impulse_event_creates_ai_impulse_hint_for_each_axis() -> None:
    for axis in ["narrative", "relation", "action"]:
        event = make_impulse_event(impulse_axis=axis)

        catalyst = SimingCatalystInput.from_authority_event(event, target_actor_id="char_a")

        assert catalyst.catalyst_type == "impulse_hint"
        assert catalyst.impulse_axis == axis
        assert catalyst.impulse_label == "check_letter"
        assert catalyst.intensity == 0.2
```

Run: `pytest backend/tests/test_siming_character_dispatch_adapter.py::test_impulse_event_creates_ai_impulse_hint_for_each_axis -v`

Expected: FAIL because `SimingCatalystInput` is not implemented.

- [ ] **Step 3: Write failing catalyst rejection tests**

Add these tests:

```python
def test_impulse_hint_rejects_over_limit_intensity_before_runtime_ingress() -> None:
    runtime = _local_runtime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime)
    event = make_impulse_event(intensity=0.36)

    result = adapter.dispatch(event)

    assert result.delivery_inputs == []
    assert result.commands_by_actor == {}
    assert len(result.audit_summaries) == 1
    assert result.audit_summaries[0].actor_id == "char_a"
    assert result.audit_summaries[0].status == "catalyst_rejected"
```

```python
def test_impulse_hint_requires_target_or_situation_and_evidence() -> None:
    runtime = _local_runtime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime)
    event = make_impulse_event()
    event.payload.pop("target_actor_id")
    event.payload.pop("target_object_id")
    event.payload.pop("evidence_refs")

    result = adapter.dispatch(event)

    assert result.delivery_inputs == []
    assert result.commands_by_actor == {}
    assert len(result.audit_summaries) == 1
    assert result.audit_summaries[0].status == "catalyst_rejected"
```

Run: `pytest backend/tests/test_siming_character_dispatch_adapter.py::test_impulse_hint_rejects_over_limit_intensity_before_runtime_ingress backend/tests/test_siming_character_dispatch_adapter.py::test_impulse_hint_requires_target_or_situation_and_evidence -v`

Expected: FAIL because catalyst validation is not implemented.

- [ ] **Step 4: Write failing forbidden-field tests**

Add this test:

```python
import pytest
```

```python
@pytest.mark.parametrize(
    "field_name",
    [
        "actor_control_frames",
        "action_request_bundle",
        "character_agent_execution",
        "physical_success",
        "world_mutation",
        "private_memory_patch",
        "selected_intent",
        "command_type",
        "low_level_motion",
    ],
)
def test_catalyst_rejects_forbidden_fields(field_name: str) -> None:
    runtime = _local_runtime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime)
    event = make_impulse_event()
    event.payload[field_name] = "forbidden"

    result = adapter.dispatch(event)

    assert result.delivery_inputs == []
    assert result.commands_by_actor == {}
    assert len(result.audit_summaries) == 1
    assert result.audit_summaries[0].status == "catalyst_rejected"
```

Run: `pytest backend/tests/test_siming_character_dispatch_adapter.py::test_catalyst_rejects_forbidden_fields -v`

Expected: FAIL because forbidden catalyst payload keys are not rejected.

- [ ] **Step 5: Implement catalyst and inner prompt models**

Create `backend/app/models/siming_catalyst.py`:

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.authority_event import AuthorityEvent


CatalystType = Literal[
    "fact_reveal",
    "attention_prompt",
    "opportunity_hint",
    "pressure_hint",
    "impulse_hint",
]
ImpulseAxis = Literal["narrative", "relation", "action"]
PresentationEffect = Literal[
    "narration_text",
    "subtle_audio_cue",
    "screen_vignette",
    "controller_rumble",
    "short_ui_hint",
]

FORBIDDEN_CATALYST_PAYLOAD_FIELDS = {
    "actor_control_frames",
    "action_request_bundle",
    "character_agent_execution",
    "physical_success",
    "world_mutation",
    "private_memory_patch",
    "selected_intent",
    "command_type",
    "low_level_motion",
}

FORBIDDEN_INNER_PROMPT_PAYLOAD_FIELDS = FORBIDDEN_CATALYST_PAYLOAD_FIELDS | {
    "focus_target_id",
    "movement_input",
    "interact_input",
    "backend_action_request",
    "object_state_patch",
    "environment_state_patch",
}


def _optional_str(value: object) -> str | None:
    rendered = str(value or "").strip()
    return rendered or None


def _required_str(value: object, fallback: str = "") -> str:
    rendered = str(value or fallback or "").strip()
    if not rendered:
        raise ValueError("required string field is empty")
    return rendered


class SimingCatalystInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalyst_id: str
    catalyst_type: CatalystType
    impulse_axis: ImpulseAxis | None = None
    impulse_label: str | None = None
    room_id: str
    scene_id: str
    zone_id: str
    target_actor_id: str
    target_object_id: str | None = None
    target_environment_id: str | None = None
    source_authority_event_id: str
    situation_snapshot_id: str | None = None
    presentation_hint: str | None = None
    pressure_hint: str | None = None
    salience_boost: float | None = None
    intensity: float = 0.0
    reason_scope: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    causation_id: str
    correlation_id: str
    producer_ts: int

    @model_validator(mode="before")
    @classmethod
    def reject_forbidden_fields(cls, value: object) -> object:
        if isinstance(value, dict):
            present = sorted(FORBIDDEN_CATALYST_PAYLOAD_FIELDS.intersection(value.keys()))
            if present:
                raise ValueError(f"forbidden catalyst field(s): {', '.join(present)}")
        return value

    @model_validator(mode="after")
    def validate_boundary(self) -> "SimingCatalystInput":
        if self.intensity > 0.35:
            raise ValueError("catalyst intensity exceeds 0.35")
        if self.catalyst_type == "impulse_hint":
            if self.impulse_axis not in {"narrative", "relation", "action"}:
                raise ValueError("impulse_hint requires impulse_axis")
            has_target_or_situation = any(
                [
                    self.target_actor_id,
                    self.target_object_id,
                    self.target_environment_id,
                    self.situation_snapshot_id,
                ]
            )
            if not has_target_or_situation:
                raise ValueError("impulse_hint requires target or situation_snapshot_id")
            if not self.evidence_refs:
                raise ValueError("impulse_hint requires evidence_refs")
        return self

    @classmethod
    def from_authority_event(cls, event: AuthorityEvent, *, target_actor_id: str) -> "SimingCatalystInput":
        raw_type = event.event_type.removeprefix("siming.")
        catalyst_type = {
            "impulse": "impulse_hint",
            "opportunity": "opportunity_hint",
            "fact_reveal": "fact_reveal",
        }.get(raw_type, raw_type)
        data = dict(event.payload)
        data.update(
            {
                "catalyst_id": str(event.payload.get("message_id", "") or event.event_id),
                "catalyst_type": catalyst_type,
                "room_id": event.room_id,
                "scene_id": event.scene_id,
                "zone_id": event.zone_id,
                "target_actor_id": target_actor_id,
                "source_authority_event_id": event.event_id,
                "causation_id": event.causation_id,
                "correlation_id": event.correlation_id,
                "producer_ts": event.producer_ts,
            }
        )
        return cls.model_validate(data)


class InnerPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_id: str
    prompt_type: Literal["inner_prompt"] = "inner_prompt"
    room_id: str
    scene_id: str
    zone_id: str
    target_actor_id: str
    source_authority_event_id: str
    situation_snapshot_id: str | None = None
    prompt_text: str
    intensity: float = 0.0
    evidence_refs: list[str] = Field(default_factory=list)
    player_facing: Literal[True] = True
    non_authoritative: Literal[True] = True
    presentation_effects: list[PresentationEffect] = Field(default_factory=list)
    causation_id: str
    correlation_id: str
    producer_ts: int

    @model_validator(mode="before")
    @classmethod
    def reject_forbidden_fields(cls, value: object) -> object:
        if isinstance(value, dict):
            present = sorted(FORBIDDEN_INNER_PROMPT_PAYLOAD_FIELDS.intersection(value.keys()))
            if present:
                raise ValueError(f"forbidden inner_prompt field(s): {', '.join(present)}")
        return value

    @model_validator(mode="after")
    def validate_prompt_boundary(self) -> "InnerPrompt":
        if self.intensity > 0.35:
            raise ValueError("inner_prompt intensity exceeds 0.35")
        if not self.situation_snapshot_id and not self.evidence_refs:
            raise ValueError("inner_prompt requires situation_snapshot_id or evidence_refs")
        return self

    @classmethod
    def from_authority_event(cls, event: AuthorityEvent) -> "InnerPrompt":
        data = dict(event.payload)
        prompt_text = _required_str(data.get("prompt_text") or data.get("presentation_hint"))
        data.update(
            {
                "prompt_id": str(event.payload.get("message_id", "") or event.event_id),
                "prompt_type": "inner_prompt",
                "room_id": event.room_id,
                "scene_id": event.scene_id,
                "zone_id": event.zone_id,
                "target_actor_id": _required_str(data.get("target_actor_id")),
                "source_authority_event_id": event.event_id,
                "prompt_text": prompt_text,
                "player_facing": True,
                "non_authoritative": True,
                "causation_id": event.causation_id,
                "correlation_id": event.correlation_id,
                "producer_ts": event.producer_ts,
            }
        )
        return cls.model_validate(data)
```

- [ ] **Step 6: Route adapter dispatch through catalyst validation**

Modify `backend/app/services/siming_character_dispatch_adapter.py`:

```python
from pydantic import ValidationError

from app.models.siming_catalyst import InnerPrompt, SimingCatalystInput
```

Add supported event type:

```python
SUPPORTED_SIMING_EVENT_TYPES = {
    "siming.impulse",
    "siming.opportunity",
    "siming.fact_reveal",
    "siming.inner_prompt",
}
```

In `dispatch()`, before runtime support checks, add:

```python
            if event.event_type == "siming.inner_prompt":
                try:
                    InnerPrompt.from_authority_event(event)
                except (ValueError, ValidationError):
                    result.audit_summaries.append(
                        CharacterDeliveryAuditSummary(
                            message_id=message_id,
                            delivery_id=delivery_id,
                            actor_id=actor_id,
                            status="catalyst_rejected",
                            producer_ts=event.producer_ts,
                            causation_id=event.causation_id,
                            correlation_id=event.correlation_id,
                        )
                    )
                continue

            try:
                catalyst = SimingCatalystInput.from_authority_event(event, target_actor_id=actor_id)
            except (ValueError, ValidationError):
                result.audit_summaries.append(
                    CharacterDeliveryAuditSummary(
                        message_id=message_id,
                        delivery_id=delivery_id,
                        actor_id=actor_id,
                        status="catalyst_rejected",
                        producer_ts=event.producer_ts,
                        causation_id=event.causation_id,
                        correlation_id=event.correlation_id,
                    )
                )
                continue
```

Then build `SimingCharacterCompatibilityInput` from `catalyst`:

```python
            delivery_input = SimingCharacterCompatibilityInput(
                message_id=message_id,
                delivery_id=delivery_id,
                actor_id=actor_id,
                input_type="siming_high_level_message",
                band=cast("str", catalyst.catalyst_type),
                producer_ts=catalyst.producer_ts,
                room_id=catalyst.room_id,
                scene_id=catalyst.scene_id,
                zone_id=catalyst.zone_id,
                causation_id=catalyst.causation_id,
                correlation_id=catalyst.correlation_id,
                presentation_hint=catalyst.presentation_hint,
                target_actor_id=actor_id,
                target_object_id=catalyst.target_object_id,
                target_environment_id=catalyst.target_environment_id,
            )
```

- [ ] **Step 7: Write failing player inner prompt runtime isolation test**

Add this test:

```python
def test_player_inner_prompt_is_validated_but_not_dispatched_to_character_runtime() -> None:
    runtime = _local_runtime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime)
    event = make_siming_event(event_type="siming.inner_prompt", target_ids=["char_a"])
    event.payload.update(
        {
            "target_actor_id": "char_a",
            "prompt_text": "Something about the letter feels wrong.",
            "intensity": 0.2,
            "evidence_refs": ["public_fact:letter_seen"],
            "player_facing": True,
            "non_authoritative": True,
            "presentation_effects": ["narration_text"],
        }
    )

    result = adapter.dispatch(event)

    assert result.delivery_inputs == []
    assert result.commands_by_actor == {}
    assert result.audit_summaries == []
    assert runtime.get_private_snapshot("char_a") is None
```

Run: `pytest backend/tests/test_siming_character_dispatch_adapter.py::test_player_inner_prompt_is_validated_but_not_dispatched_to_character_runtime -v`

Expected: PASS after Step 6.

- [ ] **Step 8: Verify catalyst adapter tests pass**

Run: `pytest backend/tests/test_siming_character_dispatch_adapter.py -v`

Expected: PASS.

- [ ] **Step 9: Commit Task 1**

```powershell
git add backend/app/models/siming_catalyst.py backend/app/services/siming_character_dispatch_adapter.py backend/tests/test_siming_character_dispatch_adapter.py
git commit -m "feat: harden siming catalyst dispatch contract"
```

---

### Task 2: System L6 Consumer Routing And Replay Semantics

**Files:**
- Modify: `backend/app/services/authority_event_bus.py`
- Test: `backend/tests/test_authority_event_bus.py`

**Interfaces:**
- Consumes: `AuthorityEvent`.
- Produces: `subscribe(event_type: str, consumer: EventConsumer, *, consumer_id: str = "*") -> None`.
- Produces: `list_events(room_id: str | None = None, event_type: str | None = None, include_realtime: bool = False, current_only: bool = True) -> list[AuthorityEvent]`.

- [ ] **Step 1: Write failing consumer identity routing test**

Add this test to `backend/tests/test_authority_event_bus.py`:

```python
def test_bus_routes_targeted_events_by_consumer_identity() -> None:
    bus = InMemoryAuthorityEventBus()
    siming_seen: list[AuthorityEvent] = []
    frontend_seen: list[AuthorityEvent] = []
    bus.subscribe("visual_fact_event", siming_seen.append, consumer_id="siming")
    bus.subscribe("visual_fact_event", frontend_seen.append, consumer_id="frontend_projector")

    bus.publish(make_authority_event())

    assert [event.event_id for event in siming_seen] == ["evt:1"]
    assert frontend_seen == []
```

Run: `pytest backend/tests/test_authority_event_bus.py::test_bus_routes_targeted_events_by_consumer_identity -v`

Expected: FAIL with `TypeError: InMemoryAuthorityEventBus.subscribe() got an unexpected keyword argument 'consumer_id'`.

- [ ] **Step 2: Write failing durability and TTL tests**

Add these tests:

```python
def test_realtime_event_delivers_but_is_not_in_current_replay() -> None:
    bus = InMemoryAuthorityEventBus()
    seen: list[AuthorityEvent] = []
    bus.subscribe("visual_fact_event", seen.append, consumer_id="siming")

    bus.publish(make_authority_event(durability="realtime"))

    assert [event.event_id for event in seen] == ["evt:1"]
    assert bus.list_events(event_type="visual_fact_event") == []
    assert [event.event_id for event in bus.list_events(event_type="visual_fact_event", include_realtime=True)] == ["evt:1"]
```

```python
def test_expired_ttl_event_is_excluded_from_current_replay() -> None:
    bus = InMemoryAuthorityEventBus(now_ts_provider=lambda: 1000)
    bus.publish(make_authority_event(event_id="evt:expired", producer_ts=100, ttl=10))
    bus.publish(make_authority_event(event_id="evt:current", producer_ts=990, ttl=20))

    current = bus.list_events(event_type="visual_fact_event")

    assert [event.event_id for event in current] == ["evt:current"]
    assert [event.event_id for event in bus.list_events(event_type="visual_fact_event", current_only=False)] == [
        "evt:expired",
        "evt:current",
    ]
```

Run: `pytest backend/tests/test_authority_event_bus.py::test_realtime_event_delivers_but_is_not_in_current_replay backend/tests/test_authority_event_bus.py::test_expired_ttl_event_is_excluded_from_current_replay -v`

Expected: FAIL because `now_ts_provider`, `consumer_id`, `include_realtime`, and `current_only` do not exist.

- [ ] **Step 3: Extend bus protocol and subscriber records**

Modify `backend/app/services/authority_event_bus.py`:

```python
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
```

Add:

```python
@dataclass(frozen=True, slots=True)
class AuthorityEventSubscriber:
    consumer_id: str
    consumer: EventConsumer
```

Change protocol signatures:

```python
class AuthorityEventBusPort(Protocol):
    def publish(self, event: AuthorityEvent) -> None:
        raise NotImplementedError

    def subscribe(self, event_type: str, consumer: EventConsumer, *, consumer_id: str = "*") -> None:
        raise NotImplementedError

    def list_events(
        self,
        *,
        room_id: str | None = None,
        event_type: str | None = None,
        include_realtime: bool = False,
        current_only: bool = True,
    ) -> list[AuthorityEvent]:
        raise NotImplementedError
```

- [ ] **Step 4: Implement route matching and current replay filtering**

Replace `InMemoryAuthorityEventBus` with this shape:

```python
class InMemoryAuthorityEventBus:
    def __init__(self, *, now_ts_provider: Callable[[], int] | None = None) -> None:
        self._events: list[AuthorityEvent] = []
        self._subscribers: dict[str, list[AuthorityEventSubscriber]] = {}
        self._now_ts_provider = now_ts_provider or (lambda: 0)

    def publish(self, event: AuthorityEvent) -> None:
        stored = event.model_copy(deep=True)
        self._events.append(stored)
        for subscriber in self._subscribers.get(event.event_type, []):
            if self._matches_route(stored, subscriber.consumer_id):
                subscriber.consumer(stored.model_copy(deep=True))

    def subscribe(self, event_type: str, consumer: EventConsumer, *, consumer_id: str = "*") -> None:
        self._subscribers.setdefault(event_type, []).append(
            AuthorityEventSubscriber(consumer_id=consumer_id, consumer=consumer)
        )

    def list_events(
        self,
        *,
        room_id: str | None = None,
        event_type: str | None = None,
        include_realtime: bool = False,
        current_only: bool = True,
    ) -> list[AuthorityEvent]:
        events = self._events
        if room_id is not None:
            events = [event for event in events if event.room_id == room_id]
        if event_type is not None:
            events = [event for event in events if event.event_type == event_type]
        if not include_realtime:
            events = [event for event in events if event.durability != "realtime"]
        if current_only:
            events = [event for event in events if not self._is_expired(event)]
        return [event.model_copy(deep=True) for event in events]

    def _matches_route(self, event: AuthorityEvent, consumer_id: str) -> bool:
        if consumer_id == "*":
            return True
        audience_mode = str(event.routing.audience_mode or "")
        if audience_mode in {"broadcast", "authority_broadcast"}:
            return True
        return consumer_id in set(event.routing.target_ids)

    def _is_expired(self, event: AuthorityEvent) -> bool:
        if event.ttl is None:
            return False
        return self._now_ts_provider() > event.producer_ts + event.ttl
```

- [ ] **Step 5: Preserve existing bus tests**

Run: `pytest backend/tests/test_authority_event_bus.py -v`

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```powershell
git add backend/app/services/authority_event_bus.py backend/tests/test_authority_event_bus.py
git commit -m "feat: execute authority event bus routing semantics"
```

---

### Task 3: Projector Wiring As A Routed Consumer

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/frontend_authority_event_projection.py`
- Modify: `backend/app/services/siming_event_pipeline.py`
- Test: `backend/tests/test_authority_event_bus.py`
- Test: `backend/tests/test_siming_event_pipeline.py`

**Interfaces:**
- Consumes: routed `AuthorityEvent` delivery from `InMemoryAuthorityEventBus`.
- Produces: unchanged frontend envelopes from `FrontendAuthorityEventProjector.drain()`.
- Produces: `inner_prompt` frontend envelope with `message_type="siming_inner_prompt"`.

- [ ] **Step 1: Add focused projector route test**

Add to `backend/tests/test_authority_event_bus.py`:

```python
def test_projector_receives_only_routed_events() -> None:
    bus = InMemoryAuthorityEventBus()
    projector_seen: list[AuthorityEvent] = []
    bus.subscribe("siming.fact_reveal", projector_seen.append, consumer_id="frontend_projector")

    bus.publish(
        make_authority_event(
            event_id="evt:siming-only",
            event_type="siming.fact_reveal",
            routing={"audience_mode": "targeted", "routing_mode": "event_type", "target_ids": ["siming"]},
        )
    )
    bus.publish(
        make_authority_event(
            event_id="evt:frontend",
            event_type="siming.fact_reveal",
            routing={
                "audience_mode": "targeted",
                "routing_mode": "event_type",
                "target_ids": ["frontend_projector"],
            },
        )
    )

    assert [event.event_id for event in projector_seen] == ["evt:frontend"]
```

Run: `pytest backend/tests/test_authority_event_bus.py::test_projector_receives_only_routed_events -v`

Expected: PASS after Task 2.

- [ ] **Step 2: Update `reset_runtime_state()` subscription wiring**

In `backend/app/main.py`, change subscriptions that currently look like:

```python
AUTHORITY_EVENT_BUS.subscribe("visual_fact_event", SIMING_PIPELINE.handle_event)
```

to:

```python
AUTHORITY_EVENT_BUS.subscribe("visual_fact_event", SIMING_PIPELINE.handle_event, consumer_id="siming")
```

For projector subscriptions, use:

```python
AUTHORITY_EVENT_BUS.subscribe("siming.fact_reveal", FRONTEND_AUTHORITY_EVENT_PROJECTOR.handle_event, consumer_id="frontend_projector")
AUTHORITY_EVENT_BUS.subscribe("siming.visual_observability_request", FRONTEND_AUTHORITY_EVENT_PROJECTOR.handle_event, consumer_id="frontend_projector")
AUTHORITY_EVENT_BUS.subscribe("siming.inner_prompt", FRONTEND_AUTHORITY_EVENT_PROJECTOR.handle_event, consumer_id="frontend_projector")
```

- [ ] **Step 3: Add inner prompt projection test**

Add to `backend/tests/test_siming_event_pipeline.py`:

```python
def test_player_inner_prompt_projects_to_frontend_only() -> None:
    from app.services.frontend_authority_event_projection import FrontendAuthorityEventProjector

    projector = FrontendAuthorityEventProjector()
    event = AuthorityEvent.model_validate(
        {
            "event_id": "siming:inner_prompt:1",
            "event_type": "siming.inner_prompt",
            "producer_ts": 900,
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "source": {"layer": "L2", "system": "siming.dispatcher", "actor_id": None},
            "routing": {
                "audience_mode": "targeted",
                "routing_mode": "event_type",
                "target_ids": ["frontend_projector"],
            },
            "priority": "p1",
            "ttl": 5000,
            "durability": "replayable",
            "causation_id": "cause:inner:1",
            "correlation_id": "corr:inner:1",
            "payload": {
                "target_actor_id": "player",
                "prompt_text": "Something about the letter feels wrong.",
                "intensity": 0.2,
                "evidence_refs": ["public_fact:letter_seen"],
                "player_facing": True,
                "non_authoritative": True,
                "presentation_effects": ["narration_text"],
            },
        }
    )

    projector.handle_event(event)

    assert projector.drain() == [
        {
            "message_type": "siming_inner_prompt",
            "payload": {
                "prompt_id": "siming:inner_prompt:1",
                "target_actor_id": "player",
                "prompt_text": "Something about the letter feels wrong.",
                "intensity": 0.2,
                "presentation_effects": ["narration_text"],
                "authority_event_id": "siming:inner_prompt:1",
                "causation_id": "cause:inner:1",
                "correlation_id": "corr:inner:1",
                "producer_ts": 900,
            },
        }
    ]
```

Run: `pytest backend/tests/test_siming_event_pipeline.py::test_player_inner_prompt_projects_to_frontend_only -v`

Expected: FAIL because projector does not handle `siming.inner_prompt`.

- [ ] **Step 4: Implement presentation-only projection**

Modify `backend/app/services/frontend_authority_event_projection.py`:

```python
FRONTEND_AUTHORITY_EVENT_TYPES = {
    "siming.visual_observability_request",
    "siming.fact_reveal",
    "siming.inner_prompt",
}
```

Add:

```python
def project_authority_event_as_inner_prompt(event: AuthorityEvent) -> dict[str, object] | None:
    if event.event_type != "siming.inner_prompt":
        return None
    payload = dict(event.payload)
    return {
        "message_type": "siming_inner_prompt",
        "payload": {
            "prompt_id": str(payload.get("message_id", "") or event.event_id),
            "target_actor_id": str(payload.get("target_actor_id", "") or ""),
            "prompt_text": str(payload.get("prompt_text", "") or payload.get("presentation_hint", "") or ""),
            "intensity": float(payload.get("intensity", 0.0) or 0.0),
            "presentation_effects": list(payload.get("presentation_effects", []) or []),
            "authority_event_id": event.event_id,
            "causation_id": event.causation_id,
            "correlation_id": event.correlation_id,
            "producer_ts": event.producer_ts,
        },
    }
```

Call it before generic Siming output projection in `handle_event()`:

```python
        envelope = project_authority_event_as_inner_prompt(event)
        if envelope is not None:
            self._pending.append(envelope)
            return
```

- [ ] **Step 5: Verify projector and pipeline compatibility**

Run:

```powershell
pytest backend/tests/test_authority_event_bus.py backend/tests/test_siming_event_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```powershell
git add backend/app/main.py backend/app/services/frontend_authority_event_projection.py backend/app/services/siming_event_pipeline.py backend/tests/test_authority_event_bus.py backend/tests/test_siming_event_pipeline.py
git commit -m "feat: route frontend projector through l6 identity"
```

---

### Task 4: Situation Provenance For Global Siming Decisions

**Files:**
- Modify: `backend/app/services/siming_global_situation.py`
- Modify: `backend/app/services/siming_runtime.py`
- Modify: `backend/app/services/siming_read_model.py`
- Test: `backend/tests/test_siming_global_situation.py`
- Test: `backend/tests/test_siming_global_situation_runtime.py`
- Test: `backend/tests/test_siming_event_pipeline.py`

**Interfaces:**
- Consumes: public authority events, public facts, world results, VLA advisory refs.
- Produces: a stable `situation_snapshot_id` on new global-decision Siming outputs.
- Produces: conflict refs for VLA advisory conflicts without replacing authoritative evidence.

- [ ] **Step 1: Inspect current global situation tests and names**

Run:

```powershell
pytest backend/tests/test_siming_global_situation.py backend/tests/test_siming_global_situation_runtime.py -v
```

Expected: PASS before edits. If either file does not exist in this checkout, run `rg -n "SimingGlobalSituation|character_private|character_mm|VLA" backend/tests` and use the matching test file for the next steps.

- [ ] **Step 2: Write failing provenance test**

Add to the existing global situation test file that already constructs snapshots:

```python
def test_global_decision_records_situation_snapshot_id() -> None:
    layer = SimingGlobalSituationLayer()
    snapshot = layer.assemble_snapshot(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        public_evidence_refs=["authority_event:visual_fact:300"],
        actor_refs=["char_a", "char_b"],
        vla_advisory_refs=["vla_advisory:lamp_shadow"],
    )

    assert snapshot.snapshot_id
    assert "authority_event:visual_fact:300" in snapshot.public_evidence_refs
```

Run the exact test path used in Step 1.

Expected: FAIL if `assemble_snapshot(...)` does not accept these exact public provenance arguments or does not expose `snapshot_id` and `public_evidence_refs`.

- [ ] **Step 3: Write boundary tests for private refs and VLA conflict refs**

Add:

```python
def test_global_situation_rejects_private_character_refs() -> None:
    layer = SimingGlobalSituationLayer()

    with pytest.raises(ValueError, match="private"):
        layer.assemble_snapshot(
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            public_evidence_refs=["character_mm:char_a:memory:1"],
            actor_refs=["char_a"],
            vla_advisory_refs=[],
        )
```

Add:

```python
def test_vla_advisory_conflict_stays_as_conflict_ref() -> None:
    layer = SimingGlobalSituationLayer()
    snapshot = layer.assemble_snapshot(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        public_evidence_refs=["authority_event:world_result:1"],
        actor_refs=["char_a"],
        vla_advisory_refs=["vla_advisory:conflict:shadow_direction"],
    )

    assert "authority_event:world_result:1" in snapshot.public_evidence_refs
    assert "vla_advisory:conflict:shadow_direction" in snapshot.conflict_refs
```

Run the exact test path used in Step 1.

Expected: FAIL until the layer exposes the provenance contract.

- [ ] **Step 4: Add public provenance fields without rewriting the runtime loop**

Implement the smallest additive contract in `backend/app/services/siming_global_situation.py`:

```python
@dataclass(frozen=True, slots=True)
class SimingGlobalSituationSnapshot:
    snapshot_id: str
    room_id: str
    scene_id: str
    zone_id: str
    public_evidence_refs: tuple[str, ...]
    actor_refs: tuple[str, ...]
    vla_advisory_refs: tuple[str, ...]
    conflict_refs: tuple[str, ...]
```

Add private ref check:

```python
def _reject_private_refs(refs: list[str] | tuple[str, ...]) -> None:
    private_prefixes = ("character_mm:", "character_private")
    for ref in refs:
        if str(ref).startswith(private_prefixes):
            raise ValueError(f"private ref is not allowed in SimingGlobalSituationSnapshot: {ref}")
```

Add or adapt `assemble_snapshot(...)`:

```python
def assemble_snapshot(
    self,
    *,
    room_id: str,
    scene_id: str,
    zone_id: str,
    public_evidence_refs: list[str],
    actor_refs: list[str],
    vla_advisory_refs: list[str],
) -> SimingGlobalSituationSnapshot:
    _reject_private_refs(public_evidence_refs)
    conflict_refs = tuple(ref for ref in vla_advisory_refs if ":conflict:" in ref)
    snapshot_id = f"siming_global_situation:{room_id}:{scene_id}:{zone_id}:{len(public_evidence_refs)}:{len(vla_advisory_refs)}"
    return SimingGlobalSituationSnapshot(
        snapshot_id=snapshot_id,
        room_id=room_id,
        scene_id=scene_id,
        zone_id=zone_id,
        public_evidence_refs=tuple(public_evidence_refs),
        actor_refs=tuple(actor_refs),
        vla_advisory_refs=tuple(vla_advisory_refs),
        conflict_refs=conflict_refs,
    )
```

If the file already has equivalent dataclasses, extend them instead of adding duplicate class names.

- [ ] **Step 5: Attach provenance to new global decision outputs only**

In `backend/app/services/siming_runtime.py`, where a new global situation decision is created after Step 4, add payload fields:

```python
"situation_snapshot_id": snapshot.snapshot_id,
"evidence_refs": list(snapshot.public_evidence_refs),
"conflict_refs": list(snapshot.conflict_refs),
```

Do not add this to old Phase0 compatibility branches unless those branches already have a snapshot in hand.

- [ ] **Step 6: Verify global situation tests**

Run:

```powershell
pytest backend/tests/test_siming_global_situation.py backend/tests/test_siming_global_situation_runtime.py backend/tests/test_siming_event_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit Task 4**

```powershell
git add backend/app/services/siming_global_situation.py backend/app/services/siming_runtime.py backend/app/services/siming_read_model.py backend/tests/test_siming_global_situation.py backend/tests/test_siming_global_situation_runtime.py backend/tests/test_siming_event_pipeline.py
git commit -m "feat: attach siming global situation provenance"
```

---

### Task 5: Documentation And Harness Notes

**Files:**
- Modify: `docs/架构/运行时/模块/SystemL6事件总线.md`
- Modify: `docs/架构/运行时/模块/Siming.md`
- Modify: `docs/架构/运行时/运行时覆盖矩阵.md`
- Modify: `docs/harness.md` only if profile evidence wording changes.

**Interfaces:**
- Consumes: implemented backend contracts from Tasks 1-4.
- Produces: updated architecture truth and verification guidance.

- [ ] **Step 1: Update System L6 docs**

In `docs/架构/运行时/模块/SystemL6事件总线.md`, document:

```text
第一阶段 L6 执行语义：
- consumer identity: siming / frontend_projector / audit / verification
- targeted route: non-broadcast event only reaches matching routing.target_ids
- replayable: stored and returned by current replay/list
- reliable: stored for audit-visible trace
- realtime: delivered to current consumers but excluded from current replay/list by default
- ttl: current replay/list filters expired events; audit storage is not physically cleaned
- FrontendAuthorityEventProjector is a consumer adapter, not route owner
```

- [ ] **Step 2: Update Siming docs**

In `docs/架构/运行时/模块/Siming.md`, document:

```text
SimingCatalystInput is the only high-level Siming -> AI-controlled Character contract.
Allowed catalyst_type values: fact_reveal, attention_prompt, opportunity_hint, pressure_hint, impulse_hint.
impulse_hint supports impulse_axis: narrative, relation, action.
impulse_hint and inner_prompt intensity must be <= 0.35.
player-controlled actors receive inner_prompt only through frontend presentation / narration.
inner_prompt is player-facing, non-authoritative, and presentation-only.
Siming catalyst payloads must not include actor_control_frames, action_request_bundle, character_agent_execution, physical_success, world_mutation, private_memory_patch, selected_intent, command_type, or low_level_motion.
New global director decisions must be backed by SimingGlobalSituationSnapshot provenance.
```

- [ ] **Step 3: Update coverage matrix**

In `docs/架构/运行时/运行时覆盖矩阵.md`, add rows or extend existing rows for:

```text
System L6 consumer identity -> backend/app/services/authority_event_bus.py -> backend/tests/test_authority_event_bus.py
Siming catalyst contract -> backend/app/models/siming_catalyst.py -> backend/tests/test_siming_character_dispatch_adapter.py
Player inner prompt projection -> backend/app/services/frontend_authority_event_projection.py -> backend/tests/test_siming_event_pipeline.py
Global situation provenance -> backend/app/services/siming_global_situation.py -> backend/tests/test_siming_global_situation*.py
```

- [ ] **Step 4: Verify docs profile**

Run: `python scripts/verification/harness.py --profile docs`

Expected: PASS with `overall_docs_passed=True`.

- [ ] **Step 5: Commit Task 5**

```powershell
git add docs/架构/运行时/模块/SystemL6事件总线.md docs/架构/运行时/模块/Siming.md docs/架构/运行时/运行时覆盖矩阵.md docs/harness.md
git commit -m "docs: record siming l6 boundary hardening"
```

---

### Task 6: Final Verification

**Files:**
- No planned source edits.
- Verification reports may be written under `.harness/verification/`.

**Interfaces:**
- Consumes: Tasks 1-5.
- Produces: focused pytest and harness evidence.

- [ ] **Step 1: Run focused backend tests**

Run:

```powershell
pytest backend/tests/test_authority_event_bus.py backend/tests/test_siming_event_pipeline.py backend/tests/test_siming_global_situation.py backend/tests/test_siming_global_situation_runtime.py backend/tests/test_siming_character_dispatch_adapter.py -v
```

Expected: PASS.

- [ ] **Step 2: Run backend contract harness**

Run: `python scripts/verification/harness.py --profile backend-contract`

Expected: PASS.

- [ ] **Step 3: Run boundaries harness**

Run: `python scripts/verification/harness.py --profile boundaries`

Expected: PASS.

- [ ] **Step 4: Run mainline runtime harness**

Run: `python scripts/verification/harness.py --profile mainline-unified-runtime`

Expected: PASS.

- [ ] **Step 5: Run Siming global situation harness**

Run: `python scripts/verification/harness.py --profile siming-global-situation-layer`

Expected: PASS.

- [ ] **Step 6: Run docs harness after any evidence file changes**

Run: `python scripts/verification/harness.py --profile docs`

Expected: PASS with `overall_docs_passed=True`.

- [ ] **Step 7: Commit verification evidence if harness creates required tracked evidence**

```powershell
git status --short
git add .harness/verification docs/harness.md
git commit -m "test: record siming l6 boundary verification"
```

Only commit `.harness/verification` files that are required by the repository evidence policy and actually changed.

---

## Self-Review

**Spec coverage:** This plan covers L6 consumer identity, targeted routing, durability, TTL current replay filtering, projector-as-adapter, `SimingCatalystInput`, `impulse_hint`, `inner_prompt`, forbidden fields, global situation provenance, private-boundary rejection, VLA conflict refs, Phase0 compatibility, docs, and harness verification.

**Placeholder scan:** The plan contains no open placeholder markers, no vague error-handling steps, and no unsupported cross-task shortcuts. Each code-changing task includes exact files, concrete tests, expected failures, implementation snippets, and verification commands.

**Type consistency:** The plan consistently uses `SimingCatalystInput.from_authority_event(...)`, `InnerPrompt.from_authority_event(...)`, `consumer_id`, `include_realtime`, `current_only`, `siming.inner_prompt`, and `message_type="siming_inner_prompt"` across tests, implementation, and docs.
