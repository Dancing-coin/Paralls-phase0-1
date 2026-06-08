# System L1 Visual Fact System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the `Phase 1` `System L1` visual fact system by filling the missing primary emitters and the `evidence_projection` layer while preserving the current working visual fact path.

**Architecture:** Keep the current shared `VisualFactEmitter -> raw_fact_event -> backend authority` spine, but expand the visual-fact subsystem to match the main-project source-domain model: `character`, `object`, `environment`, `spatial_relation`, plus `evidence_projection`.

**Tech Stack:** Godot 4.x GDScript, Python 3.13, FastAPI backend, Pydantic models, pytest, existing visual-fact verification harnesses.

---

## Status Snapshot

- Date: `2026-06-09`
- Plan status: partially executed
- Current code truth:
  - `ObjectVisualFactEmitter` exists and is wired
  - `SpatialRelationVisualFactEmitter` exists and is wired
  - `EvidenceProjectionEmitter` exists
  - verification surface proves the visual-fact emitter family is present
- Remaining gap:
  - the repo has explicit emitter coverage, but not a deeper full-volume visual domain beyond the current verified slice

### Task 1: Add `ObjectVisualFactEmitter`

**Files:**
- Create: `scripts/l1/facts/emitters/ObjectVisualFactEmitter.gd`
- Modify: `scenes/phase0/MainDemo.tscn`
- Modify: `scripts/phase0/MainDemoController.gd`
- Modify: `backend/tests/test_verification_audit.py`
- Optional Modify: `backend/tests/test_visual_fact_pipeline.py`

- [ ] **Step 1: Write the failing static verification test**

Add to `backend/tests/test_verification_audit.py`:

```python
def test_visual_fact_system_contains_object_visual_fact_emitter() -> None:
    project_root = Path(__file__).resolve().parents[2]
    emitter_source = (
        project_root / "scripts" / "l1" / "facts" / "emitters" / "ObjectVisualFactEmitter.gd"
    ).read_text(encoding="utf-8")

    assert "emit_object_state_transition" in emitter_source
```

- [ ] **Step 2: Run the test to verify failure**

Run:

```bash
python -m pytest -v tests/test_verification_audit.py::test_visual_fact_system_contains_object_visual_fact_emitter
```

Expected:

- FAIL because the emitter file does not exist yet.

- [ ] **Step 3: Implement the minimal object emitter**

Create `scripts/l1/facts/emitters/ObjectVisualFactEmitter.gd`:

```gdscript
extends Node

@export_node_path("Node") var visual_fact_emitter_path := NodePath("..")


func emit_object_state_transition(target_object_id: String, relation_type: String = "object_state_changed") -> bool:
	if target_object_id == "":
		return false

	var visual_fact_emitter := get_node_or_null(visual_fact_emitter_path)
	if visual_fact_emitter == null or not visual_fact_emitter.has_method("emit_visual_fact"):
		return false

	return visual_fact_emitter.emit_visual_fact(
		"object_state_change",
		relation_type,
		"",
		target_object_id,
		""
	)
```

- [ ] **Step 4: Wire the emitter into `MainDemo.tscn`**

Add a node under `VisualFactEmitter` in `scenes/phase0/MainDemo.tscn` matching the existing child-emitter pattern:

```text
[node name="ObjectVisualFactEmitter" type="Node" parent="VisualFactEmitter"]
script = ExtResource("<new object emitter ext_resource id>")
```

- [ ] **Step 5: Invoke it from one existing object-change path**

In `scripts/phase0/MainDemoController.gd`, after a successful object interaction path where `obj_letter` state visibly changes, call the new emitter if present.

Use the same local pattern as the existing character/environment emitters:

```gdscript
var object_visual_fact_emitter := $VisualFactEmitter/ObjectVisualFactEmitter
if object_visual_fact_emitter and object_visual_fact_emitter.has_method("emit_object_state_transition"):
	object_visual_fact_emitter.emit_object_state_transition("obj_letter")
```

- [ ] **Step 6: Re-run focused verification**

Run:

```bash
python -m pytest -v tests/test_verification_audit.py tests/test_visual_fact_pipeline.py
```

Expected:

- PASS

- [ ] **Step 7: Commit**

```bash
git add scripts/l1/facts/emitters/ObjectVisualFactEmitter.gd scenes/phase0/MainDemo.tscn scripts/phase0/MainDemoController.gd backend/tests/test_verification_audit.py backend/tests/test_visual_fact_pipeline.py
git commit -m "feat: add object visual fact emitter"
```

### Task 2: Add `SpatialRelationVisualFactEmitter`

**Files:**
- Create: `scripts/l1/facts/emitters/SpatialRelationVisualFactEmitter.gd`
- Modify: `scenes/phase0/MainDemo.tscn`
- Modify: `backend/tests/test_verification_audit.py`

- [ ] **Step 1: Add failing verification test**

```python
def test_visual_fact_system_contains_spatial_relation_visual_fact_emitter() -> None:
    project_root = Path(__file__).resolve().parents[2]
    emitter_source = (
        project_root / "scripts" / "l1" / "facts" / "emitters" / "SpatialRelationVisualFactEmitter.gd"
    ).read_text(encoding="utf-8")

    assert "emit_spatial_relation_fact" in emitter_source
```

- [ ] **Step 2: Run the test to verify failure**

Run:

```bash
python -m pytest -v tests/test_verification_audit.py::test_visual_fact_system_contains_spatial_relation_visual_fact_emitter
```

Expected:

- FAIL

- [ ] **Step 3: Create the minimal emitter**

```gdscript
extends Node

@export_node_path("Node") var visual_fact_emitter_path := NodePath("..")


func emit_spatial_relation_fact(relation_type: String, target_actor_id: String = "", target_object_id: String = "", target_environment_id: String = "") -> bool:
	var visual_fact_emitter := get_node_or_null(visual_fact_emitter_path)
	if visual_fact_emitter == null or not visual_fact_emitter.has_method("emit_visual_fact"):
		return false

	return visual_fact_emitter.emit_visual_fact(
		"spatial_relation",
		relation_type,
		target_actor_id,
		target_object_id,
		target_environment_id
	)
```

- [ ] **Step 4: Add the node to `MainDemo.tscn`**

Mirror the existing `VisualFactEmitter` child-emitter structure.

- [ ] **Step 5: Re-run focused verification**

Run:

```bash
python -m pytest -v tests/test_verification_audit.py
```

Expected:

- PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/l1/facts/emitters/SpatialRelationVisualFactEmitter.gd scenes/phase0/MainDemo.tscn backend/tests/test_verification_audit.py
git commit -m "feat: add spatial relation visual fact emitter"
```

### Task 3: Add `EvidenceProjectionEmitter`

**Files:**
- Create: `scripts/l1/facts/emitters/EvidenceProjectionEmitter.gd`
- Modify: `backend/tests/test_verification_audit.py`

- [ ] **Step 1: Add failing verification test**

```python
def test_visual_fact_system_contains_evidence_projection_emitter() -> None:
    project_root = Path(__file__).resolve().parents[2]
    emitter_source = (
        project_root / "scripts" / "l1" / "facts" / "emitters" / "EvidenceProjectionEmitter.gd"
    ).read_text(encoding="utf-8")

    assert "emit_visual_evidence_projection" in emitter_source
```

- [ ] **Step 2: Run to verify failure**

Run:

```bash
python -m pytest -v tests/test_verification_audit.py::test_visual_fact_system_contains_evidence_projection_emitter
```

Expected:

- FAIL

- [ ] **Step 3: Create the minimal emitter**

```gdscript
extends Node

@export_node_path("Node") var visual_fact_emitter_path := NodePath("..")


func emit_visual_evidence_projection(target_object_id: String = "", target_environment_id: String = "") -> bool:
	var visual_fact_emitter := get_node_or_null(visual_fact_emitter_path)
	if visual_fact_emitter == null or not visual_fact_emitter.has_method("emit_visual_fact"):
		return false

	if target_object_id == "" and target_environment_id == "":
		return false

	return visual_fact_emitter.emit_visual_fact(
		"visual_evidence_projection",
		"evidence_projection",
		"",
		target_object_id,
		target_environment_id
	)
```

- [ ] **Step 4: Re-run focused verification**

Run:

```bash
python -m pytest -v tests/test_verification_audit.py
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/l1/facts/emitters/EvidenceProjectionEmitter.gd backend/tests/test_verification_audit.py
git commit -m "feat: add evidence projection visual emitter"
```
