# L1 Raw Fact Emitter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the current Phase 0 visual fact slice to a shared `L1` raw fact pipeline that preserves existing demo behavior while adding the first minimal `spatial_access_fact` slice.

**Architecture:** Keep current Phase 0 semantics intact, but move the repo from `visual_fact_event` hardcoding to a shared `raw_fact_event -> fact_router -> fact handlers` structure. On the Godot side, separate fact sampling from fact transport by introducing a single cross-boundary emitter plus small family-specific emitters/adapters.

**Tech Stack:** Godot 4 GDScript, FastAPI, Pydantic, pytest, PowerShell, existing `BackendBridge` / `LocalPresentationBus` verification flow.

---

## File Structure

### Backend

- Create: `backend/app/models/raw_fact.py`
  - Shared raw-fact schema used by the new ingress and handlers.
- Create: `backend/app/services/fact_router.py`
  - Routes `RawFactEvent` by `fact_family`.
- Create: `backend/app/services/fact_handlers/visual_fact_handler.py`
  - Preserves current visual fact behavior via the shared ingress.
- Create: `backend/app/services/fact_handlers/spatial_access_fact_handler.py`
  - Stores minimal access evidence for Phase 0 without performing membership inference.
- Modify: `backend/app/main.py`
  - Add `raw_fact_event` ingress and route to `fact_router`.
- Modify: `backend/app/models/visual_fact.py`
  - Keep as compatibility shim or adapter during migration.
- Modify: `backend/tests/test_visual_fact_pipeline.py`
  - Preserve current behavior and add raw-fact ingress coverage.
- Create: `backend/tests/test_raw_fact_router.py`
  - Router and spatial-access tests.

### Godot

- Create: `scripts/l1/facts/RawFactEmitter.gd`
  - Single Godot -> backend raw fact transport surface.
- Create: `scripts/l1/facts/FactEnvelopeBuilder.gd`
  - Builds `raw_fact_event` payloads with shared context.
- Create: `scripts/l1/facts/FactDeduper.gd`
  - Simple signature+cooldown dedupe for noisy facts.
- Create: `scripts/l1/facts/emitters/CharacterVisualFactEmitter.gd`
  - Emits gaze-derived visual facts.
- Create: `scripts/l1/facts/emitters/EnvironmentVisualFactEmitter.gd`
  - Emits environment visual facts.
- Create: `scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd`
  - Emits the first access/privacy raw facts.
- Modify: `scripts/visual/VisualFactEmitter.gd`
  - Convert into compatibility wrapper or replace references with `RawFactEmitter`.
- Modify: `scripts/phase0/MainDemoController.gd`
  - Stop building payloads directly; call family emitters instead.
- Modify: `scripts/environment/EnvironmentStateController.gd`
  - Stop building payloads directly; call environment emitter instead.
- Modify: `scenes/phase0/MainDemo.tscn`
  - Update node/script wiring if emitter node path changes.
- Modify: `scripts/verification/common.py`
  - Update bypass scan to recognize the shared emitter instead of only `VisualFactEmitter.gd`.

### Docs

- Modify: `docs/superpowers/specs/2026-06-06-l1-raw-fact-emitter-design.md`
  - Link to the final implementation plan after execution decisions are made.

---

### Task 1: Introduce Shared Raw Fact Backend Model

**Files:**
- Create: `backend/app/models/raw_fact.py`
- Modify: `backend/app/models/visual_fact.py`
- Test: `backend/tests/test_raw_fact_router.py`

- [ ] **Step 1: Write the failing tests**

```python
from app.models.raw_fact import RawFactEvent


def test_raw_fact_event_accepts_visual_fact_shape() -> None:
    event = RawFactEvent(
        fact_family="visual_fact",
        fact_type="fixed_gaze_on_target",
        relation_type="actor_looks_at_actor",
        producer_ts=123,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={
            "layer": "L1",
            "system": "godot.raw_fact_emitter",
            "actor_id": "char_c",
        },
        targets={"actor_id": "char_a"},
    )

    assert event.fact_family == "visual_fact"
    assert event.source.actor_id == "char_c"
    assert event.targets.actor_id == "char_a"


def test_raw_fact_event_accepts_spatial_access_shape() -> None:
    event = RawFactEvent(
        fact_family="spatial_access_fact",
        fact_type="actor_entered_zone",
        relation_type="actor_approached_actor",
        producer_ts=200,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_private",
        source={
            "layer": "L1",
            "system": "godot.raw_fact_emitter",
            "actor_id": "char_c",
        },
        targets={"actor_id": "char_a"},
        world={"distance_m": 1.8, "state_before": "public", "state_after": "local"},
        observability={"visual": True, "auditory": True, "occluded": False},
    )

    assert event.world.distance_m == 1.8
    assert event.world.state_after == "local"
    assert event.observability.auditory is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -v backend/tests/test_raw_fact_router.py`

Expected: FAIL with `ModuleNotFoundError` or import failure for `app.models.raw_fact`.

- [ ] **Step 3: Write minimal implementation**

```python
from pydantic import BaseModel, Field


class RawFactSource(BaseModel):
    layer: str = "L1"
    system: str
    actor_id: str = ""
    object_id: str = ""
    environment_id: str = ""


class RawFactTargets(BaseModel):
    actor_id: str = ""
    object_id: str = ""
    environment_id: str = ""


class RawFactWorld(BaseModel):
    position: list[float] | None = None
    distance_m: float | None = None
    state_before: str = ""
    state_after: str = ""


class RawFactObservability(BaseModel):
    visual: bool = False
    auditory: bool = False
    occluded: bool = False


class RawFactEvent(BaseModel):
    event_type: str = "raw_fact_event"
    fact_family: str
    fact_type: str
    relation_type: str = ""
    producer_ts: int
    room_id: str
    scene_id: str
    zone_id: str
    source: RawFactSource
    targets: RawFactTargets
    world: RawFactWorld = Field(default_factory=RawFactWorld)
    observability: RawFactObservability = Field(default_factory=RawFactObservability)
    causation_id: str = ""
    correlation_id: str = ""
```

- [ ] **Step 4: Keep visual fact compatibility shim explicit**

```python
from app.models.raw_fact import RawFactEvent


class VisualFactEvent(RawFactEvent):
    @property
    def actor_id(self) -> str:
        return self.source.actor_id

    @property
    def target_actor_id(self) -> str | None:
        return self.targets.actor_id or None

    @property
    def target_object_id(self) -> str | None:
        return self.targets.object_id or None

    @property
    def target_environment_id(self) -> str | None:
        return self.targets.environment_id or None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest -v backend/tests/test_raw_fact_router.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/models/raw_fact.py backend/app/models/visual_fact.py backend/tests/test_raw_fact_router.py
@'
Stabilize L1 fact ingress around a shared raw fact envelope

Constraint: Phase 0 must preserve existing visual fact semantics during migration
Rejected: Replace all visual_fact_event consumers in one patch | too risky before ingress tests exist
Confidence: high
Scope-risk: narrow
Directive: Keep raw fact models inference-free; membership and privacy conclusions stay above L1 ingress
Tested: python -m pytest -v backend/tests/test_raw_fact_router.py
Not-tested: Godot runtime integration
'@ | git commit -F -
```

### Task 2: Add Backend Fact Router And Preserve Visual Fact Behavior

**Files:**
- Create: `backend/app/services/fact_router.py`
- Create: `backend/app/services/fact_handlers/visual_fact_handler.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_visual_fact_pipeline.py`

- [ ] **Step 1: Write the failing router test**

```python
from app.models.raw_fact import RawFactEvent
from app.services.fact_router import FactRouter


def test_fact_router_routes_visual_fact_to_visual_handler() -> None:
    router = FactRouter()
    event = RawFactEvent(
        fact_family="visual_fact",
        fact_type="fixed_gaze_on_target",
        relation_type="actor_looks_at_actor",
        producer_ts=300,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
        targets={"actor_id": "char_a"},
    )

    result = router.route(event)

    assert result.handler_name == "visual_fact_handler"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -v backend/tests/test_raw_fact_router.py::test_fact_router_routes_visual_fact_to_visual_handler`

Expected: FAIL because `FactRouter` does not exist.

- [ ] **Step 3: Implement the minimal router and visual handler**

```python
from dataclasses import dataclass


@dataclass
class RoutedFactResult:
    handler_name: str


class FactRouter:
    def route(self, event):
        if event.fact_family == "visual_fact":
            return RoutedFactResult(handler_name="visual_fact_handler")
        if event.fact_family == "spatial_access_fact":
            return RoutedFactResult(handler_name="spatial_access_fact_handler")
        raise ValueError(f"Unsupported fact_family: {event.fact_family}")
```

```python
from app.models.visual_fact import VisualFactEvent


def as_visual_fact(event) -> VisualFactEvent:
    return VisualFactEvent(
        fact_family=event.fact_family,
        fact_type=event.fact_type,
        relation_type=event.relation_type,
        producer_ts=event.producer_ts,
        room_id=event.room_id,
        scene_id=event.scene_id,
        zone_id=event.zone_id,
        source=event.source.model_dump(),
        targets=event.targets.model_dump(),
        world=event.world.model_dump(),
        observability=event.observability.model_dump(),
        causation_id=event.causation_id,
        correlation_id=event.correlation_id,
    )
```

- [ ] **Step 4: Add shared ingress support in `backend/app/main.py`**

```python
if envelope.message_type == "raw_fact_event":
    event = RawFactEvent(**envelope.payload)
    if event.fact_family == "visual_fact":
        visual_event = as_visual_fact(event)
        return handle_visual_fact_event(visual_event)
```

```python
def handle_visual_fact_event(event: VisualFactEvent) -> list[dict[str, object]]:
    conversation_relation_service.apply_visual_fact(event)
    event_trace.record(event.fact_type)
    event_trace.record(event.relation_type)
    messages = [
        {
            "message_type": "ack",
            "payload": {
                "accepted": True,
                "source_type": "raw_fact_event",
                "route": "authority_visual_fact",
            },
        }
    ]
    messages.extend(
        _ensure_runtime_snapshot(
            actor_id=event.actor_id,
            room_id=event.room_id,
            scene_id=event.scene_id,
            zone_id=event.zone_id,
            producer_ts=event.producer_ts,
        )
    )
    visual_delta = _project_runtime_delta(event.actor_id, event.producer_ts)
    if visual_delta is not None:
        messages.append(visual_delta)
    visual_fact_siming_output = siming_service.evaluate_visual_fact(event)
    if visual_fact_siming_output is not None:
        event_trace.record(visual_fact_siming_output.output_type)
        messages.append(_as_envelope("siming_output", visual_fact_siming_output.model_dump()))
    candidate = conversation_relation_service.build_candidate_event(
        actor_id=event.actor_id,
        causation_id=f"visual_fact:{event.producer_ts}",
        correlation_id=f"visual_fact:{event.producer_ts}",
    )
    messages.extend(_candidate_messages(candidate))
    return messages
```

- [ ] **Step 5: Add ingress parity test**

```python
def test_websocket_raw_visual_fact_event_matches_legacy_visual_fact_behavior() -> None:
    reset_runtime_state()
    client = TestClient(app)
    with client.websocket_connect("/ws") as websocket:
        websocket.send_json(
            {
                "message_type": "raw_fact_event",
                "payload": {
                    "event_type": "raw_fact_event",
                    "fact_family": "visual_fact",
                    "fact_type": "light_level_drop",
                    "relation_type": "environment_light_drop",
                    "producer_ts": 451,
                    "room_id": "room_demo",
                    "scene_id": "scene_demo",
                    "zone_id": "zone_focus",
                    "source": {
                        "layer": "L1",
                        "system": "godot.raw_fact_emitter",
                        "actor_id": "char_c",
                    },
                    "targets": {"environment_id": "env_lamp"},
                },
            }
        )
        ack = websocket.receive_json()
        assert ack["payload"]["route"] == "authority_visual_fact"
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest -v backend/tests/test_raw_fact_router.py backend/tests/test_visual_fact_pipeline.py`

Expected: PASS, including parity between legacy `visual_fact_event` and new `raw_fact_event`.

- [ ] **Step 7: Commit**

```powershell
git add backend/app/services/fact_router.py backend/app/services/fact_handlers/visual_fact_handler.py backend/app/main.py backend/tests/test_visual_fact_pipeline.py backend/tests/test_raw_fact_router.py
@'
Preserve Phase 0 visual fact behavior behind a shared raw fact ingress

Constraint: Existing runtime projection and Siming hooks must not regress while ingress generalizes
Rejected: Delay raw_fact_event until spatial access is ready | would duplicate migration work later
Confidence: high
Scope-risk: moderate
Directive: All new fact families must enter through fact_router; do not add new main.py top-level branches per family
Tested: python -m pytest -v backend/tests/test_raw_fact_router.py backend/tests/test_visual_fact_pipeline.py
Not-tested: Godot runtime scene verification
'@ | git commit -F -
```

### Task 3: Introduce Godot Shared Raw Fact Transport

**Files:**
- Create: `scripts/l1/facts/RawFactEmitter.gd`
- Create: `scripts/l1/facts/FactEnvelopeBuilder.gd`
- Create: `scripts/l1/facts/FactDeduper.gd`
- Modify: `scripts/visual/VisualFactEmitter.gd`
- Modify: `scripts/verification/common.py`

- [ ] **Step 1: Write the failing verification scan expectation**

```python
def test_visual_fact_bypass_scan_allows_shared_raw_fact_emitter_only() -> None:
    project_root = repo_root()
    result = scan_direct_visual_fact_bypass(project_root)

    assert "scripts/l1/facts/RawFactEmitter.gd:allowed-emitter-send" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest -v backend/tests/test_verification_audit.py`

Expected: FAIL because the scan helper does not recognize the shared emitter path.

- [ ] **Step 3: Add shared envelope builder**

```gdscript
extends RefCounted
class_name FactEnvelopeBuilder

static func build_raw_fact_envelope(payload: Dictionary) -> Dictionary:
    var normalized := payload.duplicate(true)
    normalized["event_type"] = "raw_fact_event"
    return {
        "message_type": "raw_fact_event",
        "payload": normalized,
    }
```

- [ ] **Step 4: Add deduper**

```gdscript
extends Node
class_name FactDeduper

var _last_by_signature: Dictionary = {}

func should_emit(signature: String, now_ms: int, cooldown_ms: int) -> bool:
    var previous: int = int(_last_by_signature.get(signature, 0))
    if previous > 0 and now_ms - previous < cooldown_ms:
        return false
    _last_by_signature[signature] = now_ms
    return true
```

- [ ] **Step 5: Add shared raw fact emitter**

```gdscript
extends Node
class_name RawFactEmitter

@export var actor_id := "char_c"
@export var room_id := "room_demo"
@export var scene_id := "scene_demo"
@export var zone_id := "zone_focus"

@onready var _deduper: FactDeduper = FactDeduper.new()

func emit_fact(payload: Dictionary, signature: String = "", cooldown_ms: int = 0) -> bool:
    var bridge := get_node_or_null("/root/BackendBridge")
    if bridge == null or not bridge.has_method("send_envelope"):
        return false
    var now_ms := Time.get_ticks_msec()
    if signature != "" and cooldown_ms > 0 and not _deduper.should_emit(signature, now_ms, cooldown_ms):
        return false
    if not payload.has("producer_ts"):
        payload["producer_ts"] = now_ms
    if not payload.has("room_id"):
        payload["room_id"] = room_id
    if not payload.has("scene_id"):
        payload["scene_id"] = scene_id
    if not payload.has("zone_id"):
        payload["zone_id"] = zone_id
    var envelope := FactEnvelopeBuilder.build_raw_fact_envelope(payload)
    var err: int = bridge.send_envelope(envelope)
    return err == OK
```

- [ ] **Step 6: Turn old `VisualFactEmitter.gd` into a compatibility wrapper**

```gdscript
extends Node

@onready var raw_fact_emitter: RawFactEmitter = $RawFactEmitter

func emit_visual_fact(
    fact_type: String,
    relation_type: String,
    target_actor_id: String = "",
    target_object_id: String = "",
    target_environment_id: String = ""
) -> bool:
    var payload := {
        "fact_family": "visual_fact",
        "fact_type": fact_type,
        "relation_type": relation_type,
        "source": {
            "layer": "L1",
            "system": "godot.raw_fact_emitter",
            "actor_id": raw_fact_emitter.actor_id,
        },
        "targets": {
            "actor_id": target_actor_id,
            "object_id": target_object_id,
            "environment_id": target_environment_id,
        },
    }
    return raw_fact_emitter.emit_fact(payload)
```

- [ ] **Step 7: Update verification scan**

```python
if normalized.endswith("scripts/l1/facts/RawFactEmitter.gd"):
    suspicious.append(f"{normalized}:allowed-emitter-send")
    continue
```

- [ ] **Step 8: Run verification tests**

Run: `python -m pytest -v backend/tests/test_verification_audit.py`

Expected: PASS with shared emitter recognized as the only allowed sender.

- [ ] **Step 9: Commit**

```powershell
git add scripts/l1/facts/RawFactEmitter.gd scripts/l1/facts/FactEnvelopeBuilder.gd scripts/l1/facts/FactDeduper.gd scripts/visual/VisualFactEmitter.gd scripts/verification/common.py backend/tests/test_verification_audit.py
@'
Unify Godot fact transport behind a single raw fact emitter

Constraint: Godot controllers must stop owning cross-boundary payload assembly
Rejected: Delete VisualFactEmitter immediately | breaks existing scene wiring before emitter migration completes
Confidence: medium
Scope-risk: moderate
Directive: RawFactEmitter is the only allowed Godot -> backend fact sender
Tested: python -m pytest -v backend/tests/test_verification_audit.py
Not-tested: MainDemo.tscn runtime wiring
'@ | git commit -F -
```

### Task 4: Migrate Existing Visual Fact Call Sites To Family Emitters

**Files:**
- Create: `scripts/l1/facts/emitters/CharacterVisualFactEmitter.gd`
- Create: `scripts/l1/facts/emitters/EnvironmentVisualFactEmitter.gd`
- Modify: `scripts/phase0/MainDemoController.gd`
- Modify: `scripts/environment/EnvironmentStateController.gd`
- Modify: `scenes/phase0/MainDemo.tscn`

- [ ] **Step 1: Write the failing backend behavior test for raw fact parity**

```python
def test_legacy_visual_paths_and_new_emitters_share_same_backend_route() -> None:
    reset_runtime_state()
    result = _handle_envelope(
        Envelope(
            message_type="raw_fact_event",
            payload={
                "event_type": "raw_fact_event",
                "fact_family": "visual_fact",
                "fact_type": "fixed_gaze_on_target",
                "relation_type": "actor_looks_at_object",
                "producer_ts": 600,
                "room_id": "room_demo",
                "scene_id": "scene_demo",
                "zone_id": "zone_focus",
                "source": {"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
                "targets": {"object_id": "obj_letter"},
            },
        )
    )

    assert result[0]["payload"]["route"] == "authority_visual_fact"
```

- [ ] **Step 2: Run test to verify it fails if routing is not fully wired**

Run: `python -m pytest -v backend/tests/test_visual_fact_pipeline.py::test_legacy_visual_paths_and_new_emitters_share_same_backend_route`

Expected: FAIL until raw ingress is fully used by migrated emitters.

- [ ] **Step 3: Add character visual emitter**

```gdscript
extends Node
class_name CharacterVisualFactEmitter

@export_node_path("Node") var raw_fact_emitter_path := NodePath("../RawFactEmitter")

func emit_fixed_gaze_on_actor(source_actor_id: String, target_actor_id: String) -> bool:
    return _emit("fixed_gaze_on_target", "actor_looks_at_actor", source_actor_id, target_actor_id, "")

func emit_fixed_gaze_on_object(source_actor_id: String, target_object_id: String) -> bool:
    return _emit("fixed_gaze_on_target", "actor_looks_at_object", source_actor_id, "", target_object_id)

func _emit(fact_type: String, relation_type: String, source_actor_id: String, target_actor_id: String, target_object_id: String) -> bool:
    var emitter := get_node_or_null(raw_fact_emitter_path)
    if emitter == null:
        return false
    return emitter.emit_fact(
        {
            "fact_family": "visual_fact",
            "fact_type": fact_type,
            "relation_type": relation_type,
            "source": {"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": source_actor_id},
            "targets": {"actor_id": target_actor_id, "object_id": target_object_id},
            "observability": {"visual": true},
        }
    )
```

- [ ] **Step 4: Add environment visual emitter**

```gdscript
extends Node
class_name EnvironmentVisualFactEmitter

@export_node_path("Node") var raw_fact_emitter_path := NodePath("../RawFactEmitter")

func emit_light_level_drop(source_actor_id: String, target_environment_id: String, previous_state: String, next_state: String) -> bool:
    var emitter := get_node_or_null(raw_fact_emitter_path)
    if emitter == null:
        return false
    return emitter.emit_fact(
        {
            "fact_family": "visual_fact",
            "fact_type": "light_level_drop",
            "relation_type": "environment_light_drop",
            "source": {"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": source_actor_id},
            "targets": {"environment_id": target_environment_id},
            "world": {"state_before": previous_state, "state_after": next_state},
            "observability": {"visual": true},
        }
    )
```

- [ ] **Step 5: Replace controller payload assembly with emitter calls**

```gdscript
var emitted: bool = character_visual_fact_emitter.emit_fixed_gaze_on_actor(player_actor_id, target_actor_id)
```

```gdscript
var emitted: bool = character_visual_fact_emitter.emit_fixed_gaze_on_object(player_actor_id, target_object_id)
```

```gdscript
var emitted: bool = environment_visual_fact_emitter.emit_light_level_drop("char_c", environment_id, previous_state, next_state)
```

- [ ] **Step 6: Update scene wiring**

```text
MainDemo
  RawFactEmitter
  CharacterVisualFactEmitter
  EnvironmentVisualFactEmitter
  VisualFactEmitter (compatibility wrapper, optional transitional node)
```

- [ ] **Step 7: Run focused backend and repo verification**

Run: `python -m pytest -v backend/tests/test_visual_fact_pipeline.py backend/tests/test_siming_service.py`

Expected: PASS with no behavior regression.

- [ ] **Step 8: Commit**

```powershell
git add scripts/l1/facts/emitters/CharacterVisualFactEmitter.gd scripts/l1/facts/emitters/EnvironmentVisualFactEmitter.gd scripts/phase0/MainDemoController.gd scripts/environment/EnvironmentStateController.gd scenes/phase0/MainDemo.tscn backend/tests/test_visual_fact_pipeline.py
@'
Move existing visual fact call sites onto family emitters

Constraint: Existing gaze and environment demo moments remain user-visible throughout migration
Rejected: Merge all visual emitters into MainDemoController | would preserve current coupling problem
Confidence: medium
Scope-risk: moderate
Directive: Controllers sample and trigger; emitters shape facts and transport through RawFactEmitter
Tested: python -m pytest -v backend/tests/test_visual_fact_pipeline.py backend/tests/test_siming_service.py
Not-tested: Live Godot scene execution
'@ | git commit -F -
```

### Task 5: Add Minimal Spatial Access Fact Slice

**Files:**
- Create: `scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd`
- Create: `backend/app/services/fact_handlers/spatial_access_fact_handler.py`
- Modify: `backend/app/services/fact_router.py`
- Modify: `backend/app/models/runtime_state.py`
- Test: `backend/tests/test_raw_fact_router.py`

- [ ] **Step 1: Write the failing access-fact handler tests**

```python
from app.models.raw_fact import RawFactEvent
from app.services.fact_handlers.spatial_access_fact_handler import SpatialAccessFactHandler


def test_spatial_access_handler_tracks_entered_zone() -> None:
    handler = SpatialAccessFactHandler()
    event = RawFactEvent(
        fact_family="spatial_access_fact",
        fact_type="actor_entered_zone",
        relation_type="actor_approached_actor",
        producer_ts=700,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_private",
        source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
        targets={"actor_id": "char_a"},
    )

    snapshot = handler.apply(event)

    assert snapshot["current_zone_id"] == "zone_private"
    assert snapshot["nearby_actor_refs"] == ["char_a"]


def test_spatial_access_handler_tracks_privacy_boundary_changes_without_membership_inference() -> None:
    handler = SpatialAccessFactHandler()
    event = RawFactEvent(
        fact_family="spatial_access_fact",
        fact_type="privacy_boundary_changed",
        relation_type="public_to_local",
        producer_ts=710,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_private",
        source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
        targets={"actor_id": "char_a"},
        world={"state_before": "public", "state_after": "local"},
    )

    snapshot = handler.apply(event)

    assert snapshot["privacy_band"] == "local"
    assert "candidate_member" not in snapshot
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest -v backend/tests/test_raw_fact_router.py`

Expected: FAIL because `SpatialAccessFactHandler` does not exist.

- [ ] **Step 3: Implement minimal access snapshot handler**

```python
class SpatialAccessFactHandler:
    def __init__(self) -> None:
        self._snapshot_by_actor: dict[str, dict[str, object]] = {}

    def apply(self, event) -> dict[str, object]:
        actor_id = event.source.actor_id
        snapshot = self._snapshot_by_actor.get(
            actor_id,
            {
                "actor_id": actor_id,
                "current_zone_id": "",
                "nearby_actor_refs": [],
                "privacy_band": "",
                "last_access_fact_ts": 0,
            },
        )
        snapshot["current_zone_id"] = event.zone_id
        snapshot["last_access_fact_ts"] = event.producer_ts
        if event.targets.actor_id and event.targets.actor_id not in snapshot["nearby_actor_refs"]:
            snapshot["nearby_actor_refs"] = [event.targets.actor_id]
        if event.fact_type == "privacy_boundary_changed":
            snapshot["privacy_band"] = event.world.state_after
        self._snapshot_by_actor[actor_id] = snapshot
        return snapshot
```

- [ ] **Step 4: Wire router support**

```python
if event.fact_family == "spatial_access_fact":
    snapshot = spatial_access_fact_handler.apply(event)
    return RoutedFactResult(handler_name="spatial_access_fact_handler", payload=snapshot)
```

- [ ] **Step 5: Add minimal runtime state support**

```python
class CharacterRuntimeStateSnapshot(BaseModel):
    ...
    access_window_open: bool | None = None
```

```python
class CharacterRuntimeStateDelta(BaseModel):
    ...
    access_window_open: bool | None = None
```

- [ ] **Step 6: Add Godot emitter methods for first three access facts**

```gdscript
extends Node
class_name SpatialAccessFactEmitter

@export_node_path("Node") var raw_fact_emitter_path := NodePath("../RawFactEmitter")

func emit_actor_entered_zone(source_actor_id: String, zone_id: String) -> bool:
    return _emit("actor_entered_zone", "", source_actor_id, "", "", "", {})

func emit_actor_approached_actor(source_actor_id: String, target_actor_id: String, distance_m: float) -> bool:
    return _emit(
        "actor_proximity_changed",
        "actor_approached_actor",
        source_actor_id,
        target_actor_id,
        "",
        "",
        {"distance_m": distance_m}
    )

func emit_privacy_boundary_changed(source_actor_id: String, before: String, after: String) -> bool:
    return _emit(
        "privacy_boundary_changed",
        "public_to_local" if before == "public" and after == "local" else "local_to_private",
        source_actor_id,
        "",
        "",
        "",
        {"state_before": before, "state_after": after}
    )
```

- [ ] **Step 7: Run tests**

Run: `python -m pytest -v backend/tests/test_raw_fact_router.py backend/tests/test_visual_fact_pipeline.py`

Expected: PASS with spatial access facts handled without membership inference.

- [ ] **Step 8: Commit**

```powershell
git add scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd backend/app/services/fact_handlers/spatial_access_fact_handler.py backend/app/services/fact_router.py backend/app/models/runtime_state.py backend/tests/test_raw_fact_router.py
@'
Add the first spatial access fact slice without crossing into membership inference

Constraint: L1 must provide access/privacy evidence while leaving membership conclusions above the ingress layer
Rejected: Emit candidate_member directly from Godot | violates the fact-production boundary
Confidence: high
Scope-risk: moderate
Directive: spatial_access_fact_handler may store access evidence, but must not infer mutual knowledge or exclusion
Tested: python -m pytest -v backend/tests/test_raw_fact_router.py backend/tests/test_visual_fact_pipeline.py
Not-tested: Live zone-boundary detection in Godot
'@ | git commit -F -
```

### Task 6: Final Verification And Doc Sync

**Files:**
- Modify: `docs/superpowers/specs/2026-06-06-l1-raw-fact-emitter-design.md`
- Modify: `docs/superpowers/plans/2026-06-06-l1-raw-fact-emitter-implementation.md`
- Test: `scripts/verification/verify_phase1_slice.py`
- Test: `python -m pytest -v`

- [ ] **Step 1: Update design doc status lines after implementation**

```markdown
- Status: implemented for Phase 0 minimal slice
- Verified: backend raw ingress, visual fact parity, first spatial access slice
```

- [ ] **Step 2: Run full backend tests**

Run: `python -m pytest -v`

Expected: PASS across the full backend suite.

- [ ] **Step 3: Run Phase 1 slice verification**

Run: `python scripts/verification/verify_phase1_slice.py`

Expected: PASS or narrow, explainable failures only in intentionally deferred areas.

- [ ] **Step 4: Capture verification evidence in docs**

```markdown
## Verification Notes

- `python -m pytest -v` passed
- `python scripts/verification/verify_phase1_slice.py` passed
- Shared raw emitter is the only allowed fact sender
- Existing visual fact behavior remained intact
- First spatial access fact family added without membership inference
```

- [ ] **Step 5: Final commit**

```powershell
git add docs/superpowers/specs/2026-06-06-l1-raw-fact-emitter-design.md docs/superpowers/plans/2026-06-06-l1-raw-fact-emitter-implementation.md
@'
Close the L1 raw fact migration with verification evidence and synced docs

Constraint: Final report must distinguish verified behavior from deferred Godot-runtime-only work
Rejected: Mark design complete before raw ingress and access slice verification | would hide migration risk
Confidence: medium
Scope-risk: narrow
Directive: Future fact families must extend the shared pipeline instead of reviving family-specific transport
Tested: python -m pytest -v; python scripts/verification/verify_phase1_slice.py
Not-tested: Godot MCP-based live editor verification
'@ | git commit -F -
```

## Self-Review

### Spec coverage

- Shared raw fact transport: covered by Tasks 1-3
- Visual fact compatibility preservation: covered by Tasks 2 and 4
- Minimal spatial access family: covered by Task 5
- Verification and doc sync: covered by Task 6

### Placeholder scan

- No `TODO`, `TBD`, or abstract “add tests later” steps remain.
- Every code-changing task includes concrete code blocks.

### Type consistency

- Shared type names are consistent:
  - `RawFactEvent`
  - `FactRouter`
  - `SpatialAccessFactHandler`
  - `RawFactEmitter`
  - `CharacterVisualFactEmitter`
  - `EnvironmentVisualFactEmitter`
  - `SpatialAccessFactEmitter`

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-06-l1-raw-fact-emitter-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
