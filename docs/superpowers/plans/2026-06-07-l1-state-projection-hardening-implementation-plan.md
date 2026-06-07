# L1 State Projection Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden the current `L1` raw fact pipeline so it supports explicit set/clear/replace semantics, fixes stale spatial state, allows repeated environment cycles, and reseeds correctly after reconnect while preserving current Phase 0 compatibility.

**Architecture:** Extend the shared raw fact contract with lightweight effect semantics (`effect_kind`, `subject_key`, optional `ttl_ms`), keep `fact_router` thin, move family-specific projection behavior into emitters and handlers, and preserve the legacy `visual_fact_event` compatibility path while upgrading the primary `raw_fact_event` route.

**Tech Stack:** Godot 4.x GDScript, Python 3.13, FastAPI backend, Pydantic models, pytest, existing Phase 0 runtime and verification audit.

---

## File Map

### Shared Godot L1

- Modify: `scripts/l1/facts/FactEnvelopeBuilder.gd`
  - Add shared effect semantics to the raw fact payload builder.
- Modify: `scripts/l1/facts/RawFactEmitter.gd`
  - Keep transport responsibilities narrow and unchanged except where new contract fields require pass-through.
- Optional Modify: `scripts/l1/facts/FactDeduper.gd`
  - Only if explicit effect fields require dedupe key or envelope normalization adjustments.

### Godot Family Emitters / Sampling

- Modify: `scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd`
  - Add explicit `replace` / `clear` / `set` semantics for spatial facts.
- Modify: `scripts/l1/facts/emitters/EnvironmentVisualFactEmitter.gd`
  - Make repeated `stable -> alerted -> stable -> alerted` cycles re-emittable.
- Modify: `scripts/phase0/MainDemoController.gd`
  - Emit explicit invalidation facts and reset bootstrap latches on reconnect.

### Backend Shared Contract / Routing

- Modify: `backend/app/models/raw_fact.py`
  - Extend schema with effect semantics.
- Modify: `backend/app/models/visual_fact.py`
  - Preserve compatibility and normalize new shared fields.
- Modify: `backend/app/services/fact_router.py`
  - Keep router thin while passing enhanced raw fact objects.
- Modify: `backend/app/main.py`
  - Preserve debug publication and `raw_fact_event` handling under the new contract.
- Modify: `backend/app/debug_narration.py`
  - Keep narration sensible for new effect kinds and fact types.

### Backend Family Handlers / State

- Modify: `backend/app/services/fact_handlers/spatial_access_fact_handler.py`
  - Apply shared effect semantics and explicit clearing/reseed logic.
- Optional Modify: `backend/app/models/runtime_state.py`
  - Only if the current spatial snapshot shape needs a field to support replay/expiry clearly.

### Tests

- Modify: `backend/tests/test_raw_fact_router.py`
- Modify: `backend/tests/test_visual_fact_pipeline.py`
- Modify: `backend/tests/test_debug_narration.py`
- Optional Modify: `backend/tests/test_verification_audit.py`
  - Only if the updated shared contract changes audit expectations.

---

### Task 1: Lock The Shared Raw Fact Contract

**Files:**
- Modify: `backend/app/models/raw_fact.py`
- Modify: `backend/app/models/visual_fact.py`
- Modify: `backend/tests/test_raw_fact_router.py`

- [ ] **Step 1: Write the failing contract tests**

Add these test cases to `backend/tests/test_raw_fact_router.py` near the existing shape/normalization tests:

```python
def test_raw_fact_event_accepts_effect_semantics_fields() -> None:
    event = RawFactEvent(
        fact_family="spatial_access_fact",
        fact_type="actor_entered_zone",
        relation_type="actor_entered_zone",
        producer_ts=700,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={
            "layer": "L1",
            "system": "godot.raw_fact_emitter",
            "actor_id": "char_c",
        },
        targets={},
        effect_kind="set",
        subject_key="current_zone_id",
        ttl_ms=1500,
    )

    assert event.effect_kind == "set"
    assert event.subject_key == "current_zone_id"
    assert event.ttl_ms == 1500


def test_visual_fact_event_model_dump_preserves_effect_semantics() -> None:
    event = VisualFactEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=701,
        fact_type="light_level_drop",
        relation_type="environment_light_drop",
        target_environment_id="env_lamp",
        effect_kind="set",
        subject_key="environment_state/env_lamp",
    )

    payload = event.model_dump()

    assert payload["effect_kind"] == "set"
    assert payload["subject_key"] == "environment_state/env_lamp"
    assert payload["ttl_ms"] is None
```

- [ ] **Step 2: Run the contract tests to verify they fail**

Run:

```bash
python -m pytest -v tests/test_raw_fact_router.py
```

Expected:

- FAIL with `ValidationError` or missing attribute assertions for `effect_kind`, `subject_key`, or `ttl_ms`.

- [ ] **Step 3: Extend the shared backend schema**

Update `backend/app/models/raw_fact.py` so the raw fact model carries effect semantics:

```python
from typing import Literal

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
    effect_kind: Literal["set", "clear", "replace", "pulse"] = "pulse"
    subject_key: str = ""
    ttl_ms: int | None = None
    causation_id: str = ""
    correlation_id: str = ""
```

Update `backend/app/models/visual_fact.py` normalization so `effect_kind`, `subject_key`, and `ttl_ms` are included both in normalized payloads and when nested `source` / `targets` are merged:

```python
normalized = {
    "event_type": payload["event_type"],
    "fact_family": payload["fact_family"],
    "fact_type": payload["fact_type"],
    "relation_type": payload.get("relation_type", ""),
    "producer_ts": payload["producer_ts"],
    "room_id": payload["room_id"],
    "scene_id": payload["scene_id"],
    "zone_id": payload["zone_id"],
    "source": legacy_source,
    "targets": legacy_targets,
    "world": payload.get("world", {}),
    "observability": payload.get("observability", {}),
    "effect_kind": payload.get("effect_kind", "pulse"),
    "subject_key": payload.get("subject_key", ""),
    "ttl_ms": payload.get("ttl_ms"),
    "causation_id": payload.get("causation_id", ""),
    "correlation_id": payload.get("correlation_id", ""),
}
```

- [ ] **Step 4: Re-run the contract tests**

Run:

```bash
python -m pytest -v tests/test_raw_fact_router.py
```

Expected:

- PASS for the new contract tests
- PASS for existing raw fact and visual fact compatibility tests

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/raw_fact.py backend/app/models/visual_fact.py backend/tests/test_raw_fact_router.py
git commit -m "feat: extend raw fact contract with effect semantics"
```

### Task 2: Upgrade Godot Payload Builders To Emit Shared Effect Semantics

**Files:**
- Modify: `scripts/l1/facts/FactEnvelopeBuilder.gd`
- Modify: `scripts/visual/VisualFactEmitter.gd`
- Test: `backend/tests/test_verification_audit.py`

- [ ] **Step 1: Add or update verification tests for the shared builder contract**

Add a focused assertion block to `backend/tests/test_verification_audit.py` near the existing shared raw fact transport checks:

```python
def test_shared_raw_fact_transport_supports_effect_semantics_fields() -> None:
    project_root = Path(__file__).resolve().parents[2]
    builder_source = (project_root / "scripts" / "l1" / "facts" / "FactEnvelopeBuilder.gd").read_text(
        encoding="utf-8"
    )

    assert '"effect_kind"' in builder_source
    assert '"subject_key"' in builder_source
    assert '"ttl_ms"' in builder_source
```

- [ ] **Step 2: Run the verification audit test to verify it fails**

Run:

```bash
python -m pytest -v tests/test_verification_audit.py::test_shared_raw_fact_transport_supports_effect_semantics_fields
```

Expected:

- FAIL because the builder source does not yet include the new fields.

- [ ] **Step 3: Extend the Godot payload builder**

Update `scripts/l1/facts/FactEnvelopeBuilder.gd` so `build_raw_fact_payload()` accepts the new fields and emits them:

```gdscript
extends RefCounted


func build_raw_fact_envelope(payload: Dictionary) -> Dictionary:
	return {
		"message_type": "raw_fact_event",
		"payload": payload.duplicate(true),
	}


func build_raw_fact_payload(
	fact_family: String,
	fact_type: String,
	relation_type: String,
	room_id: String,
	scene_id: String,
	zone_id: String,
	source_actor_id: String = "",
	source_object_id: String = "",
	source_environment_id: String = "",
	target_actor_id: String = "",
	target_object_id: String = "",
	target_environment_id: String = "",
	source_system: String = "godot.raw_fact_emitter",
	source_layer: String = "L1",
	world: Dictionary = {},
	observability: Dictionary = {},
	effect_kind: String = "pulse",
	subject_key: String = "",
	ttl_ms: Variant = null,
	causation_id: String = "",
	correlation_id: String = "",
	producer_ts: int = -1
) -> Dictionary:
	var resolved_producer_ts := producer_ts if producer_ts >= 0 else Time.get_ticks_msec()
	return {
		"event_type": "raw_fact_event",
		"fact_family": fact_family,
		"fact_type": fact_type,
		"relation_type": relation_type,
		"producer_ts": resolved_producer_ts,
		"room_id": room_id,
		"scene_id": scene_id,
		"zone_id": zone_id,
		"source": {
			"layer": source_layer,
			"system": source_system,
			"actor_id": source_actor_id,
			"object_id": source_object_id,
			"environment_id": source_environment_id,
		},
		"targets": {
			"actor_id": target_actor_id,
			"object_id": target_object_id,
			"environment_id": target_environment_id,
		},
		"world": {
			"position": world.get("position", null),
			"distance_m": world.get("distance_m", null),
			"state_before": world.get("state_before", ""),
			"state_after": world.get("state_after", ""),
		},
		"observability": {
			"visual": observability.get("visual", false),
			"auditory": observability.get("auditory", false),
			"occluded": observability.get("occluded", false),
		},
		"effect_kind": effect_kind,
		"subject_key": subject_key,
		"ttl_ms": ttl_ms,
		"causation_id": causation_id,
		"correlation_id": correlation_id,
	}
```

Update `scripts/visual/VisualFactEmitter.gd` compatibility builder call so it passes through the new positions and keeps current visual facts defaulting to `pulse`:

```gdscript
	return _fact_envelope_builder.build_raw_fact_payload(
		"visual_fact",
		fact_type,
		relation_type,
		room_id,
		scene_id,
		zone_id,
		actor_id,
		"",
		"",
		target_actor_id,
		target_object_id,
		target_environment_id,
		"godot.raw_fact_emitter",
		"L1",
		{},
		{},
		"pulse",
		"",
		null,
		"",
		"",
		producer_ts
	)
```

- [ ] **Step 4: Re-run the verification audit test**

Run:

```bash
python -m pytest -v tests/test_verification_audit.py::test_shared_raw_fact_transport_supports_effect_semantics_fields
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/l1/facts/FactEnvelopeBuilder.gd scripts/visual/VisualFactEmitter.gd backend/tests/test_verification_audit.py
git commit -m "feat: add effect semantics to raw fact payload builder"
```

### Task 3: Fix Spatial Access Projection Semantics End-To-End

**Files:**
- Modify: `scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd`
- Modify: `scripts/phase0/MainDemoController.gd`
- Modify: `backend/app/services/fact_handlers/spatial_access_fact_handler.py`
- Modify: `backend/tests/test_raw_fact_router.py`

- [ ] **Step 1: Write failing spatial projection tests**

Add these tests to `backend/tests/test_raw_fact_router.py`:

```python
def test_spatial_access_fact_handler_clears_nearby_actor_refs_on_clear_effect() -> None:
    handler = SpatialAccessFactHandler()

    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="actor_approached_actor",
            relation_type="actor_approached_actor",
            producer_ts=800,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
            targets={"actor_id": "char_a"},
            effect_kind="replace",
            subject_key="nearby_actor_refs",
        ),
        "raw_fact_event",
    )
    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="actor_left_actor_range",
            relation_type="actor_left_actor_range",
            producer_ts=801,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
            targets={},
            effect_kind="clear",
            subject_key="nearby_actor_refs",
        ),
        "raw_fact_event",
    )

    snapshot = handler.get_snapshot("char_c")

    assert snapshot is not None
    assert snapshot.nearby_actor_refs == []


def test_spatial_access_fact_handler_sets_zone_from_effect_subject() -> None:
    handler = SpatialAccessFactHandler()

    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="actor_entered_zone",
            relation_type="actor_entered_zone",
            producer_ts=802,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_private",
            source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
            targets={},
            effect_kind="set",
            subject_key="current_zone_id",
        ),
        "raw_fact_event",
    )

    snapshot = handler.get_snapshot("char_c")

    assert snapshot is not None
    assert snapshot.current_zone_id == "zone_private"
```

- [ ] **Step 2: Run the spatial tests to verify they fail**

Run:

```bash
python -m pytest -v tests/test_raw_fact_router.py
```

Expected:

- FAIL because current handler ignores `effect_kind` and `subject_key`, and because `actor_left_actor_range` is not yet supported.

- [ ] **Step 3: Add explicit spatial effect semantics on the Godot side**

Update `scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd` so each fact builder call carries shared semantics:

```gdscript
func emit_actor_entered_zone(next_zone_id: String = "") -> bool:
	var resolved_zone_id := next_zone_id if next_zone_id != "" else zone_id
	if actor_id == "" or resolved_zone_id == "":
		return false

	return _emit_spatial_access_fact(
		"actor_entered_zone",
		"actor_entered_zone",
		resolved_zone_id,
		"",
		{},
		"set",
		"current_zone_id",
		"phase0_spatial_access_fact:actor_entered_zone:%s" % resolved_zone_id
	)


func emit_actor_approached_actor(target_actor_id: String, distance_m: float = -1.0) -> bool:
	# keep current validation
	return _emit_spatial_access_fact(
		"actor_approached_actor",
		"actor_approached_actor",
		zone_id,
		target_actor_id,
		world,
		"replace",
		"nearby_actor_refs",
		"phase0_spatial_access_fact:actor_approached_actor:%s" % target_actor_id
	)


func emit_actor_left_actor_range(next_zone_id: String = "") -> bool:
	var resolved_zone_id := next_zone_id if next_zone_id != "" else zone_id
	if actor_id == "" or resolved_zone_id == "":
		return false

	return _emit_spatial_access_fact(
		"actor_left_actor_range",
		"actor_left_actor_range",
		resolved_zone_id,
		"",
		{},
		"clear",
		"nearby_actor_refs",
		"phase0_spatial_access_fact:actor_left_actor_range"
	)


func emit_privacy_boundary_changed(previous_band: String, next_band: String, next_zone_id: String = "") -> bool:
	# keep current validation
	return _emit_spatial_access_fact(
		"privacy_boundary_changed",
		"privacy_boundary_changed",
		resolved_zone_id,
		"",
		{
			"state_before": previous_band,
			"state_after": next_band,
		},
		"set",
		"privacy_band",
		"phase0_spatial_access_fact:privacy_boundary_changed:%s" % next_band
	)
```

Update `_emit_spatial_access_fact()` so it passes `effect_kind` and `subject_key` to the builder.

- [ ] **Step 4: Emit explicit invalidation and reconnect-safe reseed from `MainDemoController.gd`**

Modify `_sample_actor_approach_fact()` in `scripts/phase0/MainDemoController.gd`:

```gdscript
func _sample_actor_approach_fact() -> void:
	if spatial_access_fact_emitter == null:
		return
	if not spatial_access_fact_emitter.has_method("emit_actor_approached_actor"):
		return
	if not spatial_access_fact_emitter.has_method("emit_actor_left_actor_range"):
		return

	var target_actor_id := _resolve_focused_actor_id()
	if target_actor_id == "":
		if last_spatial_access_actor_target != "":
			spatial_access_fact_emitter.emit_actor_left_actor_range("zone_focus")
		last_spatial_access_actor_target = ""
		return

	var target_node := _find_node_by_property("actor_id", target_actor_id)
	if target_node == null:
		if last_spatial_access_actor_target != "":
			spatial_access_fact_emitter.emit_actor_left_actor_range("zone_focus")
		last_spatial_access_actor_target = ""
		return

	var distance := _get_focus_origin().distance_to(target_node.global_position)
	if distance > near_actor_spatial_access_distance:
		if last_spatial_access_actor_target != "":
			spatial_access_fact_emitter.emit_actor_left_actor_range("zone_focus")
		last_spatial_access_actor_target = ""
		return

	var now_ms := Time.get_ticks_msec()
	if target_actor_id == last_spatial_access_actor_target and now_ms - last_spatial_access_actor_ts < near_actor_spatial_access_cooldown_ms:
		return
	var emitted: bool = spatial_access_fact_emitter.emit_actor_approached_actor(target_actor_id, distance)
	if not emitted:
		return
	last_spatial_access_actor_target = target_actor_id
	last_spatial_access_actor_ts = now_ms
```

Also add a backend-disconnect reset hook near `_ready()` and `_on_backend_connected()`:

```gdscript
func _ready() -> void:
	var bus := _get_bus()
	if bus:
		bus.backend_connected.connect(_on_backend_connected)
		if bus.has_signal("backend_disconnected"):
			bus.backend_disconnected.connect(_on_backend_disconnected)
		# keep existing signal hookups


func _on_backend_disconnected() -> void:
	spatial_zone_emitted = false
	pending_focus_sync = true
	last_spatial_access_actor_target = ""
	last_spatial_access_actor_ts = 0
```

- [ ] **Step 5: Teach the backend handler to apply effect semantics**

Update `backend/app/services/fact_handlers/spatial_access_fact_handler.py`:

```python
def _apply_event(self, snapshot: SpatialAccessRuntimeStateSnapshot, event: RawFactEvent) -> None:
    snapshot.room_id = event.room_id
    snapshot.scene_id = event.scene_id
    snapshot.current_zone_id = event.zone_id
    snapshot.producer_ts = event.producer_ts
    snapshot.updated_at = event.producer_ts

    if event.effect_kind == "set" and event.subject_key == "current_zone_id":
        snapshot.current_zone_id = event.zone_id
        if event.fact_type == "actor_entered_zone":
            snapshot.nearby_actor_refs = []
        return

    if event.effect_kind == "replace" and event.subject_key == "nearby_actor_refs":
        target_actor_id = event.targets.actor_id
        snapshot.nearby_actor_refs = [target_actor_id] if target_actor_id != "" else []
        return

    if event.effect_kind == "clear" and event.subject_key == "nearby_actor_refs":
        snapshot.nearby_actor_refs = []
        return

    if event.effect_kind == "set" and event.subject_key == "privacy_band":
        next_privacy_band = event.world.state_after
        if next_privacy_band != "":
            snapshot.privacy_band = next_privacy_band
        return
```

- [ ] **Step 6: Re-run focused spatial tests**

Run:

```bash
python -m pytest -v tests/test_raw_fact_router.py tests/test_debug_narration.py
```

Expected:

- PASS for new clear/set tests
- PASS for existing spatial narration and routing coverage

- [ ] **Step 7: Commit**

```bash
git add scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd scripts/phase0/MainDemoController.gd backend/app/services/fact_handlers/spatial_access_fact_handler.py backend/tests/test_raw_fact_router.py
git commit -m "fix: harden spatial access fact state projection"
```

### Task 4: Make Environment L1 Facts Re-Emittable Across Cycles

**Files:**
- Modify: `scripts/l1/facts/emitters/EnvironmentVisualFactEmitter.gd`
- Modify: `backend/tests/test_visual_fact_pipeline.py`

- [ ] **Step 1: Write the failing environment cycle test**

Add this test to `backend/tests/test_visual_fact_pipeline.py`:

```python
def test_visual_fact_event_model_dump_supports_environment_state_subject_key() -> None:
    event = VisualFactEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=900,
        fact_type="light_level_drop",
        relation_type="environment_light_drop",
        target_environment_id="env_lamp",
        effect_kind="set",
        subject_key="environment_state/env_lamp",
    )

    payload = event.model_dump()

    assert payload["effect_kind"] == "set"
    assert payload["subject_key"] == "environment_state/env_lamp"
```

This locks the shared contract first; the Godot cycle-safe emitter behavior is then implemented to use it.

- [ ] **Step 2: Run the visual pipeline tests**

Run:

```bash
python -m pytest -v tests/test_visual_fact_pipeline.py
```

Expected:

- PASS on the new contract test if Task 1 and Task 2 are already complete.
- If not complete yet, FAIL until the shared contract work is in place.

- [ ] **Step 3: Replace one-shot environment emission with state-cycle-aware emission**

Update `scripts/l1/facts/emitters/EnvironmentVisualFactEmitter.gd`:

```gdscript
extends Node

@export_node_path("Node") var visual_fact_emitter_path := NodePath("..")

var _last_emitted_state_by_environment: Dictionary = {}


func emit_environment_state_transition(environment_id: String, previous_state: String, next_state: String) -> bool:
	if environment_id == "":
		return false
	if previous_state == next_state:
		return false

	_last_emitted_state_by_environment[environment_id] = next_state

	if next_state != "alerted":
		return false

	var visual_fact_emitter := _get_visual_fact_emitter()
	if visual_fact_emitter == null or not visual_fact_emitter.has_method("emit_visual_fact"):
		return false

	var emitted: bool = visual_fact_emitter.emit_visual_fact(
		"light_level_drop",
		"environment_light_drop",
		"",
		"",
		environment_id,
		"set",
		"environment_state/%s" % environment_id
	)
	if not emitted:
		return false

	_bus_log("phase0_visual_fact:light_level_drop:%s" % environment_id)
	return true
```

Update `scripts/visual/VisualFactEmitter.gd` so `emit_visual_fact()` accepts optional shared semantics with defaults:

```gdscript
func emit_visual_fact(
	fact_type: String,
	relation_type: String,
	target_actor_id: String = "",
	target_object_id: String = "",
	target_environment_id: String = "",
	effect_kind: String = "pulse",
	subject_key: String = "",
	ttl_ms: Variant = null
) -> bool:
	var payload := _build_visual_fact_payload(
		fact_type,
		relation_type,
		target_actor_id,
		target_object_id,
		target_environment_id,
		-1,
		effect_kind,
		subject_key,
		ttl_ms
	)
	return _get_raw_fact_emitter().emit_raw_fact(
		payload,
		"phase0_visual_fact_emitter",
		"phase0_visual_fact_emitter:%s:%s" % [fact_type, relation_type]
	)
```

And update `_build_visual_fact_payload()` to pass those fields into the shared builder.

- [ ] **Step 4: Re-run the visual pipeline tests**

Run:

```bash
python -m pytest -v tests/test_visual_fact_pipeline.py tests/test_debug_narration.py
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/l1/facts/emitters/EnvironmentVisualFactEmitter.gd scripts/visual/VisualFactEmitter.gd backend/tests/test_visual_fact_pipeline.py
git commit -m "fix: allow repeated environment L1 fact cycles"
```

### Task 5: Preserve Backend Ingress, Debugging, And Full Verification

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/debug_narration.py`
- Modify: `backend/tests/test_debug_narration.py`
- Optional Modify: `backend/tests/test_verification_audit.py`

- [ ] **Step 1: Add failing debug narration tests for the new fact shape**

Add this test to `backend/tests/test_debug_narration.py`:

```python
def test_summarize_character_input_from_spatial_access_clear_fact_is_natural_language() -> None:
    event = RawFactEvent(
        fact_family="spatial_access_fact",
        fact_type="actor_left_actor_range",
        relation_type="actor_left_actor_range",
        producer_ts=950,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
        targets={},
        effect_kind="clear",
        subject_key="nearby_actor_refs",
    )

    summary = summarize_character_input_from_fact(event)

    assert "离开" in summary or "退出" in summary or "不再接近" in summary
```

- [ ] **Step 2: Run the debug narration tests to verify failure**

Run:

```bash
python -m pytest -v tests/test_debug_narration.py
```

Expected:

- FAIL or produce a generic summary that does not mention the new clear semantics.

- [ ] **Step 3: Keep ingress compatible and improve narration**

Update `backend/app/main.py` only as needed to keep:

- `visual_fact_event` ingress
- `raw_fact_event` ingress
- debug event publication

No routing logic should move out of handlers into `main.py`.

Update `backend/app/debug_narration.py` so new spatial clear semantics remain readable:

```python
if event.fact_family == "spatial_access_fact":
    if event.fact_type == "actor_left_actor_range":
        return f"{source_label} 不再接近当前关注的角色了。"
```

And in `summarize_character_input_from_fact()`:

```python
if event.fact_family == "spatial_access_fact":
    if event.fact_type == "actor_left_actor_range":
        return f"{actor_label} 收到了一条空间接入事实：自己已离开当前近距角色范围。"
```

- [ ] **Step 4: Re-run focused L1 verification**

Run:

```bash
python -m pytest -v tests/test_raw_fact_router.py tests/test_visual_fact_pipeline.py tests/test_debug_narration.py
```

Expected:

- PASS

- [ ] **Step 5: Re-run the full backend suite**

Run:

```bash
python -m pytest -v
```

Expected:

- PASS with all backend tests green

- [ ] **Step 6: Commit**

```bash
git add backend/app/main.py backend/app/debug_narration.py backend/tests/test_debug_narration.py
git commit -m "fix: preserve L1 ingress clarity under effect semantics"
```

### Task 6: Final Audit, Docs Sync, And Completion Proof

**Files:**
- Modify: `docs/superpowers/specs/2026-06-07-l1-state-projection-hardening-design.md` only if implementation requires clarifying edits
- Modify: `docs/superpowers/plans/2026-06-07-l1-state-projection-hardening-implementation-plan.md` by checking boxes during execution
- Optional Modify: `docs/asset-policy.md` only if unexpectedly relevant (not expected)

- [ ] **Step 1: Re-read the design spec and compare it to the implementation**

Check:

- `effect_kind` exists end-to-end
- `subject_key` exists end-to-end
- `ttl_ms` exists end-to-end
- spatial clear / replace / set behavior is implemented
- environment cycles are re-emittable
- reconnect reseed behavior is implemented

- [ ] **Step 2: Run targeted static scan for the new semantics**

Run:

```bash
rg -n "effect_kind|subject_key|ttl_ms|actor_left_actor_range|backend_disconnected" scripts backend
```

Expected:

- matches in shared builder, emitters, backend model, handler, and reconnect logic

- [ ] **Step 3: Run final verification commands**

Run:

```bash
python -m pytest -v tests/test_raw_fact_router.py tests/test_visual_fact_pipeline.py tests/test_debug_narration.py
python -m pytest -v
```

Expected:

- PASS

- [ ] **Step 4: Commit final polish if any spec or test wording changed**

```bash
git add docs/superpowers/specs/2026-06-07-l1-state-projection-hardening-design.md docs/superpowers/plans/2026-06-07-l1-state-projection-hardening-implementation-plan.md
git commit -m "docs: sync L1 state projection hardening plan and spec"
```

- [ ] **Step 5: Prepare closeout summary**

Report:

- changed files
- which stale-state / one-shot / reconnect issues were fixed
- exact verification commands run
- any remaining scope intentionally deferred
