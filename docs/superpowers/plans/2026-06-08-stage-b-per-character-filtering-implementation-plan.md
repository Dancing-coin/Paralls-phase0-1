# Stage B Remaining Implementation Plan: Per-Character Filtering And Character-Agent L1 Consumption

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the remaining Stage B work by making the Per-Character filter actor-context-aware and by introducing at least one real character-facing path that consumes `CharacterPerceivedEvent` instead of only shared raw/candidate state.

**Architecture:** Build on the already-shipped Stage A slice. Keep `CandidatePerceptEvent`, `compile_candidate_percepts(...)`, `CharacterPerceivedEvent`, and the first filter boundary intact, but deepen the filter with actor-specific context and add one narrow downstream bridge where character-facing logic consumes filtered perceived events. This plan does not redo raw fact emission, routing, or the already-completed system-L1 work.

**Tech Stack:** Python 3.13, FastAPI backend, Pydantic models, pytest, existing candidate-percept services, current Phase 0 and Phase1-slice verification harnesses.

---

## File Map

### New or expanded backend models

- Optional Create: `backend/app/models/perception_context.py`
  - If a dedicated actor perception context object is cleaner than raw dicts.

### Backend services

- Modify: `backend/app/services/per_character_percept_filter.py`
  - Upgrade from target-id-only filtering to actor-context-aware filtering.
- Optional Create: `backend/app/services/character_perceived_input_service.py`
  - A narrow adapter that converts `CharacterPerceivedEvent` into a character-facing input path.

### Existing runtime / character integration

- Modify: `backend/app/main.py`
  - Feed filter context and route at least one narrow downstream consumer path.
- Optional Modify: `backend/app/services/character_runtime_state_service.py`
  - Only if the perceived-event bridge needs a minimal state application path.
- Optional Modify: `backend/app/services/character_service.py`
  - Only if the first consumer path is best anchored there.
- Optional Modify: `backend/app/services/conversation_relation_service.py`
  - Only if candidate-to-private-perception bridging belongs there.

### Tests

- Modify: `backend/tests/test_per_character_percept_filter.py`
- Optional Create: `backend/tests/test_character_perceived_input_service.py`
- Modify: `backend/tests/test_visual_fact_pipeline.py`
- Optional Modify: `backend/tests/test_character_runtime_state_service.py`

### Optional docs sync

- Modify: `docs/superpowers/specs/2026-06-08-stage-b-per-character-filtering-design.md` only if implementation forces clarified wording.

---

### Task 1: Add Actor-Context-Aware Filter Inputs

**Files:**
- Modify: `backend/tests/test_per_character_percept_filter.py`
- Optional Create: `backend/app/models/perception_context.py`
- Modify: `backend/app/services/per_character_percept_filter.py`

- [ ] **Step 1: Write failing actor-context tests**

Extend `backend/tests/test_per_character_percept_filter.py` with:

```python
from app.models.candidate_percept import CandidatePerceptEvent
from app.services.per_character_percept_filter import filter_candidate_for_actor


def test_filter_drops_visual_candidate_when_actor_is_not_facing_target() -> None:
    candidate = CandidatePerceptEvent(
        percept_channel="visual",
        source_fact_family="visual_fact",
        source_fact_type="fixed_gaze_on_target",
        producer_ts=500,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source_actor_id="char_c",
        target_actor_id="char_a",
        audience_scope="candidate",
        observability={"visual": True},
        causation_id="vf:500",
        correlation_id="vf:500",
    )

    perceived = filter_candidate_for_actor(
        candidate,
        actor_id="char_a",
        context={
            "is_facing_target": False,
            "distance_m": 2.0,
            "privacy_band": "local",
            "current_zone_id": "zone_focus",
        },
    )

    assert perceived is None


def test_filter_keeps_visual_candidate_when_actor_is_facing_target() -> None:
    candidate = CandidatePerceptEvent(
        percept_channel="visual",
        source_fact_family="visual_fact",
        source_fact_type="fixed_gaze_on_target",
        producer_ts=501,
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        source_actor_id="char_c",
        target_actor_id="char_a",
        audience_scope="candidate",
        observability={"visual": True},
        causation_id="vf:501",
        correlation_id="vf:501",
    )

    perceived = filter_candidate_for_actor(
        candidate,
        actor_id="char_a",
        context={
            "is_facing_target": True,
            "distance_m": 2.0,
            "privacy_band": "local",
            "current_zone_id": "zone_focus",
        },
    )

    assert perceived is not None
    assert perceived.actor_id == "char_a"
```

- [ ] **Step 2: Run the filter tests to verify failure**

Run:

```bash
python -m pytest -v tests/test_per_character_percept_filter.py
```

Expected:

- FAIL because `filter_candidate_for_actor(...)` does not yet accept or use actor context.

- [ ] **Step 3: Add the minimal filter context support**

If you want a dedicated model, create `backend/app/models/perception_context.py`:

```python
from pydantic import BaseModel


class PerActorPerceptionContext(BaseModel):
    current_zone_id: str = ""
    privacy_band: str = "public"
    distance_m: float | None = None
    is_facing_target: bool = True
    current_focus_target: str = ""
```

If you do not create the model, use a typed dict-like argument shape directly.

Update `backend/app/services/per_character_percept_filter.py` to accept `context` and apply the first meaningful rule:

```python
from app.models.candidate_percept import CandidatePerceptEvent
from app.models.character_perceived import CharacterPerceivedEvent


def filter_candidate_for_actor(
    candidate: CandidatePerceptEvent,
    *,
    actor_id: str,
    context: dict[str, object] | None = None,
) -> CharacterPerceivedEvent | None:
    if candidate.target_actor_id != "" and candidate.target_actor_id != actor_id:
        return None

    ctx = context or {}
    is_facing_target = bool(ctx.get("is_facing_target", True))

    if candidate.percept_channel == "visual" and not is_facing_target:
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
git add backend/app/services/per_character_percept_filter.py backend/tests/test_per_character_percept_filter.py backend/app/models/perception_context.py
git commit -m "feat: add actor-context-aware per-character filtering"
```

If you skipped the dedicated model file, omit it from `git add`.

### Task 2: Introduce One Real Character-Facing Consumer Path

**Files:**
- Optional Create: `backend/app/services/character_perceived_input_service.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_visual_fact_pipeline.py`

- [ ] **Step 1: Write a failing consumer-path test**

Add to `backend/tests/test_visual_fact_pipeline.py`:

```python
def test_raw_visual_fact_compiles_and_filters_before_authority_route_returns() -> None:
    from app.models.visual_fact import VisualFactEvent

    event = VisualFactEvent(
        actor_id="char_c",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        producer_ts=600,
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

    assert messages[0]["payload"]["route"] == "authority_visual_fact"
```

This is still a guardrail, but the implementation below should make the filtered path real enough that the hook is no longer a no-op.

- [ ] **Step 2: Run the visual pipeline tests**

Run:

```bash
python -m pytest -v tests/test_visual_fact_pipeline.py
```

Expected:

- PASS initially.

- [ ] **Step 3: Add a minimal perceived-input adapter**

If needed, create `backend/app/services/character_perceived_input_service.py`:

```python
from app.models.character_perceived import CharacterPerceivedEvent


def apply_character_perceived_event(event: CharacterPerceivedEvent) -> dict[str, object]:
    return {
        "actor_id": event.actor_id,
        "percept_channel": event.percept_channel,
        "perceived_summary": event.perceived_summary,
        "source_candidate_event_id": event.source_candidate_event_id,
    }
```

Then update `backend/app/main.py` so the compiler/filter path is no longer a discarded side effect:

```python
compiled_candidates = compile_candidate_percepts(event)
filtered_perceived_events = []
for candidate in compiled_candidates:
    if event.source.actor_id:
        perceived = filter_candidate_for_actor(
            candidate,
            actor_id=event.source.actor_id,
            context={"is_facing_target": True},
        )
        if perceived is not None:
            filtered_perceived_events.append(perceived)
            _ = apply_character_perceived_event(perceived)
```

The point here is not to rewrite all character behavior.

The point is to ensure:

- a character-facing path now consumes `CharacterPerceivedEvent`

instead of only constructing the object and discarding it.

- [ ] **Step 4: Re-run the focused integration tests**

Run:

```bash
python -m pytest -v tests/test_candidate_percept_service.py tests/test_per_character_percept_filter.py tests/test_visual_fact_pipeline.py
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_visual_fact_pipeline.py backend/app/services/character_perceived_input_service.py
git commit -m "feat: route first character-facing path through perceived events"
```

If you did not need the adapter file, omit it from `git add`.

### Task 3: Verify Stage B Remaining Slice And Document What Still Isn’t Done

**Files:**
- Modify: `docs/superpowers/specs/2026-06-08-stage-b-per-character-filtering-design.md` only if needed
- Modify: `docs/superpowers/plans/2026-06-08-stage-b-per-character-filtering-implementation-plan.md` by checking boxes during execution

- [ ] **Step 1: Run focused Stage B verification**

Run:

```bash
python -m pytest -v tests/test_candidate_percept_service.py tests/test_per_character_percept_filter.py tests/test_visual_fact_pipeline.py
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

- [ ] **Step 3: Re-run Godot/runtime verification**

Run:

```bash
python scripts/verification/verify_phase1_slice.py
python scripts/verification/verify_phase0.py
python scripts/verification/verify_l1_runtime_edges.py
```

Expected:

- PASS

- [ ] **Step 4: Static scan for the new Stage B seams**

Run:

```bash
rg -n "CharacterPerceivedEvent|filter_candidate_for_actor|apply_character_perceived_event|is_facing_target" backend
```

Expected:

- Per-Character filtering is no longer a target-id-only placeholder
- at least one character-facing path consumes perceived events

- [ ] **Step 5: Commit final doc sync if needed**

```bash
git add docs/superpowers/specs/2026-06-08-stage-b-per-character-filtering-design.md docs/superpowers/plans/2026-06-08-stage-b-per-character-filtering-implementation-plan.md
git commit -m "docs: sync stage-b per-character filtering spec and plan"
```

- [ ] **Step 6: Prepare closeout summary**

Report clearly:

- what Stage B remaining work is now closed
- what still remains outside this plan
- whether the repo now has:
  - real actor-context filtering
  - at least one character-facing perceived-event consumer path
  - but still lacks the full character-agent `L1-L4` downstream rebuild
