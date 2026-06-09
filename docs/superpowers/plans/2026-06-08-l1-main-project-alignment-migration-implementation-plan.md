# System-L1 To Character-Perception Alignment Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve the current demo repo from a working system-level `L1` raw-fact skeleton into a migration-grade perception chain where system-level `L1` facts feed a formal system-level `L2` candidate percept compiler, then a system-level `L2` `Per-Character` filter, and finally a character-agent `L1` perceived-event input boundary.

**Architecture:** Keep the current `raw_fact_event` fact-production path stable, add a formal `CandidatePerceptEvent` model and compilation service behind it, then add a first `PerCharacterPerceptFilter` and `CharacterPerceivedEvent` model so character-facing consumption can stop depending on shared raw/candidate state. The plan intentionally scopes itself to the currently implemented fact families (`visual_fact` and `spatial_access_fact`) instead of trying to complete all sensory families at once.

**Tech Stack:** Godot 4.x GDScript, Python 3.13, FastAPI backend, Pydantic models, pytest, existing L1 runtime probes, current Phase 0 and Phase1-slice verification harnesses.

---

## Status Snapshot

- Date: `2026-06-10`
- Plan status: executed and verified for the repository-local target
- Current code truth:
  - `CandidatePerceptEvent` and `CharacterPerceivedEvent` models exist
  - candidate compilation for the repo-local fact families exists
  - per-character filtering exists
  - role-private perceived-event storage and self-body perceived-event storage both exist
- Verification evidence:
  - `backend/tests/test_candidate_percept_service.py::test_candidate_percept_event_shape`
  - `backend/tests/test_candidate_percept_service.py::test_compile_visual_fact_to_candidate_percept`
  - `backend/tests/test_candidate_percept_service.py::test_compile_spatial_access_fact_to_candidate_percept`
  - `backend/tests/test_per_character_percept_filter.py::test_character_perceived_event_shape`
  - `backend/tests/test_per_character_percept_filter.py::test_filter_candidate_for_matching_actor_returns_character_perceived_event`
  - `backend/tests/test_visual_fact_pipeline.py::test_raw_visual_fact_updates_character_perceived_input_path`

## File Map

### New backend perception-chain models

- Create: `backend/app/models/candidate_percept.py`
  - Defines the system-level `L2` candidate percept event object.
- Create: `backend/app/models/character_perceived.py`
  - Defines the role-private perceived event consumed by character-agent `L1`.

### New backend services

- Create: `backend/app/services/candidate_percept_service.py`
  - Compiles `RawFactEvent` into `CandidatePerceptEvent`.
- Create: `backend/app/services/per_character_percept_filter.py`
  - Filters candidate percepts into role-private perceived events.

### Runtime wiring

- Modify: `backend/app/main.py`
  - Insert candidate compilation and per-character filtering into the existing `raw_fact_event` path.
- Modify: `backend/app/debug_narration.py`
  - Add readable debug summaries for candidate percepts and role-private perceived events where necessary.

### Existing backend fact handling

- Modify: `backend/app/services/fact_router.py`
  - Keep router thin; do not convert it into the compiler or filter layer.
- Optional Modify: `backend/app/services/conversation_relation_service.py`
  - Only if some existing candidate generation needs to consume new candidate-percept objects cleanly.

### Tests

- Create: `backend/tests/test_candidate_percept_service.py`
- Create: `backend/tests/test_per_character_percept_filter.py`
- Modify: `backend/tests/test_visual_fact_pipeline.py`
- Modify: `backend/tests/test_raw_fact_router.py`
- Optional Modify: `backend/tests/test_debug_narration.py`

### Optional docs sync

- Modify: `docs/superpowers/specs/2026-06-08-l1-main-project-alignment-migration-design.md` only if implementation forces clarified wording.

---

### Task 1: Define Candidate Percept And Character-Perceived Event Models

**Files:**
- Create: `backend/app/models/candidate_percept.py`
- Create: `backend/app/models/character_perceived.py`
- Create: `backend/tests/test_candidate_percept_service.py`
- Create: `backend/tests/test_per_character_percept_filter.py`

- [ ] **Step 1: Write failing model-shape tests**

Create `backend/tests/test_candidate_percept_service.py` with:

```python
from app.models.candidate_percept import CandidatePerceptEvent


def test_candidate_percept_event_shape() -> None:
    event = CandidatePerceptEvent(
        event_type="candidate_percept_event",
        percept_channel="visual",
        source_fact_family="visual_fact",
        source_fact_type="fixed_gaze_on_target",
        producer_ts=100,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source_actor_id="char_c",
        target_actor_id="char_a",
        audience_scope="candidate",
        observability={"visual": True},
        causation_id="vf:100",
        correlation_id="vf:100",
    )

    payload = event.model_dump()

    assert payload["event_type"] == "candidate_percept_event"
    assert payload["percept_channel"] == "visual"
    assert payload["source_fact_family"] == "visual_fact"
    assert payload["target_actor_id"] == "char_a"
```

Create `backend/tests/test_per_character_percept_filter.py` with:

```python
from app.models.candidate_percept import CandidatePerceptEvent
from app.models.character_perceived import CharacterPerceivedEvent


def test_character_perceived_event_shape() -> None:
    event = CharacterPerceivedEvent(
        event_type="character_perceived_event",
        actor_id="char_a",
        percept_channel="visual",
        producer_ts=101,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        perceived_summary="char_c is looking at char_a",
        source_candidate_event_id="cand:101",
    )

    payload = event.model_dump()

    assert payload["event_type"] == "character_perceived_event"
    assert payload["actor_id"] == "char_a"
    assert payload["perceived_summary"] == "char_c is looking at char_a"
```

- [ ] **Step 2: Run the tests to verify failure**

Run:

```bash
python -m pytest -v tests/test_candidate_percept_service.py tests/test_per_character_percept_filter.py
```

Expected:

- FAIL with import errors because the new model modules do not exist yet.

- [ ] **Step 3: Create the minimal Pydantic models**

Create `backend/app/models/candidate_percept.py`:

```python
from pydantic import BaseModel, Field


class CandidatePerceptEvent(BaseModel):
    event_type: str = "candidate_percept_event"
    percept_channel: str
    source_fact_family: str
    source_fact_type: str
    producer_ts: int
    room_id: str
    scene_id: str
    zone_id: str
    source_actor_id: str = ""
    source_object_id: str = ""
    source_environment_id: str = ""
    target_actor_id: str = ""
    target_object_id: str = ""
    target_environment_id: str = ""
    audience_scope: str = "candidate"
    observability: dict[str, object] = Field(default_factory=dict)
    causation_id: str = ""
    correlation_id: str = ""
```

Create `backend/app/models/character_perceived.py`:

```python
from pydantic import BaseModel


class CharacterPerceivedEvent(BaseModel):
    event_type: str = "character_perceived_event"
    actor_id: str
    percept_channel: str
    producer_ts: int
    room_id: str
    scene_id: str
    zone_id: str
    perceived_summary: str
    source_candidate_event_id: str
```

- [ ] **Step 4: Re-run the model tests**

Run:

```bash
python -m pytest -v tests/test_candidate_percept_service.py tests/test_per_character_percept_filter.py
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/candidate_percept.py backend/app/models/character_perceived.py backend/tests/test_candidate_percept_service.py backend/tests/test_per_character_percept_filter.py
git commit -m "feat: define candidate and character-perceived event models"
```

### Task 2: Add A Formal Candidate Percept Compilation Layer

**Files:**
- Create: `backend/app/services/candidate_percept_service.py`
- Create: `backend/tests/test_candidate_percept_service.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add failing compiler tests**

Extend `backend/tests/test_candidate_percept_service.py`:

```python
from app.models.raw_fact import RawFactEvent
from app.services.candidate_percept_service import compile_candidate_percepts


def test_compile_visual_fact_to_candidate_percept() -> None:
    event = RawFactEvent(
        fact_family="visual_fact",
        fact_type="fixed_gaze_on_target",
        relation_type="actor_looks_at_actor",
        producer_ts=200,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
        targets={"actor_id": "char_a"},
    )

    compiled = compile_candidate_percepts(event)

    assert len(compiled) == 1
    assert compiled[0].percept_channel == "visual"
    assert compiled[0].source_fact_family == "visual_fact"
    assert compiled[0].target_actor_id == "char_a"


def test_compile_spatial_access_fact_to_candidate_percept() -> None:
    event = RawFactEvent(
        fact_family="spatial_access_fact",
        fact_type="actor_approached_actor",
        relation_type="actor_approached_actor",
        producer_ts=201,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
        targets={"actor_id": "char_b"},
        world={"distance_m": 2.4},
        effect_kind="replace",
        subject_key="nearby_actor_refs",
    )

    compiled = compile_candidate_percepts(event)

    assert len(compiled) == 1
    assert compiled[0].percept_channel == "spatial"
    assert compiled[0].source_fact_family == "spatial_access_fact"
    assert compiled[0].target_actor_id == "char_b"
```

- [ ] **Step 2: Run the compiler tests to verify failure**

Run:

```bash
python -m pytest -v tests/test_candidate_percept_service.py
```

Expected:

- FAIL with import errors because the service does not exist yet.

- [ ] **Step 3: Implement the minimal compiler**

Create `backend/app/services/candidate_percept_service.py`:

```python
from app.models.candidate_percept import CandidatePerceptEvent
from app.models.raw_fact import RawFactEvent


def compile_candidate_percepts(event: RawFactEvent) -> list[CandidatePerceptEvent]:
    if event.fact_family == "visual_fact":
        return [
            CandidatePerceptEvent(
                percept_channel="visual",
                source_fact_family=event.fact_family,
                source_fact_type=event.fact_type,
                producer_ts=event.producer_ts,
                room_id=event.room_id,
                scene_id=event.scene_id,
                zone_id=event.zone_id,
                source_actor_id=event.source.actor_id,
                source_object_id=event.source.object_id,
                source_environment_id=event.source.environment_id,
                target_actor_id=event.targets.actor_id,
                target_object_id=event.targets.object_id,
                target_environment_id=event.targets.environment_id,
                audience_scope="candidate",
                observability=event.observability.model_dump(),
                causation_id=event.causation_id,
                correlation_id=event.correlation_id,
            )
        ]

    if event.fact_family == "spatial_access_fact":
        return [
            CandidatePerceptEvent(
                percept_channel="spatial",
                source_fact_family=event.fact_family,
                source_fact_type=event.fact_type,
                producer_ts=event.producer_ts,
                room_id=event.room_id,
                scene_id=event.scene_id,
                zone_id=event.zone_id,
                source_actor_id=event.source.actor_id,
                source_object_id=event.source.object_id,
                source_environment_id=event.source.environment_id,
                target_actor_id=event.targets.actor_id,
                target_object_id=event.targets.object_id,
                target_environment_id=event.targets.environment_id,
                audience_scope="candidate",
                observability=event.observability.model_dump(),
                causation_id=event.causation_id,
                correlation_id=event.correlation_id,
            )
        ]

    return []
```

- [ ] **Step 4: Re-run the compiler tests**

Run:

```bash
python -m pytest -v tests/test_candidate_percept_service.py
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/candidate_percept_service.py backend/tests/test_candidate_percept_service.py
git commit -m "feat: compile raw facts into candidate percept events"
```

### Task 3: Add A First Per-Character Filter

**Files:**
- Create: `backend/app/services/per_character_percept_filter.py`
- Modify: `backend/tests/test_per_character_percept_filter.py`

- [ ] **Step 1: Add failing filter tests**

Extend `backend/tests/test_per_character_percept_filter.py`:

```python
from app.models.candidate_percept import CandidatePerceptEvent
from app.services.per_character_percept_filter import filter_candidate_for_actor


def test_filter_candidate_for_matching_actor_returns_character_perceived_event() -> None:
    candidate = CandidatePerceptEvent(
        percept_channel="visual",
        source_fact_family="visual_fact",
        source_fact_type="fixed_gaze_on_target",
        producer_ts=300,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source_actor_id="char_c",
        target_actor_id="char_a",
        audience_scope="candidate",
        observability={"visual": True},
        causation_id="vf:300",
        correlation_id="vf:300",
    )

    perceived = filter_candidate_for_actor(candidate, actor_id="char_a")

    assert perceived is not None
    assert perceived.actor_id == "char_a"
    assert perceived.percept_channel == "visual"


def test_filter_candidate_for_non_matching_actor_returns_none() -> None:
    candidate = CandidatePerceptEvent(
        percept_channel="visual",
        source_fact_family="visual_fact",
        source_fact_type="fixed_gaze_on_target",
        producer_ts=301,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source_actor_id="char_c",
        target_actor_id="char_a",
        audience_scope="candidate",
        observability={"visual": True},
        causation_id="vf:301",
        correlation_id="vf:301",
    )

    perceived = filter_candidate_for_actor(candidate, actor_id="char_b")

    assert perceived is None
```

- [ ] **Step 2: Run the filter tests to verify failure**

Run:

```bash
python -m pytest -v tests/test_per_character_percept_filter.py
```

Expected:

- FAIL with import error because the filter service does not exist yet.

- [ ] **Step 3: Implement the minimal per-character filter**

Create `backend/app/services/per_character_percept_filter.py`:

```python
from app.models.candidate_percept import CandidatePerceptEvent
from app.models.character_perceived import CharacterPerceivedEvent


def filter_candidate_for_actor(candidate: CandidatePerceptEvent, *, actor_id: str) -> CharacterPerceivedEvent | None:
    if candidate.target_actor_id != "" and candidate.target_actor_id != actor_id:
        return None

    return CharacterPerceivedEvent(
        actor_id=actor_id,
        percept_channel=candidate.percept_channel,
        producer_ts=candidate.producer_ts,
        room_id=candidate.room_id,
        scene_id=candidate.scene_id,
        zone_id=candidate.zone_id,
        perceived_summary=f"{candidate.source_fact_family}/{candidate.source_fact_type}",
        source_candidate_event_id=f"{candidate.source_fact_family}:{candidate.producer_ts}:{actor_id}",
    )
```

- [ ] **Step 4: Re-run the filter tests**

Run:

```bash
python -m pytest -v tests/test_per_character_percept_filter.py
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/per_character_percept_filter.py backend/tests/test_per_character_percept_filter.py
git commit -m "feat: add first per-character candidate percept filter"
```

### Task 4: Wire Candidate Compilation And Filtering Into The Existing Runtime Path

**Files:**
- Modify: `backend/app/main.py`
- Optional Modify: `backend/app/debug_narration.py`
- Optional Modify: `backend/tests/test_visual_fact_pipeline.py`

- [ ] **Step 1: Add failing integration tests for the new mid-layer objects**

Add focused coverage to `backend/tests/test_visual_fact_pipeline.py`:

```python
from app.main import _handle_envelope, reset_runtime_state
from app.ws_protocol import Envelope


def test_handle_envelope_raw_visual_fact_still_routes_after_candidate_compilation_integration() -> None:
    from app.models.visual_fact import VisualFactEvent

    event = VisualFactEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=400,
        fact_type="fixed_gaze_on_target",
        relation_type="actor_looks_at_actor",
        target_actor_id="char_a",
    )

    reset_runtime_state()
    messages = _handle_envelope(
        Envelope(
            message_type="raw_fact_event",
            payload=event.model_dump(),
        )
    )

    assert messages[0]["message_type"] == "ack"
    assert messages[0]["payload"]["route"] == "authority_visual_fact"
```

This guards the existing fact path while Stage A wiring is introduced.

- [ ] **Step 2: Run the integration test**

Run:

```bash
python -m pytest -v tests/test_visual_fact_pipeline.py
```

Expected:

- PASS initially.
- This is a guardrail test, not a red test.

- [ ] **Step 3: Wire candidate compilation and filtering into `main.py` without breaking existing outputs**

Update `backend/app/main.py`:

- import the new compiler and filter services
- for `raw_fact_event`, compile candidate percepts after parsing the raw event
- for each compiled candidate, run a minimal filter for the source actor
- publish debug events if helpful
- do **not** replace the existing routed messages yet

The key rule for this stage:

- the new layers are introduced in parallel
- the old authority path must stay intact

Suggested insertion pattern:

```python
compiled_candidates = compile_candidate_percepts(event)
for candidate in compiled_candidates:
    if event.source.actor_id:
        _ = filter_candidate_for_actor(candidate, actor_id=event.source.actor_id)
```

Keep this first wiring intentionally minimal.

- [ ] **Step 4: Re-run the integration suite**

Run:

```bash
python -m pytest -v tests/test_candidate_percept_service.py tests/test_per_character_percept_filter.py tests/test_visual_fact_pipeline.py
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_visual_fact_pipeline.py
git commit -m "feat: wire candidate percept compilation behind raw fact ingress"
```

### Task 5: Full Verification And Migration Readiness Proof

**Files:**
- Modify: `docs/superpowers/specs/2026-06-08-l1-main-project-alignment-migration-design.md` only if needed
- Modify: `docs/superpowers/plans/2026-06-08-l1-main-project-alignment-migration-implementation-plan.md` by checking boxes during execution

- [ ] **Step 1: Run focused verification**

Run:

```bash
python -m pytest -v tests/test_candidate_percept_service.py tests/test_per_character_percept_filter.py tests/test_visual_fact_pipeline.py tests/test_raw_fact_router.py
```

Expected:

- PASS

- [ ] **Step 2: Run the full backend suite**

Run:

```bash
python -m pytest -v
```

Expected:

- PASS

- [ ] **Step 3: Re-run existing Godot/runtime verification**

Run:

```bash
python scripts/verification/verify_phase1_slice.py
python scripts/verification/verify_phase0.py
python scripts/verification/verify_l1_runtime_edges.py
```

Expected:

- PASS

- [ ] **Step 4: Run a static scan for the new architecture seams**

Run:

```bash
rg -n "CandidatePerceptEvent|CharacterPerceivedEvent|compile_candidate_percepts|filter_candidate_for_actor" backend
```

Expected:

- new model and service names appear in the expected files
- the repo now has explicit system-level `L2` perception-chain objects

- [ ] **Step 5: Commit final polish if needed**

```bash
git add docs/superpowers/specs/2026-06-08-l1-main-project-alignment-migration-design.md docs/superpowers/plans/2026-06-08-l1-main-project-alignment-migration-implementation-plan.md
git commit -m "docs: sync system-l1 migration spec and implementation plan"
```

- [ ] **Step 6: Prepare closeout summary**

Report:

- which part of the main-project gap is now closed
- what still remains for later stages
- whether character-agent `L1` is now consuming role-private events yet or only has the new boundary introduced
