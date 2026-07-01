# World Runtime Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define and land the canonical outer-world runtime model, world-facing taxonomy, and fact-fabric ownership rules for the new mainline.

**Architecture:** Build a small `world_runtime` package in the backend that becomes the explicit home for world entity references, world-state change envelopes, and fact-routing normalization. Reuse existing `AuthorityEvent`, `Phase0AuthorityEventAdapter`, `fact_router`, and `world_result` semantics where possible instead of inventing a parallel runtime. Keep the first pass additive and documentation-backed so the existing `Phase 0` smoke path keeps working.

**Tech Stack:** Python, Pydantic, FastAPI backend package layout, pytest, existing authority-event and world-result models.

**Progress Snapshot (`2026-06-30`):**
- Tasks `1-4` now have direct repository evidence.
- Current proof chain covers:
  - canonical world-runtime models
  - dedicated fact-family registry routing
  - authority-facing world-result delta projection
  - docs entrypoint exposure through the dedicated mainline tree

**Direct Evidence Audit (`2026-06-30`):**
- Required outcome `1. canonical outer-world runtime model surfaces`
  - Direct evidence:
    - `backend/tests/test_world_runtime_models.py`
    - `backend/app/world_runtime/models.py`
    - `backend/app/world_runtime/__init__.py`
- Required outcome `2. fact-family routing through a dedicated world-runtime seam`
  - Direct evidence:
    - `backend/tests/test_world_runtime_fact_registry.py`
    - `backend/app/world_runtime/fact_registry.py`
    - `backend/app/services/fact_router.py`
- Required outcome `3. authority-facing world-runtime projection helpers`
  - Direct evidence:
    - `backend/tests/test_world_runtime_projection.py`
    - `backend/app/world_runtime/projection.py`
    - `backend/app/main.py`
- Required outcome `4. world-runtime entrypoint truth is visible in repository docs`
  - Direct evidence:
    - `docs/INDEX.md`
    - `docs/ai-engineering-workflow.md`
    - `backend/tests/test_documentation_entrypoints.py::test_docs_index_mentions_world_runtime_mainline`
    - `python scripts/verification/harness.py --profile docs`

**Completion Audit Conclusion (`2026-06-30`):**
- Within the current additive first-pass scope of this plan, the four required outcomes now have direct repository evidence.
- Remaining non-goals for this plan:
  - no heavy live world scheduler here
  - no full websocket-native world-runtime envelope adoption across every route yet
  - no replacement of existing Phase 0 adapters; this lane establishes canonical surfaces first

---

### Task 1: Introduce canonical world-runtime model surfaces

**Files:**
- Create: `backend/app/world_runtime/models.py`
- Create: `backend/app/world_runtime/__init__.py`
- Test: `backend/tests/test_world_runtime_models.py`

- [x] **Step 1: Write the failing model tests**

```python
from app.world_runtime.models import WorldEntityRef, WorldStateDelta, WorldRuntimeEnvelope


def test_world_entity_ref_supports_actor_object_environment_and_zone() -> None:
    ref = WorldEntityRef(entity_type="actor", entity_id="char_a", zone_id="zone_focus")
    assert ref.entity_type == "actor"
    assert ref.zone_id == "zone_focus"


def test_world_state_delta_tracks_changed_fields() -> None:
    delta = WorldStateDelta(
        entity=WorldEntityRef(entity_type="environment", entity_id="env_lamp"),
        changed_fields={"light_level": "low", "visibility_level": "reduced"},
        producer_ts=9,
    )
    assert delta.changed_fields["light_level"] == "low"


def test_world_runtime_envelope_groups_refs_and_deltas() -> None:
    envelope = WorldRuntimeEnvelope(
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        facts=["visual_fact"],
        deltas=[],
    )
    assert envelope.scene_id == "scene_demo"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_world_runtime_models.py -v`
Expected: `FAIL` because `app.world_runtime` does not yet exist.

- [x] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class WorldEntityRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str
    entity_id: str
    zone_id: str | None = None


class WorldStateDelta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity: WorldEntityRef
    changed_fields: dict[str, object] = Field(default_factory=dict)
    producer_ts: int


class WorldRuntimeEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    room_id: str
    scene_id: str
    zone_id: str
    facts: list[str] = Field(default_factory=list)
    deltas: list[WorldStateDelta] = Field(default_factory=list)
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_world_runtime_models.py -v`
Expected: `PASS`

- [x] **Step 5: Commit**

```bash
git add backend/app/world_runtime backend/tests/test_world_runtime_models.py
git commit -m "Create canonical world-runtime model surfaces

Constraint: The new mainline needs explicit world-facing runtime objects rather than only Phase 0 adapters
Rejected: Reuse loose dict payloads directly as the long-term outer-runtime contract | too implicit for replay and taxonomy work
Confidence: high
Scope-risk: narrow
Directive: World-facing runtime additions must remain additive until docs-truth rewrite and harness gates are aligned
Tested: pytest backend/tests/test_world_runtime_models.py -v
Not-tested: websocket integration"
```

### Task 2: Normalize fact-family routing into a dedicated world-runtime seam

**Files:**
- Create: `backend/app/world_runtime/fact_registry.py`
- Modify: `backend/app/services/fact_router.py`
- Test: `backend/tests/test_world_runtime_fact_registry.py`

- [x] **Step 1: Write the failing routing tests**

```python
from app.world_runtime.fact_registry import WorldFactRegistry


def test_world_fact_registry_classifies_visual_and_auditory_families() -> None:
    registry = WorldFactRegistry()
    assert registry.route_for_family("visual_fact") == "visual"
    assert registry.route_for_family("auditory_fact") == "auditory"


def test_world_fact_registry_marks_unknown_family_explicitly() -> None:
    registry = WorldFactRegistry()
    assert registry.route_for_family("mystery_family") == "unknown"
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_world_runtime_fact_registry.py -v`
Expected: `FAIL` because the registry file does not yet exist.

- [x] **Step 3: Write minimal implementation and connect the router**

```python
class WorldFactRegistry:
    _ROUTES = {
        "visual_fact": "visual",
        "auditory_fact": "auditory",
        "spatial_access_fact": "spatial_access",
        "raw_fact": "raw",
        "world_result": "world_result",
    }

    def route_for_family(self, family: str) -> str:
        return self._ROUTES.get(family, "unknown")
```

```python
from app.world_runtime.fact_registry import WorldFactRegistry

_FACT_REGISTRY = WorldFactRegistry()


def route_raw_fact_event(...):
    family = getattr(event, "fact_family", "")
    route_kind = _FACT_REGISTRY.route_for_family(family)
    # keep existing behavior, but drive branch selection through route_kind
```

- [x] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_world_runtime_fact_registry.py -v`
Expected: `PASS`

- [x] **Step 5: Commit**

```bash
git add backend/app/world_runtime/fact_registry.py backend/app/services/fact_router.py backend/tests/test_world_runtime_fact_registry.py
git commit -m "Normalize world fact-family routing through explicit registry

Constraint: The outer runtime needs one taxonomy owner for world fact families
Rejected: Keep routing rules duplicated across handlers | drift risk grows as new world-runtime families are added
Confidence: high
Scope-risk: narrow
Directive: New fact families must be registered here before they become mainline truth
Tested: pytest backend/tests/test_world_runtime_fact_registry.py -v
Not-tested: full handler integration"
```

### Task 3: Introduce world-runtime projection helpers for authority-facing writeback

**Files:**
- Create: `backend/app/world_runtime/projection.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_world_runtime_projection.py`

- [x] **Step 1: Write the failing projection tests**

```python
from app.world_runtime.models import WorldEntityRef, WorldStateDelta
from app.world_runtime.projection import project_world_result_delta


def test_project_world_result_delta_maps_environment_result_to_delta() -> None:
    payload = {
        "result_type": "environment_state_result",
        "target_environment_id": "env_lamp",
        "producer_ts": 10,
        "current_state": "alerted",
    }
    delta = project_world_result_delta(payload)
    assert delta.entity == WorldEntityRef(entity_type="environment", entity_id="env_lamp")
    assert delta.changed_fields["current_state"] == "alerted"


def test_project_world_result_delta_returns_none_when_no_entity_ref_exists() -> None:
    assert project_world_result_delta({"result_type": "noop"}) is None
```

- [x] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_world_runtime_projection.py -v`
Expected: `FAIL` because the projection helper does not yet exist.

- [x] **Step 3: Write minimal implementation**

```python
from __future__ import annotations

from app.world_runtime.models import WorldEntityRef, WorldStateDelta


def project_world_result_delta(payload: dict[str, object]) -> WorldStateDelta | None:
    if str(payload.get("target_environment_id", "") or ""):
        return WorldStateDelta(
            entity=WorldEntityRef(
                entity_type="environment",
                entity_id=str(payload["target_environment_id"]),
            ),
            changed_fields={"current_state": payload.get("current_state", "")},
            producer_ts=int(payload.get("producer_ts", 0) or 0),
        )
    if str(payload.get("target_object_id", "") or ""):
        return WorldStateDelta(
            entity=WorldEntityRef(
                entity_type="object",
                entity_id=str(payload["target_object_id"]),
            ),
            changed_fields={"current_state": payload.get("current_state", "")},
            producer_ts=int(payload.get("producer_ts", 0) or 0),
        )
    return None
```

- [x] **Step 4: Thread the helper into outbound world-result handling**

```python
from app.world_runtime.projection import project_world_result_delta


def _as_world_result_envelope(payload: dict[str, object]) -> dict[str, object]:
    delta = project_world_result_delta(payload)
    envelope = {
        ...
        "payload": payload,
    }
    if delta is not None:
        envelope["payload"]["world_runtime_delta"] = delta.model_dump()
    return envelope
```

- [x] **Step 5: Run test to verify it passes**

Run: `pytest backend/tests/test_world_runtime_projection.py -v`
Expected: `PASS`

- [x] **Step 6: Commit**

```bash
git add backend/app/world_runtime/projection.py backend/app/main.py backend/tests/test_world_runtime_projection.py
git commit -m "Project world results into canonical world-runtime deltas

Constraint: The new outer runtime must derive structured deltas from existing authority outputs rather than rebuild world state ad hoc
Rejected: Leave world-result payloads as the only writeback shape | too coupled to per-result handler details
Confidence: medium
Scope-risk: moderate
Directive: Authority-facing result families should progressively expose canonical world-runtime deltas
Tested: pytest backend/tests/test_world_runtime_projection.py -v
Not-tested: all world result families"
```

### Task 4: Add documentation and harness-visible world-runtime entrypoint truth

**Files:**
- Modify: `docs/INDEX.md`
- Modify: `docs/ai-engineering-workflow.md`
- Test: `python scripts/verification/harness.py --profile docs`

- [x] **Step 1: Write a doc regression test**

```python
from pathlib import Path


def test_docs_index_mentions_world_runtime_mainline() -> None:
    text = Path("docs/INDEX.md").read_text(encoding="utf-8")
    assert "world-character-siming-authority-mainline" in text
```

- [x] **Step 2: Run test to verify failure if not already present**

Run: `pytest backend/tests/test_documentation_entrypoints.py::test_docs_index_mentions_world_runtime_mainline -v`
Expected: `FAIL` if the entrypoint is missing.

- [x] **Step 3: Update the docs entrypoints**

```markdown
## Active Design And Plans

- `docs/superpowers/specs/world-character-siming-authority-mainline/README.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/2026-06-29-world-character-siming-authority-mainline-master-design.md`
- `docs/superpowers/plans/world-character-siming-authority-mainline/README.md`
```

- [x] **Step 4: Run docs verification**

Run: `python scripts/verification/harness.py --profile docs`
Expected: `PASS`

- [x] **Step 5: Commit**

```bash
git add docs/INDEX.md docs/ai-engineering-workflow.md backend/tests/test_documentation_entrypoints.py
git commit -m "Expose world-runtime foundation as a repository entrypoint

Constraint: The new outer-runtime layer must be visible from top-level documentation before implementation fans out
Rejected: Leave the runtime foundation implicit in lower-level specs only | too hard to discover and review
Confidence: medium
Scope-risk: narrow
Directive: Entry-point docs should point to the dedicated mainline tree, not a one-off flat file
Tested: python scripts/verification/harness.py --profile docs
Not-tested: runtime behavior"
```
