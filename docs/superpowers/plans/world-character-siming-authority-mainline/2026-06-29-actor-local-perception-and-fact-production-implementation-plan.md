# Actor-Local Perception And Fact Production Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move perception ownership from demo-controller-centric logic to reusable actor-local sampling and fact emission.

**Architecture:** Extract view-cone, range, and line-of-sight logic from `MainDemoController` into actor-owned helpers under `scripts/character/`, then wire those helpers to standard fact emitters rather than direct backend calls. Keep `MainDemoController` as a consumer of shared utilities during the transition so `Phase 0` probes do not break.

**Tech Stack:** Godot 4.6 GDScript, existing fact emitters under `scripts/l1/facts/emitters/`, backend raw-fact pipeline, pytest static checks, runtime verification scripts.

**Progress Snapshot (`2026-06-30`):**
- Tasks `1-4` now have direct repository evidence.
- Current proof chain covers:
  - extracted actor-local target resolution and sampling helpers
  - standard fact-emitter routing from actor-local observation
  - `CharacterReplica` ownership of the sampling hook
  - dedicated runtime verifier `verify_actor_local_perception.py`

**Direct Evidence Audit (`2026-06-30`):**
- Required outcome `1. shared actor-view sampling helpers`
  - Direct evidence:
    - `backend/tests/test_relationship_overlay_static.py::test_actor_perception_sampler_declares_cone_range_and_los_hooks`
    - `scripts/character/ActorPerceptionSampler.gd`
    - `scripts/character/ActorPerceptionTargetResolver.gd`
- Required outcome `2. actor-local observation routes through standard fact emitters`
  - Direct evidence:
    - `backend/tests/test_visual_fact_pipeline.py::test_actor_local_sampling_emits_standard_visual_fact_shape`
    - `scripts/l1/facts/emitters/CharacterVisualFactEmitter.gd`
    - `scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd`
    - `scripts/character/CharacterReplica.gd`
- Required outcome `3. actor-local sampling is owned by CharacterReplica`
  - Direct evidence:
    - `backend/tests/test_character_actor_reacquisition_runtime.py::test_character_replica_wires_actor_perception_sampler`
    - `scripts/character/CharacterReplica.gd`
    - `scenes/phase0/CharacterReplica.tscn`
- Required outcome `4. dedicated runtime verification exists`
  - Direct evidence:
    - `python scripts/verification/verify_actor_local_perception.py`
    - `.harness/verification/actor-local-perception-report.json`
    - unified verifier result `actor_local_perception=proved`

**Completion Audit Conclusion (`2026-06-30`):**
- Within the current first-pass scope of this plan, the four required outcomes now have direct repository evidence.
- Remaining non-goals for this plan:
  - no production multi-sensor perception fusion layer here
  - no broader replacement of all controller-side debug consumers; this lane establishes actor ownership first

---

### Task 1: Extract shared actor-view sampling helpers

**Files:**
- Create: `scripts/character/ActorPerceptionTargetResolver.gd`
- Create: `scripts/character/ActorPerceptionSampler.gd`
- Modify: `scripts/phase0/MainDemoController.gd`
- Test: `backend/tests/test_relationship_overlay_static.py`

- [x] **Step 1: Write the failing static extraction test**

```python
from pathlib import Path


def test_actor_perception_sampler_declares_cone_range_and_los_hooks() -> None:
    text = Path("scripts/character/ActorPerceptionSampler.gd").read_text(encoding="utf-8")
    assert "sample_visible_targets" in text
    assert "_has_line_of_sight_to_target" in text
    assert "focus_max_distance" not in text
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_relationship_overlay_static.py::test_actor_perception_sampler_declares_cone_range_and_los_hooks -v`
Expected: `FAIL` because the sampler file does not yet exist.

- [x] **Step 3: Write minimal implementation**

```gdscript
extends RefCounted

class_name ActorPerceptionSampler

var range_m := 28.0
var forward_threshold := 0.2

func sample_visible_targets(origin: Vector3, forward: Vector3, candidates: Array[Node3D], owner: Node3D) -> Array[Node3D]:
	var visible: Array[Node3D] = []
	for candidate in candidates:
		if candidate == null or candidate == owner:
			continue
		if not _passes_cone(origin, forward, candidate.global_position):
			continue
		if not _has_line_of_sight_to_target(owner, candidate):
			continue
		visible.append(candidate)
	return visible
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_relationship_overlay_static.py::test_actor_perception_sampler_declares_cone_range_and_los_hooks -v`
Expected: `PASS`

- [x] **Step 5: Commit**

```bash
git add scripts/character/ActorPerceptionSampler.gd scripts/character/ActorPerceptionTargetResolver.gd scripts/phase0/MainDemoController.gd backend/tests/test_relationship_overlay_static.py
git commit -m "Extract actor-local perception sampling helpers

Constraint: MainDemoController must stop being the long-term owner of perception geometry
Rejected: Duplicate the same cone and LOS logic in every actor shell | unmaintainable and not generalizable
Confidence: medium
Scope-risk: moderate
Directive: Shared geometry logic should be extracted once and consumed by both actors and controller-side debug UI
Tested: pytest backend/tests/test_relationship_overlay_static.py::test_actor_perception_sampler_declares_cone_range_and_los_hooks -v
Not-tested: runtime behavior"
```

### Task 2: Route actor-local observation through standard fact emitters

**Files:**
- Modify: `scripts/l1/facts/emitters/CharacterVisualFactEmitter.gd`
- Modify: `scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd`
- Modify: `scripts/character/CharacterReplica.gd`
- Test: `backend/tests/test_visual_fact_pipeline.py`

- [x] **Step 1: Write the failing pipeline assertion**

```python
def test_actor_local_sampling_emits_standard_visual_fact_shape() -> None:
    from pathlib import Path

    text = Path("scripts/character/CharacterReplica.gd").read_text(encoding="utf-8")
    assert "emit_fixed_gaze_on_target" in text
    assert "message_type\": \"visual_fact_event\"" not in text
```

- [x] **Step 2: Run test to verify failure if actor path is still missing**

Run: `pytest backend/tests/test_visual_fact_pipeline.py::test_actor_local_sampling_emits_standard_visual_fact_shape -v`
Expected: `FAIL` until actor-local emission is wired.

- [x] **Step 3: Write minimal implementation**

```gdscript
func _emit_actor_notice_fact(target_actor_id: String) -> void:
	var emitter := get_node_or_null("CharacterVisualFactEmitter")
	if emitter == null:
		return
	if emitter.has_method("emit_fixed_gaze_on_target"):
		emitter.emit_fixed_gaze_on_target(target_actor_id, "")
```

```gdscript
func _emit_arrival_fact(target_actor_id: String, distance_m: float) -> void:
	var emitter := get_node_or_null("SpatialAccessFactEmitter")
	if emitter == null:
		return
	if emitter.has_method("emit_actor_approached_actor"):
		emitter.emit_actor_approached_actor(target_actor_id, distance_m)
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_visual_fact_pipeline.py::test_actor_local_sampling_emits_standard_visual_fact_shape -v`
Expected: `PASS`

- [x] **Step 5: Commit**

```bash
git add scripts/l1/facts/emitters/CharacterVisualFactEmitter.gd scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd scripts/character/CharacterReplica.gd backend/tests/test_visual_fact_pipeline.py
git commit -m "Route actor-local noticing through standard fact emitters

Constraint: Actor-local perception must enter the same fact fabric as existing world facts
Rejected: Send direct backend perception messages from actor runtime | violates the shared fact boundary
Confidence: high
Scope-risk: moderate
Directive: New actor-local observation should always be projected through reusable emitters first
Tested: pytest backend/tests/test_visual_fact_pipeline.py::test_actor_local_sampling_emits_standard_visual_fact_shape -v
Not-tested: multi-actor runtime loop"
```

### Task 3: Wire actor-local sampling into `CharacterReplica` without breaking current debug cone

**Files:**
- Modify: `scripts/character/CharacterReplica.gd`
- Modify: `scenes/phase0/CharacterReplica.tscn`
- Test: `backend/tests/test_character_actor_reacquisition_runtime.py`

- [x] **Step 1: Write the failing actor-wiring static/runtime test**

```python
from pathlib import Path


def test_character_replica_wires_actor_perception_sampler() -> None:
    source = Path("scripts/character/CharacterReplica.gd").read_text(encoding="utf-8")
    assert "ActorPerceptionSampler" in source
    assert "_sample_actor_local_perception" in source
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_character_actor_reacquisition_runtime.py::test_character_replica_wires_actor_perception_sampler -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```gdscript
const ActorPerceptionSamplerRef = preload("res://scripts/character/ActorPerceptionSampler.gd")
const ActorPerceptionTargetResolverRef = preload("res://scripts/character/ActorPerceptionTargetResolver.gd")

var _perception_sampler = ActorPerceptionSamplerRef.new()
var _perception_target_resolver = ActorPerceptionTargetResolverRef.new()
var _last_notice_target := ""
var _last_notice_ts := 0

func _process(delta: float) -> void:
	...
	_sample_actor_local_perception()

func _sample_actor_local_perception() -> void:
	var targets := _perception_target_resolver.resolve_targets(get_tree().current_scene, self)
	var visible := _perception_sampler.sample_visible_targets(get_focus_anchor_position(), global_basis.z.normalized(), targets, self)
	if visible.is_empty():
		return
	var first := visible[0]
	var target_actor_id := str(first.get("actor_id", "") or "")
	if target_actor_id == "" or target_actor_id == _last_notice_target:
		return
	_last_notice_target = target_actor_id
	_emit_actor_notice_fact(target_actor_id)
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_character_actor_reacquisition_runtime.py::test_character_replica_wires_actor_perception_sampler -v`
Expected: `PASS`

- [x] **Step 5: Commit**

```bash
git add scripts/character/CharacterReplica.gd scenes/phase0/CharacterReplica.tscn backend/tests/test_character_actor_reacquisition_runtime.py
git commit -m "Wire actor-local perception sampling into CharacterReplica

Constraint: Actor-local perception must be owned by the actor runtime, not only by the demo controller
Rejected: Keep sampling exclusively in MainDemoController and mirror results back into actors | wrong ownership boundary
Confidence: medium
Scope-risk: moderate
Directive: CharacterReplica should own the runtime sampling hook even while MainDemoController still consumes shared utilities for UI/debug
Tested: pytest backend/tests/test_character_actor_reacquisition_runtime.py::test_character_replica_wires_actor_perception_sampler -v
Not-tested: scene runtime performance"
```

### Task 4: Add actor-local perception runtime verification

**Files:**
- Create: `scripts/verification/verify_actor_local_perception.py`
- Modify: `docs/INDEX.md`
- Test: `python scripts/verification/verify_actor_local_perception.py`

- [x] **Step 1: Write the verifier shell**

```python
from pathlib import Path


def main() -> int:
    # start backend if needed
    # launch Godot probe scene
    # wait for actor-local perception markers
    # write markdown/json report
    return 0
```

- [x] **Step 2: Wire expected markers**

```text
actor_local_perception:notice_emitted=true
actor_local_perception:fact_routed=true
actor_local_perception:character_runtime_seen=true
```

- [x] **Step 3: Run verifier and record current expected status**

Run: `python scripts/verification/verify_actor_local_perception.py`
Expected: initial `FAIL` or partial result until the full runtime path is complete.

- [x] **Step 4: Commit**

```bash
git add scripts/verification/verify_actor_local_perception.py docs/INDEX.md
git commit -m "Add actor-local perception verification entrypoint

Constraint: Actor-local perception must have a dedicated runtime proof surface before it becomes mainline truth
Rejected: Infer success only from broader Phase 0 logs | too indirect for the new ownership boundary
Confidence: medium
Scope-risk: narrow
Directive: New runtime ownership shifts should gain dedicated verification surfaces, not only static tests
Tested: python scripts/verification/verify_actor_local_perception.py
Not-tested: full green runtime path"
```
