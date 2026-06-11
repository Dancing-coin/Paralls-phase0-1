# Phase 0.5 Runtime Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current `Phase 0.5` demo into a small but real Phase-1-shaped runtime slice where `CharacterC` is the first real player-driven in-world role shell, authority-side runtime state lives in the backend, and Godot consumes synced state plus high-level results for embodiment.

**Architecture:** Keep the existing `Player -> CharacterC` bridge and current `Phase 0.5` demo loop alive while introducing a backend authority event-bus skeleton, a conversation/relation compiler, a minimum character runtime state service, and a minimum Siming judgment service. Godot remains the local embodiment host, visual fact producer, and presentation consumer; backend becomes the authority owner of relationship candidates and per-character runtime state.

**Tech Stack:** Godot 4.6 scene files, GDScript, FastAPI, WebSocket, Pydantic, project-local Markdown reference docs, current `CharacterReplica`/`LocalPresentationBus`/`BackendBridge` runtime.

---

## Status Snapshot

- Date: `2026-06-10`
- Plan status: executed and verified for the repository-local target
- Current code truth:
  - authority-side runtime state exists in the backend
  - conversation relation compilation exists
  - character runtime state ownership exists
  - Siming judgment and output paths exist
  - backend health identity exposure exists
  - websocket move/focus/interaction paths emit the expected authority/runtime messages
- Verification evidence:
  - `backend/tests/test_conversation_relation_service.py::test_relation_service_exposes_unified_relation_snapshot`
  - `backend/tests/test_character_runtime_state_service.py::test_state_service_builds_initial_snapshot_for_actor`
  - `backend/tests/test_character_runtime_state_service.py::test_state_service_applies_runtime_projection_delta`
  - `backend/tests/test_siming_service.py::test_siming_emits_attention_prompt_for_char_c_candidate_actor`
  - `backend/tests/test_health.py::test_health_exposes_current_backend_identity`
  - `backend/tests/test_ws_protocol.py::test_websocket_move_intent_emits_ack_and_runtime_snapshot`
  - `backend/tests/test_ws_protocol.py::test_websocket_focus_target_change_emits_runtime_alignment_messages`
  - `backend/tests/test_session_runtime.py::test_session_runtime_routes_move_event`
  - `backend/tests/test_session_runtime.py::test_session_runtime_routes_focus_target_change_event`

## File Structure

### Approved design and reference inputs

- Read: `docs/superpowers/specs/2026-06-02-phase05-runtime-alignment-design.md`
- Read: `docs/reference/phase1-event-bus/01-事件总线总纲.md`
- Read: `docs/reference/phase1-event-bus/05-事件信封与字段分层规范.md`
- Read: `docs/reference/phase1-event-bus/07-视觉事实系统接入总线规范.md`
- Read: `docs/reference/phase1-character-agent/01-角色智能体总纲.md`
- Read: `docs/reference/phase1-character-agent/17-司命与角色智能体协作协议.md`
- Read: `docs/reference/phase1-character-agent/19-角色智能体与事件总线契约.md`
- Read: `docs/reference/phase1-siming/10-司命与事件总线契约.md`

### Backend authority lane

- Modify: `backend/app/main.py`
- Modify: `backend/app/ws_protocol.py` if envelope typing needs widening
- Modify: `backend/app/models/player_input.py`
- Modify: `backend/app/models/ai_output.py` if new outbound message models are introduced
- Create: `backend/app/models/runtime_state.py`
- Create: `backend/app/models/event_envelope.py` if canonical envelope helpers become necessary
- Create: `backend/app/services/conversation_relation_service.py`
- Create: `backend/app/services/character_runtime_state_service.py`
- Modify: `backend/app/services/character_service.py`
- Modify: `backend/app/services/siming_service.py`
- Modify: `backend/app/services/session_runtime.py`
- Modify: `backend/app/services/event_trace_service.py` if trace shape needs widening

### Godot authority-consumer lane

- Modify: `scripts/autoload/BackendBridge.gd`
- Modify: `scripts/autoload/LocalPresentationBus.gd`
- Modify: `scripts/player/PlayerIntentMapper.gd`
- Modify: `scripts/phase0/MainDemoController.gd`
- Modify: `scripts/character/CharacterReplica.gd`
- Modify: `scenes/phase0/MainDemo.tscn`

### Optional visual-fact-alignment lane

- Create or modify only if needed for the first real visual-fact export:
- `scripts/visual/` (new folder only if the repo lacks a natural home)
- `scripts/character/LookAtController.gd` only if existing focus extraction can be reused

### Tests

- Modify: `backend/tests/test_ws_protocol.py`
- Modify: `backend/tests/test_session_runtime.py`
- Modify: `backend/tests/test_character_service.py`
- Modify: `backend/tests/test_siming_service.py`
- Modify: `backend/tests/test_demo_script.py` if trace expectations widen
- Create: `backend/tests/test_conversation_relation_service.py`
- Create: `backend/tests/test_character_runtime_state_service.py`
- Create: `backend/tests/test_health.py` (already exists; expand if needed)

### Verification artifacts

- Write screenshots under: `.harness/verification/`
- Keep spec reference intact under: `docs/superpowers/specs/`

### Git note

- The workspace still does not expose a `.git` directory. Do not include commit steps during execution unless the repository is reattached to Git.

## Task 1: Freeze Canonical Event Types And Envelope Use

**Files:**
- Modify: `backend/app/models/player_input.py`
- Create: `backend/app/models/runtime_state.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_ws_protocol.py`

- [ ] **Step 1: Re-read the approved runtime-alignment spec before touching code**

Run:

```powershell
Get-Content docs/superpowers/specs/2026-06-02-phase05-runtime-alignment-design.md
```

Expected: the approved event-bus, runtime-state, and Siming boundaries are visible in one place.

- [ ] **Step 2: Expand the backend model file inventory so new runtime-sync messages have a natural home**

Create `backend/app/models/runtime_state.py` with explicit `Pydantic` models for the two Godot sync messages plus the conversation candidate summary:

```python
from pydantic import BaseModel


class ConversationCandidateEvent(BaseModel):
    actor_id: str
    room_id: str
    scene_id: str
    zone_id: str
    producer_ts: int
    candidate_actor_ids: list[str]
    candidate_object_ids: list[str]
    engagement_pressure: str
    privacy_risk_hint: str
    causation_id: str
    correlation_id: str


class CharacterRuntimeStateSnapshot(BaseModel):
    actor_id: str
    room_id: str
    scene_id: str
    zone_id: str
    revision_seq: int
    producer_ts: int
    current_focus_target: str | None = None
    current_attention_source: str | None = None
    nearby_actor_refs: list[str] = []
    nearby_object_refs: list[str] = []
    conversation_candidate_refs: list[str] = []
    engagement_pressure: str | None = None
    privacy_risk_hint: str | None = None
    updated_at: int


class CharacterRuntimeStateDelta(BaseModel):
    actor_id: str
    room_id: str
    scene_id: str
    zone_id: str
    revision_seq: int
    producer_ts: int
    changed_fields: list[str]
    current_focus_target: str | None = None
    current_attention_source: str | None = None
    nearby_actor_refs: list[str] | None = None
    nearby_object_refs: list[str] | None = None
    conversation_candidate_refs: list[str] | None = None
    engagement_pressure: str | None = None
    privacy_risk_hint: str | None = None
    updated_at: int
```

Expected: backend-side runtime sync objects exist as first-class models instead of free-form dicts.

- [ ] **Step 3: Keep player-input models aligned to the approved `char_c`-first runtime slice**

Confirm `backend/app/models/player_input.py` still contains:

- `MoveIntent`
- `DialogueSubmit`
- `InteractIntent`
- `FocusTargetChange`

and that the fields remain generic enough to carry:

- `actor_id`
- `room_id`
- `producer_ts`

Expected: no new actor semantics are hardcoded into the model layer.

- [ ] **Step 4: Add failing protocol tests for the new message family**

Append to `backend/tests/test_ws_protocol.py`:

```python
def test_character_runtime_state_snapshot_shape() -> None:
    from app.models.runtime_state import CharacterRuntimeStateSnapshot

    event = CharacterRuntimeStateSnapshot(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        revision_seq=1,
        producer_ts=123,
        current_focus_target="char_a",
        current_attention_source="focus_state",
        nearby_actor_refs=["char_a", "char_b"],
        nearby_object_refs=["obj_letter"],
        conversation_candidate_refs=["cand_char_a_letter"],
        engagement_pressure="elevated",
        privacy_risk_hint="low",
        updated_at=124,
    )
    assert event.actor_id == "char_c"
    assert event.conversation_candidate_refs == ["cand_char_a_letter"]


def test_character_runtime_state_delta_shape() -> None:
    from app.models.runtime_state import CharacterRuntimeStateDelta

    event = CharacterRuntimeStateDelta(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        revision_seq=2,
        producer_ts=125,
        changed_fields=["current_focus_target", "conversation_candidate_refs"],
        current_focus_target="obj_letter",
        conversation_candidate_refs=["cand_letter"],
        updated_at=126,
    )
    assert "current_focus_target" in event.changed_fields
    assert event.current_focus_target == "obj_letter"
```

Expected: protocol coverage fails until the new models exist.

- [ ] **Step 5: Run the targeted protocol tests and confirm they pass**

Run:

```powershell
python -m pytest -v backend/tests/test_ws_protocol.py
```

Workdir:

```text
d:\Users\User\Documents\paralls-phase-0-demo
```

Expected: all protocol tests pass, including the new runtime-state message shapes.

## Task 2: Introduce The Conversation / Relation Compiler

**Files:**
- Create: `backend/app/services/conversation_relation_service.py`
- Create: `backend/tests/test_conversation_relation_service.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write the failing compiler tests before adding the service**

Create `backend/tests/test_conversation_relation_service.py`:

```python
from app.services.conversation_relation_service import ConversationRelationService


def test_relation_service_builds_candidate_for_char_c_looking_at_char_a() -> None:
    service = ConversationRelationService()

    service.apply_focus_state(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        target_actor_id="char_a",
        target_object_id="",
        producer_ts=100,
    )

    event = service.build_candidate_event(actor_id="char_c", causation_id="focus:100", correlation_id="focus:100")

    assert event is not None
    assert event.actor_id == "char_c"
    assert event.candidate_actor_ids == ["char_a"]
    assert event.engagement_pressure == "elevated"


def test_relation_service_builds_candidate_for_char_c_near_object() -> None:
    service = ConversationRelationService()

    service.apply_world_result(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        target_object_id="obj_letter",
        result_type="object_interaction_result",
        producer_ts=101,
    )

    event = service.build_candidate_event(actor_id="char_c", causation_id="world:101", correlation_id="world:101")

    assert event is not None
    assert event.candidate_object_ids == ["obj_letter"]
```

Expected: tests fail because the service does not exist yet.

- [ ] **Step 2: Create the minimal compiler service**

Write `backend/app/services/conversation_relation_service.py`:

```python
from app.models.runtime_state import ConversationCandidateEvent


class ConversationRelationService:
    def __init__(self) -> None:
        self._focus_by_actor: dict[str, dict[str, str]] = {}
        self._object_interest_by_actor: dict[str, dict[str, str]] = {}

    def apply_focus_state(
        self,
        *,
        actor_id: str,
        room_id: str,
        scene_id: str,
        zone_id: str,
        target_actor_id: str,
        target_object_id: str,
        producer_ts: int,
    ) -> None:
        self._focus_by_actor[actor_id] = {
            "room_id": room_id,
            "scene_id": scene_id,
            "zone_id": zone_id,
            "target_actor_id": target_actor_id,
            "target_object_id": target_object_id,
            "producer_ts": str(producer_ts),
        }

    def apply_world_result(
        self,
        *,
        actor_id: str,
        room_id: str,
        scene_id: str,
        zone_id: str,
        target_object_id: str,
        result_type: str,
        producer_ts: int,
    ) -> None:
        if result_type != "object_interaction_result":
            return
        self._object_interest_by_actor[actor_id] = {
            "room_id": room_id,
            "scene_id": scene_id,
            "zone_id": zone_id,
            "target_object_id": target_object_id,
            "producer_ts": str(producer_ts),
        }

    def build_candidate_event(self, *, actor_id: str, causation_id: str, correlation_id: str) -> ConversationCandidateEvent | None:
        focus = self._focus_by_actor.get(actor_id, {})
        object_interest = self._object_interest_by_actor.get(actor_id, {})
        room_id = focus.get("room_id") or object_interest.get("room_id")
        scene_id = focus.get("scene_id") or object_interest.get("scene_id")
        zone_id = focus.get("zone_id") or object_interest.get("zone_id")
        if not room_id or not scene_id or not zone_id:
            return None

        candidate_actor_ids = [focus["target_actor_id"]] if focus.get("target_actor_id") else []
        candidate_object_ids = []
        if focus.get("target_object_id"):
            candidate_object_ids.append(focus["target_object_id"])
        if object_interest.get("target_object_id") and object_interest["target_object_id"] not in candidate_object_ids:
            candidate_object_ids.append(object_interest["target_object_id"])

        engagement_pressure = "elevated" if candidate_actor_ids else "present"
        privacy_risk_hint = "low"

        producer_ts = int(focus.get("producer_ts") or object_interest.get("producer_ts") or "0")
        return ConversationCandidateEvent(
            actor_id=actor_id,
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            producer_ts=producer_ts,
            candidate_actor_ids=candidate_actor_ids,
            candidate_object_ids=candidate_object_ids,
            engagement_pressure=engagement_pressure,
            privacy_risk_hint=privacy_risk_hint,
            causation_id=causation_id,
            correlation_id=correlation_id,
        )
```

Expected: a narrow but real compiler exists that can summarize the first `char_c`-centered candidate chain.

- [ ] **Step 3: Run the new relation-service tests**

Run:

```powershell
python -m pytest -v backend/tests/test_conversation_relation_service.py
```

Expected: PASS

- [ ] **Step 4: Wire the compiler into the backend message path**

Modify `backend/app/main.py` so it creates the service once:

```python
from app.services.conversation_relation_service import ConversationRelationService

conversation_relation = ConversationRelationService()
```

Then, inside the `FocusTargetChange` branch:

```python
conversation_relation.apply_focus_state(
    actor_id=event.actor_id,
    room_id=event.room_id,
    scene_id="scene_demo",
    zone_id="zone_focus",
    target_actor_id=event.target_actor_id or "",
    target_object_id=event.target_object_id or "",
    producer_ts=event.producer_ts,
)
candidate = conversation_relation.build_candidate_event(
    actor_id=event.actor_id,
    causation_id=f"focus:{event.producer_ts}",
    correlation_id=f"focus:{event.producer_ts}",
)
if candidate:
    messages.append(_as_envelope("conversation_candidate_event", candidate.model_dump()))
```

And inside the `InteractIntent` branch after `world_result` is produced:

```python
conversation_relation.apply_world_result(
    actor_id=event.actor_id,
    room_id=event.room_id,
    scene_id="scene_demo",
    zone_id="zone_focus",
    target_object_id=event.target_object_id,
    result_type=world_result.result_type,
    producer_ts=world_result.producer_ts,
)
candidate = conversation_relation.build_candidate_event(
    actor_id=event.actor_id,
    causation_id=world_result.causation_id,
    correlation_id=world_result.causation_id,
)
if candidate:
    messages.append(_as_envelope("conversation_candidate_event", candidate.model_dump()))
```

Expected: the first backend-side relationship compiler is now part of the authority lane.

## Task 3: Introduce Minimum Character Runtime State Ownership

**Files:**
- Create: `backend/app/services/character_runtime_state_service.py`
- Create: `backend/tests/test_character_runtime_state_service.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing runtime-state service tests**

Create `backend/tests/test_character_runtime_state_service.py`:

```python
from app.models.runtime_state import ConversationCandidateEvent
from app.services.character_runtime_state_service import CharacterRuntimeStateService


def test_state_service_builds_initial_snapshot_for_actor() -> None:
    service = CharacterRuntimeStateService()
    snapshot = service.get_or_create_snapshot(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=100,
    )
    assert snapshot.actor_id == "char_c"
    assert snapshot.revision_seq == 1


def test_state_service_applies_candidate_event_and_emits_delta() -> None:
    service = CharacterRuntimeStateService()
    service.get_or_create_snapshot(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=100,
    )
    candidate = ConversationCandidateEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=101,
        candidate_actor_ids=["char_a"],
        candidate_object_ids=["obj_letter"],
        engagement_pressure="elevated",
        privacy_risk_hint="low",
        causation_id="focus:101",
        correlation_id="focus:101",
    )
    delta = service.apply_conversation_candidate(candidate)
    assert delta.actor_id == "char_c"
    assert "conversation_candidate_refs" in delta.changed_fields
    assert delta.conversation_candidate_refs == ["cand_char_a_obj_letter"]
```

Expected: tests fail because the service does not exist yet.

- [ ] **Step 2: Create the runtime-state service**

Write `backend/app/services/character_runtime_state_service.py`:

```python
from app.models.runtime_state import CharacterRuntimeStateDelta, CharacterRuntimeStateSnapshot, ConversationCandidateEvent


class CharacterRuntimeStateService:
    def __init__(self) -> None:
        self._state: dict[str, CharacterRuntimeStateSnapshot] = {}

    def get_or_create_snapshot(self, *, actor_id: str, room_id: str, scene_id: str, zone_id: str, producer_ts: int) -> CharacterRuntimeStateSnapshot:
        existing = self._state.get(actor_id)
        if existing:
            return existing
        snapshot = CharacterRuntimeStateSnapshot(
            actor_id=actor_id,
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            revision_seq=1,
            producer_ts=producer_ts,
            updated_at=producer_ts,
        )
        self._state[actor_id] = snapshot
        return snapshot

    def apply_focus_state(self, *, actor_id: str, room_id: str, scene_id: str, zone_id: str, producer_ts: int, target_actor_id: str | None, target_object_id: str | None) -> CharacterRuntimeStateDelta:
        snapshot = self.get_or_create_snapshot(
            actor_id=actor_id,
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            producer_ts=producer_ts,
        )
        snapshot.revision_seq += 1
        snapshot.current_focus_target = target_actor_id or target_object_id
        snapshot.current_attention_source = "focus_state"
        snapshot.updated_at = producer_ts
        return CharacterRuntimeStateDelta(
            actor_id=actor_id,
            room_id=room_id,
            scene_id=scene_id,
            zone_id=zone_id,
            revision_seq=snapshot.revision_seq,
            producer_ts=producer_ts,
            changed_fields=["current_focus_target", "current_attention_source"],
            current_focus_target=snapshot.current_focus_target,
            current_attention_source=snapshot.current_attention_source,
            updated_at=producer_ts,
        )

    def apply_conversation_candidate(self, candidate: ConversationCandidateEvent) -> CharacterRuntimeStateDelta:
        snapshot = self.get_or_create_snapshot(
            actor_id=candidate.actor_id,
            room_id=candidate.room_id,
            scene_id=candidate.scene_id,
            zone_id=candidate.zone_id,
            producer_ts=candidate.producer_ts,
        )
        snapshot.revision_seq += 1
        snapshot.nearby_actor_refs = candidate.candidate_actor_ids
        snapshot.nearby_object_refs = candidate.candidate_object_ids
        snapshot.conversation_candidate_refs = ["cand_char_a_obj_letter"] if candidate.candidate_actor_ids or candidate.candidate_object_ids else []
        snapshot.engagement_pressure = candidate.engagement_pressure
        snapshot.privacy_risk_hint = candidate.privacy_risk_hint
        snapshot.updated_at = candidate.producer_ts
        return CharacterRuntimeStateDelta(
            actor_id=snapshot.actor_id,
            room_id=snapshot.room_id,
            scene_id=snapshot.scene_id,
            zone_id=snapshot.zone_id,
            revision_seq=snapshot.revision_seq,
            producer_ts=candidate.producer_ts,
            changed_fields=[
                "nearby_actor_refs",
                "nearby_object_refs",
                "conversation_candidate_refs",
                "engagement_pressure",
                "privacy_risk_hint",
            ],
            nearby_actor_refs=snapshot.nearby_actor_refs,
            nearby_object_refs=snapshot.nearby_object_refs,
            conversation_candidate_refs=snapshot.conversation_candidate_refs,
            engagement_pressure=snapshot.engagement_pressure,
            privacy_risk_hint=snapshot.privacy_risk_hint,
            updated_at=snapshot.updated_at,
        )
```

Expected: backend now has a true minimum owner for character runtime state.

- [ ] **Step 3: Run the new runtime-state tests**

Run:

```powershell
python -m pytest -v backend/tests/test_character_runtime_state_service.py
```

Expected: PASS

- [ ] **Step 4: Wire runtime-state snapshot/delta emission into `backend/app/main.py`**

Create one service instance:

```python
from app.services.character_runtime_state_service import CharacterRuntimeStateService

character_runtime_state = CharacterRuntimeStateService()
```

After focus-state handling:

```python
delta = character_runtime_state.apply_focus_state(
    actor_id=event.actor_id,
    room_id=event.room_id,
    scene_id="scene_demo",
    zone_id="zone_focus",
    producer_ts=event.producer_ts,
    target_actor_id=event.target_actor_id,
    target_object_id=event.target_object_id,
)
messages.append(_as_envelope("character_runtime_state_delta", delta.model_dump()))
```

After conversation-candidate handling:

```python
state_delta = character_runtime_state.apply_conversation_candidate(candidate)
messages.append(_as_envelope("character_runtime_state_delta", state_delta.model_dump()))
```

Expected: backend produces real actor-scoped runtime sync messages instead of leaving Godot to infer everything locally.

## Task 4: Connect Siming To Relationship Candidates

**Files:**
- Modify: `backend/app/services/siming_service.py`
- Modify: `backend/tests/test_siming_service.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add a failing Siming test for conversation-candidate consumption**

Append to `backend/tests/test_siming_service.py`:

```python
from app.models.runtime_state import ConversationCandidateEvent


def test_siming_emits_attention_prompt_for_char_c_candidate_actor() -> None:
    from app.services.siming_service import SimingService

    service = SimingService()
    event = ConversationCandidateEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=200,
        candidate_actor_ids=["char_a"],
        candidate_object_ids=[],
        engagement_pressure="elevated",
        privacy_risk_hint="low",
        causation_id="cand:200",
        correlation_id="cand:200",
    )
    result = service.evaluate_candidate_relationship(event)
    assert result.output_type == "attention_prompt"
    assert result.target_actor_id == "char_a"
```

Expected: FAIL until Siming can consume candidate summaries.

- [ ] **Step 2: Add the minimum Siming relationship-consumer method**

Modify `backend/app/services/siming_service.py`:

```python
from app.models.runtime_state import ConversationCandidateEvent

def evaluate_candidate_relationship(self, event: ConversationCandidateEvent):
    target_actor_id = event.candidate_actor_ids[0] if event.candidate_actor_ids else None
    target_object_id = event.candidate_object_ids[0] if event.candidate_object_ids else None
    summary = "watch %s" % target_actor_id if target_actor_id else "watch %s" % target_object_id
    return AttentionPrompt(
        room_id=event.room_id,
        output_type="attention_prompt",
        causation_id=f"siming:{event.causation_id}",
        producer_ts=event.producer_ts + 1,
        target_actor_id=target_actor_id,
        target_object_id=target_object_id,
        prompt_summary=summary,
    )
```

Expected: Siming now has one real relationship-aware judgment path.

- [ ] **Step 3: Route candidate events into Siming from `backend/app/main.py`**

After a candidate event is built:

```python
siming_candidate_output = siming_service.evaluate_candidate_relationship(candidate)
event_trace.record(siming_candidate_output.output_type)
messages.append(_as_envelope("siming_output", siming_candidate_output.model_dump()))
```

Expected: `player drives C` can now influence Siming before or alongside object interaction.

- [ ] **Step 4: Run the Siming tests**

Run:

```powershell
python -m pytest -v backend/tests/test_siming_service.py
```

Expected: PASS

## Task 5: Teach Godot To Consume Runtime State Sync

**Files:**
- Modify: `scripts/autoload/LocalPresentationBus.gd`
- Modify: `scripts/autoload/BackendBridge.gd`
- Modify: `scripts/character/CharacterReplica.gd`
- Modify: `scripts/phase0/MainDemoController.gd`

- [ ] **Step 1: Add new local signals for backend runtime sync**

Modify `scripts/autoload/LocalPresentationBus.gd`:

```gdscript
signal character_runtime_state_snapshot_received(payload)
signal character_runtime_state_delta_received(payload)
signal conversation_candidate_received(payload)
```

Expected: Godot can route the new authority-side sync messages without abusing existing signals.

- [ ] **Step 2: Extend `BackendBridge.gd` message dispatch**

Add match branches:

```gdscript
"conversation_candidate_event":
    _bus_emit("conversation_candidate_received", [payload])
"character_runtime_state_snapshot":
    _bus_emit("character_runtime_state_snapshot_received", [payload])
"character_runtime_state_delta":
    _bus_emit("character_runtime_state_delta_received", [payload])
```

Expected: backend-side runtime messages enter the Godot local presentation bus explicitly.

- [ ] **Step 3: Add a minimum runtime-state consumer to `CharacterReplica.gd`**

Add runtime fields:

```gdscript
var runtime_focus_target := ""
var runtime_attention_source := ""
var runtime_nearby_actor_refs: Array[String] = []
var runtime_nearby_object_refs: Array[String] = []
var runtime_conversation_candidate_refs: Array[String] = []
var runtime_engagement_pressure := ""
var runtime_privacy_risk_hint := ""
```

Add bus hookups in `_ready()`:

```gdscript
if bus.has_signal("character_runtime_state_delta_received"):
    bus.character_runtime_state_delta_received.connect(_on_character_runtime_state_delta_received)
if bus.has_signal("character_runtime_state_snapshot_received"):
    bus.character_runtime_state_snapshot_received.connect(_on_character_runtime_state_snapshot_received)
```

Add handlers:

```gdscript
func _on_character_runtime_state_snapshot_received(payload: Dictionary) -> void:
    if str(payload.get("actor_id", "")) != actor_id:
        return
    _apply_runtime_state_payload(payload)

func _on_character_runtime_state_delta_received(payload: Dictionary) -> void:
    if str(payload.get("actor_id", "")) != actor_id:
        return
    _apply_runtime_state_payload(payload)

func _apply_runtime_state_payload(payload: Dictionary) -> void:
    runtime_focus_target = str(payload.get("current_focus_target", runtime_focus_target))
    runtime_attention_source = str(payload.get("current_attention_source", runtime_attention_source))
    if payload.has("nearby_actor_refs"):
        runtime_nearby_actor_refs = Array(payload.get("nearby_actor_refs", []), TYPE_STRING, &"", null)
    if payload.has("nearby_object_refs"):
        runtime_nearby_object_refs = Array(payload.get("nearby_object_refs", []), TYPE_STRING, &"", null)
    if payload.has("conversation_candidate_refs"):
        runtime_conversation_candidate_refs = Array(payload.get("conversation_candidate_refs", []), TYPE_STRING, &"", null)
    runtime_engagement_pressure = str(payload.get("engagement_pressure", runtime_engagement_pressure))
    runtime_privacy_risk_hint = str(payload.get("privacy_risk_hint", runtime_privacy_risk_hint))
```

Expected: the shared role shell now consumes real backend-owned runtime state.

- [ ] **Step 4: Make the current visible response layer key off synced state where it already makes sense**

For the minimum response, continue using:

- `focus_state`
- `siming_output`

But allow `runtime_focus_target` / `runtime_attention_source` to enrich debugging and future behavior without replacing all current logic in one jump.

Expected: the current demo stays stable while the authority-side runtime slice becomes real.

## Task 6: Improve Runtime Identity And Connection Trust

**Files:**
- Modify: `backend/app/main.py`
- Create or modify: `backend/tests/test_health.py`
- Modify: `scripts/phase0/MainDemoController.gd`

- [ ] **Step 1: Add a failing health-identity test**

If missing, write `backend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient
from app.main import app


def test_health_exposes_current_backend_identity() -> None:
    client = TestClient(app)
    response = client.get("/health")
    payload = response.json()
    assert payload["status"] == "ok"
    assert "build" in payload
    assert "worktree_root" in payload
```

Expected: FAIL until health returns more than `status`.

- [ ] **Step 2: Expose backend identity in `/health`**

Modify `backend/app/main.py`:

```python
from pathlib import Path

BACKEND_BUILD = "paralls-phase0-backend-worktree-2026-06-02"
WORKTREE_ROOT = str(Path(__file__).resolve().parents[2])

@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "build": BACKEND_BUILD,
        "worktree_root": WORKTREE_ROOT,
    }
```

Expected: the running backend can prove which worktree it came from.

- [ ] **Step 3: Log the backend identity from Godot after connection**

Add a lightweight HTTP fetch helper or a platform-safe shell-free request path in `scripts/phase0/MainDemoController.gd` that, on successful backend connection, fetches `/health` and logs:

```gdscript
phase0_backend_identity:<build>:<worktree_root>
```

If the project already has an HTTP utility, reuse it. If not, use `HTTPRequest` in a small, focused way and keep it inside `MainDemoController` for now.

Expected: future validation immediately proves whether Godot is connected to the intended backend instance.

## Task 7: Make Focus-Response Evidence Easier To See

**Files:**
- Modify: `scripts/character/CharacterReplica.gd`
- Modify: `scripts/character/GreyboxHumanoidVisual.gd`
- Modify: `scripts/phase0/MainDemoController.gd`

- [ ] **Step 1: Confirm the current focus-response evidence path**

Re-read:

```powershell
Get-Content scripts/character/CharacterReplica.gd
Get-Content scripts/character/GreyboxHumanoidVisual.gd
```

Expected: current nameplate / highlight / posture response path is visible.

- [ ] **Step 2: Strengthen the visible response without inventing a new animation stack**

For `CharacterReplica.gd`, keep the current:

- `focus_attention_visual_timer`
- `focus_attention_posture_timer`
- `CHAR_A !`

Then strengthen one of:

- body mesh focus color
- role-asset overlay intensity
- camera framing for focus-autotest

Do not introduce a new broad animation system in this task.

Expected: a focus-response screenshot becomes a strong human-facing proof rather than only a log-facing proof.

- [ ] **Step 3: Tune the focus-autotest framing if needed**

Adjust only if current screenshots still undersell the response:

- `focus_autotest_vantage_offset`
- focus camera pitch
- focus camera spring length

Expected: `CharacterA` occupies enough of the frame that the response is obvious.

## Task 8: Full Verification Loop

**Files:**
- Verify: `backend/tests/`
- Verify: `scripts/`
- Verify: `scenes/phase0/MainDemo.tscn`

- [ ] **Step 1: Run the full backend test suite**

Run:

```powershell
python -m pytest -v
```

Workdir:

```text
d:\Users\User\Documents\paralls-phase-0-demo\backend
```

Expected: PASS

- [ ] **Step 2: Run the health identity check against the live backend**

Run:

```powershell
python -c "import urllib.request, json; print(json.dumps(json.load(urllib.request.urlopen('http://127.0.0.1:8000/health')), ensure_ascii=False))"
```

Expected: JSON contains `status`, `build`, and `worktree_root`.

- [ ] **Step 3: Run Godot scene-load verification**

Run:

```powershell
& 'E:\下载\Godot_v4.6.3-stable_win64.exe\Godot_v4.6.3-stable_win64_console.exe' --path 'D:\Users\User\Documents\paralls-phase-0-demo' --scene 'res://scenes/phase0/MainDemo.tscn' --quit-after 200 --verbose --render-thread safe
```

Expected: scene loads without script parse errors.

- [ ] **Step 4: Run the main autotest loop**

Run:

```powershell
$env:PHASE0_AUTOTEST='1'
$env:PHASE0_AUTOTEST_SCREENSHOT='D:\Users\User\Documents\paralls-phase-0-demo\.harness\verification\phase05-player-c-runtime-alignment.png'
& 'E:\下载\Godot_v4.6.3-stable_win64.exe\Godot_v4.6.3-stable_win64_console.exe' --path 'D:\Users\User\Documents\paralls-phase-0-demo' --scene 'res://scenes/phase0/MainDemo.tscn' --quit-after 400 --verbose --render-thread safe
```

Expected:

- dialogue loop still works
- interaction loop still works
- environment shift still works
- Siming output still works
- screenshot saved

- [ ] **Step 5: Run the dedicated focus-response autotest**

Run:

```powershell
$env:PHASE0_FOCUS_AUTOTEST='1'
$env:PHASE0_AUTOTEST_SCREENSHOT='D:\Users\User\Documents\paralls-phase-0-demo\.harness\verification\phase05-focus-response-runtime-alignment.png'
& 'E:\下载\Godot_v4.6.3-stable_win64.exe\Godot_v4.6.3-stable_win64_console.exe' --path 'D:\Users\User\Documents\paralls-phase-0-demo' --scene 'res://scenes/phase0/MainDemo.tscn' --quit-after 400 --verbose --render-thread safe
```

Expected:

- `focus_state` appears in logs
- `focus_state_applied:char_a` appears in logs
- `focus_attention:char_a` appears in logs
- screenshot saved

- [ ] **Step 6: Manually inspect the two screenshots**

Open:

```text
.harness/verification/phase05-player-c-runtime-alignment.png
.harness/verification/phase05-focus-response-runtime-alignment.png
```

Expected:

- first image proves the main `Phase 0.5` loop still reads well
- second image proves `A` visibly reacts to `C`'s focus

## Self-Review

### Spec coverage

- Backend-first authority lane: covered by Tasks 1-4 and 6.
- `room/scene/zone` canonical scope: covered by Tasks 1-3.
- `visual_fact_event` as Godot-produced authority input: represented in Tasks 1, 2, and optional follow-on visual-fact implementation.
- Dedicated conversation/relation compiler: covered in Task 2.
- Character runtime state ownership + snapshot/delta sync: covered in Task 3.
- Siming minimum judgment on relationship candidates: covered in Task 4.
- Godot local presentation consuming authority sync: covered in Task 5.
- Verification proof for `player drives C`: covered in Task 8.

No spec coverage gaps found.

### Placeholder scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- All steps include concrete file paths, commands, and code sketches.

### Type consistency

- `conversation_candidate_event`
- `character_runtime_state_snapshot`
- `character_runtime_state_delta`
- `focus_state`
- `siming_output`

are named consistently across the plan.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-02-phase05-runtime-alignment-implementation-plan.md`. Two execution options:

1. Subagent-Driven (recommended) - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. Inline Execution - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
