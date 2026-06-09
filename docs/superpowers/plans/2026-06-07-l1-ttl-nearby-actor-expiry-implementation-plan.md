# L1 TTL Nearby Actor Expiry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `ttl_ms` a real L1 capability by applying it to `nearby_actor_refs` in the `spatial_access_fact` path, so stale proximity evidence can self-clear even if an explicit leave fact is missed.

**Architecture:** Keep explicit `replace` and `clear` semantics as the primary path, and add a handler-local expiry fallback for `nearby_actor_refs` only. Godot emits `ttl_ms` on approach facts, the backend spatial-access handler tracks expiry per actor/subject, and expiry is enforced opportunistically during later events for the same actor.

**Tech Stack:** Godot 4.x GDScript, Python 3.13, FastAPI backend, Pydantic models, pytest, existing L1 raw fact contract, current Phase 0 runtime verification harnesses.

---

## Status Snapshot

- Date: `2026-06-10`
- Plan status: executed and verified for the repository-local target
- Current code truth:
  - `ttl_ms` is part of the shared raw-fact contract
  - `SpatialAccessFactEmitter` emits TTL-backed proximity evidence
  - backend spatial-access handling prunes expired `nearby_actor_refs`
  - fresh `replace` events reset the expiry deadline
- Verification evidence:
  - `backend/tests/test_raw_fact_router.py::test_spatial_access_fact_handler_prunes_expired_nearby_actor_refs_before_next_event`
  - `backend/tests/test_raw_fact_router.py::test_spatial_access_fact_handler_resets_nearby_actor_ttl_on_fresh_replace`
  - `backend/tests/test_verification_audit.py::test_spatial_access_fact_emitter_sets_nearby_actor_ttl`

## File Map

### Godot

- Modify: `scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd`
  - Emit `ttl_ms` on `actor_approached_actor`.

### Backend

- Modify: `backend/app/services/fact_handlers/spatial_access_fact_handler.py`
  - Track expiry metadata for `nearby_actor_refs`.
  - Prune expired proximity state before applying the next event for that actor.

### Tests

- Modify: `backend/tests/test_raw_fact_router.py`
  - Add deterministic expiry tests using explicit `producer_ts` values.

### Optional verification docs

- Optional Modify: `docs/superpowers/specs/2026-06-07-l1-ttl-nearby-actor-expiry-design.md`
  - Only if implementation forces a clarified TTL boundary.

---

### Task 1: Lock TTL Expiry Behavior With Failing Backend Tests

**Files:**
- Modify: `backend/tests/test_raw_fact_router.py`

- [ ] **Step 1: Add the failing TTL tests**

Append these tests near the spatial-access handler coverage in `backend/tests/test_raw_fact_router.py`:

```python
def test_spatial_access_fact_handler_prunes_expired_nearby_actor_refs_before_next_event() -> None:
    handler = SpatialAccessFactHandler()

    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="actor_approached_actor",
            relation_type="actor_approached_actor",
            producer_ts=1000,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
            targets={"actor_id": "char_a"},
            effect_kind="replace",
            subject_key="nearby_actor_refs",
            ttl_ms=1500,
        ),
        "raw_fact_event",
    )

    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="privacy_boundary_changed",
            relation_type="privacy_boundary_changed",
            producer_ts=2601,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
            targets={},
            world={"state_before": "local", "state_after": "private"},
            effect_kind="set",
            subject_key="privacy_band",
        ),
        "raw_fact_event",
    )

    snapshot = handler.get_snapshot("char_c")

    assert snapshot is not None
    assert snapshot.nearby_actor_refs == []
    assert snapshot.privacy_band == "private"


def test_spatial_access_fact_handler_resets_nearby_actor_ttl_on_fresh_replace() -> None:
    handler = SpatialAccessFactHandler()

    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="actor_approached_actor",
            relation_type="actor_approached_actor",
            producer_ts=1000,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
            targets={"actor_id": "char_a"},
            effect_kind="replace",
            subject_key="nearby_actor_refs",
            ttl_ms=1500,
        ),
        "raw_fact_event",
    )
    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="actor_approached_actor",
            relation_type="actor_approached_actor",
            producer_ts=2000,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
            targets={"actor_id": "char_b"},
            effect_kind="replace",
            subject_key="nearby_actor_refs",
            ttl_ms=1500,
        ),
        "raw_fact_event",
    )
    handler.handle_event(
        RawFactEvent(
            fact_family="spatial_access_fact",
            fact_type="privacy_boundary_changed",
            relation_type="privacy_boundary_changed",
            producer_ts=3000,
            room_id="room_demo",
            scene_id="scene_demo",
            zone_id="zone_focus",
            source={"layer": "L1", "system": "godot.raw_fact_emitter", "actor_id": "char_c"},
            targets={},
            world={"state_before": "public", "state_after": "local"},
            effect_kind="set",
            subject_key="privacy_band",
        ),
        "raw_fact_event",
    )

    snapshot = handler.get_snapshot("char_c")

    assert snapshot is not None
    assert snapshot.nearby_actor_refs == ["char_b"]
```

- [ ] **Step 2: Run the handler tests to verify they fail**

Run:

```bash
python -m pytest -v tests/test_raw_fact_router.py
```

Expected:

- FAIL because the handler does not yet track or prune `ttl_ms`.

- [ ] **Step 3: Commit the failing tests checkpoint only if you are using a branch-per-step workflow**

```bash
git add backend/tests/test_raw_fact_router.py
git commit -m "test: lock nearby actor ttl expiry behavior"
```

If you are not committing red-state checkpoints, skip this commit and continue immediately.

### Task 2: Implement Backend TTL Expiry In The Spatial Access Handler

**Files:**
- Modify: `backend/app/services/fact_handlers/spatial_access_fact_handler.py`
- Modify: `backend/tests/test_raw_fact_router.py`

- [ ] **Step 1: Add minimal internal expiry bookkeeping**

Update `SpatialAccessFactHandler` to store expiry metadata:

```python
class SpatialAccessFactHandler:
    def __init__(self) -> None:
        self._snapshots: dict[str, SpatialAccessRuntimeStateSnapshot] = {}
        self._expiry_deadlines_by_actor: dict[str, dict[str, int]] = {}
```

Add helpers:

```python
    def _get_actor_expiry_map(self, actor_id: str) -> dict[str, int]:
        return self._expiry_deadlines_by_actor.setdefault(actor_id, {})

    def _prune_expired_state(self, actor_id: str, now_ms: int) -> None:
        snapshot = self._snapshots.get(actor_id)
        if snapshot is None:
            return
        expiry_map = self._expiry_deadlines_by_actor.get(actor_id, {})
        expiry_deadline = expiry_map.get("nearby_actor_refs")
        if expiry_deadline is None:
            return
        if now_ms < expiry_deadline:
            return
        snapshot.nearby_actor_refs = []
        expiry_map.pop("nearby_actor_refs", None)
```

- [ ] **Step 2: Prune expired state before applying the next event**

At the start of `handle_event()`:

```python
    def handle_event(self, event: RawFactEvent, source_type: str) -> list[Message]:
        actor_id = event.source.actor_id
        self._prune_expired_state(actor_id, event.producer_ts)
        snapshot = self._get_or_create_snapshot(event)
        self._apply_event(snapshot, event)
        ...
```

- [ ] **Step 3: Apply expiry metadata only for nearby actor replace facts**

Inside `_apply_event()` after `replace nearby_actor_refs` succeeds:

```python
        if effect_kind == "replace" and subject_key == "nearby_actor_refs":
            target_actor_id = event.targets.actor_id
            snapshot.nearby_actor_refs = [target_actor_id] if target_actor_id != "" else []
            expiry_map = self._get_actor_expiry_map(event.source.actor_id)
            if event.ttl_ms is not None and event.ttl_ms > 0:
                expiry_map["nearby_actor_refs"] = event.producer_ts + event.ttl_ms
            else:
                expiry_map.pop("nearby_actor_refs", None)
            return
```

For explicit clear:

```python
        if effect_kind == "clear" and subject_key == "nearby_actor_refs":
            snapshot.nearby_actor_refs = []
            self._get_actor_expiry_map(event.source.actor_id).pop("nearby_actor_refs", None)
            return
```

For zone reset:

```python
        if effect_kind == "set" and subject_key == "current_zone_id":
            snapshot.current_zone_id = event.zone_id
            if event.fact_type == "actor_entered_zone":
                snapshot.nearby_actor_refs = []
                self._get_actor_expiry_map(event.source.actor_id).pop("nearby_actor_refs", None)
            return
```

- [ ] **Step 4: Re-run the handler tests**

Run:

```bash
python -m pytest -v tests/test_raw_fact_router.py
```

Expected:

- PASS, including the new TTL expiry tests and all legacy compatibility tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/fact_handlers/spatial_access_fact_handler.py backend/tests/test_raw_fact_router.py
git commit -m "feat: add nearby actor ttl expiry fallback to spatial access handler"
```

### Task 3: Emit TTL From The Godot Spatial Access Emitter

**Files:**
- Modify: `scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd`
- Modify: `backend/tests/test_verification_audit.py`

- [ ] **Step 1: Add a static verification test for emitted TTL**

Add this to `backend/tests/test_verification_audit.py` near the spatial/shared contract assertions:

```python
def test_spatial_access_fact_emitter_sets_nearby_actor_ttl() -> None:
    project_root = Path(__file__).resolve().parents[2]
    emitter_source = (
        project_root / "scripts" / "l1" / "facts" / "emitters" / "SpatialAccessFactEmitter.gd"
    ).read_text(encoding="utf-8")

    assert '"nearby_actor_refs"' in emitter_source
    assert "1500" in emitter_source
```

- [ ] **Step 2: Run the static verification test to verify failure**

Run:

```bash
python -m pytest -v tests/test_verification_audit.py::test_spatial_access_fact_emitter_sets_nearby_actor_ttl
```

Expected:

- FAIL because the emitter does not yet pass `ttl_ms=1500`.

- [ ] **Step 3: Emit `ttl_ms` on actor approach**

Update `scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd` in `_emit_spatial_access_fact()` callers.

For `emit_actor_approached_actor()`:

```gdscript
	return _emit_spatial_access_fact(
		"actor_approached_actor",
		"actor_approached_actor",
		zone_id,
		target_actor_id,
		world,
		"replace",
		"nearby_actor_refs",
		1500,
		"phase0_spatial_access_fact:actor_approached_actor:%s" % target_actor_id
	)
```

Change `_emit_spatial_access_fact()` signature to accept `ttl_ms`:

```gdscript
func _emit_spatial_access_fact(
	fact_type: String,
	relation_type: String,
	next_zone_id: String,
	target_actor_id: String,
	world: Dictionary,
	effect_kind: String,
	subject_key: String,
	ttl_ms: Variant,
	success_log: String
) -> bool:
```

Pass it into the builder:

```gdscript
		effect_kind,
		subject_key,
		ttl_ms,
		"",
		""
```

For the other spatial facts, pass `null`:

- `actor_entered_zone`
- `actor_left_actor_range`
- `privacy_boundary_changed`

- [ ] **Step 4: Re-run the static verification test**

Run:

```bash
python -m pytest -v tests/test_verification_audit.py::test_spatial_access_fact_emitter_sets_nearby_actor_ttl
```

Expected:

- PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd backend/tests/test_verification_audit.py
git commit -m "feat: emit nearby actor ttl from spatial access facts"
```

### Task 4: Full Verification And Closeout

**Files:**
- Modify: `docs/superpowers/specs/2026-06-07-l1-ttl-nearby-actor-expiry-design.md` only if implementation needs clarified wording
- Modify: `docs/superpowers/plans/2026-06-07-l1-ttl-nearby-actor-expiry-implementation-plan.md` by checking boxes during execution

- [ ] **Step 1: Run focused verification**

Run:

```bash
python -m pytest -v tests/test_raw_fact_router.py
python -m pytest -v tests/test_verification_audit.py::test_spatial_access_fact_emitter_sets_nearby_actor_ttl
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

- [ ] **Step 3: Re-run current Godot verification harnesses**

Run:

```bash
python scripts/verification/verify_phase1_slice.py
python scripts/verification/verify_phase0.py
python scripts/verification/verify_l1_runtime_edges.py
```

Expected:

- no regression in Phase 0
- no regression in Phase1-shaped slice
- runtime edge probe still passes

- [ ] **Step 4: Final static scan for TTL wiring**

Run:

```bash
rg -n "ttl_ms|nearby_actor_refs" scripts backend
```

Expected:

- `ttl_ms` appears in the shared schema, spatial emitter, and spatial handler
- `nearby_actor_refs` expiry logic is clearly localized to the spatial-access path

- [ ] **Step 5: Commit final polish if needed**

```bash
git add docs/superpowers/specs/2026-06-07-l1-ttl-nearby-actor-expiry-design.md docs/superpowers/plans/2026-06-07-l1-ttl-nearby-actor-expiry-implementation-plan.md
git commit -m "docs: sync nearby actor ttl expiry plan and spec"
```

- [ ] **Step 6: Prepare closeout summary**

Report:

- changed files
- exact TTL behavior now supported
- whether TTL is backend fallback only or runtime-proved end-to-end
- exact verification commands run
