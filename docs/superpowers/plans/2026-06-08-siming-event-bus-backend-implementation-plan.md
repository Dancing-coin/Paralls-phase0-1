# Siming Event Bus Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the minimum backend authority event bus path for Siming while preserving the current Phase 0 WebSocket demo behavior.

**Architecture:** Introduce a hard `AuthorityEvent` envelope, an in-memory `AuthorityEventBusPort`, and a small Siming event pipeline made of consumer, runtime, producer, and audit writer components. Wire the current `/ws` handler through a Phase 0 adapter that dual-writes authority events while leaving existing observable WebSocket messages intact.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, pytest, existing Paralls harness profiles.

---

## Source Context

- Primary design: `docs/phase1/core/01-运行时核心/司命/19-司命接入事件总线后端设计.md`
- Current backend entry point: `backend/app/main.py`
- Current Siming Phase 0 service: `backend/app/services/siming_service.py`
- Current protocol models: `backend/app/models/player_input.py`, `backend/app/models/visual_fact.py`, `backend/app/models/world_result.py`, `backend/app/models/runtime_state.py`, `backend/app/models/siming_output.py`
- Current tests: `backend/tests/test_ws_protocol.py`, `backend/tests/test_visual_fact_pipeline.py`, `backend/tests/test_siming_service.py`
- Static verification: `scripts/verification/check_backend_contract.py`, `scripts/verification/check_boundaries.py`

## Architecture Map Alignment

The implementation must match the current architecture map:

- `L1` remains Godot plus ESM/world fact production. Siming cannot write physical success facts.
- `L2` remains character intelligence plus Siming. Siming consumes authority events and emits high-level judgement events only.
- `L6` is the backend authority event bus layer. This plan creates the minimum in-memory form behind a port, not a parallel private Siming bus.
- `L3`, `L4`, and `L5` are reserved execution/presentation layers. This plan may publish request events for those layers, but must not implement real L3/L4/L5 orchestration.

## Non-Goals

- No NATS JetStream adapter.
- No Redis or PostgreSQL runtime dependency.
- No replacement of the existing `/ws` message contract.
- No deletion of `SimingService` or current `siming_output` messages.
- No Godot scene, GDScript, animation, skeleton, physics, or presentation bus rewrite.
- No full long-horizon narrative search or multi-agent framework integration.

## File Structure

Create these backend model files:

- `backend/app/models/authority_event.py`: public authority event envelope, nested `source` and `routing` schemas, hard envelope validation.
- `backend/app/models/siming_event.py`: Siming event-pipeline domain objects used between consumer, runtime, producer, and audit writer.

Create these backend service files:

- `backend/app/services/authority_event_bus.py`: `AuthorityEventBusPort` protocol and `InMemoryAuthorityEventBus`.
- `backend/app/services/siming_event_consumer.py`: filters allowed authority events and converts them into `SimingInput` objects.
- `backend/app/services/siming_runtime.py`: minimum deterministic Siming tick that emits fairness snapshots, decisions, no-action records, and environment rejection audit records.
- `backend/app/services/siming_event_producer.py`: maps Siming outputs to official authority bus event families.
- `backend/app/services/siming_audit_writer.py`: in-memory audit writer with idempotency and correction append behavior.
- `backend/app/services/siming_event_pipeline.py`: local orchestration of consumer, runtime, producer, and audit writer.
- `backend/app/services/phase0_authority_event_adapter.py`: converts current Phase 0 model objects into authority events without growing `main.py`.

Create these backend tests:

- `backend/tests/test_authority_event.py`
- `backend/tests/test_authority_event_bus.py`
- `backend/tests/test_siming_event_consumer.py`
- `backend/tests/test_siming_runtime.py`
- `backend/tests/test_siming_event_producer.py`
- `backend/tests/test_siming_audit_writer.py`
- `backend/tests/test_siming_event_pipeline.py`
- `backend/tests/test_phase0_authority_event_adapter.py`
- `backend/tests/test_ws_authority_event_dual_write.py`

Modify these existing files:

- `backend/app/main.py`: initialize the bus pipeline in `reset_runtime_state()` and dual-write current Phase 0 events.
- `scripts/verification/check_backend_contract.py`: include authority event contracts in backend contract checks.
- `scripts/verification/tests/test_formal_profile_checks.py`: assert the new backend-contract result id.
- `scripts/verification/check_boundaries.py`: assert Siming uses the authority bus port and still emits high-level outputs only.
- `scripts/verification/tests/test_boundary_checks.py`: assert the new boundary result id.
- `docs/harness.md`: document that `backend-contract` now covers the authority event envelope and Siming bus edge.

---

## Task 1: AuthorityEvent Hard Schema

**Files:**
- Create: `backend/app/models/authority_event.py`
- Test: `backend/tests/test_authority_event.py`

- [ ] **Step 1: Write failing AuthorityEvent schema tests**

Add `backend/tests/test_authority_event.py`:

```python
import pytest
from pydantic import ValidationError

from app.models.authority_event import AuthorityEvent


def valid_event_dict() -> dict[str, object]:
    return {
        "event_id": "evt_visual_1",
        "event_type": "visual_fact_event",
        "producer_ts": 100,
        "room_id": "room_demo",
        "scene_id": "scene_demo",
        "zone_id": "zone_focus",
        "source": {
            "layer": "L1",
            "system": "visual_fact",
            "actor_id": "char_c",
        },
        "routing": {
            "audience_mode": "room",
            "routing_mode": "broadcast",
            "target_ids": ["siming"],
        },
        "priority": "p2",
        "ttl": 5000,
        "durability": "replayable",
        "causation_id": "visual_fact:100",
        "correlation_id": "visual_fact:100",
        "payload": {
            "fact_type": "light_level_drop",
            "target_environment_id": "env_lamp",
        },
    }


def test_authority_event_accepts_required_public_envelope() -> None:
    event = AuthorityEvent.model_validate(valid_event_dict())

    assert event.event_id == "evt_visual_1"
    assert event.source.system == "visual_fact"
    assert event.routing.target_ids == ["siming"]
    assert event.payload["fact_type"] == "light_level_drop"


@pytest.mark.parametrize(
    "missing_key",
    [
        "event_id",
        "event_type",
        "producer_ts",
        "room_id",
        "source",
        "routing",
        "causation_id",
        "correlation_id",
        "payload",
    ],
)
def test_authority_event_rejects_missing_required_envelope_keys(missing_key: str) -> None:
    payload = valid_event_dict()
    payload.pop(missing_key)

    with pytest.raises(ValidationError):
        AuthorityEvent.model_validate(payload)


@pytest.mark.parametrize("forbidden_key", ["world_ts", "sim_tick_ts"])
def test_authority_event_rejects_domain_time_at_public_envelope_root(forbidden_key: str) -> None:
    payload = valid_event_dict()
    payload[forbidden_key] = 123

    with pytest.raises(ValidationError, match=forbidden_key):
        AuthorityEvent.model_validate(payload)


@pytest.mark.parametrize("legacy_key", ["producer", "source_actor_id", "target_actor_ids"])
def test_authority_event_rejects_legacy_flat_envelope_fields(legacy_key: str) -> None:
    payload = valid_event_dict()
    payload[legacy_key] = "legacy"

    with pytest.raises(ValidationError, match=legacy_key):
        AuthorityEvent.model_validate(payload)


@pytest.mark.parametrize("priority", ["low", "urgent", "p4"])
def test_authority_event_rejects_unknown_priority(priority: str) -> None:
    payload = valid_event_dict()
    payload["priority"] = priority

    with pytest.raises(ValidationError):
        AuthorityEvent.model_validate(payload)


@pytest.mark.parametrize("durability", ["durable", "ephemeral", "memory"])
def test_authority_event_rejects_unknown_durability(durability: str) -> None:
    payload = valid_event_dict()
    payload["durability"] = durability

    with pytest.raises(ValidationError):
        AuthorityEvent.model_validate(payload)
```

- [ ] **Step 2: Run the failing schema tests**

Run from `backend/`:

```powershell
python -m pytest tests/test_authority_event.py -v
```

Expected: fail with `ModuleNotFoundError: No module named 'app.models.authority_event'`.

- [ ] **Step 3: Implement the hard authority envelope**

Create `backend/app/models/authority_event.py`:

```python
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Priority = Literal["p0", "p1", "p2", "p3"]
Durability = Literal["replayable", "reliable", "realtime"]


class AuthorityEventSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer: str
    system: str
    actor_id: str | None = None


class AuthorityEventRouting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    audience_mode: str
    routing_mode: str
    target_ids: list[str] = Field(default_factory=list)


class AuthorityEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: str
    producer_ts: int
    room_id: str
    scene_id: str
    zone_id: str
    source: AuthorityEventSource
    routing: AuthorityEventRouting
    priority: Priority
    ttl: int | None = None
    durability: Durability
    causation_id: str
    correlation_id: str
    payload: dict[str, Any]

    @model_validator(mode="before")
    @classmethod
    def reject_forbidden_public_envelope_fields(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value

        forbidden = {
            "world_ts",
            "sim_tick_ts",
            "producer",
            "source_actor_id",
            "target_actor_ids",
        }
        present = sorted(forbidden.intersection(value.keys()))
        if present:
            joined = ", ".join(present)
            raise ValueError(f"forbidden authority envelope field(s): {joined}")
        return value
```

- [ ] **Step 4: Verify the schema tests pass**

Run from `backend/`:

```powershell
python -m pytest tests/test_authority_event.py -v
```

Expected: all tests in `test_authority_event.py` pass.

- [ ] **Step 5: Commit Task 1**

```powershell
git add backend/app/models/authority_event.py backend/tests/test_authority_event.py
git commit -m "Add authority event envelope schema" -m "The Siming bus path needs a strict public envelope before any bus or runtime code can rely on replay and audit identifiers." -m "Constraint: world_ts and sim_tick_ts stay out of the public envelope" -m "Confidence: high" -m "Scope-risk: narrow" -m "Tested: python -m pytest tests/test_authority_event.py -v"
```

## Task 2: In-Memory Authority Event Bus Port

**Files:**
- Create: `backend/app/services/authority_event_bus.py`
- Test: `backend/tests/test_authority_event_bus.py`

- [ ] **Step 1: Write failing bus tests**

Add `backend/tests/test_authority_event_bus.py`:

```python
from app.models.authority_event import AuthorityEvent
from app.services.authority_event_bus import InMemoryAuthorityEventBus

from tests.test_authority_event import valid_event_dict


def make_event(event_id: str, event_type: str = "visual_fact_event") -> AuthorityEvent:
    payload = valid_event_dict()
    payload["event_id"] = event_id
    payload["event_type"] = event_type
    return AuthorityEvent.model_validate(payload)


def test_in_memory_bus_preserves_publish_order() -> None:
    bus = InMemoryAuthorityEventBus()
    bus.publish(make_event("evt_1"))
    bus.publish(make_event("evt_2", "esm_result_event"))

    assert [event.event_id for event in bus.list_events()] == ["evt_1", "evt_2"]


def test_in_memory_bus_returns_deep_copies() -> None:
    bus = InMemoryAuthorityEventBus()
    bus.publish(make_event("evt_1"))

    first_read = bus.list_events()[0]
    first_read.payload["fact_type"] = "mutated"

    second_read = bus.list_events()[0]
    assert second_read.payload["fact_type"] == "light_level_drop"


def test_in_memory_bus_filters_by_room_and_event_type() -> None:
    bus = InMemoryAuthorityEventBus()
    bus.publish(make_event("evt_1", "visual_fact_event"))
    bus.publish(make_event("evt_2", "esm_result_event"))

    assert [event.event_id for event in bus.list_events(event_type="esm_result_event")] == ["evt_2"]
    assert [event.event_id for event in bus.list_events(room_id="room_demo")] == ["evt_1", "evt_2"]


def test_in_memory_bus_invokes_exact_event_type_subscribers() -> None:
    bus = InMemoryAuthorityEventBus()
    received: list[str] = []
    bus.subscribe("visual_fact_event", lambda event: received.append(event.event_id))

    bus.publish(make_event("evt_1", "visual_fact_event"))
    bus.publish(make_event("evt_2", "esm_result_event"))

    assert received == ["evt_1"]
```

- [ ] **Step 2: Run the failing bus tests**

Run from `backend/`:

```powershell
python -m pytest tests/test_authority_event_bus.py -v
```

Expected: fail with `ModuleNotFoundError: No module named 'app.services.authority_event_bus'`.

- [ ] **Step 3: Implement bus port and in-memory adapter**

Create `backend/app/services/authority_event_bus.py`:

```python
from collections.abc import Callable
from typing import Protocol

from app.models.authority_event import AuthorityEvent


EventConsumer = Callable[[AuthorityEvent], None]


class AuthorityEventBusPort(Protocol):
    def publish(self, event: AuthorityEvent) -> None:
        raise NotImplementedError

    def subscribe(self, event_type: str, consumer: EventConsumer) -> None:
        raise NotImplementedError

    def list_events(self, *, room_id: str | None = None, event_type: str | None = None) -> list[AuthorityEvent]:
        raise NotImplementedError


class InMemoryAuthorityEventBus:
    def __init__(self) -> None:
        self._events: list[AuthorityEvent] = []
        self._subscribers: dict[str, list[EventConsumer]] = {}

    def publish(self, event: AuthorityEvent) -> None:
        stored = event.model_copy(deep=True)
        self._events.append(stored)
        for consumer in self._subscribers.get(event.event_type, []):
            consumer(stored.model_copy(deep=True))

    def subscribe(self, event_type: str, consumer: EventConsumer) -> None:
        self._subscribers.setdefault(event_type, []).append(consumer)

    def list_events(self, *, room_id: str | None = None, event_type: str | None = None) -> list[AuthorityEvent]:
        events = self._events
        if room_id is not None:
            events = [event for event in events if event.room_id == room_id]
        if event_type is not None:
            events = [event for event in events if event.event_type == event_type]
        return [event.model_copy(deep=True) for event in events]
```

- [ ] **Step 4: Verify bus tests pass**

Run from `backend/`:

```powershell
python -m pytest tests/test_authority_event_bus.py -v
```

Expected: all tests in `test_authority_event_bus.py` pass.

- [ ] **Step 5: Commit Task 2**

```powershell
git add backend/app/services/authority_event_bus.py backend/tests/test_authority_event_bus.py
git commit -m "Add in-memory authority event bus port" -m "Siming needs a bus boundary now, while external transports remain outside this Phase 1 minimum slice." -m "Constraint: No NATS, Redis, or PostgreSQL dependency is introduced" -m "Rejected: Use FastAPI WebSocket messages as the bus | they are presentation protocol messages, not replayable authority events" -m "Confidence: high" -m "Scope-risk: narrow" -m "Tested: python -m pytest tests/test_authority_event_bus.py -v"
```

## Task 3: Siming Event Domain Models

**Files:**
- Create: `backend/app/models/siming_event.py`
- Test: `backend/tests/test_siming_event_models.py`

- [ ] **Step 1: Write failing domain model tests**

Add `backend/tests/test_siming_event_models.py`:

```python
from app.models.authority_event import AuthorityEvent
from app.models.siming_event import SimingAuditRecord, SimingInput, SimingOutput, SimingTickResult

from tests.test_authority_event import valid_event_dict


def test_siming_input_preserves_source_authority_event() -> None:
    event = AuthorityEvent.model_validate(valid_event_dict())
    siming_input = SimingInput(input_type="visual_fact_event", source_event=event)

    assert siming_input.source_event.event_id == "evt_visual_1"
    assert siming_input.input_type == "visual_fact_event"


def test_siming_output_can_represent_dispatch_intent() -> None:
    output = SimingOutput(
        output_type="dispatch_intent",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="evt_visual_1",
        correlation_id="visual_fact:100",
        producer_ts=101,
        selected_path="visual_fact_path",
        intervention_band="fact_reveal",
        payload={"established_fact_id": "evt_visual_1"},
    )

    assert output.selected_path == "visual_fact_path"
    assert output.payload["established_fact_id"] == "evt_visual_1"


def test_siming_tick_result_groups_outputs_and_audit_records() -> None:
    audit = SimingAuditRecord(
        audit_id="audit_evt_visual_1",
        room_id="room_demo",
        correlation_id="visual_fact:100",
        causation_id="evt_visual_1",
        source_event_id="evt_visual_1",
        status="no_action",
        reason="no eligible intervention",
    )
    result = SimingTickResult(outputs=[], audit_records=[audit])

    assert result.audit_records[0].status == "no_action"
```

- [ ] **Step 2: Run the failing domain model tests**

Run from `backend/`:

```powershell
python -m pytest tests/test_siming_event_models.py -v
```

Expected: fail with `ModuleNotFoundError: No module named 'app.models.siming_event'`.

- [ ] **Step 3: Implement Siming event domain models**

Create `backend/app/models/siming_event.py`:

```python
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.authority_event import AuthorityEvent


SimingInputType = Literal[
    "world_fact_event",
    "visual_fact_event",
    "esm_result_event",
    "character_behavior_event",
    "conversation_resolution_event",
    "constraint_state_event",
]

SimingOutputType = Literal[
    "fairness_snapshot",
    "intervention_candidate",
    "intervention_decision",
    "dispatch_intent",
    "audit_record",
    "no_action",
]

SelectedPath = Literal[
    "character_input_path",
    "environment_change_path",
    "visual_fact_path",
    "l3_highlight_path",
    "no_action",
]

InterventionBand = Literal[
    "impulse",
    "opportunity",
    "fact_reveal",
    "environment_request",
    "none",
]

AuditStatus = Literal[
    "recorded",
    "no_action",
    "duplicate_suppressed",
    "stale_candidate",
    "dispatch_timeout",
    "partial_target_delivery",
    "esm_rejected",
    "expired_ttl",
    "late_input",
    "late_result_correction",
]


class SimingInput(BaseModel):
    input_type: SimingInputType
    source_event: AuthorityEvent


class SimingOutput(BaseModel):
    output_type: SimingOutputType
    room_id: str
    scene_id: str
    zone_id: str
    causation_id: str
    correlation_id: str
    producer_ts: int
    selected_path: SelectedPath | None = None
    intervention_band: InterventionBand | None = None
    priority: str = "p2"
    ttl: int | None = 5000
    durability: str = "replayable"
    payload: dict[str, Any] = Field(default_factory=dict)


class SimingAuditCorrection(BaseModel):
    correction_id: str
    status: AuditStatus
    reason: str
    causation_id: str
    producer_ts: int


class SimingAuditRecord(BaseModel):
    audit_id: str
    room_id: str
    correlation_id: str
    causation_id: str
    source_event_id: str
    status: AuditStatus
    reason: str
    dispatch_event_id: str | None = None
    correction_records: list[SimingAuditCorrection] = Field(default_factory=list)


class SimingTickResult(BaseModel):
    outputs: list[SimingOutput] = Field(default_factory=list)
    audit_records: list[SimingAuditRecord] = Field(default_factory=list)
```

- [ ] **Step 4: Verify domain model tests pass**

Run from `backend/`:

```powershell
python -m pytest tests/test_siming_event_models.py -v
```

Expected: all tests in `test_siming_event_models.py` pass.

- [ ] **Step 5: Commit Task 3**

```powershell
git add backend/app/models/siming_event.py backend/tests/test_siming_event_models.py
git commit -m "Add Siming event pipeline domain models" -m "The Siming event bus path needs typed objects between the bus envelope, runtime, producer, and audit writer." -m "Constraint: These models stay minimal and do not encode the full fairness auditor graph" -m "Confidence: high" -m "Scope-risk: narrow" -m "Tested: python -m pytest tests/test_siming_event_models.py -v"
```

## Task 4: SimingEventConsumer

**Files:**
- Create: `backend/app/services/siming_event_consumer.py`
- Test: `backend/tests/test_siming_event_consumer.py`

- [ ] **Step 1: Write failing consumer tests**

Add `backend/tests/test_siming_event_consumer.py`:

```python
from app.models.authority_event import AuthorityEvent
from app.services.siming_event_consumer import SimingEventConsumer

from tests.test_authority_event import valid_event_dict


def make_event(event_type: str) -> AuthorityEvent:
    payload = valid_event_dict()
    payload["event_type"] = event_type
    return AuthorityEvent.model_validate(payload)


def test_consumer_accepts_visual_fact_event() -> None:
    consumer = SimingEventConsumer()

    result = consumer.handle_event(make_event("visual_fact_event"))

    assert len(result) == 1
    assert result[0].input_type == "visual_fact_event"
    assert result[0].source_event.event_type == "visual_fact_event"


def test_consumer_accepts_esm_result_event() -> None:
    consumer = SimingEventConsumer()

    result = consumer.handle_event(make_event("esm_result_event"))

    assert len(result) == 1
    assert result[0].input_type == "esm_result_event"


def test_consumer_ignores_unqualified_event_family() -> None:
    consumer = SimingEventConsumer()

    assert consumer.handle_event(make_event("player_input")) == []
    assert consumer.handle_event(make_event("siming.fairness_snapshot")) == []
```

- [ ] **Step 2: Run the failing consumer tests**

Run from `backend/`:

```powershell
python -m pytest tests/test_siming_event_consumer.py -v
```

Expected: fail with `ModuleNotFoundError: No module named 'app.services.siming_event_consumer'`.

- [ ] **Step 3: Implement the consumer**

Create `backend/app/services/siming_event_consumer.py`:

```python
from app.models.authority_event import AuthorityEvent
from app.models.siming_event import SimingInput


class SimingEventConsumer:
    ALLOWED_EVENT_TYPES = {
        "world_fact_event",
        "visual_fact_event",
        "esm_result_event",
        "character_behavior_event",
        "conversation_resolution_event",
        "constraint_state_event",
    }

    def handle_event(self, event: AuthorityEvent) -> list[SimingInput]:
        if event.event_type not in self.ALLOWED_EVENT_TYPES:
            return []
        return [SimingInput(input_type=event.event_type, source_event=event)]
```

- [ ] **Step 4: Verify consumer tests pass**

Run from `backend/`:

```powershell
python -m pytest tests/test_siming_event_consumer.py -v
```

Expected: all tests in `test_siming_event_consumer.py` pass.

- [ ] **Step 5: Commit Task 4**

```powershell
git add backend/app/services/siming_event_consumer.py backend/tests/test_siming_event_consumer.py
git commit -m "Add Siming authority event consumer" -m "Siming must consume only the authority event families it is allowed to judge." -m "Constraint: Siming output events are not consumed back into the runtime path" -m "Confidence: high" -m "Scope-risk: narrow" -m "Tested: python -m pytest tests/test_siming_event_consumer.py -v"
```

## Task 5: Minimum SimingRuntime Tick

**Files:**
- Create: `backend/app/services/siming_runtime.py`
- Test: `backend/tests/test_siming_runtime.py`

- [ ] **Step 1: Write failing runtime tests**

Add `backend/tests/test_siming_runtime.py`:

```python
from app.models.authority_event import AuthorityEvent
from app.models.siming_event import SimingInput
from app.services.siming_runtime import SimingRuntime

from tests.test_authority_event import valid_event_dict


def make_input(event_type: str, payload_override: dict[str, object] | None = None) -> SimingInput:
    payload = valid_event_dict()
    payload["event_type"] = event_type
    payload["payload"] = payload_override or payload["payload"]
    event = AuthorityEvent.model_validate(payload)
    return SimingInput(input_type=event_type, source_event=event)


def test_runtime_emits_fairness_snapshot_for_consumed_event() -> None:
    runtime = SimingRuntime()

    result = runtime.tick([make_input("visual_fact_event")])

    assert result.outputs[0].output_type == "fairness_snapshot"
    assert result.outputs[0].causation_id == "evt_visual_1"


def test_runtime_emits_visual_observability_dispatch_for_light_drop() -> None:
    runtime = SimingRuntime()

    result = runtime.tick([make_input("visual_fact_event")])

    dispatches = [output for output in result.outputs if output.output_type == "dispatch_intent"]
    assert len(dispatches) == 1
    assert dispatches[0].selected_path == "visual_fact_path"
    assert dispatches[0].intervention_band == "fact_reveal"
    assert dispatches[0].payload["established_fact_id"] == "evt_visual_1"


def test_runtime_records_no_action_for_irrelevant_visual_fact() -> None:
    runtime = SimingRuntime()

    result = runtime.tick(
        [
            make_input(
                "visual_fact_event",
                {
                    "fact_type": "fixed_gaze_on_target",
                    "target_actor_id": "char_a",
                },
            )
        ]
    )

    assert [output.output_type for output in result.outputs] == ["fairness_snapshot", "no_action"]
    assert result.audit_records[0].status == "no_action"
    assert result.audit_records[0].reason == "no eligible intervention"


def test_runtime_records_esm_rejection_for_constraint_state_event() -> None:
    runtime = SimingRuntime()

    result = runtime.tick(
        [
            make_input(
                "constraint_state_event",
                {
                    "result_type": "constraint_state_result",
                    "constraint_type": "distance",
                    "constraint_summary": "target is too far away",
                },
            )
        ]
    )

    assert result.audit_records[0].status == "esm_rejected"
    assert result.audit_records[0].reason == "target is too far away"
```

- [ ] **Step 2: Run the failing runtime tests**

Run from `backend/`:

```powershell
python -m pytest tests/test_siming_runtime.py -v
```

Expected: fail with `ModuleNotFoundError: No module named 'app.services.siming_runtime'`.

- [ ] **Step 3: Implement the minimum runtime**

Create `backend/app/services/siming_runtime.py`:

```python
from app.models.authority_event import AuthorityEvent
from app.models.siming_event import SimingAuditRecord, SimingInput, SimingOutput, SimingTickResult


class SimingRuntime:
    def tick(self, inputs: list[SimingInput]) -> SimingTickResult:
        result = SimingTickResult()
        for siming_input in inputs:
            event = siming_input.source_event
            result.outputs.append(self._fairness_snapshot(event))

            if self._is_light_drop(event):
                result.outputs.extend(
                    [
                        self._intervention_candidate(event),
                        self._intervention_decision(event, selected_path="visual_fact_path", intervention_band="fact_reveal"),
                        self._visual_fact_dispatch(event),
                    ]
                )
                result.audit_records.append(self._audit(event, status="recorded", reason="visual fact observability requested"))
                continue

            if event.event_type == "constraint_state_event":
                reason = str(event.payload.get("constraint_summary", "constraint rejected downstream"))
                result.audit_records.append(self._audit(event, status="esm_rejected", reason=reason))
                continue

            result.outputs.append(self._no_action(event))
            result.audit_records.append(self._audit(event, status="no_action", reason="no eligible intervention"))
        return result

    def _fairness_snapshot(self, event: AuthorityEvent) -> SimingOutput:
        return SimingOutput(
            output_type="fairness_snapshot",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            producer_ts=event.producer_ts + 1,
            payload={"source_event_id": event.event_id},
        )

    def _intervention_candidate(self, event: AuthorityEvent) -> SimingOutput:
        return SimingOutput(
            output_type="intervention_candidate",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            producer_ts=event.producer_ts + 2,
            payload={"candidate_id": f"candidate_{event.event_id}"},
        )

    def _intervention_decision(self, event: AuthorityEvent, *, selected_path: str, intervention_band: str) -> SimingOutput:
        return SimingOutput(
            output_type="intervention_decision",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            producer_ts=event.producer_ts + 3,
            selected_path=selected_path,
            intervention_band=intervention_band,
            payload={"decision_id": f"decision_{event.event_id}"},
        )

    def _visual_fact_dispatch(self, event: AuthorityEvent) -> SimingOutput:
        established_fact_id = str(event.payload.get("established_fact_id", event.event_id))
        return SimingOutput(
            output_type="dispatch_intent",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            producer_ts=event.producer_ts + 4,
            selected_path="visual_fact_path",
            intervention_band="fact_reveal",
            payload={
                "established_fact_id": established_fact_id,
                "presentation_hint": "increase observability for established light change",
            },
        )

    def _no_action(self, event: AuthorityEvent) -> SimingOutput:
        return SimingOutput(
            output_type="no_action",
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            causation_id=event.event_id,
            correlation_id=event.correlation_id,
            producer_ts=event.producer_ts + 1,
            selected_path="no_action",
            intervention_band="none",
            payload={"reason": "no eligible intervention"},
        )

    def _audit(self, event: AuthorityEvent, *, status: str, reason: str) -> SimingAuditRecord:
        return SimingAuditRecord(
            audit_id=f"audit_{event.event_id}_{status}",
            room_id=event.room_id,
            correlation_id=event.correlation_id,
            causation_id=event.event_id,
            source_event_id=event.event_id,
            status=status,
            reason=reason,
        )

    def _is_light_drop(self, event: AuthorityEvent) -> bool:
        return event.event_type == "visual_fact_event" and event.payload.get("fact_type") == "light_level_drop"
```

- [ ] **Step 4: Verify runtime tests pass**

Run from `backend/`:

```powershell
python -m pytest tests/test_siming_runtime.py -v
```

Expected: all tests in `test_siming_runtime.py` pass.

- [ ] **Step 5: Commit Task 5**

```powershell
git add backend/app/services/siming_runtime.py backend/tests/test_siming_runtime.py
git commit -m "Add minimum Siming event runtime tick" -m "The event bus integration needs a deterministic Siming runtime before producer, audit, and WebSocket wiring can be verified." -m "Constraint: Runtime emits high-level events only and does not write ESM success facts" -m "Confidence: medium" -m "Scope-risk: moderate" -m "Tested: python -m pytest tests/test_siming_runtime.py -v"
```

## Task 6: SimingEventProducer Official Event Mapping

**Files:**
- Create: `backend/app/services/siming_event_producer.py`
- Test: `backend/tests/test_siming_event_producer.py`

- [ ] **Step 1: Write failing producer tests**

Add `backend/tests/test_siming_event_producer.py`:

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
        "causation_id": "evt_visual_1",
        "correlation_id": "visual_fact:100",
        "producer_ts": 101,
        "selected_path": "visual_fact_path",
        "intervention_band": "fact_reveal",
        "payload": {"established_fact_id": "evt_visual_1"},
    }
    payload.update(overrides)
    return SimingOutput.model_validate(payload)


def test_producer_maps_visual_fact_path_to_observability_event() -> None:
    bus = InMemoryAuthorityEventBus()
    producer = SimingEventProducer(bus)

    producer.publish_outputs([make_output()])

    events = bus.list_events()
    assert events[0].event_type == "siming.visual_observability_request"
    assert events[0].source.system == "siming.dispatcher"
    assert events[0].payload["established_fact_id"] == "evt_visual_1"


def test_producer_rejects_visual_observability_without_established_fact_id() -> None:
    bus = InMemoryAuthorityEventBus()
    producer = SimingEventProducer(bus)

    with pytest.raises(ValueError, match="established_fact_id"):
        producer.publish_outputs([make_output(payload={})])


def test_producer_maps_no_action_to_no_action_recorded() -> None:
    bus = InMemoryAuthorityEventBus()
    producer = SimingEventProducer(bus)
    output = make_output(
        output_type="no_action",
        selected_path="no_action",
        intervention_band="none",
        payload={"reason": "no eligible intervention"},
    )

    producer.publish_outputs([output])

    assert bus.list_events()[0].event_type == "siming.no_action_recorded"


def test_producer_never_publishes_internal_dispatch_requested_label() -> None:
    bus = InMemoryAuthorityEventBus()
    producer = SimingEventProducer(bus)
    output = make_output(payload={"event_type": "siming.dispatch_requested", "established_fact_id": "evt_visual_1"})

    producer.publish_outputs([output])

    assert all(event.event_type != "siming.dispatch_requested" for event in bus.list_events())
```

- [ ] **Step 2: Run the failing producer tests**

Run from `backend/`:

```powershell
python -m pytest tests/test_siming_event_producer.py -v
```

Expected: fail with `ModuleNotFoundError: No module named 'app.services.siming_event_producer'`.

- [ ] **Step 3: Implement official event mapping**

Create `backend/app/services/siming_event_producer.py`:

```python
from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.models.siming_event import SimingOutput
from app.services.authority_event_bus import AuthorityEventBusPort


class SimingEventProducer:
    def __init__(self, bus: AuthorityEventBusPort) -> None:
        self._bus = bus

    def publish_outputs(self, outputs: list[SimingOutput]) -> None:
        for output in outputs:
            self._bus.publish(self._to_authority_event(output))

    def _to_authority_event(self, output: SimingOutput) -> AuthorityEvent:
        event_type = self._event_type_for(output)
        if event_type == "siming.visual_observability_request" and not output.payload.get("established_fact_id"):
            raise ValueError("visual observability requests require established_fact_id")

        return AuthorityEvent(
            event_id=f"siming:{output.output_type}:{output.producer_ts}:{output.causation_id}",
            event_type=event_type,
            producer_ts=output.producer_ts,
            room_id=output.room_id,
            scene_id=output.scene_id,
            zone_id=output.zone_id,
            source=AuthorityEventSource(layer="L2", system=self._source_system_for(output), actor_id=None),
            routing=AuthorityEventRouting(
                audience_mode="targeted" if output.selected_path not in (None, "no_action") else "audit",
                routing_mode="event_type",
                target_ids=self._target_ids_for(output),
            ),
            priority=output.priority,
            ttl=output.ttl,
            durability=output.durability,
            causation_id=output.causation_id,
            correlation_id=output.correlation_id,
            payload=dict(output.payload),
        )

    def _event_type_for(self, output: SimingOutput) -> str:
        if output.output_type == "fairness_snapshot":
            return "siming.fairness_snapshot"
        if output.output_type == "intervention_candidate":
            return "siming.intervention_candidate"
        if output.output_type == "intervention_decision":
            return "siming.intervention_decision"
        if output.output_type == "audit_record":
            return "siming.audit_recorded"
        if output.output_type == "no_action" or output.selected_path == "no_action":
            return "siming.no_action_recorded"
        if output.selected_path == "visual_fact_path":
            return "siming.visual_observability_request"
        if output.selected_path == "l3_highlight_path":
            return "siming.presentation_highlight_request"
        if output.selected_path == "environment_change_path":
            return "siming.environment_request"
        if output.selected_path == "character_input_path" and output.intervention_band == "impulse":
            return "siming.impulse"
        if output.selected_path == "character_input_path" and output.intervention_band == "opportunity":
            return "siming.opportunity"
        if output.selected_path == "character_input_path" and output.intervention_band == "fact_reveal":
            return "siming.fact_reveal"
        raise ValueError(f"unsupported Siming output mapping: {output.output_type}/{output.selected_path}/{output.intervention_band}")

    def _source_system_for(self, output: SimingOutput) -> str:
        if output.output_type in {"fairness_snapshot", "intervention_candidate", "intervention_decision"}:
            return "siming.orchestrator"
        return "siming.dispatcher"

    def _target_ids_for(self, output: SimingOutput) -> list[str]:
        if output.selected_path == "environment_change_path":
            return ["esm"]
        if output.selected_path == "visual_fact_path":
            return ["visual_fact"]
        if output.selected_path == "l3_highlight_path":
            return ["presentation"]
        if output.selected_path == "character_input_path":
            return ["character_runtime"]
        return ["audit"]
```

- [ ] **Step 4: Verify producer tests pass**

Run from `backend/`:

```powershell
python -m pytest tests/test_siming_event_producer.py -v
```

Expected: all tests in `test_siming_event_producer.py` pass.

- [ ] **Step 5: Commit Task 6**

```powershell
git add backend/app/services/siming_event_producer.py backend/tests/test_siming_event_producer.py
git commit -m "Map Siming outputs to authority event families" -m "Formal bus output must use concrete event families instead of the internal dispatch_requested summary label." -m "Constraint: visual observability requires an established fact reference" -m "Rejected: Publish siming.dispatch_requested | design reserves it for internal read models only" -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: python -m pytest tests/test_siming_event_producer.py -v"
```

## Task 7: SimingAuditWriter

**Files:**
- Create: `backend/app/services/siming_audit_writer.py`
- Test: `backend/tests/test_siming_audit_writer.py`

- [ ] **Step 1: Write failing audit writer tests**

Add `backend/tests/test_siming_audit_writer.py`:

```python
from app.models.siming_event import SimingAuditCorrection, SimingAuditRecord
from app.services.siming_audit_writer import SimingAuditWriter


def make_audit(audit_id: str = "audit_evt_visual_1") -> SimingAuditRecord:
    return SimingAuditRecord(
        audit_id=audit_id,
        room_id="room_demo",
        correlation_id="visual_fact:100",
        causation_id="evt_visual_1",
        source_event_id="evt_visual_1",
        status="no_action",
        reason="no eligible intervention",
    )


def test_audit_writer_records_no_action_and_queries_by_correlation() -> None:
    writer = SimingAuditWriter()
    writer.record(make_audit())

    records = writer.find_by_correlation(room_id="room_demo", correlation_id="visual_fact:100")

    assert len(records) == 1
    assert records[0].status == "no_action"


def test_audit_writer_suppresses_duplicate_audit_ids() -> None:
    writer = SimingAuditWriter()
    writer.record(make_audit())
    writer.record(make_audit())

    records = writer.find_by_correlation(room_id="room_demo", correlation_id="visual_fact:100")

    assert len(records) == 1
    assert writer.duplicate_count == 1


def test_audit_writer_appends_late_result_correction_without_overwriting_final_record() -> None:
    writer = SimingAuditWriter()
    writer.record(make_audit())
    writer.append_correction(
        "audit_evt_visual_1",
        SimingAuditCorrection(
            correction_id="correction_1",
            status="late_result_correction",
            reason="downstream result arrived after final audit",
            causation_id="esm_result:late",
            producer_ts=150,
        ),
    )

    record = writer.find_by_causation(room_id="room_demo", causation_id="evt_visual_1")[0]

    assert record.status == "no_action"
    assert record.correction_records[0].status == "late_result_correction"
```

- [ ] **Step 2: Run the failing audit writer tests**

Run from `backend/`:

```powershell
python -m pytest tests/test_siming_audit_writer.py -v
```

Expected: fail with `ModuleNotFoundError: No module named 'app.services.siming_audit_writer'`.

- [ ] **Step 3: Implement audit writer**

Create `backend/app/services/siming_audit_writer.py`:

```python
from app.models.siming_event import SimingAuditCorrection, SimingAuditRecord


class SimingAuditWriter:
    def __init__(self) -> None:
        self._records_by_id: dict[str, SimingAuditRecord] = {}
        self.duplicate_count = 0

    def record(self, audit: SimingAuditRecord) -> None:
        if audit.audit_id in self._records_by_id:
            self.duplicate_count += 1
            return
        self._records_by_id[audit.audit_id] = audit.model_copy(deep=True)

    def append_correction(self, audit_id: str, correction: SimingAuditCorrection) -> None:
        record = self._records_by_id[audit_id]
        next_record = record.model_copy(deep=True)
        next_record.correction_records.append(correction.model_copy(deep=True))
        self._records_by_id[audit_id] = next_record

    def find_by_correlation(self, *, room_id: str, correlation_id: str) -> list[SimingAuditRecord]:
        return [
            record.model_copy(deep=True)
            for record in self._records_by_id.values()
            if record.room_id == room_id and record.correlation_id == correlation_id
        ]

    def find_by_causation(self, *, room_id: str, causation_id: str) -> list[SimingAuditRecord]:
        return [
            record.model_copy(deep=True)
            for record in self._records_by_id.values()
            if record.room_id == room_id and record.causation_id == causation_id
        ]
```

- [ ] **Step 4: Verify audit writer tests pass**

Run from `backend/`:

```powershell
python -m pytest tests/test_siming_audit_writer.py -v
```

Expected: all tests in `test_siming_audit_writer.py` pass.

- [ ] **Step 5: Commit Task 7**

```powershell
git add backend/app/services/siming_audit_writer.py backend/tests/test_siming_audit_writer.py
git commit -m "Add in-memory Siming audit writer" -m "Siming judgements need an audit trail for no_action, duplicate suppression, and late downstream corrections." -m "Constraint: Audit storage remains in-memory for the minimum slice" -m "Confidence: high" -m "Scope-risk: narrow" -m "Tested: python -m pytest tests/test_siming_audit_writer.py -v"
```

## Task 8: SimingEventPipeline Integration

**Files:**
- Create: `backend/app/services/siming_event_pipeline.py`
- Test: `backend/tests/test_siming_event_pipeline.py`

- [ ] **Step 1: Write failing pipeline tests**

Add `backend/tests/test_siming_event_pipeline.py`:

```python
from app.models.authority_event import AuthorityEvent
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_pipeline import SimingEventPipeline
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_runtime import SimingRuntime

from tests.test_authority_event import valid_event_dict


def build_pipeline() -> tuple[InMemoryAuthorityEventBus, SimingAuditWriter, SimingEventPipeline]:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    pipeline = SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=SimingRuntime(),
        producer=SimingEventProducer(bus),
        audit_writer=audit_writer,
    )
    return bus, audit_writer, pipeline


def make_event(event_type: str, payload_override: dict[str, object] | None = None) -> AuthorityEvent:
    payload = valid_event_dict()
    payload["event_type"] = event_type
    if payload_override is not None:
        payload["payload"] = payload_override
    return AuthorityEvent.model_validate(payload)


def test_pipeline_publishes_siming_outputs_and_records_audit() -> None:
    bus, audit_writer, pipeline = build_pipeline()

    pipeline.handle_event(make_event("visual_fact_event"))

    event_types = [event.event_type for event in bus.list_events()]
    assert "siming.fairness_snapshot" in event_types
    assert "siming.visual_observability_request" in event_types
    assert audit_writer.find_by_correlation(room_id="room_demo", correlation_id="visual_fact:100")[0].status == "recorded"


def test_pipeline_records_esm_rejection_closed_loop() -> None:
    _bus, audit_writer, pipeline = build_pipeline()
    event = make_event(
        "constraint_state_event",
        {
            "result_type": "constraint_state_result",
            "constraint_type": "distance",
            "constraint_summary": "target is too far away",
        },
    )

    pipeline.handle_event(event)

    audit = audit_writer.find_by_correlation(room_id="room_demo", correlation_id="visual_fact:100")[0]
    assert audit.status == "esm_rejected"
    assert audit.reason == "target is too far away"
```

- [ ] **Step 2: Run the failing pipeline tests**

Run from `backend/`:

```powershell
python -m pytest tests/test_siming_event_pipeline.py -v
```

Expected: fail with `ModuleNotFoundError: No module named 'app.services.siming_event_pipeline'`.

- [ ] **Step 3: Implement pipeline orchestration**

Create `backend/app/services/siming_event_pipeline.py`:

```python
from app.models.authority_event import AuthorityEvent
from app.services.authority_event_bus import AuthorityEventBusPort
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_runtime import SimingRuntime


class SimingEventPipeline:
    def __init__(
        self,
        *,
        bus: AuthorityEventBusPort,
        consumer: SimingEventConsumer,
        runtime: SimingRuntime,
        producer: SimingEventProducer,
        audit_writer: SimingAuditWriter,
    ) -> None:
        self._bus = bus
        self._consumer = consumer
        self._runtime = runtime
        self._producer = producer
        self._audit_writer = audit_writer

    def handle_event(self, event: AuthorityEvent) -> None:
        inputs = self._consumer.handle_event(event)
        if not inputs:
            return
        result = self._runtime.tick(inputs)
        for audit in result.audit_records:
            self._audit_writer.record(audit)
        self._producer.publish_outputs(result.outputs)
```

- [ ] **Step 4: Verify pipeline tests pass**

Run from `backend/`:

```powershell
python -m pytest tests/test_siming_event_pipeline.py -v
```

Expected: all tests in `test_siming_event_pipeline.py` pass.

- [ ] **Step 5: Commit Task 8**

```powershell
git add backend/app/services/siming_event_pipeline.py backend/tests/test_siming_event_pipeline.py
git commit -m "Connect Siming event pipeline components" -m "Consumer, runtime, producer, and audit writer need one local orchestration path before Phase 0 WebSocket dual-write can be wired." -m "Constraint: Pipeline remains synchronous and in-memory for this validation slice" -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: python -m pytest tests/test_siming_event_pipeline.py -v"
```

## Task 9: Phase 0 Authority Event Adapter

**Files:**
- Create: `backend/app/services/phase0_authority_event_adapter.py`
- Test: `backend/tests/test_phase0_authority_event_adapter.py`

- [ ] **Step 1: Write failing adapter tests**

Add `backend/tests/test_phase0_authority_event_adapter.py`:

```python
from app.models.player_input import InteractIntent
from app.models.visual_fact import VisualFactEvent
from app.models.world_result import ConstraintStateResult, ObjectInteractionResult
from app.services.phase0_authority_event_adapter import Phase0AuthorityEventAdapter


def test_adapter_converts_visual_fact_to_authority_event() -> None:
    adapter = Phase0AuthorityEventAdapter()
    event = adapter.visual_fact_event(
        VisualFactEvent(
            actor_id="char_c",
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            producer_ts=300,
            fact_type="light_level_drop",
            relation_type="environment_light_drop",
            target_environment_id="env_lamp",
        )
    )

    assert event.event_type == "visual_fact_event"
    assert event.source.layer == "L1"
    assert event.source.system == "visual_fact"
    assert event.payload["established_fact_id"] == event.event_id


def test_adapter_converts_success_world_result_to_esm_result_event() -> None:
    adapter = Phase0AuthorityEventAdapter()
    source = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=456,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )
    result = ObjectInteractionResult(
        room_id="room_demo",
        source_type="player",
        result_type="object_interaction_result",
        causation_id="interact:456",
        producer_ts=457,
        target_object_id="obj_letter",
        interaction_type="inspect",
        result_summary="object interaction accepted",
        state_changed=True,
    )

    event = adapter.world_result_event(result, source_event=source)

    assert event.event_type == "esm_result_event"
    assert event.source.system == "esm"
    assert event.causation_id == "interact:456"


def test_adapter_converts_constraint_result_to_constraint_state_event() -> None:
    adapter = Phase0AuthorityEventAdapter()
    source = InteractIntent(
        player_id="p1",
        room_id="room_demo",
        actor_id="char_c",
        intent_type="interact_intent",
        producer_ts=456,
        target_object_id="obj_letter",
        interaction_type="inspect",
    )
    result = ConstraintStateResult(
        room_id="room_demo",
        source_type="player",
        result_type="constraint_state_result",
        causation_id="interact:456",
        producer_ts=457,
        target_object_id="obj_letter",
        constraint_type="distance",
        constraint_summary="target is too far away",
    )

    event = adapter.world_result_event(result, source_event=source)

    assert event.event_type == "constraint_state_event"
    assert event.payload["constraint_type"] == "distance"
```

- [ ] **Step 2: Run the failing adapter tests**

Run from `backend/`:

```powershell
python -m pytest tests/test_phase0_authority_event_adapter.py -v
```

Expected: fail with `ModuleNotFoundError: No module named 'app.services.phase0_authority_event_adapter'`.

- [ ] **Step 3: Implement Phase 0 adapter**

Create `backend/app/services/phase0_authority_event_adapter.py`:

```python
from app.models.authority_event import AuthorityEvent, AuthorityEventRouting, AuthorityEventSource
from app.models.player_input import DialogueSubmit, FocusTargetChange, InteractIntent, MoveIntent
from app.models.visual_fact import VisualFactEvent
from app.models.world_result import ConstraintStateResult, EnvironmentStateResult, ObjectInteractionResult


PlayerInputEvent = MoveIntent | DialogueSubmit | InteractIntent | FocusTargetChange
WorldResultEvent = ObjectInteractionResult | EnvironmentStateResult | ConstraintStateResult


class Phase0AuthorityEventAdapter:
    def visual_fact_event(self, event: VisualFactEvent) -> AuthorityEvent:
        event_id = f"visual_fact:{event.producer_ts}:{event.actor_id}:{event.fact_type}"
        payload = event.model_dump(exclude_none=True)
        payload["established_fact_id"] = event_id
        return AuthorityEvent(
            event_id=event_id,
            event_type="visual_fact_event",
            producer_ts=event.producer_ts,
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            source=AuthorityEventSource(layer="L1", system="visual_fact", actor_id=event.actor_id),
            routing=AuthorityEventRouting(audience_mode="room", routing_mode="event_type", target_ids=["siming"]),
            priority="p2",
            ttl=5000,
            durability="replayable",
            causation_id=f"visual_fact:{event.producer_ts}",
            correlation_id=f"visual_fact:{event.producer_ts}",
            payload=payload,
        )

    def world_result_event(self, result: WorldResultEvent, *, source_event: PlayerInputEvent) -> AuthorityEvent:
        event_type = "constraint_state_event" if isinstance(result, ConstraintStateResult) else "esm_result_event"
        return AuthorityEvent(
            event_id=f"{event_type}:{result.producer_ts}:{result.causation_id}",
            event_type=event_type,
            producer_ts=result.producer_ts,
            room_id=result.room_id,
            scene_id=source_event.scene_id,
            zone_id=source_event.zone_id,
            source=AuthorityEventSource(layer="L1", system="esm", actor_id=getattr(source_event, "actor_id", None)),
            routing=AuthorityEventRouting(audience_mode="room", routing_mode="event_type", target_ids=["siming"]),
            priority="p1" if isinstance(result, ConstraintStateResult) else "p2",
            ttl=5000,
            durability="replayable",
            causation_id=result.causation_id,
            correlation_id=result.causation_id,
            payload=result.model_dump(exclude_none=True),
        )
```

- [ ] **Step 4: Verify adapter tests pass**

Run from `backend/`:

```powershell
python -m pytest tests/test_phase0_authority_event_adapter.py -v
```

Expected: all tests in `test_phase0_authority_event_adapter.py` pass.

- [ ] **Step 5: Commit Task 9**

```powershell
git add backend/app/services/phase0_authority_event_adapter.py backend/tests/test_phase0_authority_event_adapter.py
git commit -m "Add Phase 0 authority event adapter" -m "The current WebSocket handler needs a small translation layer so authority events can be dual-written without replacing the observable demo protocol." -m "Constraint: Existing Phase 0 message shapes remain unchanged" -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: python -m pytest tests/test_phase0_authority_event_adapter.py -v"
```

## Task 10: Phase 0 WebSocket Dual-Write Wiring

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_ws_authority_event_dual_write.py`
- Existing regression tests: `backend/tests/test_ws_protocol.py`, `backend/tests/test_visual_fact_pipeline.py`

- [ ] **Step 1: Write failing WebSocket dual-write tests**

Add `backend/tests/test_ws_authority_event_dual_write.py`:

```python
from app.main import _handle_envelope, authority_event_bus, reset_runtime_state, siming_audit_writer
from app.models.player_input import InteractIntent
from app.models.visual_fact import VisualFactEvent
from app.ws_protocol import Envelope


def test_visual_fact_handler_dual_writes_authority_and_siming_events_without_changing_outbound_messages() -> None:
    reset_runtime_state()
    outbound = _handle_envelope(
        Envelope(
            message_type="visual_fact_event",
            payload=VisualFactEvent(
                actor_id="char_c",
                room_id="room_demo",
                scene_id="scene_demo",
                zone_id="zone_focus",
                producer_ts=300,
                fact_type="light_level_drop",
                relation_type="environment_light_drop",
                target_environment_id="env_lamp",
            ).model_dump(),
        )
    )

    assert outbound[0]["message_type"] == "ack"
    event_types = [event.event_type for event in authority_event_bus.list_events()]
    assert "visual_fact_event" in event_types
    assert "siming.fairness_snapshot" in event_types
    assert "siming.visual_observability_request" in event_types
    assert siming_audit_writer.find_by_correlation(room_id="room_demo", correlation_id="visual_fact:300")


def test_failed_interaction_dual_writes_constraint_state_event() -> None:
    reset_runtime_state()
    _handle_envelope(
        Envelope(
            message_type="player_input",
            payload={
                "player_id": "p1",
                "room_id": "room_demo",
                "actor_id": "char_c",
                "intent_type": "move_intent",
                "producer_ts": 455,
                "move_mode": "locomotion",
                "target_point": [0.0, 0.0, 20.0],
            },
        )
    )

    outbound = _handle_envelope(
        Envelope(
            message_type="player_input",
            payload=InteractIntent(
                player_id="p1",
                room_id="room_demo",
                actor_id="char_c",
                intent_type="interact_intent",
                producer_ts=456,
                target_object_id="obj_letter",
                interaction_type="inspect",
            ).model_dump(),
        )
    )

    assert outbound[1]["message_type"] == "world_result"
    event_types = [event.event_type for event in authority_event_bus.list_events()]
    assert "constraint_state_event" in event_types
    assert any(audit.status == "esm_rejected" for audit in siming_audit_writer.find_by_correlation(room_id="room_demo", correlation_id="interact:456"))
```

- [ ] **Step 2: Run the failing dual-write tests**

Run from `backend/`:

```powershell
python -m pytest tests/test_ws_authority_event_dual_write.py -v
```

Expected: fail because `authority_event_bus` and `siming_audit_writer` are not initialized in `app.main`.

- [ ] **Step 3: Wire global runtime services in `reset_runtime_state()`**

Modify imports in `backend/app/main.py`:

```python
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.phase0_authority_event_adapter import Phase0AuthorityEventAdapter
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_pipeline import SimingEventPipeline
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_runtime import SimingRuntime
```

Extend `reset_runtime_state()` globals:

```python
    global authority_event_bus
    global phase0_authority_event_adapter
    global siming_audit_writer
    global siming_event_pipeline
```

Initialize the new services at the end of `reset_runtime_state()`:

```python
    authority_event_bus = InMemoryAuthorityEventBus()
    phase0_authority_event_adapter = Phase0AuthorityEventAdapter()
    siming_audit_writer = SimingAuditWriter()
    siming_event_pipeline = SimingEventPipeline(
        bus=authority_event_bus,
        consumer=SimingEventConsumer(),
        runtime=SimingRuntime(),
        producer=SimingEventProducer(authority_event_bus),
        audit_writer=siming_audit_writer,
    )
```

- [ ] **Step 4: Add a helper that publishes and runs the Siming pipeline**

Add to `backend/app/main.py` near `_as_envelope()`:

```python
def _publish_authority_event(event: object) -> None:
    from app.models.authority_event import AuthorityEvent

    if not isinstance(event, AuthorityEvent):
        return
    authority_event_bus.publish(event)
    siming_event_pipeline.handle_event(event)
```

- [ ] **Step 5: Dual-write visual facts**

In the `visual_fact_event` branch, immediately after `event = VisualFactEvent(**envelope.payload)`, add:

```python
        _publish_authority_event(phase0_authority_event_adapter.visual_fact_event(event))
```

- [ ] **Step 6: Dual-write ESM world results**

In the successful and failed `InteractIntent` branch, immediately after `world_result = esm_service.resolve_interaction(event, actor_position=actor_position)`, add:

```python
        _publish_authority_event(phase0_authority_event_adapter.world_result_event(world_result, source_event=event))
```

After `environment_result = esm_service.emit_environment_shift(room_id=event.room_id, target_environment_id="env_lamp", previous_state="stable", current_state="alerted")`, add:

```python
            _publish_authority_event(phase0_authority_event_adapter.world_result_event(environment_result, source_event=event))
```

- [ ] **Step 7: Verify dual-write tests pass**

Run from `backend/`:

```powershell
python -m pytest tests/test_ws_authority_event_dual_write.py -v
```

Expected: all tests in `test_ws_authority_event_dual_write.py` pass.

- [ ] **Step 8: Run WebSocket regression tests**

Run from `backend/`:

```powershell
python -m pytest tests/test_ws_protocol.py tests/test_visual_fact_pipeline.py -v
```

Expected: existing Phase 0 WebSocket and visual fact tests still pass.

- [ ] **Step 9: Commit Task 10**

```powershell
git add backend/app/main.py backend/tests/test_ws_authority_event_dual_write.py
git commit -m "Dual-write Phase 0 events to the authority event bus" -m "The backend can start exercising the Siming event bus chain while preserving current WebSocket output for the demo and Godot presentation path." -m "Constraint: No current websocket message type is removed or renamed" -m "Confidence: medium" -m "Scope-risk: moderate" -m "Tested: python -m pytest tests/test_ws_authority_event_dual_write.py -v; python -m pytest tests/test_ws_protocol.py tests/test_visual_fact_pipeline.py -v"
```

## Task 11: Verification Harness Boundary Updates

**Files:**
- Modify: `scripts/verification/check_backend_contract.py`
- Modify: `scripts/verification/tests/test_formal_profile_checks.py`
- Modify: `scripts/verification/check_boundaries.py`
- Modify: `scripts/verification/tests/test_boundary_checks.py`
- Modify: `docs/harness.md`

- [ ] **Step 1: Write failing backend-contract verification test changes**

In `scripts/verification/tests/test_formal_profile_checks.py`, extend `test_backend_contract_profile_proves_protocol_contracts()`:

```python
    assert statuses["authority_event_contract_exists"] == "proved"
```

- [ ] **Step 2: Extend backend-contract check**

In `scripts/verification/check_backend_contract.py`, add:

```python
    authority_event = project_root / "backend" / "app" / "models" / "authority_event.py"
    authority_event_tests = project_root / "backend" / "tests" / "test_authority_event.py"
```

Append this result block to the `results` list:

```python
        _result(
            "authority_event_contract_exists",
            "Authority event envelope exists and rejects forbidden public fields",
            _contains(
                authority_event,
                [
                    "class AuthorityEvent",
                    "class AuthorityEventSource",
                    "class AuthorityEventRouting",
                    "world_ts",
                    "sim_tick_ts",
                    "source_actor_id",
                    "target_actor_ids",
                    'Literal["p0", "p1", "p2", "p3"]',
                    'Literal["replayable", "reliable", "realtime"]',
                ],
            )
            and _contains(
                authority_event_tests,
                [
                    "test_authority_event_rejects_domain_time_at_public_envelope_root",
                    "test_authority_event_rejects_legacy_flat_envelope_fields",
                    "test_authority_event_rejects_unknown_priority",
                    "test_authority_event_rejects_unknown_durability",
                ],
            ),
            ["backend/app/models/authority_event.py", "backend/tests/test_authority_event.py"],
        ),
```

- [ ] **Step 3: Write failing boundary verification test changes**

In `scripts/verification/tests/test_boundary_checks.py`, extend `test_evaluate_boundaries_proves_core_runtime_ownership_rules()`:

```python
    assert statuses["siming_event_bus_port_exists"] == "proved"
```

- [ ] **Step 4: Extend boundary check**

In `scripts/verification/check_boundaries.py`, add these paths inside `evaluate_boundaries()`:

```python
    authority_bus = project_root / "backend" / "app" / "services" / "authority_event_bus.py"
    siming_pipeline = project_root / "backend" / "app" / "services" / "siming_event_pipeline.py"
    siming_producer = project_root / "backend" / "app" / "services" / "siming_event_producer.py"
```

Append this result block to the `results` list:

```python
        _result(
            "siming_event_bus_port_exists",
            "Siming integrates through an authority event bus port and concrete high-level event families",
            _contains(authority_bus, ["class AuthorityEventBusPort", "class InMemoryAuthorityEventBus"])
            and _contains(siming_pipeline, ["class SimingEventPipeline", "handle_event"])
            and _contains(
                siming_producer,
                [
                    "siming.visual_observability_request",
                    "siming.environment_request",
                    "siming.no_action_recorded",
                    "siming.impulse",
                    "siming.opportunity",
                    "siming.fact_reveal",
                ],
            )
            and _contains_none(siming_producer, ['return "siming.dispatch_requested"']),
            [
                "backend/app/services/authority_event_bus.py",
                "backend/app/services/siming_event_pipeline.py",
                "backend/app/services/siming_event_producer.py",
            ],
        ),
```

- [ ] **Step 5: Update `docs/harness.md`**

In the `backend-contract` section, add:

```markdown
- authority event envelope rejects forbidden public fields and legacy flat fields
```

In the `boundaries` section, add:

```markdown
- Siming integrates through the backend authority event bus port and emits concrete high-level event families
```

- [ ] **Step 6: Verify static profile tests pass**

Run from repository root:

```powershell
python -m pytest scripts/verification/tests/test_formal_profile_checks.py scripts/verification/tests/test_boundary_checks.py -v
```

Expected: all selected verification tests pass.

- [ ] **Step 7: Verify harness profiles pass**

Run from repository root:

```powershell
python scripts/verification/harness.py --profile backend-contract
python scripts/verification/harness.py --profile boundaries
python scripts/verification/harness.py --profile docs
```

Expected: all three profiles report `overall_*_passed=True`.

- [ ] **Step 8: Commit Task 11**

```powershell
git add scripts/verification/check_backend_contract.py scripts/verification/tests/test_formal_profile_checks.py scripts/verification/check_boundaries.py scripts/verification/tests/test_boundary_checks.py docs/harness.md
git commit -m "Extend harness checks for Siming event bus boundary" -m "The new authority event bus edge needs mechanical checks so future changes do not regress into flat websocket-only messaging." -m "Constraint: Static checks prove contract and boundary wiring, not Godot runtime behavior" -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: python scripts/verification/harness.py --profile backend-contract; python scripts/verification/harness.py --profile boundaries; python scripts/verification/harness.py --profile docs"
```

## Task 12: Final Backend Verification

**Files:**
- No new source files.
- Generated evidence remains under `.harness/verification/`.

- [ ] **Step 1: Run focused backend test suite**

Run from `backend/`:

```powershell
python -m pytest -v
```

Expected: all backend tests pass.

- [ ] **Step 2: Run static harness profiles**

Run from repository root:

```powershell
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile boundaries
python scripts/verification/harness.py --profile backend-contract
```

Expected: all three profiles pass.

- [ ] **Step 3: Run the minimum runtime slice when Godot is available**

Run from repository root:

```powershell
python scripts/verification/harness.py --profile phase1-slice
```

Expected: profile passes and writes `.harness/verification/phase1-slice-runtime-trace.ndjson`.

- [ ] **Step 4: Inspect generated evidence**

Read:

```powershell
Get-Content -Raw -Encoding UTF8 .harness/verification/backend-contract-report.md
Get-Content -Raw -Encoding UTF8 .harness/verification/boundary-report.md
Get-Content -Raw -Encoding UTF8 .harness/verification/docs-report.md
```

Expected: each report marks the new and existing rule results as `proved`.

- [ ] **Step 5: Confirm verification did not create source changes**

Run from repository root:

```powershell
git status --short
```

Expected: no tracked source or documentation files are listed. Generated evidence under `.harness/verification/` should remain ignored. If tracked files changed during verification, return to the task that owns those files, make the correction there, rerun its verification command, and commit that task normally.

## Self-Review Checklist

- [ ] `AuthorityEvent` rejects missing required fields, public `world_ts`, public `sim_tick_ts`, and legacy flat fields.
- [ ] `AuthorityEventBusPort` exists, and Siming does not depend on NATS, Redis, PostgreSQL, or a concrete external SDK.
- [ ] `SimingEventConsumer` consumes only allowed event families.
- [ ] `SimingRuntime` emits high-level judgement outputs only.
- [ ] `SimingEventProducer` maps dispatches to concrete event families and never publishes `siming.dispatch_requested`.
- [ ] `visual_fact_path` dispatch requires `established_fact_id`.
- [ ] `environment_change_path` maps to `siming.environment_request`, and downstream `constraint_state_event` produces audit.
- [ ] `no_action` writes an audit record.
- [ ] Duplicate audit IDs are suppressed.
- [ ] Late downstream results append corrections instead of overwriting final audit records.
- [ ] Current `/ws` outbound message shapes remain compatible with existing tests.
- [ ] Harness static checks cover the new authority event envelope and Siming bus edge.

## Execution Handoff

Recommended execution mode: `superpowers:subagent-driven-development`, one fresh worker per task, with review after each commit.

Inline execution is also viable because the work is sequential and local, but it should still follow the task order above. Do not start Task 10 before Tasks 1 through 9 pass, because WebSocket dual-write depends on all typed boundaries.
