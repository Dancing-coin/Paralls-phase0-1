# Full L1 And Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the role-private perception layer and the five-pool memory architecture, including dynamic-state deposition and higher-order-memory updates from perception and writeback.

**Architecture:** This plan deepens runtime truth below cognition. `L1` becomes a true private-world entrance with modality, quality, and pressure semantics; memory becomes a full five-pool system plus dynamic-state writeback inputs. It does not finish final cognition reasoning, but it makes that reasoning possible and auditable.

**Tech Stack:** Python, Pydantic, pytest, current `CharacterAgentRuntime`, current memory stores and snapshot models.

---

### Task 1: Expand the private snapshot to full role-private perception coverage

**Files:**
- Modify: `backend/app/character_agent/models/private_world_snapshot.py`
- Modify: `backend/app/character_agent/reasoning/l1_perception.py`
- Test: `backend/tests/test_character_agent_l1_full_runtime.py`
- Test: `backend/tests/test_character_agent_private_snapshot_models.py`

- [ ] **Step 1: Write the failing snapshot tests**

```python
from app.character_agent.models.private_world_snapshot import CharacterPrivateWorldSnapshot


def test_private_snapshot_tracks_modality_and_quality_specific_fields() -> None:
    snapshot = CharacterPrivateWorldSnapshot(
        actor_id="char_a",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=1,
        updated_at=1,
        olfactory_entities=["smoke_trace"],
        thermal_entities=["heat_bloom"],
        tactile_entities=["nearby_brush_contact"],
        partial_observations=["char_b motion silhouette only"],
        distorted_details=["voice direction uncertain"],
        missed_details=["speaker identity lost in noise"],
    )
    assert snapshot.olfactory_entities == ["smoke_trace"]
    assert snapshot.partial_observations == ["char_b motion silhouette only"]
```

- [ ] **Step 2: Run the focused test to verify failure**

Run: `pytest backend/tests/test_character_agent_private_snapshot_models.py::test_private_snapshot_tracks_modality_and_quality_specific_fields -v`
Expected: `FAIL` because the expanded snapshot fields do not yet exist.

- [ ] **Step 3: Extend the snapshot model**

```python
olfactory_entities: list[str] = Field(default_factory=list)
thermal_entities: list[str] = Field(default_factory=list)
tactile_entities: list[str] = Field(default_factory=list)
partial_observations: list[str] = Field(default_factory=list)
distorted_details: list[str] = Field(default_factory=list)
missed_details: list[str] = Field(default_factory=list)
salience_tags: list[str] = Field(default_factory=list)
attention_pressure: float = Field(default=0.0, ge=0.0, le=1.0)
```

- [ ] **Step 4: Teach `L1` to populate the new modality and quality fields**

```python
if event.percept_channel == "olfactory":
    snapshot.olfactory_entities = self._append_unique(snapshot.olfactory_entities, event.perceived_summary)
elif event.percept_channel == "thermal":
    snapshot.thermal_entities = self._append_unique(snapshot.thermal_entities, event.perceived_summary)
elif event.percept_channel == "tactile":
    snapshot.tactile_entities = self._append_unique(snapshot.tactile_entities, event.perceived_summary)

if event.clarity_score < 0.75:
    snapshot.partial_observations = self._append_unique(snapshot.partial_observations, event.perceived_summary)
if event.certainty_score < 0.65:
    snapshot.distorted_details = self._append_unique(snapshot.distorted_details, event.perceived_summary)
if event.certainty_score < 0.45:
    snapshot.missed_details = self._append_unique(snapshot.missed_details, event.perceived_summary)
```

- [ ] **Step 5: Run the snapshot and `L1` tests**

Run: `pytest backend/tests/test_character_agent_private_snapshot_models.py backend/tests/test_character_agent_l1_full_runtime.py -v`
Expected: `PASS`

- [ ] **Step 6: Commit**

```bash
git add backend/app/character_agent/models/private_world_snapshot.py backend/app/character_agent/reasoning/l1_perception.py backend/tests/test_character_agent_private_snapshot_models.py backend/tests/test_character_agent_l1_full_runtime.py
git commit -m "Expand L1 private snapshot to full role-private perception coverage

Constraint: Complete mind core requires modality- and quality-aware private perception, not only visual/auditory lists
Rejected: Keep new modality semantics implicit in free-text event summaries | blocks reliable cognition updates
Confidence: medium
Scope-risk: moderate
Directive: New perception work should extend the private snapshot explicitly before deepening L2 interpretation rules
Tested: pytest backend/tests/test_character_agent_private_snapshot_models.py backend/tests/test_character_agent_l1_full_runtime.py -v
Not-tested: Godot runtime smoke"
```

### Task 2: Upgrade memory architecture from four pools to five pools plus dynamic-state deposition

**Files:**
- Create: `backend/app/character_agent/memory/higher_order_memory.py`
- Modify: `backend/app/character_agent/storage/memory_store.py`
- Modify: `backend/app/character_agent/memory/working_memory.py`
- Test: `backend/tests/test_character_agent_stage2_memory_models.py`
- Test: `backend/tests/test_character_agent_stage2_memory_deposition.py`
- Test: `backend/tests/test_character_agent_runtime_memory_integration.py`

- [ ] **Step 1: Write the failing five-pool retrieval test**

```python
from app.character_agent.storage.memory_store import CharacterAgentMemoryStore


def test_retrieval_bundle_exposes_five_memory_pools_and_dynamic_state_inputs() -> None:
    store = CharacterAgentMemoryStore()
    bundle = store.retrieval_bundle("char_a")
    assert set(bundle.keys()) >= {
        "working_memory",
        "event_memories",
        "observation_memories",
        "knowledge_memories",
        "social_memories",
        "higher_order_memories",
    }
```

- [ ] **Step 2: Run the targeted test to verify failure**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py::test_retrieval_bundle_exposes_five_memory_pools_and_dynamic_state_inputs -v`
Expected: `FAIL` because `higher_order_memories` is not yet part of the retrieval bundle.

- [ ] **Step 3: Add `CharacterHigherOrderMemory`**

```python
from __future__ import annotations

from copy import deepcopy


class CharacterHigherOrderMemory:
    def __init__(self) -> None:
        self._entries_by_actor: dict[str, list[dict[str, object]]] = {}

    def append(self, *, actor_id: str, record: dict[str, object]) -> None:
        self._entries_by_actor.setdefault(actor_id, []).append(deepcopy(record))

    def recall(self, actor_id: str) -> list[dict[str, object]]:
        return deepcopy(self._entries_by_actor.get(actor_id, []))
```

- [ ] **Step 4: Wire higher-order memory and dynamic-state deposition into `CharacterAgentMemoryStore`**

```python
self._higher_order = CharacterHigherOrderMemory()

return {
    "working_memory": self._working.recall(actor_id),
    "event_memories": event_memories,
    "observation_memories": observation_memories,
    "knowledge_memories": knowledge_memories,
    "social_memories": social_memories,
    "higher_order_memories": self._higher_order.recall(actor_id),
    "episodic_memories": self._legacy_episodic_memories(event_memories),
    "relational_memories": self._legacy_relational_memories(knowledge_memories),
}
```

Add deposition rule for higher-order belief events:

```python
elif event_type == "higher_order_belief_event":
    self._higher_order.append(
        actor_id=actor_id,
        record={
            "memory_id": str(event.get("event_id", "") or ""),
            "actor_id": actor_id,
            "subject_actor_id": str(payload.get("subject_actor_id", "") or ""),
            "proposition_key": str(payload.get("proposition_key", "") or ""),
            "meta_belief": str(payload.get("meta_belief", "") or ""),
            "confidence": float(payload.get("confidence", 0.0) or 0.0),
            "source_event_id": str(event.get("event_id", "") or ""),
            "producer_ts": int(event.get("producer_ts", 0) or 0),
        },
    )
```

- [ ] **Step 5: Run the memory suites**

Run: `pytest backend/tests/test_character_agent_stage2_memory_models.py backend/tests/test_character_agent_stage2_memory_deposition.py backend/tests/test_character_agent_runtime_memory_integration.py -v`
Expected: `PASS`

- [ ] **Step 6: Commit**

```bash
git add backend/app/character_agent/memory/higher_order_memory.py backend/app/character_agent/storage/memory_store.py backend/app/character_agent/memory/working_memory.py backend/tests/test_character_agent_stage2_memory_models.py backend/tests/test_character_agent_stage2_memory_deposition.py backend/tests/test_character_agent_runtime_memory_integration.py
git commit -m "Upgrade character memory to five cognitive pools

Constraint: Complete mind core requires higher-order cognition and explicit memory separation before full L2/L3 work
Rejected: Keep higher-order cognition as a future note only | prevents full social-cognitive planning
Confidence: medium
Scope-risk: moderate
Directive: New cognition deposition rules should preserve source lineage and avoid flattening into one generic memory list
Tested: pytest backend/tests/test_character_agent_stage2_memory_models.py backend/tests/test_character_agent_stage2_memory_deposition.py backend/tests/test_character_agent_runtime_memory_integration.py -v
Not-tested: broad websocket integration"
```
