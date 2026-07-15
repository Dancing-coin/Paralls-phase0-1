# Current Project Siming L6 Boundary Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the current in-memory System L6 and Siming runtime contracts so Siming catalyst, player-facing inner prompts, route matching, replay semantics, and global situation provenance are executable and testable without expanding Siming into a character brain, world-truth owner, or presentation host.

**Architecture:** This plan implements the boundary-hardening layer only. `System L6` remains an in-memory authority event infrastructure layer; `Siming` remains global situation and high-level catalyst; `FrontendAuthorityEventProjector` remains a projection adapter; `CharacterAgentRuntime` remains the owner of character cognition and execution. `Siming Perspective Graph v0.1` is intentionally split into a follow-up Plan B after these contracts are stable.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, existing backend service classes, existing harness profiles.

## Global Constraints

- Work from the current `feat/siming_20260625` architecture truth in `docs/架构/`.
- Do not edit `docs/架构/` in this implementation plan unless the user explicitly asks for a separate documentation update.
- Do not replace the in-memory authority event bus with an external broker.
- Do not introduce distributed ordering, dead-letter queues, persistent databases, or cross-process delivery.
- `System L6` owns authority envelope, publish/subscribe, route matching, replay/list filtering, and audit support only.
- `System L6` must not own perception semantics, character reasoning, ESM settlement, world truth, or Godot presentation behavior.
- `Siming` must not emit `character_agent_execution`, ESM settlement results, world mutation, physical success claims, low-level motion commands, actor control frames, selected intent, or action request bundles.
- AI-controlled actors may receive `impulse_hint` through `CharacterAgentRuntime` as high-level catalyst input only.
- Player-controlled actors must not receive `impulse_hint` through `CharacterAgentRuntime`; they may only receive `inner_prompt` through frontend presentation / narration.
- `impulse_hint` and `inner_prompt` intensity must not exceed `0.35`; over-limit payloads are rejected and audited, not clamped.
- Siming must not read, emit, or store `character_mm:*`, `character_private*`, `private_cache*`, `private_patch*`, `patch_session*`, `patch_context*`, or `inference_history*` private refs.
- Private-ref runtime validation is strict for ref/id/lineage/context/source/conflict fields and does not scan prose fields such as `summary`, `guidance`, `notes`, `prompt_text`, or `presentation_hint`.
- Task checkpoint commits are optional. Do not commit unless the user asks or the execution strategy explicitly requires checkpoint commits.

---

## File Structure

- `backend/app/services/authority_event_bus.py`: add `consumer_id`, targeted route matching, durability-aware replay/list behavior, and TTL filtering.
- `backend/app/models/siming_catalyst.py`: create the single payload validation source for `SimingCatalystInput`, `InnerPrompt`, forbidden fields, intensity limits, and private-ref validation.
- `backend/app/services/siming_character_dispatch_adapter.py`: convert valid AI-facing Siming catalyst events into character runtime inputs; reject player-targeted `impulse_hint`; never dispatch `inner_prompt` to character runtime.
- `backend/app/services/siming_event_producer.py`: validate every outgoing `siming.*` event through `siming_catalyst.py` before publish.
- `backend/app/services/frontend_authority_event_projection.py`: project `siming.inner_prompt` as presentation-only frontend output and keep projector out of route ownership.
- `backend/app/main.py`: subscribe Siming and frontend projector with explicit `consumer_id`.
- `backend/app/services/siming_global_situation.py`: harden provenance refs and private-ref rejection on ref-bearing fields only.
- `backend/app/services/siming_runtime.py`: attach global situation provenance to new global-decision Siming outputs only when a `SimingGlobalSituationSnapshot` is in scope.
- `backend/tests/test_authority_event_bus.py`: L6 route, durability, replay, and TTL tests.
- `backend/tests/test_siming_catalyst.py`: model-level catalyst / inner prompt validation tests.
- `backend/tests/test_siming_character_dispatch_adapter.py`: dispatch boundary tests.
- `backend/tests/test_siming_event_producer.py`: producer validation and route tests.
- `backend/tests/test_siming_event_pipeline.py`: pipeline / projector integration tests.
- `backend/tests/test_siming_global_situation_runtime.py`: provenance and private-boundary tests.

---

### Task 1: System L6 Executed Routing Semantics

**Files:**
- Modify: `backend/app/services/authority_event_bus.py`
- Modify: `backend/tests/test_authority_event_bus.py`

**Interfaces:**
- Produces: `InMemoryAuthorityEventBus.subscribe(event_type: str, consumer: EventConsumer, *, consumer_id: str = "*") -> None`
- Produces: `InMemoryAuthorityEventBus.list_events(..., consumer_id: str = "*", include_realtime: bool = False, current_only: bool = True) -> list[AuthorityEvent]`
- Preserves: existing subscribe/list calls that omit `consumer_id`.

- [ ] **Step 1: Add failing targeted route test**

Add a test proving `target_ids=["siming"]` reaches only the Siming consumer:

```python
def test_bus_routes_targeted_events_by_consumer_identity() -> None:
    bus = InMemoryAuthorityEventBus()
    siming_seen: list[AuthorityEvent] = []
    projector_seen: list[AuthorityEvent] = []

    bus.subscribe("visual_fact_event", siming_seen.append, consumer_id="siming")
    bus.subscribe("visual_fact_event", projector_seen.append, consumer_id="frontend_projector")

    bus.publish(
        make_authority_event(
            event_id="evt:siming",
            routing={
                "audience_mode": "targeted",
                "routing_mode": "event_type",
                "target_ids": ["siming"],
            },
        )
    )

    assert [event.event_id for event in siming_seen] == ["evt:siming"]
    assert projector_seen == []
```

Run: `python -m pytest backend/tests/test_authority_event_bus.py::test_bus_routes_targeted_events_by_consumer_identity -v`

Expected: FAIL until `consumer_id` routing exists.

- [ ] **Step 2: Add failing room-is-not-broadcast test**

Add a test locking the stricter route rule:

```python
def test_room_audience_does_not_bypass_target_ids() -> None:
    bus = InMemoryAuthorityEventBus()
    siming_seen: list[AuthorityEvent] = []
    projector_seen: list[AuthorityEvent] = []

    bus.subscribe("visual_fact_event", siming_seen.append, consumer_id="siming")
    bus.subscribe("visual_fact_event", projector_seen.append, consumer_id="frontend_projector")

    bus.publish(
        make_authority_event(
            event_id="evt:room-targeted",
            room_id="room_demo",
            routing={
                "audience_mode": "room",
                "routing_mode": "event_type",
                "target_ids": ["siming"],
            },
        )
    )

    assert [event.event_id for event in siming_seen] == ["evt:room-targeted"]
    assert projector_seen == []
```

Run: `python -m pytest backend/tests/test_authority_event_bus.py::test_room_audience_does_not_bypass_target_ids -v`

Expected: FAIL if `room` is treated as broadcast.

- [ ] **Step 3: Add durability and TTL replay tests**

Add:

```python
def test_realtime_event_delivers_but_is_not_in_current_replay() -> None:
    bus = InMemoryAuthorityEventBus()
    seen: list[AuthorityEvent] = []
    bus.subscribe("visual_fact_event", seen.append, consumer_id="siming")

    event = make_authority_event(
        event_id="evt:realtime",
        durability="realtime",
        routing={
            "audience_mode": "targeted",
            "routing_mode": "event_type",
            "target_ids": ["siming"],
        },
    )

    bus.publish(event)

    assert [item.event_id for item in seen] == ["evt:realtime"]
    assert bus.list_events(event_type="visual_fact_event", consumer_id="siming") == []
    assert [
        item.event_id
        for item in bus.list_events(
            event_type="visual_fact_event",
            consumer_id="siming",
            include_realtime=True,
        )
    ] == ["evt:realtime"]
```

Add:

```python
def test_expired_ttl_event_is_excluded_from_current_replay() -> None:
    bus = InMemoryAuthorityEventBus(now_ts_provider=lambda: 6000)

    bus.publish(
        make_authority_event(
            event_id="evt:expired",
            producer_ts=100,
            ttl=500,
            routing={
                "audience_mode": "targeted",
                "routing_mode": "event_type",
                "target_ids": ["siming"],
            },
        )
    )

    assert bus.list_events(event_type="visual_fact_event", consumer_id="siming") == []
    assert [
        item.event_id
        for item in bus.list_events(
            event_type="visual_fact_event",
            consumer_id="siming",
            current_only=False,
        )
    ] == ["evt:expired"]
```

Run:

```powershell
python -m pytest backend/tests/test_authority_event_bus.py::test_realtime_event_delivers_but_is_not_in_current_replay backend/tests/test_authority_event_bus.py::test_expired_ttl_event_is_excluded_from_current_replay -v
```

Expected: FAIL until `include_realtime`, `current_only`, and `now_ts_provider` exist.

- [ ] **Step 4: Implement L6 route and current replay semantics**

Implementation requirements:

```python
def _matches_route(self, event: AuthorityEvent, consumer_id: str) -> bool:
    if consumer_id == "*":
        return True
    if event.routing.audience_mode in {"broadcast", "authority_broadcast"}:
        return True
    return consumer_id in set(event.routing.target_ids)
```

Do not include `room` in the broadcast set. `room_id` filtering belongs to `list_events(room_id=...)`, not to consumer matching.

Replay semantics:

```python
if not include_realtime:
    events = [event for event in events if event.durability != "realtime"]
if current_only:
    events = [event for event in events if not self._is_expired(event)]
```

TTL check:

```python
def _is_expired(self, event: AuthorityEvent) -> bool:
    if event.ttl is None:
        return False
    return self._now_ts_provider() > event.producer_ts + event.ttl
```

- [ ] **Step 5: Verify Task 1**

Run: `python -m pytest backend/tests/test_authority_event_bus.py -v`

Expected: PASS.

- [ ] **Step 6: Optional checkpoint**

If the execution strategy requires a checkpoint, commit:

```powershell
git add backend/app/services/authority_event_bus.py backend/tests/test_authority_event_bus.py
git commit -m "feat: execute authority event bus routing semantics"
```

---

### Task 2: Siming Catalyst And Inner Prompt Contracts

**Files:**
- Create: `backend/app/models/siming_catalyst.py`
- Create/Modify: `backend/tests/test_siming_catalyst.py`
- Modify: `backend/tests/test_siming_character_dispatch_adapter.py`

**Interfaces:**
- Produces: `SimingCatalystInput.from_authority_event(event: AuthorityEvent) -> SimingCatalystInput`
- Produces: `InnerPrompt.from_authority_event(event: AuthorityEvent) -> InnerPrompt`
- Produces: `validate_siming_authority_event(event: AuthorityEvent) -> None`
- Produces: shared constants for forbidden fields and private-ref prefixes.

- [ ] **Step 1: Add failing catalyst import and conversion test**

Create or extend `backend/tests/test_siming_catalyst.py`:

```python
from app.models.siming_catalyst import SimingCatalystInput


def test_fact_reveal_creates_catalyst_input() -> None:
    event = make_siming_event(event_type="siming.fact_reveal", target_ids=["char_a"])
    event.payload.update(
        {
            "target_actor_id": "char_a",
            "target_object_id": "obj_letter",
            "presentation_hint": "the letter becomes narratively salient",
            "evidence_refs": ["authority_event:visual_fact:300"],
        }
    )

    catalyst = SimingCatalystInput.from_authority_event(event)

    assert catalyst.catalyst_type == "fact_reveal"
    assert catalyst.target_actor_id == "char_a"
    assert catalyst.target_object_id == "obj_letter"
    assert catalyst.evidence_refs == ["authority_event:visual_fact:300"]
```

Run: `python -m pytest backend/tests/test_siming_catalyst.py::test_fact_reveal_creates_catalyst_input -v`

Expected: FAIL with missing module or missing model.

- [ ] **Step 2: Add failing impulse and player-boundary tests**

Add:

```python
def test_impulse_hint_requires_axis_target_evidence_and_intensity_limit() -> None:
    event = make_siming_event(event_type="siming.impulse", target_ids=["char_a"])
    event.payload.update(
        {
            "target_actor_id": "char_a",
            "target_object_id": "obj_letter",
            "presentation_hint": "a sudden urge to check the letter",
            "impulse_axis": "action",
            "impulse_label": "check_letter",
            "intensity": 0.35,
            "evidence_refs": ["public_fact:letter_seen"],
        }
    )

    catalyst = SimingCatalystInput.from_authority_event(event)

    assert catalyst.catalyst_type == "impulse_hint"
    assert catalyst.impulse_axis == "action"
    assert catalyst.intensity == 0.35
```

Add:

```python
def test_impulse_hint_rejects_over_limit_intensity() -> None:
    event = make_siming_event(event_type="siming.impulse", target_ids=["char_a"])
    event.payload.update(
        {
            "target_actor_id": "char_a",
            "impulse_axis": "narrative",
            "intensity": 0.36,
            "evidence_refs": ["public_fact:letter_seen"],
        }
    )

    with pytest.raises(ValueError, match="intensity"):
        SimingCatalystInput.from_authority_event(event)
```

Add:

```python
def test_player_targeted_impulse_hint_is_rejected_not_auto_converted() -> None:
    event = make_siming_event(event_type="siming.impulse", target_ids=["player"])
    event.payload.update(
        {
            "target_actor_id": "player",
            "target_actor_control": "player",
            "impulse_axis": "narrative",
            "intensity": 0.2,
            "evidence_refs": ["public_fact:letter_seen"],
        }
    )

    with pytest.raises(ValueError, match="player"):
        SimingCatalystInput.from_authority_event(event)
```

Run:

```powershell
python -m pytest backend/tests/test_siming_catalyst.py::test_impulse_hint_requires_axis_target_evidence_and_intensity_limit backend/tests/test_siming_catalyst.py::test_impulse_hint_rejects_over_limit_intensity backend/tests/test_siming_catalyst.py::test_player_targeted_impulse_hint_is_rejected_not_auto_converted -v
```

Expected: FAIL until model validation exists.

- [ ] **Step 3: Add failing inner prompt tests**

Add:

```python
from app.models.siming_catalyst import InnerPrompt


def test_inner_prompt_is_player_facing_and_non_authoritative() -> None:
    event = make_siming_event(event_type="siming.inner_prompt", target_ids=["frontend_projector"])
    event.payload.update(
        {
            "target_actor_id": "player",
            "prompt_text": "Something about the letter feels wrong.",
            "intensity": 0.2,
            "evidence_refs": ["public_fact:letter_seen"],
            "player_facing": True,
            "non_authoritative": True,
            "presentation_effects": ["narration_text"],
        }
    )

    prompt = InnerPrompt.from_authority_event(event)

    assert prompt.target_actor_id == "player"
    assert prompt.player_facing is True
    assert prompt.non_authoritative is True
    assert prompt.presentation_effects == ["narration_text"]
```

Add:

```python
def test_inner_prompt_rejects_action_or_world_mutation_fields() -> None:
    event = make_siming_event(event_type="siming.inner_prompt", target_ids=["frontend_projector"])
    event.payload.update(
        {
            "target_actor_id": "player",
            "prompt_text": "Open the letter now.",
            "intensity": 0.2,
            "evidence_refs": ["public_fact:letter_seen"],
            "backend_action_request": {"action": "open"},
        }
    )

    with pytest.raises(ValueError, match="forbidden"):
        InnerPrompt.from_authority_event(event)
```

Run:

```powershell
python -m pytest backend/tests/test_siming_catalyst.py::test_inner_prompt_is_player_facing_and_non_authoritative backend/tests/test_siming_catalyst.py::test_inner_prompt_rejects_action_or_world_mutation_fields -v
```

Expected: FAIL until `InnerPrompt` exists.

- [ ] **Step 4: Implement `backend/app/models/siming_catalyst.py`**

Implementation requirements:

```python
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
```

Forbidden catalyst fields:

```python
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
```

Forbidden inner prompt fields:

```python
FORBIDDEN_INNER_PROMPT_PAYLOAD_FIELDS = FORBIDDEN_CATALYST_PAYLOAD_FIELDS | {
    "focus_target_id",
    "movement_input",
    "interact_input",
    "backend_action_request",
    "object_state_patch",
    "environment_state_patch",
}
```

Private ref prefixes:

```python
PRIVATE_REF_NAMESPACE_PREFIXES = (
    "character_private_cache",
    "character_private_context",
    "character_private",
    "character_mm",
    "private_cache",
    "private_patch",
    "patch_session",
    "patch_context",
    "inference_history",
)
```

`validate_siming_authority_event(event)` must:

```python
if event.event_type == "siming.inner_prompt":
    InnerPrompt.from_authority_event(event)
elif event.event_type.startswith("siming."):
    SimingCatalystInput.from_authority_event(event)
```

Do not duplicate payload legality rules in producer, adapter, or projector.

- [ ] **Step 5: Verify Task 2**

Run:

```powershell
python -m pytest backend/tests/test_siming_catalyst.py backend/tests/test_siming_character_dispatch_adapter.py -v
```

Expected: PASS.

- [ ] **Step 6: Optional checkpoint**

If the execution strategy requires a checkpoint, commit:

```powershell
git add backend/app/models/siming_catalyst.py backend/tests/test_siming_catalyst.py backend/tests/test_siming_character_dispatch_adapter.py
git commit -m "feat: add Siming catalyst and inner prompt contracts"
```

---

### Task 3: Producer, Adapter, And Projector Boundary Wiring

**Files:**
- Modify: `backend/app/services/siming_event_producer.py`
- Modify: `backend/app/services/siming_character_dispatch_adapter.py`
- Modify: `backend/app/services/frontend_authority_event_projection.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_siming_event_producer.py`
- Modify: `backend/tests/test_siming_character_dispatch_adapter.py`
- Modify: `backend/tests/test_siming_event_pipeline.py`

**Interfaces:**
- Consumes: `validate_siming_authority_event(event: AuthorityEvent) -> None`
- Consumes: `SimingCatalystInput.from_authority_event(event)`
- Consumes: `InnerPrompt.from_authority_event(event)`
- Produces: explicit `consumer_id` subscriptions for `siming` and `frontend_projector`.

- [ ] **Step 1: Add producer validation tests**

Add a test proving producer rejects forbidden Siming payloads before publish:

```python
def test_siming_event_producer_rejects_forbidden_character_execution_payload() -> None:
    bus = InMemoryAuthorityEventBus()
    producer = SimingEventProducer(authority_event_bus=bus)

    with pytest.raises(ValueError, match="forbidden"):
        producer.publish_siming_event(
            event_type="siming.impulse",
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            target_ids=["char_a"],
            payload={
                "target_actor_id": "char_a",
                "impulse_axis": "action",
                "intensity": 0.2,
                "evidence_refs": ["public_fact:letter_seen"],
                "character_agent_execution": {"actor_id": "char_a"},
            },
        )
```

Run: `python -m pytest backend/tests/test_siming_event_producer.py::test_siming_event_producer_rejects_forbidden_character_execution_payload -v`

Expected: FAIL until producer calls `validate_siming_authority_event`.

- [ ] **Step 2: Add adapter dispatch boundary tests**

Add:

```python
def test_inner_prompt_is_not_dispatched_to_character_runtime() -> None:
    runtime = _local_runtime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime)
    event = make_siming_event(event_type="siming.inner_prompt", target_ids=["frontend_projector"])
    event.payload.update(
        {
            "target_actor_id": "player",
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
```

Add:

```python
def test_player_impulse_hint_is_rejected_by_dispatch_adapter() -> None:
    runtime = _local_runtime()
    adapter = SimingCharacterDispatchAdapter(runtime=runtime)
    event = make_siming_event(event_type="siming.impulse", target_ids=["player"])
    event.payload.update(
        {
            "target_actor_id": "player",
            "target_actor_control": "player",
            "impulse_axis": "narrative",
            "intensity": 0.2,
            "evidence_refs": ["public_fact:letter_seen"],
        }
    )

    result = adapter.dispatch(event)

    assert result.delivery_inputs == []
    assert result.commands_by_actor == {}
    assert result.audit_summaries
```

Run:

```powershell
python -m pytest backend/tests/test_siming_character_dispatch_adapter.py::test_inner_prompt_is_not_dispatched_to_character_runtime backend/tests/test_siming_character_dispatch_adapter.py::test_player_impulse_hint_is_rejected_by_dispatch_adapter -v
```

Expected: FAIL until adapter uses the model contract.

- [ ] **Step 3: Add frontend projector inner prompt test**

Add:

```python
def test_frontend_projector_projects_inner_prompt_as_presentation_only() -> None:
    projector = FrontendAuthorityEventProjector()
    event = make_siming_event(event_type="siming.inner_prompt", target_ids=["frontend_projector"])
    event.payload.update(
        {
            "target_actor_id": "player",
            "prompt_text": "Something about the letter feels wrong.",
            "intensity": 0.2,
            "evidence_refs": ["public_fact:letter_seen"],
            "player_facing": True,
            "non_authoritative": True,
            "presentation_effects": ["narration_text"],
        }
    )

    projected = projector.handle_event(event)

    assert projected["type"] == "siming_inner_prompt"
    assert projected["target_actor_id"] == "player"
    assert projected["non_authoritative"] is True
    assert "backend_action_request" not in projected
    assert "world_mutation" not in projected
```

Run: `python -m pytest backend/tests/test_siming_event_pipeline.py::test_frontend_projector_projects_inner_prompt_as_presentation_only -v`

Expected: FAIL until projector supports `siming.inner_prompt`.

- [ ] **Step 4: Wire producer, adapter, projector, and subscriptions**

Implementation requirements:

- `siming_event_producer.py` must call `validate_siming_authority_event(event)` after constructing the `AuthorityEvent` and before `publish`.
- `siming_character_dispatch_adapter.py` must call `SimingCatalystInput.from_authority_event(event)` for AI-facing catalyst events and must never dispatch `siming.inner_prompt`.
- `frontend_authority_event_projection.py` must call `InnerPrompt.from_authority_event(event)` before projecting `siming.inner_prompt`.
- `backend/app/main.py` must use explicit subscription identities:

```python
authority_event_bus.subscribe(event_type, siming_event_pipeline.handle_event, consumer_id="siming")
authority_event_bus.subscribe(event_type, frontend_authority_event_projector.handle_event, consumer_id="frontend_projector")
```

- [ ] **Step 5: Verify Task 3**

Run:

```powershell
python -m pytest backend/tests/test_siming_event_producer.py backend/tests/test_siming_character_dispatch_adapter.py backend/tests/test_siming_event_pipeline.py backend/tests/test_authority_event_bus.py -v
```

Expected: PASS.

- [ ] **Step 6: Optional checkpoint**

If the execution strategy requires a checkpoint, commit:

```powershell
git add backend/app/services/siming_event_producer.py backend/app/services/siming_character_dispatch_adapter.py backend/app/services/frontend_authority_event_projection.py backend/app/main.py backend/tests/test_siming_event_producer.py backend/tests/test_siming_character_dispatch_adapter.py backend/tests/test_siming_event_pipeline.py
git commit -m "feat: harden Siming producer and projection boundaries"
```

---

### Task 4: Global Situation Provenance Hardening

**Files:**
- Modify: `backend/app/services/siming_global_situation.py`
- Modify: `backend/app/services/siming_runtime.py`
- Modify: `backend/tests/test_siming_global_situation_runtime.py`

**Interfaces:**
- Produces: `SimingGlobalSituationSnapshot.public_fact_refs`
- Produces: `SimingGlobalSituationSnapshot.authority_event_refs`
- Produces: `SimingGlobalSituationSnapshot.world_result_refs`
- Produces: `SimingGlobalSituationSnapshot.evidence_chain`
- Produces: `SimingGlobalSituationSnapshot.conflict_refs`
- Produces: global Siming decision payload fields `situation_snapshot_id`, `evidence_refs`, and `conflict_refs` when a snapshot is in scope.

- [ ] **Step 1: Add provenance dispatch regression test**

Add:

```python
def test_runtime_dispatch_emits_global_fact_reveal_provenance_fields() -> None:
    layer = SimingGlobalSituationLayer()
    snapshot = layer.assemble_snapshot(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        context_id="siming_mm:room_demo:scene_demo",
        l1_projected_facts=["authority_event:visual_fact:300"],
        world_results=[{"result_id": "world_result:1", "result_type": "environment_state_result"}],
        vla_global_findings=[
            {
                "ref_id": "vla_advisory:conflict:shadow_direction",
                "conflicts_with": "authority_event:visual_fact:300",
            }
        ],
        producer_ts=90,
    )

    assert snapshot.snapshot_id == "siming_situation:room_demo:scene_demo:90"
    assert "authority_event:visual_fact:300" in snapshot.public_fact_refs
    assert "world_result:1" in snapshot.world_result_refs
    assert snapshot.conflict_refs
```

Run: `python -m pytest backend/tests/test_siming_global_situation_runtime.py::test_runtime_dispatch_emits_global_fact_reveal_provenance_fields -v`

Expected: PASS if the current snapshot already covers this; keep it as regression either way.

- [ ] **Step 2: Add private-ref matrix tests**

Add:

```python
@pytest.mark.parametrize(
    "private_ref",
    [
        "character_mm:char_a:memory:1",
        "character_mm_hidden",
        "character_private:hidden_note",
        "character_private_context",
        "character_private_cache:char_a",
        "private_cache:hidden_note",
        "private_patch:hidden_note",
        "patch_session:hidden_note",
        "patch_context:hidden_note",
        "inference_history:hidden_note",
    ],
)
def test_global_situation_rejects_private_refs_in_ref_bearing_fields(private_ref: str) -> None:
    layer = SimingGlobalSituationLayer()

    with pytest.raises(ValueError, match="private"):
        layer.assemble_snapshot(
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            context_id="siming_mm:room_demo:scene_demo",
            l1_projected_facts=[private_ref],
            producer_ts=91,
        )
```

Add:

```python
def test_global_situation_does_not_scan_prose_fields_for_private_ref_markers() -> None:
    layer = SimingGlobalSituationLayer()

    snapshot = layer.assemble_snapshot(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        context_id="siming_mm:room_demo:scene_demo",
        multi_actor_patch={"guidance": "private_cache:hidden_note"},
        vla_global_findings=[
            {
                "ref_id": "vla_global:prose_keys:1",
                "guidance": "character_mm_hidden",
            }
        ],
        producer_ts=92,
    )

    assert snapshot.snapshot_id == "siming_situation:room_demo:scene_demo:92"
```

Run:

```powershell
python -m pytest backend/tests/test_siming_global_situation_runtime.py::test_global_situation_rejects_private_refs_in_ref_bearing_fields backend/tests/test_siming_global_situation_runtime.py::test_global_situation_does_not_scan_prose_fields_for_private_ref_markers -v
```

Expected: FAIL until private-ref scanning is narrowed and hardened.

- [ ] **Step 3: Implement ref-bearing field scanner**

Implementation requirements:

```python
_REF_FIELD_HINTS = {
    "ref",
    "refs",
    "id",
    "ids",
    "lineage",
    "context",
    "conflict",
    "conflicts",
    "source",
}
```

```python
def _should_scan_private_ref_field(key: object) -> bool:
    if not isinstance(key, str):
        return False
    return any(part in _REF_FIELD_HINTS for part in key.lower().split("_"))
```

Scan only ref-bearing fields in dict/list structures. Do not scan prose-only keys such as `summary`, `guidance`, `hidden`, `notes`, `prompt_text`, or `presentation_hint`.

- [ ] **Step 4: Attach provenance only to global situation-backed outputs**

In `siming_runtime.py`, when a new global decision has a `SimingGlobalSituationSnapshot` in scope, include:

```python
payload["situation_snapshot_id"] = snapshot.snapshot_id
payload["evidence_refs"] = list(snapshot.public_fact_refs or snapshot.intervention_candidate_evidence)
payload["conflict_refs"] = list(snapshot.conflict_refs)
```

Do not add these fields to old Phase0 compatibility branches unless a snapshot is actually in scope.

- [ ] **Step 5: Verify Task 4**

Run:

```powershell
python -m pytest backend/tests/test_siming_global_situation_runtime.py backend/tests/test_siming_event_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 6: Optional checkpoint**

If the execution strategy requires a checkpoint, commit:

```powershell
git add backend/app/services/siming_global_situation.py backend/app/services/siming_runtime.py backend/tests/test_siming_global_situation_runtime.py
git commit -m "feat: harden Siming global situation provenance"
```

---

### Task 5: Final Verification

**Files:**
- No planned source edits.
- `.harness/verification/` may update only if tracked evidence policy requires it.

**Interfaces:**
- Consumes: Tasks 1-4.
- Produces: final verification evidence for the Plan A boundary-hardening scope.

- [ ] **Step 1: Run focused backend tests**

Run:

```powershell
python -m pytest backend/tests/test_authority_event_bus.py backend/tests/test_siming_catalyst.py backend/tests/test_siming_event_producer.py backend/tests/test_siming_character_dispatch_adapter.py backend/tests/test_siming_event_pipeline.py backend/tests/test_siming_global_situation_runtime.py -v
```

Expected: PASS.

- [ ] **Step 2: Run backend contract harness**

Run: `python scripts/verification/harness.py --profile backend-contract`

Expected: `overall_backend_contract_passed=True`.

- [ ] **Step 3: Run boundaries harness**

Run: `python scripts/verification/harness.py --profile boundaries`

Expected: `overall_boundaries_passed=True`.

- [ ] **Step 4: Run mainline runtime harness**

Run: `python scripts/verification/harness.py --profile mainline-unified-runtime`

Expected: `overall_mainline_unified_runtime_passed=True`.

- [ ] **Step 5: Run Siming global situation harness**

Run: `python scripts/verification/harness.py --profile siming-global-situation-layer`

Expected: `overall_siming_global_situation_layer_passed=True`.

- [ ] **Step 6: Run docs harness without editing `docs/架构/`**

Run: `python scripts/verification/harness.py --profile docs`

Expected: `overall_docs_passed=True`.

- [ ] **Step 7: Check working tree and evidence**

Run: `git status --short`.

Expected: source/test files touched by Tasks 1-4 only, plus optional tracked evidence if repository policy requires it. Do not report Godot editor/runtime verification unless Godot was actually opened or executed.

---

## Deferred Plan B: Siming Perspective Graph v0.1

This file no longer implements Perspective Graph. Plan B must be created as a separate implementation plan after Plan A passes verification.

Plan B starting decisions:

- First implement a typed `ActorPerspectiveReadFacade`; do not start with `ingest_actor_perspective(actor_id, facade: dict)` as the public boundary.
- Required facade fields: `actor_id`, `capture_id`, `world_anchor_refs`, `observed_fact_refs`, `missed_fact_refs`, `known_refs`, `suspected_refs`, `source_ref_lineage`, and `private_scope = actor_read_facade`.
- The facade must reject `character_mm:*`, `character_private*`, `private_cache*`, `patch_session*`, and `inference_history*` refs.
- First implementation phase is offline projection only: typed facade, graph ingest, compression summary, private-ref rejection, and advisory/truth/conflict separation.
- Runtime integration into `SimingRuntime` or `NarrativeReadModel` is a second phase after offline projection passes.
- Graph output may enrich a read model but must not participate in policy, feasibility, catalyst selection, world truth, ESM settlement, or character execution.

---

## Self-Review

**Spec coverage:** Tasks 1-4 cover the `2026-07-07-current-project-siming-l6-boundary-hardening-design.md` requirements: L6 consumer identity, route matching, replay/list filtering, TTL behavior, projector as adapter, single catalyst/inner-prompt contract, AI impulse hints, player-facing inner prompts, forbidden payload rejection, private-ref rejection, and global situation provenance.

**Perspective Graph scope:** The `2026-07-08-current-project-siming-perspective-graph-design.md` requirements are not implemented here by design. They are deferred to Plan B because Perspective Graph depends on the stable contracts produced by this plan.

**Placeholder scan:** This plan contains no TBD markers or open-ended implementation placeholders. Every task has exact files, test names, expected failures, implementation constraints, and verification commands.

**Type consistency:** `consumer_id`, `include_realtime`, `current_only`, `SimingCatalystInput`, `InnerPrompt`, `validate_siming_authority_event`, and provenance field names are defined before later tasks use them.
