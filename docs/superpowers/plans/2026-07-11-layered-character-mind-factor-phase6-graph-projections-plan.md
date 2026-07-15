# Layered Character Mind Factor Phase 6 Graph Projections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an optional graph-backed memory projection port that can enrich memory-evidence cards without making graph queries a cognition authority or replacing memory ownership.

**Architecture:** Add a protocol and no-op provider under `backend/app/character_agent/mind/graph_projection.py`. `CharacterMindFrameBuilder` optionally accepts a provider; graph output augments memory-evidence card payload/source refs only.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, existing `backend/app/character_agent` runtime models, no new dependencies.

---

## Status Snapshot

Status: `implemented-and-focused-verified-optional-port`.

Current main contains `backend/app/character_agent/mind/graph_projection.py`
and `backend/tests/test_character_mind_graph_projection.py`. Graph-backed
memory remains an optional projection input and does not replace owned memory or
social-relationship truth.

## Scope Boundary

Included:

- Optional graph projection provider protocol.
- No-op provider for current default behavior.
- Knowledge/social/higher-order graph projection enrichment.
- Tests proving graph projection does not replace event memory or social memory ownership.

Excluded:

- Graph database implementation.
- Graph query planner.
- Graph-backed cognition decisions.
- Making relationship graph an external truth source.

## File Structure

- `backend/app/character_agent/mind/graph_projection.py`
  - Graph projection provider protocol and no-op implementation.
- `backend/app/character_agent/mind/projectors.py`
  - Accepts optional graph enrichment payloads for memory-evidence cards.
- `backend/app/character_agent/mind/frame_builder.py`
  - Accepts optional graph projection provider.
- `backend/app/character_agent/mind/__init__.py`
  - Public exports for graph projection provider types.
- `backend/tests/test_character_mind_graph_projection.py`
  - Tests optional graph projection behavior.

---

### Task 1: Add Optional Graph-Backed Memory Projection Port

**Files:**
- Create: `backend/app/character_agent/mind/graph_projection.py`
- Modify: `backend/app/character_agent/mind/projectors.py`
- Modify: `backend/app/character_agent/mind/frame_builder.py`
- Modify: `backend/app/character_agent/mind/__init__.py`
- Test: `backend/tests/test_character_mind_graph_projection.py`

- [ ] **Step 1: Write failing graph projection tests**

Create `backend/tests/test_character_mind_graph_projection.py`:

```python
from app.character_agent.mind.frame_builder import CharacterMindFrameBuilder
from app.character_agent.mind.graph_projection import (
    GraphMemoryProjectionProvider,
    NoopGraphMemoryProjectionProvider,
)


class FakeGraphProjectionProvider(GraphMemoryProjectionProvider):
    def project_memory_context(self, *, actor_id: str, memory_bundle: dict[str, object]) -> dict[str, object]:
        return {
            "knowledge_context": {
                "summary": "B is a medic",
                "source_refs": ["knowledge_graph:node:b_medic"],
            },
            "relationship_context": {
                "summary": "char_a trusts char_b through social memory evidence",
                "top_target": "char_b",
                "source_refs": ["social_graph:edge:char_a:char_b"],
            },
            "higher_order_belief": {
                "summary": "A suspects B is protecting a child",
                "source_refs": ["higher_order_graph:belief:b_motive"],
            },
        }


def test_noop_graph_provider_returns_empty_projection() -> None:
    assert NoopGraphMemoryProjectionProvider().project_memory_context(
        actor_id="char_a",
        memory_bundle={},
    ) == {}


def test_graph_projection_enriches_memory_cards_without_becoming_authority() -> None:
    frame = CharacterMindFrameBuilder(
        graph_projection_provider=FakeGraphProjectionProvider(),
    ).build_frame(
        actor_id="char_a",
        producer_ts=1,
        memory_bundle={
            "knowledge_memories": [{"memory_id": "knowledge:1", "proposition": "B is a medic"}],
            "social_memories": [{"memory_id": "social:1", "entity_id": "char_b"}],
            "higher_order_memories": [
                {
                    "memory_id": "higher:1",
                    "subject_actor_id": "char_b",
                    "proposition_key": "b_motive",
                    "meta_belief": "B may be protecting a child",
                }
            ],
        },
    )

    cards = {card.factor_type: card for card in frame.memory_evidence.cards}

    assert cards["knowledge_context"].payload["graph_projection"]["summary"] == "B is a medic"
    assert cards["relationship_context"].payload["graph_projection"]["top_target"] == "char_b"
    assert cards["higher_order_belief"].payload["graph_projection"]["summary"].startswith("A suspects")
    assert cards["relationship_context"].scope == "actor_private"
    assert "social_graph:edge:char_a:char_b" in cards["relationship_context"].source_refs
    assert "cognition_owner" not in cards["relationship_context"].payload
```

- [ ] **Step 2: Run graph projection tests and verify they fail**

Run: `pytest backend/tests/test_character_mind_graph_projection.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.character_agent.mind.graph_projection'` or `TypeError` for missing `graph_projection_provider`.

- [ ] **Step 3: Implement optional graph projection port**

Create `backend/app/character_agent/mind/graph_projection.py`:

```python
from __future__ import annotations

from typing import Protocol


class GraphMemoryProjectionProvider(Protocol):
    def project_memory_context(
        self,
        *,
        actor_id: str,
        memory_bundle: dict[str, object],
    ) -> dict[str, object]:
        ...


class NoopGraphMemoryProjectionProvider:
    def project_memory_context(
        self,
        *,
        actor_id: str,
        memory_bundle: dict[str, object],
    ) -> dict[str, object]:
        return {}
```

Modify `CharacterMindFrameBuilder.__init__`:

```python
    def __init__(
        self,
        *,
        graph_projection_provider: GraphMemoryProjectionProvider | None = None,
    ) -> None:
        self._graph_projection_provider = graph_projection_provider or NoopGraphMemoryProjectionProvider()
```

Import the graph provider protocol/no-op provider. In `build_frame`, compute:

```python
        graph_projection = self._graph_projection_provider.project_memory_context(
            actor_id=actor_id,
            memory_bundle=normalized_memory,
        )
```

Pass `graph_projection` into `_memory_evidence_layer`. Update `MemoryActivationProjector` and `RelationshipContextProjector` so graph payload is appended under `payload["graph_projection"]` for the matching cards and source refs are extended from `graph_projection[card_type]["source_refs"]`. Do not let graph projection replace event memory counts, social memory ownership, or actor-private scope.

Modify `backend/app/character_agent/mind/__init__.py` to export `GraphMemoryProjectionProvider` and `NoopGraphMemoryProjectionProvider`.

- [ ] **Step 4: Run graph projection and builder tests**

Run:

```bash
pytest backend/tests/test_character_mind_graph_projection.py backend/tests/test_character_mind_projectors.py backend/tests/test_character_mind_frame_builder.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add backend/app/character_agent/mind/__init__.py backend/app/character_agent/mind/frame_builder.py backend/app/character_agent/mind/graph_projection.py backend/app/character_agent/mind/projectors.py backend/tests/test_character_mind_graph_projection.py
git commit -m "Treat graph memory as optional projection evidence" -m "Graph-backed knowledge, relationship, and higher-order belief context can now enrich memory-evidence cards through an optional provider while event memory remains the evidence timeline and social relationships remain memory-owned." -m "Constraint: Graph projections feed CharacterMindFrame and never own cognition" -m "Rejected: Add a graph database in this task | the spec only requires projection compatibility" -m "Confidence: high" -m "Scope-risk: moderate" -m "Tested: pytest backend/tests/test_character_mind_graph_projection.py backend/tests/test_character_mind_projectors.py backend/tests/test_character_mind_frame_builder.py -v"
```
