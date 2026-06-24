# Character Memory And Knowledge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current transitional working/episodic/relational layering with the Stage 2 four-pool memory system and explicit knowledge-state progression while preserving current runtime continuity.

**Architecture:** Keep `CharacterAgentMemoryStore` as the aggregation seam, but expand it into explicit `Event`, `Observation`, `Knowledge`, and `Social` memory pools plus a formal `KnowledgeState` model. Reuse the current session timeline as the deposition source while separating short-horizon snapshot state from durable role-internal cognition.

**Tech Stack:** Python, current memory store/session store, Pydantic models, pytest.

---

### Task 1: Add explicit observation, knowledge, and social memory models

**Files:**
- Create: `backend/app/character_agent/models/knowledge_state.py`
- Create: `backend/app/character_agent/memory/event_memory.py`
- Create: `backend/app/character_agent/memory/observation_memory.py`
- Create: `backend/app/character_agent/memory/knowledge_memory.py`
- Create: `backend/app/character_agent/memory/social_memory.py`
- Test: `backend/tests/test_character_agent_knowledge_state.py`
- Test: `backend/tests/test_character_agent_stage2_memory_models.py`

- [ ] **Step 1: Write failing tests for knowledge state and memory records**

```python
from app.character_agent.models.knowledge_state import KnowledgeState
from app.character_agent.memory.knowledge_memory import CharacterKnowledgeMemory


def test_knowledge_state_supports_stage2_progression() -> None:
    assert KnowledgeState.NOTICED.value == "noticed"
    assert KnowledgeState.HIGH_CONFIDENCE_BELIEVED.value == "high_confidence_believed"


def test_knowledge_memory_upserts_proposition_records() -> None:
    memory = CharacterKnowledgeMemory()
    record = memory.upsert_proposition(
        actor_id="char_a",
        proposition_key="letter_is_important",
        proposition="the letter is important",
        state="suspected",
        confidence=0.55,
        source_event_id="evt-1",
        producer_ts=10,
    )
    assert record["state"] == "suspected"
    assert record["confidence"] == 0.55
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest backend/tests/test_character_agent_knowledge_state.py backend/tests/test_character_agent_stage2_memory_models.py -v`
Expected: FAIL because state enum and memory classes do not exist.

- [ ] **Step 3: Implement the state enum and memory classes**

```python
from enum import Enum


class KnowledgeState(str, Enum):
    NOTICED = "noticed"
    SUSPECTED = "suspected"
    TENTATIVELY_BELIEVED = "tentatively_believed"
    BELIEVED = "believed"
    HIGH_CONFIDENCE_BELIEVED = "high_confidence_believed"
    DISPUTED = "disputed"
    ABANDONED = "abandoned"
```

```python
class CharacterKnowledgeMemory:
    def __init__(self) -> None:
        self._entries_by_actor: dict[str, list[dict[str, object]]] = {}

    def upsert_proposition(self, *, actor_id: str, proposition_key: str, proposition: str, state: str, confidence: float, source_event_id: str, producer_ts: int) -> dict[str, object]:
        entry = {
            "memory_id": f"knowledge:{actor_id}:{proposition_key}",
            "actor_id": actor_id,
            "proposition_key": proposition_key,
            "proposition": proposition,
            "state": state,
            "confidence": confidence,
            "source_event_id": source_event_id,
            "producer_ts": producer_ts,
        }
        entries = self._entries_by_actor.setdefault(actor_id, [])
        for idx, existing in enumerate(entries):
            if existing["proposition_key"] == proposition_key:
                entries[idx] = entry
                return entry
        entries.append(entry)
        return entry
```

- [ ] **Step 4: Run tests**

Run: `pytest backend/tests/test_character_agent_knowledge_state.py backend/tests/test_character_agent_stage2_memory_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/character_agent/models/knowledge_state.py backend/app/character_agent/memory backend/tests/test_character_agent_knowledge_state.py backend/tests/test_character_agent_stage2_memory_models.py
git commit -m "Add Stage 2 knowledge state and explicit memory pool models

Constraint: Stage 2 requires proposition-state progression instead of implicit belief strings
Rejected: Extend relational memory in place to represent all cognition | collapses social and proposition semantics
Confidence: high
Scope-risk: moderate
Directive: Keep knowledge-state progression explicit and machine-testable
Tested: pytest backend/tests/test_character_agent_knowledge_state.py backend/tests/test_character_agent_stage2_memory_models.py -v
Not-tested: integration with runtime writeback"
```

### Task 2: Expand memory store retrieval bundle to four pools

**Files:**
- Modify: `backend/app/character_agent/storage/memory_store.py`
- Modify: `backend/app/character_agent/memory/working_memory.py`
- Test: `backend/tests/test_character_agent_runtime_memory_integration.py`
- Test: `backend/tests/test_character_agent_memory_writeback.py`

- [ ] **Step 1: Write the failing retrieval-bundle test**

```python
from app.character_agent.storage.memory_store import CharacterAgentMemoryStore


def test_retrieval_bundle_exposes_four_stage2_memory_pools() -> None:
    store = CharacterAgentMemoryStore()
    bundle = store.retrieval_bundle("char_a")
    assert set(bundle.keys()) == {
        "working_memory",
        "event_memories",
        "observation_memories",
        "knowledge_memories",
        "social_memories",
    }
```

- [ ] **Step 2: Run the test to verify failure**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py::test_retrieval_bundle_exposes_four_stage2_memory_pools -v`
Expected: FAIL because bundle still returns `episodic_memories` and `relational_memories`.

- [ ] **Step 3: Update memory store to own the four pools**

```python
self._event = CharacterEventMemory()
self._observation = CharacterObservationMemory()
self._knowledge = CharacterKnowledgeMemory()
self._social = CharacterSocialMemory()

def retrieval_bundle(self, actor_id: str) -> dict[str, list[dict[str, object]]]:
    return {
        "working_memory": self._working.recall(actor_id),
        "event_memories": self._event.recall(actor_id),
        "observation_memories": self._observation.recall(actor_id),
        "knowledge_memories": self._knowledge.recall(actor_id),
        "social_memories": self._social.recall(actor_id),
    }
```

- [ ] **Step 4: Update working-memory state to keep Stage 2 slices distinct**

```python
return CharacterWorkingMemoryState(
    recent_perceived_events=recent_perceived_events,
    recent_esm_results=recent_esm_results,
    recent_siming_catalysts=recent_siming_catalysts,
    private_snapshot=dict(private_snapshot or {}),
)
```

Expected change: keep working memory as the short-horizon window, not the home of durable knowledge/social truth.

- [ ] **Step 5: Run memory integration tests**

Run: `pytest backend/tests/test_character_agent_runtime_memory_integration.py backend/tests/test_character_agent_memory_writeback.py -v`
Expected: PASS after bundle/test fixtures are updated.

- [ ] **Step 6: Commit**

```bash
git add backend/app/character_agent/storage/memory_store.py backend/app/character_agent/memory/working_memory.py backend/tests/test_character_agent_runtime_memory_integration.py backend/tests/test_character_agent_memory_writeback.py
git commit -m "Expand runtime retrieval bundle to Stage 2 memory pools

Constraint: Stage 2 requires event/observation/knowledge/social separation without introducing DB persistence yet
Rejected: Keep episodic/relational names and reinterpret them in docs only | leaves runtime semantics ambiguous
Confidence: medium
Scope-risk: moderate
Directive: Retrieval bundles must expose durable cognition pools separately from working memory
Tested: pytest backend/tests/test_character_agent_runtime_memory_integration.py backend/tests/test_character_agent_memory_writeback.py -v
Not-tested: full L2/L3 consumption after bundle rename"
```

### Task 3: Write deposition rules from runtime events into knowledge and social memory

**Files:**
- Modify: `backend/app/character_agent/storage/memory_store.py`
- Modify: `backend/app/character_agent/runtime/runtime_loop.py`
- Test: `backend/tests/test_character_agent_stage2_memory_deposition.py`

- [ ] **Step 1: Write the failing deposition tests**

```python
from app.character_agent.storage.memory_store import CharacterAgentMemoryStore


def test_settlement_result_can_create_knowledge_memory() -> None:
    store = CharacterAgentMemoryStore()
    store.write_event(
        {
            "event_id": "evt-1",
            "actor_id": "char_a",
            "event_type": "character_agent_settlement_result",
            "producer_ts": 10,
            "payload": {
                "result_type": "environment_state_result",
                "change_summary": "the room darkened",
                "target_environment_id": "env_room",
            },
        }
    )
    bundle = store.retrieval_bundle("char_a")
    assert any(item["state"] == "noticed" for item in bundle["knowledge_memories"])


def test_relational_belief_event_upgrades_social_memory() -> None:
    store = CharacterAgentMemoryStore()
    store.write_event(
        {
            "event_id": "evt-2",
            "actor_id": "char_a",
            "event_type": "relational_belief_event",
            "producer_ts": 15,
            "payload": {"entity_id": "char_b", "belief_type": "trust_level", "value": "guarded"},
        }
    )
    bundle = store.retrieval_bundle("char_a")
    assert bundle["social_memories"][0]["entity_id"] == "char_b"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest backend/tests/test_character_agent_stage2_memory_deposition.py -v`
Expected: FAIL because no knowledge/social deposition rules exist.

- [ ] **Step 3: Add deposition rules**

```python
elif event_type == "character_agent_settlement_result":
    proposition_key = f"world:{payload.get('target_environment_id', '')}:{payload.get('result_type', '')}"
    self._knowledge.upsert_proposition(
        actor_id=actor_id,
        proposition_key=proposition_key,
        proposition=str(payload.get("change_summary", "") or payload.get("result_type", "")),
        state="noticed",
        confidence=0.7,
        source_event_id=str(event.get("event_id", "") or ""),
        producer_ts=int(event.get("producer_ts", 0) or 0),
    )
elif event_type == "relational_belief_event":
    self._social.upsert_relation(
        actor_id=actor_id,
        entity_id=str(payload.get("entity_id", "") or ""),
        trust_baseline=str(payload.get("value", "") or ""),
        source_event_id=str(event.get("event_id", "") or ""),
        producer_ts=int(event.get("producer_ts", 0) or 0),
    )
```

- [ ] **Step 4: Run deposition tests**

Run: `pytest backend/tests/test_character_agent_stage2_memory_deposition.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/character_agent/storage/memory_store.py backend/app/character_agent/runtime/runtime_loop.py backend/tests/test_character_agent_stage2_memory_deposition.py
git commit -m "Deposit runtime events into Stage 2 knowledge and social memory

Constraint: Stage 2 requires durable proposition and relationship cognition from existing runtime events
Rejected: Wait for a future DB schema before defining deposition semantics | blocks L2/L3 grounding
Confidence: medium
Scope-risk: moderate
Directive: Keep deposition logic source-aware and event-type-specific
Tested: pytest backend/tests/test_character_agent_stage2_memory_deposition.py -v
Not-tested: broad runtime verification"
```
