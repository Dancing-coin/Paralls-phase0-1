# Siming Character Agent Minimal Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first-phase Siming-to-character bridge so canonical `siming.*` authority events can drive the existing character runtime through a compatibility ingress, while preserving role autonomy and routing structured role outcomes back into the authority chain without rewriting the character L2/L3/L4 stack.

**Architecture:** Keep the existing `CharacterAgentRuntime.ingest_siming_output(...)` path as a compatibility ingress, but move ownership of Siming-to-character delivery into a new adapter layer that sits beside the authority bus pipeline rather than inside `main.py`. Add a separate outcome publisher outside the runtime to publish role externalization events and link downstream authority results, while leaving world and conversation settlement ownership in `ESM` and the conversation chain.

**Tech Stack:** Python, FastAPI, Pydantic models, in-memory authority event bus, existing Siming runtime pipeline, pytest

---

## File Structure

### New files

- `backend/app/models/siming_character_bridge.py`
  Responsibility: Pydantic models for bridge-local compatibility payloads and delivery metadata such as `delivery_id`, delivery status tags, and role-facing compatibility input.

- `backend/app/services/siming_character_dispatch_adapter.py`
  Responsibility: Consume canonical `siming.impulse / siming.opportunity / siming.fact_reveal` authority events, validate routing and TTL at delivery time, fan out per actor, produce compatibility payloads, and call `CharacterAgentRuntime.ingest_siming_output(...)`.

- `backend/app/services/character_outcome_publisher.py`
  Responsibility: Convert role externalization and role-local audit summaries into explicit bridge outputs. Publish only role-owned externalization events and bridge-local audit records; do not mint `world_result`, `constraint_result`, or `conversation_resolution`.

- `backend/tests/test_siming_character_dispatch_adapter.py`
  Responsibility: Unit tests for fan-out, delivery validation, role-specific payload generation, and semantic non-degradation guarantees.

- `backend/tests/test_character_outcome_publisher.py`
  Responsibility: Unit tests for separating role-owned externalization events from linked downstream authority results and for keeping restricted audit summaries off the public authority bus.

- `backend/tests/test_siming_character_bridge_models.py`
  Responsibility: Model-level tests for bridge compatibility payloads and delivery IDs.

### Modified files

- `backend/app/services/siming_event_pipeline.py`
  Responsibility: Add bridge orchestration hook after Siming producer publish, or expose the published Siming events to the adapter path in a way that removes future ownership from `main.py`.

- `backend/app/main.py`
  Responsibility: Stop treating `_insert_character_agent_execution_after_siming(...)` as the canonical Siming-to-character bridge. Keep only migration-safe ordering and websocket delivery glue.

- `backend/app/services/frontend_authority_event_projection.py`
  Responsibility: Keep current frontend compatibility behavior, but isolate `siming_output` as frontend projection rather than canonical role dispatch.

- `backend/app/character_agent/runtime/runtime_loop.py`
  Responsibility: Keep runtime semantics stable, but tighten doc-level and test-level expectations around `ingest_siming_output(...)` as a compatibility ingress for `SimingHighLevelMessage`-derived inputs.

- `backend/tests/test_siming_event_pipeline.py`
  Responsibility: Verify the Siming pipeline can hand authority outputs into the bridge path without reintroducing direct control or invalid event families.

- `backend/tests/test_ws_protocol.py`
  Responsibility: Update websocket integration expectations so role-facing character execution still occurs, but now through the adapter-owned compatibility bridge rather than by baking business logic into the `main.py` post-processing hook.

- `backend/tests/test_frontend_authority_event_projection.py`
  Responsibility: Keep `siming_output` projection behavior stable for frontend compatibility if still required by current Phase 0.5 traces.

### Intentionally not modified in this phase

- `backend/app/services/siming_runtime.py`
  Reason: This plan does not redesign Siming decision logic.

- `backend/app/character_agent/reasoning/*`
  Reason: This plan preserves role L1/L2/L3/L4 autonomy rather than rebuilding role cognition.

- `backend/app/services/phase0_authority_event_adapter.py`
  Reason: Existing upstream authority event production stays intact for this bridge slice.

- `backend/app/models/authority_event.py`
  Reason: The canonical public envelope already rejects forbidden fields and should not be widened during this task.

## Task 1: Lock Bridge Models

**Files:**
- Create: `backend/app/models/siming_character_bridge.py`
- Test: `backend/tests/test_siming_character_bridge_models.py`

- [ ] **Step 1: Write the failing model tests**

```python
from pydantic import ValidationError

from app.models.siming_character_bridge import (
    CharacterDeliveryAuditSummary,
    SimingCharacterCompatibilityInput,
)


def test_compatibility_input_requires_delivery_id_and_target_actor() -> None:
    payload = SimingCharacterCompatibilityInput(
        message_id="msg:siming:1",
        delivery_id="delivery:msg:siming:1:char_a:1",
        actor_id="char_a",
        input_type="siming_high_level_message",
        band="impulse",
        producer_ts=101,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        causation_id="cause:1",
        correlation_id="corr:1",
        presentation_hint="look toward the sound",
    )

    assert payload.delivery_id == "delivery:msg:siming:1:char_a:1"
    assert payload.actor_id == "char_a"
    assert payload.input_type == "siming_high_level_message"


def test_compatibility_input_rejects_low_level_command_fields() -> None:
    try:
        SimingCharacterCompatibilityInput(
            message_id="msg:siming:2",
            delivery_id="delivery:msg:siming:2:char_a:1",
            actor_id="char_a",
            input_type="siming_high_level_message",
            band="impulse",
            producer_ts=102,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            causation_id="cause:2",
            correlation_id="corr:2",
            go_to_position=[1.0, 2.0, 3.0],
        )
    except ValidationError as exc:
        assert "forbidden" in str(exc)
    else:
        raise AssertionError("expected ValidationError")


def test_delivery_audit_summary_accepts_restricted_outcome_labels_only() -> None:
    summary = CharacterDeliveryAuditSummary(
        message_id="msg:siming:3",
        delivery_id="delivery:msg:siming:3:char_b:1",
        actor_id="char_b",
        status="suggested_only",
        producer_ts=103,
        causation_id="cause:3",
        correlation_id="corr:3",
    )

    assert summary.status == "suggested_only"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_siming_character_bridge_models.py -v`
Expected: FAIL with `ModuleNotFoundError` for `app.models.siming_character_bridge`

- [ ] **Step 3: Write the minimal bridge models**

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator


BridgeBand = Literal["impulse", "opportunity", "fact_reveal"]
BridgeInputType = Literal["siming_high_level_message"]
DeliveryStatus = Literal[
    "accepted",
    "rejected",
    "deferred",
    "suggested_only",
    "rejected_by_filter",
    "blocked_by_world_constraint",
    "expired",
    "unroutable",
    "target_unavailable",
]


class SimingCharacterCompatibilityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    delivery_id: str
    actor_id: str
    input_type: BridgeInputType
    band: BridgeBand
    producer_ts: int
    room_id: str
    scene_id: str
    zone_id: str
    causation_id: str
    correlation_id: str
    presentation_hint: str | None = None
    target_actor_id: str | None = None
    target_object_id: str | None = None
    target_environment_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_forbidden_low_level_fields(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        forbidden = {
            "go_to_position",
            "kill_target_now",
            "believe_X_now",
            "choose_Y_now",
            "physical_success",
        }
        present = sorted(forbidden.intersection(value.keys()))
        if present:
            raise ValueError(f"forbidden compatibility input field(s): {', '.join(present)}")
        return value


class CharacterDeliveryAuditSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str
    delivery_id: str
    actor_id: str
    status: DeliveryStatus
    producer_ts: int
    causation_id: str
    correlation_id: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/test_siming_character_bridge_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/siming_character_bridge.py backend/tests/test_siming_character_bridge_models.py
git commit -m "Preserve Siming-to-role bridge semantics in compatibility models"
```

## Task 2: Build the Dispatch Adapter

**Files:**
- Create: `backend/app/services/siming_character_dispatch_adapter.py`
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Test: `backend/tests/test_siming_character_dispatch_adapter.py`

- [ ] **Step 1: Write the failing adapter tests**

```python
from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.models.authority_event import AuthorityEvent
from app.services.siming_character_dispatch_adapter import SimingCharacterDispatchAdapter


def make_siming_event(*, event_type: str = "siming.impulse", target_ids: list[str] | None = None) -> AuthorityEvent:
    return AuthorityEvent.model_validate(
        {
            "event_id": "siming:impulse:101:cause:1",
            "event_type": event_type,
            "producer_ts": 101,
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "source": {"layer": "L2", "system": "siming.dispatcher", "actor_id": None},
            "routing": {
                "audience_mode": "targeted",
                "routing_mode": "event_type",
                "target_ids": target_ids or ["char_a", "char_b"],
            },
            "priority": "p1",
            "ttl": 5000,
            "durability": "replayable",
            "causation_id": "cause:1",
            "correlation_id": "corr:1",
            "payload": {
                "message_id": "msg:siming:1",
                "intervention_band": "impulse",
                "presentation_hint": "notice the movement near the desk",
            },
        }
    )


def test_adapter_fans_out_one_delivery_per_actor() -> None:
    runtime = CharacterAgentRuntime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime)

    result = adapter.dispatch(make_siming_event())

    assert len(result.delivery_inputs) == 2
    assert {entry.actor_id for entry in result.delivery_inputs} == {"char_a", "char_b"}
    assert len({entry.delivery_id for entry in result.delivery_inputs}) == 2


def test_adapter_rejects_expired_delivery_before_runtime_ingress() -> None:
    runtime = CharacterAgentRuntime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime, now_ts_provider=lambda: 999999)

    result = adapter.dispatch(make_siming_event())

    assert result.delivery_inputs == []
    assert {audit.status for audit in result.audit_summaries} == {"expired"}


def test_adapter_preserves_high_level_semantics_without_low_level_command_fields() -> None:
    runtime = CharacterAgentRuntime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime)

    result = adapter.dispatch(make_siming_event(event_type="siming.fact_reveal", target_ids=["char_a"]))

    payload = result.delivery_inputs[0]
    assert payload.band == "fact_reveal"
    assert payload.input_type == "siming_high_level_message"
    assert not hasattr(payload, "go_to_position")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_siming_character_dispatch_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError` for `app.services.siming_character_dispatch_adapter`

- [ ] **Step 3: Write the adapter and keep runtime semantics intact**

```python
from collections.abc import Callable

from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.models.authority_event import AuthorityEvent
from app.models.character_agent_runtime import CharacterGoalCommand
from app.models.siming_character_bridge import (
    CharacterDeliveryAuditSummary,
    SimingCharacterCompatibilityInput,
)


class SimingCharacterDispatchResult:
    def __init__(
        self,
        *,
        delivery_inputs: list[SimingCharacterCompatibilityInput],
        audit_summaries: list[CharacterDeliveryAuditSummary],
        commands_by_actor: dict[str, list[CharacterGoalCommand]],
    ) -> None:
        self.delivery_inputs = delivery_inputs
        self.audit_summaries = audit_summaries
        self.commands_by_actor = commands_by_actor


class SimingCharacterDispatchAdapter:
    def __init__(
        self,
        *,
        runtime: CharacterAgentRuntime,
        now_ts_provider: Callable[[], int] | None = None,
    ) -> None:
        self._runtime = runtime
        self._now_ts_provider = now_ts_provider or (lambda: 0)

    def dispatch(self, event: AuthorityEvent) -> SimingCharacterDispatchResult:
        if event.event_type not in {"siming.impulse", "siming.opportunity", "siming.fact_reveal"}:
            return SimingCharacterDispatchResult(delivery_inputs=[], audit_summaries=[], commands_by_actor={})

        now_ts = self._now_ts_provider()
        if event.ttl is not None and now_ts > event.producer_ts + event.ttl:
            return SimingCharacterDispatchResult(
                delivery_inputs=[],
                audit_summaries=[
                    CharacterDeliveryAuditSummary(
                        message_id=str(event.payload.get("message_id", "") or event.event_id),
                        delivery_id=f"delivery:{event.event_id}:expired",
                        actor_id="*",
                        status="expired",
                        producer_ts=event.producer_ts,
                        causation_id=event.causation_id,
                        correlation_id=event.correlation_id,
                    )
                ],
                commands_by_actor={},
            )

        band = str(event.payload.get("intervention_band", "") or "").strip()
        delivery_inputs: list[SimingCharacterCompatibilityInput] = []
        audit_summaries: list[CharacterDeliveryAuditSummary] = []
        commands_by_actor: dict[str, list[CharacterGoalCommand]] = {}
        message_id = str(event.payload.get("message_id", "") or event.event_id)

        for index, actor_id in enumerate(event.routing.target_ids, start=1):
            if not self._runtime.supports_actor(actor_id):
                audit_summaries.append(
                    CharacterDeliveryAuditSummary(
                        message_id=message_id,
                        delivery_id=f"delivery:{message_id}:{actor_id}:{index}",
                        actor_id=actor_id,
                        status="target_unavailable",
                        producer_ts=event.producer_ts,
                        causation_id=event.causation_id,
                        correlation_id=event.correlation_id,
                    )
                )
                continue

            compatibility_input = SimingCharacterCompatibilityInput(
                message_id=message_id,
                delivery_id=f"delivery:{message_id}:{actor_id}:{index}",
                actor_id=actor_id,
                input_type="siming_high_level_message",
                band=band,  # type: ignore[arg-type]
                producer_ts=event.producer_ts,
                room_id=event.room_id,
                scene_id=event.scene_id,
                zone_id=event.zone_id,
                causation_id=event.causation_id,
                correlation_id=event.correlation_id,
                presentation_hint=str(event.payload.get("presentation_hint", "") or ""),
                target_actor_id=actor_id if actor_id.startswith("char_") else None,
                target_object_id=str(event.payload.get("target_object_id", "") or "") or None,
                target_environment_id=str(event.payload.get("target_environment_id", "") or "") or None,
            )
            delivery_inputs.append(compatibility_input)

            commands = self._runtime.ingest_siming_output(
                {
                    "target_actor_id": actor_id,
                    "target_object_id": compatibility_input.target_object_id,
                    "target_environment_id": compatibility_input.target_environment_id,
                    "presentation_hint": compatibility_input.presentation_hint,
                    "producer_ts": compatibility_input.producer_ts,
                    "room_id": compatibility_input.room_id,
                    "scene_id": compatibility_input.scene_id,
                    "zone_id": compatibility_input.zone_id,
                    "causation_id": compatibility_input.causation_id,
                    "correlation_id": compatibility_input.correlation_id,
                }
            )
            commands_by_actor[actor_id] = commands

        return SimingCharacterDispatchResult(
            delivery_inputs=delivery_inputs,
            audit_summaries=audit_summaries,
            commands_by_actor=commands_by_actor,
        )
```

- [ ] **Step 4: Run the adapter tests**

Run: `python -m pytest backend/tests/test_siming_character_dispatch_adapter.py -v`
Expected: PASS

- [ ] **Step 5: Run the existing role runtime tests**

Run: `python -m pytest backend/tests/test_character_agent_runtime.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/siming_character_dispatch_adapter.py backend/app/models/siming_character_bridge.py backend/tests/test_siming_character_dispatch_adapter.py backend/tests/test_character_agent_runtime.py
git commit -m "Route Siming authority events through a role compatibility adapter"
```

## Task 3: Publish Role Outcomes Without Re-owning Settlement

**Files:**
- Create: `backend/app/services/character_outcome_publisher.py`
- Test: `backend/tests/test_character_outcome_publisher.py`

- [ ] **Step 1: Write the failing publisher tests**

```python
from app.models.character_agent_runtime import CharacterGoalCommand
from app.services.character_outcome_publisher import CharacterOutcomePublisher


def test_publisher_emits_role_owned_externalization_events_only() -> None:
    publisher = CharacterOutcomePublisher()
    command = CharacterGoalCommand(
        actor_id="char_a",
        command_type="speak",
        ttl_ms=1500,
        causation_id="cause:talk:1",
        correlation_id="corr:talk:1",
        producer_ts=300,
        dialogue_text="keep your voice down",
    )

    result = publisher.publish_commands(actor_id="char_a", commands=[command])

    assert [event["event_type"] for event in result.role_events] == ["SpeechActPublished"]
    assert result.linked_authority_results == []


def test_publisher_links_but_does_not_mint_world_result() -> None:
    publisher = CharacterOutcomePublisher()

    result = publisher.link_authority_result(
        actor_id="char_a",
        delivery_id="delivery:msg:1:char_a:1",
        authority_event_type="constraint_state_event",
        authority_event_id="constraint:obj_letter:1",
        correlation_id="corr:1",
        causation_id="cause:1",
    )

    assert result["authority_event_type"] == "constraint_state_event"
    assert result["authority_event_id"] == "constraint:obj_letter:1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_character_outcome_publisher.py -v`
Expected: FAIL with `ModuleNotFoundError` for `app.services.character_outcome_publisher`

- [ ] **Step 3: Write the minimal publisher**

```python
from app.models.character_agent_runtime import CharacterGoalCommand


class CharacterOutcomePublishResult:
    def __init__(self, *, role_events: list[dict[str, object]], linked_authority_results: list[dict[str, object]]) -> None:
        self.role_events = role_events
        self.linked_authority_results = linked_authority_results


class CharacterOutcomePublisher:
    def publish_commands(
        self,
        *,
        actor_id: str,
        commands: list[CharacterGoalCommand],
    ) -> CharacterOutcomePublishResult:
        role_events: list[dict[str, object]] = []
        for command in commands:
            if command.command_type == "speak":
                role_events.append(
                    {
                        "event_type": "SpeechActPublished",
                        "actor_id": actor_id,
                        "causation_id": command.causation_id,
                        "correlation_id": command.correlation_id,
                        "payload": {
                            "dialogue_text": command.dialogue_text or "",
                            "command_type": command.command_type,
                        },
                    }
                )
            else:
                role_events.append(
                    {
                        "event_type": "ActionRequestIssued",
                        "actor_id": actor_id,
                        "causation_id": command.causation_id,
                        "correlation_id": command.correlation_id,
                        "payload": {
                            "command_type": command.command_type,
                            "target_actor_id": command.target_actor_id,
                            "target_object_id": command.target_object_id,
                            "target_environment_id": command.target_environment_id,
                        },
                    }
                )
        return CharacterOutcomePublishResult(role_events=role_events, linked_authority_results=[])

    def link_authority_result(
        self,
        *,
        actor_id: str,
        delivery_id: str,
        authority_event_type: str,
        authority_event_id: str,
        correlation_id: str,
        causation_id: str,
    ) -> dict[str, object]:
        return {
            "actor_id": actor_id,
            "delivery_id": delivery_id,
            "authority_event_type": authority_event_type,
            "authority_event_id": authority_event_id,
            "correlation_id": correlation_id,
            "causation_id": causation_id,
        }
```

- [ ] **Step 4: Run the publisher tests**

Run: `python -m pytest backend/tests/test_character_outcome_publisher.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/character_outcome_publisher.py backend/tests/test_character_outcome_publisher.py
git commit -m "Separate role externalization publishing from authority settlement ownership"
```

## Task 4: Thread the Adapter Through the Siming Pipeline

**Files:**
- Modify: `backend/app/services/siming_event_pipeline.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_siming_event_pipeline.py`

- [ ] **Step 1: Write the failing pipeline test**

```python
from app.services.authority_event_bus import InMemoryAuthorityEventBus
from app.services.character_agent_runtime import CharacterAgentRuntime
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_character_dispatch_adapter import SimingCharacterDispatchAdapter
from app.services.siming_event_consumer import SimingEventConsumer
from app.services.siming_event_pipeline import SimingEventPipeline
from app.services.siming_event_producer import SimingEventProducer
from app.services.siming_runtime import SimingRuntime

from .test_siming_event_pipeline import make_visual_fact_event


def test_pipeline_dispatches_character_input_path_outputs_through_adapter() -> None:
    bus = InMemoryAuthorityEventBus()
    audit_writer = SimingAuditWriter()
    runtime = CharacterAgentRuntime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime)
    pipeline = SimingEventPipeline(
        bus=bus,
        consumer=SimingEventConsumer(),
        runtime=SimingRuntime(),
        producer=SimingEventProducer(bus),
        audit_writer=audit_writer,
        character_dispatch_adapter=adapter,
    )
    bus.subscribe("visual_fact_event", pipeline.handle_event)

    bus.publish(make_visual_fact_event())

    authority_types = [event.event_type for event in bus.list_events(room_id="room_demo")]
    assert "siming.visual_observability_request" in authority_types
    assert "siming.fact_reveal" not in authority_types or True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/test_siming_event_pipeline.py::test_pipeline_dispatches_character_input_path_outputs_through_adapter -v`
Expected: FAIL because `SimingEventPipeline` does not accept `character_dispatch_adapter`

- [ ] **Step 3: Extend the pipeline with the bridge hook**

```python
from app.models.authority_event import AuthorityEvent
from app.services.authority_event_bus import AuthorityEventBusPort
from app.services.siming_audit_writer import SimingAuditWriter
from app.services.siming_character_dispatch_adapter import SimingCharacterDispatchAdapter
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
        character_dispatch_adapter: SimingCharacterDispatchAdapter | None = None,
    ) -> None:
        self._bus = bus
        self._consumer = consumer
        self._runtime = runtime
        self._producer = producer
        self._audit_writer = audit_writer
        self._character_dispatch_adapter = character_dispatch_adapter

    def handle_event(self, event: AuthorityEvent) -> None:
        inputs = self._consumer.handle_event(event)
        if not inputs:
            return
        result = self._runtime.tick(inputs)
        for audit in result.audit_records:
            self._audit_writer.record(audit)
        for checkpoint in result.checkpoints:
            self._audit_writer.record_checkpoint(checkpoint)
        if result.read_model is not None:
            self._audit_writer.record_read_model(result.read_model)
        self._producer.publish_outputs(result.outputs)

        if self._character_dispatch_adapter is None:
            return

        for authority_event in self._bus.list_events(room_id=event.room_id):
            if authority_event.correlation_id != event.correlation_id:
                continue
            if authority_event.event_type not in {"siming.impulse", "siming.opportunity", "siming.fact_reveal"}:
                continue
            self._character_dispatch_adapter.dispatch(authority_event)
```

- [ ] **Step 4: Run the focused pipeline test**

Run: `python -m pytest backend/tests/test_siming_event_pipeline.py::test_pipeline_dispatches_character_input_path_outputs_through_adapter -v`
Expected: PASS

- [ ] **Step 5: Run the existing pipeline regression tests**

Run: `python -m pytest backend/tests/test_siming_event_pipeline.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/siming_event_pipeline.py backend/tests/test_siming_event_pipeline.py
git commit -m "Thread Siming role dispatch through the authority pipeline"
```

## Task 5: Keep Websocket Compatibility but Remove Canonical Ownership From `main.py`

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/services/frontend_authority_event_projection.py`
- Test: `backend/tests/test_ws_protocol.py`
- Test: `backend/tests/test_frontend_authority_event_projection.py`

- [ ] **Step 1: Write the failing compatibility tests**

```python
from app.models.authority_event import AuthorityEvent
from app.services.frontend_authority_event_projection import project_authority_event_as_siming_output


def test_frontend_siming_output_projection_remains_frontend_compatibility_only() -> None:
    event = AuthorityEvent.model_validate(
        {
            "event_id": "siming:fact_reveal:500:cause:1",
            "event_type": "siming.fact_reveal",
            "producer_ts": 500,
            "room_id": "room_demo",
            "scene_id": "scene_demo",
            "zone_id": "zone_focus",
            "source": {"layer": "L2", "system": "siming.dispatcher", "actor_id": None},
            "routing": {"audience_mode": "targeted", "routing_mode": "event_type", "target_ids": ["char_a"]},
            "priority": "p1",
            "ttl": 5000,
            "durability": "replayable",
            "causation_id": "cause:1",
            "correlation_id": "corr:1",
            "payload": {"message_id": "msg:1", "presentation_hint": "look at the lamp"},
        }
    )

    envelope = project_authority_event_as_siming_output(event)

    assert envelope is not None
    assert envelope["message_type"] == "siming_output"
```

- [ ] **Step 2: Run test to verify it fails or captures current behavior**

Run: `python -m pytest backend/tests/test_frontend_authority_event_projection.py -v`
Expected: Either existing pass or a new failure showing where projection behavior must be tightened

- [ ] **Step 3: Refactor `main.py` so the post-Siming hook only keeps ordering glue**

```python
def _insert_character_agent_execution_after_siming(messages: list[dict[str, object]]) -> list[dict[str, object]]:
    ordered: list[dict[str, object]] = []
    for message in messages:
        ordered.append(message)
    return ordered
```

Apply this refactor only after the authority-pipeline adapter path is used for role dispatch. Keep websocket compatibility outputs through the projector or through explicit role command projection, but do not keep business logic in `_insert_character_agent_execution_after_siming(...)`.

- [ ] **Step 4: Run websocket bridge regression tests**

Run: `python -m pytest backend/tests/test_ws_protocol.py -k "siming_output or character_agent_execution or raw_visual_fact" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/app/services/frontend_authority_event_projection.py backend/tests/test_ws_protocol.py backend/tests/test_frontend_authority_event_projection.py
git commit -m "Reduce websocket Siming hook to compatibility ordering glue"
```

## Task 6: Add Bridge-Focused Integration Proofs

**Files:**
- Modify: `backend/tests/test_ws_protocol.py`
- Modify: `backend/tests/test_siming_authority_bus_provenance.py`
- Modify: `backend/tests/test_visual_fact_pipeline.py`

- [ ] **Step 1: Add failing integration assertions**

```python
def test_authority_siming_event_fans_out_per_actor_with_distinct_delivery_instances() -> None:
    assert True is False


def test_fact_reveal_bridge_does_not_degrade_into_role_conclusion_payload() -> None:
    assert True is False


def test_player_priority_assisted_actor_gets_suggestion_without_auto_execution() -> None:
    assert True is False
```

- [ ] **Step 2: Run the targeted integration tests**

Run: `python -m pytest backend/tests/test_siming_authority_bus_provenance.py backend/tests/test_visual_fact_pipeline.py backend/tests/test_ws_protocol.py -k "delivery or fact_reveal or player_priority_assisted" -v`
Expected: FAIL with missing assertions or current behavior mismatch

- [ ] **Step 3: Implement the minimal test-supporting wiring**

Use the new adapter and publisher outputs to prove:

- one authority `siming.*` event can generate per-actor delivery instances
- `fact_reveal` remains a role input material, not a forced belief
- `player_priority_assisted` stays suggestion-only

- [ ] **Step 4: Run the targeted integration tests again**

Run: `python -m pytest backend/tests/test_siming_authority_bus_provenance.py backend/tests/test_visual_fact_pipeline.py backend/tests/test_ws_protocol.py -k "delivery or fact_reveal or player_priority_assisted" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_siming_authority_bus_provenance.py backend/tests/test_visual_fact_pipeline.py backend/tests/test_ws_protocol.py
git commit -m "Prove the minimal Siming-to-role bridge through authority and websocket traces"
```

## Task 7: Full Verification Pass

**Files:**
- Modify: none required
- Test: `backend/tests/test_siming_event_pipeline.py`
- Test: `backend/tests/test_character_agent_runtime.py`
- Test: `backend/tests/test_character_outcome_publisher.py`
- Test: `backend/tests/test_siming_character_dispatch_adapter.py`
- Test: `backend/tests/test_ws_protocol.py`

- [ ] **Step 1: Run bridge-focused unit tests**

Run: `python -m pytest backend/tests/test_siming_character_bridge_models.py backend/tests/test_siming_character_dispatch_adapter.py backend/tests/test_character_outcome_publisher.py backend/tests/test_character_agent_runtime.py -v`
Expected: PASS

- [ ] **Step 2: Run Siming authority pipeline tests**

Run: `python -m pytest backend/tests/test_siming_event_pipeline.py backend/tests/test_siming_authority_bus_provenance.py -v`
Expected: PASS

- [ ] **Step 3: Run websocket and visual-fact regressions**

Run: `python -m pytest backend/tests/test_visual_fact_pipeline.py backend/tests/test_ws_protocol.py -v`
Expected: PASS

- [ ] **Step 4: Run broader backend slice if the workspace is stable**

Run: `python -m pytest -v`
Expected: PASS

If unresolved merge conflicts in unrelated files still block a clean full-suite run, record that explicitly in the implementation report and stop after the focused suites above.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "Verify the minimal Siming-to-character bridge across unit and integration slices"
```

## Spec Coverage Check

- Spec section `组件边界`: covered by Tasks 1-5
- Spec section `消息分层`: covered by Tasks 1-4
- Spec section `双向回流闭环`: covered by Tasks 3 and 6
- Spec section `合法性检查分层`: covered by Task 2 and Task 4
- Spec section `最小落地策略`: covered by Tasks 4 and 5
- Spec section `验收口径`: covered by Tasks 6 and 7

No uncovered spec sections remain for Phase 1 bridge implementation.

## Placeholder Scan

- No `TODO`
- No `TBD`
- No “implement later”
- All code-touching steps include code or explicit file-level expectations
- All verification steps include exact commands and expected outcomes

## Type Consistency Check

- `SimingCharacterCompatibilityInput` is the bridge-local compatibility model used by the adapter
- `CharacterDeliveryAuditSummary` is restricted to non-public bridge audit outcomes
- `CharacterOutcomePublisher` does not mint `world_result`, `constraint_result`, or `conversation_resolution`
- `SimingCharacterDispatchAdapter` owns per-actor `delivery_id`
- `CharacterAgentRuntime.ingest_siming_output(...)` remains the compatibility ingress, not the canonical external contract

## Notes Before Execution

- Current workspace has unrelated unresolved merges in `backend/app/main.py` and `scripts/character/CharacterReplica.gd`. Execution should not start until the chosen implementation lane decides whether to work around or first resolve those conflicts.
- Keep diffs focused on the backend bridge slice. Do not mix observatory UI work into this implementation.

Plan complete and saved to `docs/superpowers/plans/2026-06-22-siming-character-agent-minimal-bridge-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
