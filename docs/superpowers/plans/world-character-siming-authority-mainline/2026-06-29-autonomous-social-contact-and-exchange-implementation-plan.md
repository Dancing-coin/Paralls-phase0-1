# Autonomous Social Contact And Exchange Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the runtime loop for autonomous notice, approach, contact, greeting, probing, and exchange ownership.

**Architecture:** Reuse the completed mind core and keep social contact as a runtime framework around it. Formalize contact lifecycle objects, fix utterance ownership on the backend, and stage greeting/probing behavior through execution semantics and presentation inputs instead of scene-script branches.

**Tech Stack:** Python backend runtime, Godot shared actor ingress, existing dialogue service, existing `CharacterAgentRuntime`, pytest, runtime verification scripts.

**Progress Snapshot (`2026-06-30`):**
- Tasks `1-4` now have direct repository evidence.
- Current proof chain covers:
  - proactive utterance ownership split
  - contact lifecycle / greeting semantics
  - arrival-driven social continuity
  - dedicated runtime verifier `verify_autonomous_social_contact.py`

**Direct Evidence Audit (`2026-06-30`):**
- Required outcome `1. agent-initiated utterance preserves speaker ownership`
  - Direct evidence:
    - `backend/tests/test_character_service.py::test_agent_initiated_utterance_preserves_speaking_actor`
    - `backend/app/services/dialogue_service.py`
    - `backend/app/services/character_service.py`
- Required outcome `2. contact lifecycle is formalized on the live runtime path`
  - Direct evidence:
    - `backend/tests/test_character_agent_runtime.py -k greeting -v`
    - `backend/app/character_agent/execution/l4_executor.py`
    - `scripts/character/CharacterRuntimeState.gd`
    - `scripts/character/KnightRoleSkin.gd`
- Required outcome `3. arrival-driven approach/contact continuity is closed`
  - Direct evidence:
    - `backend/tests/test_ws_protocol.py -k arrival_fact -v`
    - `scripts/character/CharacterReplica.gd`
    - `scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd`
- Required outcome `4. dedicated end-to-end verifier exists`
  - Direct evidence:
    - `python scripts/verification/verify_autonomous_social_contact.py`
    - `.harness/verification/autonomous-social-contact-report.json`
    - unified verifier result `autonomous_social_contact=proved`

**Completion Audit Conclusion (`2026-06-30`):**
- Within the current first-pass scope of this plan, the four required outcomes now have direct repository evidence.
- Remaining non-goals for this plan:
  - no broader social exchange dramaturgy beyond the current notice/approach/arrival/greeting/utterance closure
  - no generalized multi-party conversation choreography yet

---

### Task 1: Separate agent-initiated utterance from reply-style dialogue

**Files:**
- Modify: `backend/app/services/dialogue_service.py`
- Modify: `backend/app/services/character_service.py`
- Test: `backend/tests/test_character_service.py`

- [x] **Step 1: Write the failing ownership tests**

```python
from app.services.character_service import CharacterService
from app.models.player_input import DialogueSubmit


def test_agent_initiated_utterance_preserves_speaking_actor() -> None:
    service = CharacterService()
    event = DialogueSubmit(
        player_id="character_agent",
        room_id="room_demo",
        actor_id="char_a",
        intent_type="dialogue_submit",
        producer_ts=1,
        target_actor_id="char_c",
        content="approach greeting",
    )
    result = service.handle_dialogue(event)
    assert result.actor_id == "char_a"
    assert result.target_actor_id == "char_c"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_character_service.py::test_agent_initiated_utterance_preserves_speaking_actor -v`
Expected: `FAIL` because the current reply path inverts speaker ownership.

- [x] **Step 3: Write minimal implementation**

```python
def generate_utterance(self, actor_id: str, target_actor_id: str, content: str) -> tuple[str, str]:
    output = self._gateway.run_task(
        task_kind="dialogue_generation",
        context={
            "actor_id": actor_id,
            "control_mode": "agent_initiated_utterance",
            "snapshot": {},
            "memory": {"working_memories": [], "episodic_memories": [], "relational_memories": []},
            "event": {
                "content": content,
                "target_actor_id": target_actor_id,
                "intent_type": "agent_initiated_utterance",
            },
        },
    )
    return str(output.get("content", "") or ""), str(output.get("tone", "") or "neutral")
```

```python
if event.player_id == "character_agent":
    content, tone = self.dialogue.generate_utterance(event.actor_id, event.target_actor_id, event.content)
    return DialogueResponse(
        actor_id=event.actor_id,
        target_actor_id=event.target_actor_id,
        ...
    )
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_character_service.py::test_agent_initiated_utterance_preserves_speaking_actor -v`
Expected: `PASS`

- [x] **Step 5: Commit**

```bash
git add backend/app/services/dialogue_service.py backend/app/services/character_service.py backend/tests/test_character_service.py
git commit -m "Split autonomous utterance ownership from reply-style dialogue

Constraint: Social exchange needs role-owned speech, not target-owned reply inversion
Rejected: Keep one reply-shaped service for both reactions and initiations | breaks autonomous contact semantics
Confidence: high
Scope-risk: moderate
Directive: All future proactive speech paths must preserve the initiating actor explicitly
Tested: pytest backend/tests/test_character_service.py::test_agent_initiated_utterance_preserves_speaking_actor -v
Not-tested: full websocket/runtime loop"
```

### Task 2: Formalize contact lifecycle on the live runtime path

**Files:**
- Modify: `backend/app/character_agent/execution/l4_executor.py`
- Modify: `scripts/character/CharacterRuntimeState.gd`
- Modify: `scripts/character/KnightRoleSkin.gd`
- Test: `backend/tests/test_character_agent_runtime.py`

- [x] **Step 1: Write the failing contact-lifecycle test**

```python
def test_contact_lifecycle_can_stage_greeting_after_approach() -> None:
    from app.character_agent.execution.l4_executor import CharacterAgentL4Executor

    executor = CharacterAgentL4Executor()
    # use an existing fixture style snapshot/interpretation/decision in the test file
    # assert the resulting plan contains a social or gesture hint for greeting when arrival semantics are active
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_character_agent_runtime.py -k greeting -v`
Expected: `FAIL` because greeting-stage semantics are not yet formalized.

- [x] **Step 3: Write minimal implementation**

```python
"social_spatial_channel": {
    "spacing_behavior": spacing_behavior,
    "target_ref": target,
    "orientation_mode": orientation_mode,
    "contact_phase": "greeting" if decision.selected_intent in {"speak_public", "speak_private", "approach"} else "none",
},
```

```gdscript
if str(presentation_plan.get("contact_phase", "")) == "greeting":
    action_state["requested_action"] = "greeting_nod"
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_character_agent_runtime.py -k greeting -v`
Expected: `PASS`

- [x] **Step 5: Commit**

```bash
git add backend/app/character_agent/execution/l4_executor.py scripts/character/CharacterRuntimeState.gd scripts/character/KnightRoleSkin.gd backend/tests/test_character_agent_runtime.py
git commit -m "Formalize contact lifecycle and greeting-phase execution semantics

Constraint: Contact closure must run on the real runtime path rather than a scene-script branch
Rejected: Trigger greeting through MainDemoController-only callbacks | not a reusable exchange lifecycle
Confidence: medium
Scope-risk: moderate
Directive: Greeting, probing, and silence should be represented as runtime contact phases, not ad hoc scene actions
Tested: pytest backend/tests/test_character_agent_runtime.py -k greeting -v
Not-tested: live in-scene arrival timing"
```

### Task 3: Close arrival-driven approach and contact continuity

**Files:**
- Modify: `scripts/character/CharacterReplica.gd`
- Modify: `scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd`
- Test: `backend/tests/test_ws_protocol.py`

- [x] **Step 1: Write the failing continuity test**

```python
def test_autonomous_approach_can_emit_arrival_fact_after_execution() -> None:
    # send character_agent_execution with approach semantics
    # assert a follow-on spatial access fact or status signal is emitted on arrival
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_ws_protocol.py -k arrival_fact -v`
Expected: `FAIL`

- [x] **Step 3: Write minimal implementation**

```gdscript
func _move_toward_target(target: Vector3, delta: float, clear_on_arrival: bool) -> void:
	...
	if to_target.length() < 0.05:
		if clear_on_arrival and _active_contact_target_actor_id != "":
			_emit_arrival_fact(_active_contact_target_actor_id, 0.0)
		...
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_ws_protocol.py -k arrival_fact -v`
Expected: `PASS`

- [x] **Step 5: Commit**

```bash
git add scripts/character/CharacterReplica.gd scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd backend/tests/test_ws_protocol.py
git commit -m "Emit arrival facts for autonomous social contact closure

Constraint: Social contact needs explicit arrival continuity, not only movement completion
Rejected: Treat arrival as a purely visual local event | loses role-to-role writeback continuity
Confidence: medium
Scope-risk: moderate
Directive: Any approach-like behavior that matters socially should emit a reusable arrival/proximity fact
Tested: pytest backend/tests/test_ws_protocol.py -k arrival_fact -v
Not-tested: multi-role chained interactions"
```

### Task 4: Add end-to-end autonomous contact verifier

**Files:**
- Create: `scripts/verification/verify_autonomous_social_contact.py`
- Modify: `docs/INDEX.md`
- Test: `python scripts/verification/verify_autonomous_social_contact.py`

- [x] **Step 1: Write the verifier shell**

```python
def main() -> int:
    # launch backend
    # launch Godot scene or probe
    # confirm actor notice, approach, arrival, greeting, and speech ownership markers
    return 0
```

- [x] **Step 2: Define proof markers**

```text
autonomous_contact:notice=true
autonomous_contact:approach_started=true
autonomous_contact:arrival_fact=true
autonomous_contact:greeting_applied=true
autonomous_contact:utterance_owned_by_initiator=true
```

- [x] **Step 3: Run verifier and record current expected status**

Run: `python scripts/verification/verify_autonomous_social_contact.py`
Expected: initial `FAIL` or partial until the full loop is landed.

- [x] **Step 4: Commit**

```bash
git add scripts/verification/verify_autonomous_social_contact.py docs/INDEX.md
git commit -m "Add end-to-end autonomous social contact verifier

Constraint: The mainline needs direct proof for role-owned contact and exchange closure
Rejected: Infer completion only from generic execution and observatory verifiers | too indirect for the new mainline claim
Confidence: medium
Scope-risk: narrow
Directive: Mainline runtime loops should gain dedicated end-to-end proof scripts as they become architecture truth
Tested: python scripts/verification/verify_autonomous_social_contact.py
Not-tested: full green autonomous contact runtime"
```
