# Execution Semantics And Realization Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stabilize canonical execution semantics below `L4` while keeping the current local host usable as a transition path.

**Architecture:** Freeze a canonical downstream contract that names movement, contact, greeting, speech, interruption, and physiology semantics without binding them to today’s local implementation details. Keep `CharacterReplica` and related Godot files as a compatibility realization host while pushing meaning up into reusable semantics.

**Tech Stack:** Python `L4Executor`, Godot `CharacterRuntimeState` / `CharacterPresentationInput`, shared actor ingress, pytest static/runtime tests.

**Progress Snapshot (`2026-06-30`):**
- Tasks `1-2` now have direct repository evidence.
- Current proof chain covers:
  - explicit `execution_semantics` on downstream execution plans
  - `CharacterReplica` / `CharacterRuntimeState` consuming semantics as a transitional local host
  - current docs and static/runtime tests record the local host as realization consumer rather than semantics owner

**Direct Evidence Audit (`2026-06-30`):**
- Required outcome `1. stable downstream execution semantic vocabulary`
  - Direct evidence:
    - `backend/tests/test_character_agent_runtime.py::test_execution_plan_carries_contact_and_realization_semantic_keys`
    - `scripts/character/CharacterPresentationInput.gd`
    - `backend/app/character_agent/execution/l4_executor.py`
- Required outcome `2. local host stays transitional but semantics-complete`
  - Direct evidence:
    - `backend/tests/test_character_actor_boundary_audit.py::test_character_replica_still_behaves_as_local_realization_host_not_semantics_owner`
    - `scripts/character/CharacterReplica.gd`
    - `scripts/character/CharacterRuntimeState.gd`
    - `docs/character/character-agent-runtime-architecture.md`

**Completion Audit Conclusion (`2026-06-30`):**
- Within the current first-pass scope of this plan, both required outcomes now have direct repository evidence.
- Remaining non-goals for this plan:
  - no fully replaced local realization host yet
  - no final skeletal/bone-space production backend here; this remains a semantics freeze plus transitional-host closure

---

### Task 1: Freeze downstream execution semantic vocabulary

**Files:**
- Modify: `backend/app/character_agent/execution/l4_executor.py`
- Modify: `scripts/character/CharacterPresentationInput.gd`
- Test: `backend/tests/test_character_agent_runtime.py`

- [x] **Step 1: Write the failing execution-semantic vocabulary test**

```python
def test_execution_plan_carries_contact_and_realization_semantic_keys() -> None:
    # use existing executor fixture style
    # assert social_spatial_channel and speech_state include stable semantic labels
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_character_agent_runtime.py -k execution_plan -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```python
"execution_semantics": {
    "movement_intent": "approach",
    "contact_phase": "greeting",
    "speech_mode": "public",
    "gesture_mode": "acknowledge",
}
```

```gdscript
var execution_semantics: Dictionary = presentation_plan.get("execution_semantics", {})
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_character_agent_runtime.py -k execution_plan -v`
Expected: `PASS`

- [x] **Step 5: Commit**

```bash
git add backend/app/character_agent/execution/l4_executor.py scripts/character/CharacterPresentationInput.gd backend/tests/test_character_agent_runtime.py
git commit -m "Freeze downstream execution semantic vocabulary under L4

Constraint: Future realization backends need stable semantics that outlive the current light host
Rejected: Keep semantics implicit in gesture/action string guesses | impossible to map cleanly to asset-runtime and Kimodo
Confidence: high
Scope-risk: moderate
Directive: New embodiment behaviors must be named semantically before they are realized locally
Tested: pytest backend/tests/test_character_agent_runtime.py -k execution_plan -v
Not-tested: live actor rendering"
```

### Task 2: Keep the local presentation host explicitly transitional but semantics-complete

**Files:**
- Modify: `scripts/character/CharacterRuntimeState.gd`
- Modify: `scripts/character/CharacterReplica.gd`
- Modify: `docs/character/character-agent-runtime-architecture.md`
- Test: `backend/tests/test_character_actor_boundary_audit.py`

- [x] **Step 1: Write the failing transitional-host audit**

```python
from pathlib import Path


def test_character_replica_still_behaves_as_local_realization_host_not_semantics_owner() -> None:
    source = Path("scripts/character/CharacterReplica.gd").read_text(encoding="utf-8")
    assert "execution_semantics" in source
    assert "selected_intent" not in source
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_character_actor_boundary_audit.py::test_character_replica_still_behaves_as_local_realization_host_not_semantics_owner -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```gdscript
var execution_semantics: Dictionary = presentation_plan.get("execution_semantics", {})
var movement_intent := str(execution_semantics.get("movement_intent", ""))
if movement_intent == "approach" and target_node != null:
	set_move_target(target_node.global_position)
```

```markdown
Current actor-side realization remains a compatibility host for execution semantics and must not become the long-term owner of role intent semantics.
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_character_actor_boundary_audit.py::test_character_replica_still_behaves_as_local_realization_host_not_semantics_owner -v`
Expected: `PASS`

- [x] **Step 5: Commit**

```bash
git add scripts/character/CharacterRuntimeState.gd scripts/character/CharacterReplica.gd docs/character/character-agent-runtime-architecture.md backend/tests/test_character_actor_boundary_audit.py
git commit -m "Keep local actor host transitional while semantics move below L4

Constraint: The current Godot host must remain a realization surface, not the new owner of role semantics
Rejected: Let CharacterReplica infer long-term execution meaning from local state alone | freezes the temporary host as architecture truth
Confidence: medium
Scope-risk: moderate
Directive: Local realization code should consume execution semantics, not recreate upstream intent selection
Tested: pytest backend/tests/test_character_actor_boundary_audit.py::test_character_replica_still_behaves_as_local_realization_host_not_semantics_owner -v
Not-tested: full runtime verifier"
```
