# Mind Core Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reframe the repository around the complete character mind core and land the runtime object, storage, and documentation foundation that later `L1/L2/L3` work will build on.

**Architecture:** Treat this plan as the source-of-truth and substrate pass. It does not attempt to finish cognition behavior by itself. It creates the new runtime object model, marks outdated repository-local truths as transitional, and introduces explicit state holders for dynamic state and higher-order cognition so later plans can deepen behavior without reopening architecture.

**Tech Stack:** Python, Pydantic, pytest, repository docs under `docs/`, backend character-agent package.

---

### Task 1: Rewrite repository-local character-agent source-of-truth entry points

**Files:**
- Modify: `docs/INDEX.md`
- Modify: `docs/character/character-agent-runtime-architecture.md`
- Modify: `docs/character/character-actor-migration-status.md`
- Modify: `docs/ai-engineering-workflow.md`
- Test: `scripts/verification/harness.py --profile docs`

- [ ] **Step 1: Write the failing doc-truth regression test**

```python
from pathlib import Path


def test_character_index_points_to_complete_mind_core_spec() -> None:
    index_text = Path("docs/INDEX.md").read_text(encoding="utf-8")
    assert "2026-06-29-complete-character-mind-core-design.md" in index_text
    assert "character-agent-runtime-architecture.md" in index_text
```

- [ ] **Step 2: Run the targeted test to verify failure**

Run: `pytest backend/tests/test_documentation_entrypoints.py::test_character_index_points_to_complete_mind_core_spec -v`
Expected: `FAIL` because the new top-level spec is not yet linked from `docs/INDEX.md`.

- [ ] **Step 3: Update `docs/INDEX.md` to promote the new top-level spec**

```markdown
## Active Design And Plans

- `docs/superpowers/specs/2026-06-29-complete-character-mind-core-design.md`
- `docs/superpowers/plans/2026-06-29-mind-core-foundation-implementation-plan.md`
- `docs/superpowers/plans/2026-06-29-full-l1-and-memory-implementation-plan.md`
- `docs/superpowers/plans/2026-06-29-full-l2-and-l3-implementation-plan.md`
- `docs/superpowers/plans/2026-06-29-execution-preservation-and-readiness-implementation-plan.md`
```

- [ ] **Step 4: Mark stale runtime docs as transitional instead of current final truth**

```markdown
## Status

This document now describes the current runnable runtime shape only.

For the approved mainline target for character-agent work, see:

- `docs/superpowers/specs/2026-06-29-complete-character-mind-core-design.md`

This file must not be used as the final architectural target for perception, cognition memory, or planning completeness.
```

Apply the status block near the top of:

- `docs/character/character-agent-runtime-architecture.md`
- `docs/character/character-actor-migration-status.md`

- [ ] **Step 5: Update workflow doc so future character-agent work follows the new top-level source of truth**

```markdown
## Character-Agent Mainline Rule

For character-agent work after `2026-06-29`, the source of truth begins with:

- `docs/superpowers/specs/2026-06-29-complete-character-mind-core-design.md`

Older `Phase 0`-bounded character-agent docs are historical or transitional unless explicitly re-linked by a newer spec.
```

- [ ] **Step 6: Run documentation verification**

Run: `python scripts/verification/harness.py --profile docs`
Expected: `PASS`

- [ ] **Step 7: Commit**

```bash
git add docs/INDEX.md docs/character/character-agent-runtime-architecture.md docs/character/character-actor-migration-status.md docs/ai-engineering-workflow.md backend/tests/test_documentation_entrypoints.py
git commit -m "Promote complete character mind core as repository truth

Constraint: Character-agent work must stop inheriting the old Phase 0-only mission
Rejected: Leave old docs as implicit truth and rely on one new spec file | keeps future planning ambiguous
Confidence: high
Scope-risk: moderate
Directive: Repository-local character-agent implementation plans must anchor to the 2026-06-29 top-level spec unless a newer one supersedes it
Tested: python scripts/verification/harness.py --profile docs
Not-tested: downstream runtime behavior"
```

### Task 2: Add explicit runtime object model for dynamic state and higher-order cognition

**Files:**
- Create: `backend/app/character_agent/models/dynamic_state.py`
- Create: `backend/app/character_agent/models/higher_order_memory.py`
- Create: `backend/app/character_agent/models/cognition_update.py`
- Modify: `backend/app/character_agent/models/__init__.py`
- Test: `backend/tests/test_character_mind_core_models.py`

- [ ] **Step 1: Write the failing model tests**

```python
from app.character_agent.models.cognition_update import CharacterCognitionUpdate
from app.character_agent.models.dynamic_state import CharacterDynamicState
from app.character_agent.models.higher_order_memory import CharacterHigherOrderMemoryRecord


def test_dynamic_state_tracks_live_subjective_pressure_fields() -> None:
    state = CharacterDynamicState(
        actor_id="char_a",
        vigilance_level=0.7,
        distraction_level=0.2,
        stress_load=0.5,
        social_pressure=0.6,
        masking_pressure=0.3,
        motivation_stack=["preserve_order", "avoid_public_exposure"],
    )
    assert state.motivation_stack == ["preserve_order", "avoid_public_exposure"]


def test_higher_order_memory_tracks_who_knows_what_about_whom() -> None:
    record = CharacterHigherOrderMemoryRecord(
        memory_id="hom:1",
        actor_id="char_a",
        subject_actor_id="char_b",
        proposition_key="obj_letter:is_sensitive",
        meta_belief="char_b suspects char_c knows the letter matters",
        confidence=0.66,
        source_event_id="evt:1",
        producer_ts=10,
    )
    assert record.subject_actor_id == "char_b"
    assert record.confidence == 0.66


def test_cognition_update_groups_belief_social_higher_order_and_dynamic_deltas() -> None:
    update = CharacterCognitionUpdate(
        interpreted_situation="char_b appears to test whether char_c will disclose",
        belief_deltas=[{"proposition_key": "char_b:is_probing", "state": "suspected"}],
        social_deltas=[{"entity_id": "char_b", "suspicion_baseline": 0.8}],
        higher_order_deltas=[{"subject_actor_id": "char_b", "meta_belief": "char_b suspects char_c knows more"}],
        dynamic_state_delta={"social_pressure": 0.6, "masking_pressure": 0.4},
    )
    assert update.dynamic_state_delta["social_pressure"] == 0.6
```

- [ ] **Step 2: Run the model tests to verify failure**

Run: `pytest backend/tests/test_character_mind_core_models.py -v`
Expected: `FAIL` because the new model files do not yet exist.

- [ ] **Step 3: Add `CharacterDynamicState`**

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CharacterDynamicState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    vigilance_level: float = Field(ge=0.0, le=1.0)
    distraction_level: float = Field(ge=0.0, le=1.0)
    stress_load: float = Field(ge=0.0, le=1.0)
    social_pressure: float = Field(ge=0.0, le=1.0)
    masking_pressure: float = Field(ge=0.0, le=1.0)
    affect_valence: float = Field(default=0.0, ge=-1.0, le=1.0)
    motivation_stack: list[str] = Field(default_factory=list)
    unresolved_conflicts: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Add `CharacterHigherOrderMemoryRecord` and `CharacterCognitionUpdate`**

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CharacterHigherOrderMemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    memory_id: str
    actor_id: str
    subject_actor_id: str
    proposition_key: str
    meta_belief: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_event_id: str
    producer_ts: int
```

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CharacterCognitionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    interpreted_situation: str
    belief_deltas: list[dict[str, object]] = Field(default_factory=list)
    social_deltas: list[dict[str, object]] = Field(default_factory=list)
    higher_order_deltas: list[dict[str, object]] = Field(default_factory=list)
    dynamic_state_delta: dict[str, float] = Field(default_factory=dict)
```

- [ ] **Step 5: Export the new model surfaces**

```python
from app.character_agent.models.cognition_update import CharacterCognitionUpdate
from app.character_agent.models.dynamic_state import CharacterDynamicState
from app.character_agent.models.higher_order_memory import CharacterHigherOrderMemoryRecord

__all__ = [
    "CharacterCognitionUpdate",
    "CharacterDynamicState",
    "CharacterHigherOrderMemoryRecord",
]
```

- [ ] **Step 6: Run the model tests**

Run: `pytest backend/tests/test_character_mind_core_models.py -v`
Expected: `PASS`

- [ ] **Step 7: Commit**

```bash
git add backend/app/character_agent/models backend/tests/test_character_mind_core_models.py
git commit -m "Add mind-core runtime model foundation

Constraint: Complete character mind core requires dynamic state and higher-order cognition as first-class runtime objects
Rejected: Keep these concerns implicit inside snapshot or memory dicts | blocks deeper L2/L3 implementation
Confidence: high
Scope-risk: narrow
Directive: New cognition behavior should move through explicit runtime models before being hidden inside service-local dictionaries
Tested: pytest backend/tests/test_character_mind_core_models.py -v
Not-tested: runtime integration"
```

### Task 3: Add stateful storage seams for dynamic state and higher-order memory

**Files:**
- Create: `backend/app/character_agent/storage/dynamic_state_store.py`
- Create: `backend/app/character_agent/storage/higher_order_memory_store.py`
- Modify: `backend/app/character_agent/storage/__init__.py`
- Test: `backend/tests/test_character_mind_core_storage.py`

- [ ] **Step 1: Write the failing storage tests**

```python
from app.character_agent.storage.dynamic_state_store import CharacterDynamicStateStore
from app.character_agent.storage.higher_order_memory_store import CharacterHigherOrderMemoryStore


def test_dynamic_state_store_round_trips_actor_state() -> None:
    store = CharacterDynamicStateStore()
    store.write(
        "char_a",
        {
            "actor_id": "char_a",
            "vigilance_level": 0.7,
            "distraction_level": 0.1,
            "stress_load": 0.4,
            "social_pressure": 0.5,
            "masking_pressure": 0.2,
            "motivation_stack": ["preserve_order"],
        },
    )
    assert store.read("char_a")["vigilance_level"] == 0.7


def test_higher_order_memory_store_groups_records_by_actor() -> None:
    store = CharacterHigherOrderMemoryStore()
    store.append(
        "char_a",
        {
            "memory_id": "hom:1",
            "actor_id": "char_a",
            "subject_actor_id": "char_b",
            "proposition_key": "obj_letter:is_sensitive",
            "meta_belief": "char_b suspects char_c knows more",
            "confidence": 0.66,
            "source_event_id": "evt:1",
            "producer_ts": 10,
        },
    )
    assert store.recall("char_a")[0]["subject_actor_id"] == "char_b"
```

- [ ] **Step 2: Run the storage tests to verify failure**

Run: `pytest backend/tests/test_character_mind_core_storage.py -v`
Expected: `FAIL` because the new stores do not yet exist.

- [ ] **Step 3: Add the two stores**

```python
from __future__ import annotations

from copy import deepcopy


class CharacterDynamicStateStore:
    def __init__(self) -> None:
        self._by_actor: dict[str, dict[str, object]] = {}

    def write(self, actor_id: str, state: dict[str, object]) -> None:
        self._by_actor[actor_id] = deepcopy(state)

    def read(self, actor_id: str) -> dict[str, object]:
        return deepcopy(self._by_actor.get(actor_id, {}))
```

```python
from __future__ import annotations

from copy import deepcopy


class CharacterHigherOrderMemoryStore:
    def __init__(self) -> None:
        self._by_actor: dict[str, list[dict[str, object]]] = {}

    def append(self, actor_id: str, record: dict[str, object]) -> None:
        self._by_actor.setdefault(actor_id, []).append(deepcopy(record))

    def recall(self, actor_id: str) -> list[dict[str, object]]:
        return deepcopy(self._by_actor.get(actor_id, []))
```

- [ ] **Step 4: Export the store surfaces**

```python
from app.character_agent.storage.dynamic_state_store import CharacterDynamicStateStore
from app.character_agent.storage.higher_order_memory_store import CharacterHigherOrderMemoryStore

__all__ = [
    "CharacterDynamicStateStore",
    "CharacterHigherOrderMemoryStore",
]
```

- [ ] **Step 5: Run the storage tests**

Run: `pytest backend/tests/test_character_mind_core_storage.py -v`
Expected: `PASS`

- [ ] **Step 6: Commit**

```bash
git add backend/app/character_agent/storage backend/tests/test_character_mind_core_storage.py
git commit -m "Add storage seams for dynamic state and higher-order memory

Constraint: L2 and L3 cannot become complete mind-core layers without stable state and meta-cognition storage
Rejected: Hide dynamic and higher-order state in service instance fields only | blocks replay and auditability
Confidence: high
Scope-risk: narrow
Directive: Treat dynamic state and higher-order cognition as durable runtime surfaces, not temporary inference locals
Tested: pytest backend/tests/test_character_mind_core_storage.py -v
Not-tested: timeline integration"
```
