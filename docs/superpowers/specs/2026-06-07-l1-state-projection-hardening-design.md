# L1 State Projection Hardening Design

## Goal

Harden the current `L1` raw fact layer so it scales beyond the first `visual_fact` and `spatial_access_fact` slice without accumulating stale state, one-shot emitters, or reconnect gaps.

This design keeps the existing `raw_fact_event -> fact_router -> fact handler` spine, but tightens the contract so `L1` facts can explicitly express whether they set, clear, replace, or pulse state.

## Why This Exists

The current implementation proved the shared emitter pattern, but it still has three structural weaknesses:

1. `spatial_access_fact` can leave stale `nearby_actor_refs` behind when proximity evidence disappears.
2. environment alert emission is effectively one-shot per environment instance.
3. bootstrap facts such as zone entry are not replay-safe across backend reconnects or runtime reset.

Those are not isolated bugs. They all come from the same missing concept: `L1` currently emits raw facts, but the facts do not clearly describe how they should affect projected state.

## Boundary

### L1 Responsibilities

`L1` is responsible for:

- sampling observable runtime evidence in Godot
- emitting normalized raw facts across the Godot/backend boundary
- projecting those facts into current low-level runtime state on the backend
- supporting explicit invalidation, replacement, and replay

### L1 Is Not Responsible For

`L1` is not responsible for:

- social inference
- mutual knowledge inference
- membership or exclusion claims
- conversation intent
- role-level interpretation

Those still belong above `L1`.

## Design Summary

Keep the current family-based raw fact pipeline, but add a small shared semantics layer to each raw fact:

- `effect_kind`
- `subject_key`
- optional `ttl_ms`

This lets the backend update projected `L1` state using one shared mental model:

- `set`
- `clear`
- `replace`
- `pulse`

Instead of each fact handler inventing its own ad hoc invalidation rules.

## Target Architecture

### Godot Side

`Scene Runtime -> family emitter -> FactEnvelopeBuilder -> RawFactEmitter -> BackendBridge`

### Backend Side

`raw_fact_event -> RawFactEvent schema -> fact_router -> family handler -> projected runtime snapshot`

## Shared Raw Fact Contract

### Existing Fields To Keep

- `event_type`
- `fact_family`
- `fact_type`
- `relation_type`
- `producer_ts`
- `room_id`
- `scene_id`
- `zone_id`
- `source`
- `targets`
- `world`
- `observability`
- `causation_id`
- `correlation_id`

### New Fields

#### `effect_kind`

Controls how the fact should affect projected low-level state.

Allowed values:

- `set`
- `clear`
- `replace`
- `pulse`

Definitions:

- `set`: assign or update the current value for a subject
- `clear`: explicitly remove the current value for a subject
- `replace`: overwrite the current collection/value with the new evidence
- `pulse`: event is meaningful, but should not persist as projected state unless a handler chooses to use it transiently

#### `subject_key`

Names the projected state slot this fact affects.

Examples:

- `nearby_actor_refs`
- `privacy_band`
- `environment_state/env_lamp`
- `current_zone_id`

This gives handlers a stable shared vocabulary without forcing all fact families into one giant schema.

#### `ttl_ms`

Optional per-fact expiry window.

Purpose:

- future-compatible hook for ephemeral low-level evidence
- allows later families to express freshness limits without inventing custom timeout logic

This design does not require broad TTL behavior immediately, but the field should be available now to avoid another contract migration later.

## Effect Semantics By Current Family

### `visual_fact`

Keep current behavior compatible.

Most current `visual_fact` paths can remain effectively event-shaped, with minimal use of the new fields where useful.

Examples:

- `fixed_gaze_on_target`
  - can remain a `pulse` if current focus state is already maintained elsewhere
- `light_level_drop`
  - should move toward explicit environment state projection semantics

The point is not to force a full visual fact rewrite in this pass.

### `spatial_access_fact`

This family should be upgraded first because it already exposes the stale-state problem clearly.

#### `actor_entered_zone`

Recommended semantics:

- `effect_kind = set`
- `subject_key = current_zone_id`

May also be used as replay/bootstrap evidence so the backend can reconstruct a minimal spatial snapshot after reconnect.

#### `actor_approached_actor`

Recommended semantics:

- `effect_kind = replace`
- `subject_key = nearby_actor_refs`

Meaning:

- for the emitting actor, the latest low-level nearby-actor evidence replaces the last projected nearby actor set represented by this narrow slice

#### `actor_left_actor_range`

Add this new fact type.

Recommended semantics:

- `effect_kind = clear`
- `subject_key = nearby_actor_refs`

Meaning:

- explicit invalidation when the previously tracked actor is no longer the current proximity target

This solves the current stale `nearby_actor_refs` issue cleanly.

#### `privacy_boundary_changed`

Recommended semantics:

- `effect_kind = set`
- `subject_key = privacy_band`

The fact still expresses only low-level access/privacy evidence, not group membership.

## Environment State Behavior

The current `EnvironmentVisualFactEmitter` suppresses repeated alert cycles because it remembers only that `alerted` has already fired.

That should be replaced with state-aware emission:

- `stable -> alerted` emits
- `alerted -> stable` updates local state and may emit if needed for projection
- later `stable -> alerted` emits again

The important rule is:

`L1` should suppress duplicate identical state transitions, not suppress future legitimate re-entry into the same state.

## Reconnect And Runtime Reset

Bootstrap facts must be replay-safe.

Required behavior:

- if backend runtime resets or reconnects, the Godot side must be able to re-seed minimum `L1` state
- zone-entry bootstrap must not be permanently disabled by a latch that survives a backend disconnect

This does not require full history replay.

It does require:

- resettable client bootstrap latches
- deterministic re-seeding of the current zone/spatial baseline

## File-Level Changes

### Godot Shared Layer

#### `scripts/l1/facts/FactEnvelopeBuilder.gd`

Extend payload construction to support:

- `effect_kind`
- `subject_key`
- `ttl_ms`

Keep envelope creation generic and family-agnostic.

#### `scripts/l1/facts/RawFactEmitter.gd`

No business logic expansion.

It should continue to do only:

- envelope build
- dedupe
- send
- local debug log on failure/success

### Godot Family Emitters

#### `scripts/l1/facts/emitters/SpatialAccessFactEmitter.gd`

Add explicit methods for:

- zone entry bootstrap
- actor approach replace
- actor range exit clear
- privacy band set

This emitter owns family-level effect semantics.

#### `scripts/l1/facts/emitters/EnvironmentVisualFactEmitter.gd`

Replace one-shot-per-environment behavior with cycle-safe transition behavior.

It should remember current emitted state, not just “alerted already happened once”.

### Godot Sampling Layer

#### `scripts/phase0/MainDemoController.gd`

Keep responsibility limited to:

- deciding when evidence should be sampled
- calling the correct family-emitter methods

It should no longer rely on local variables alone to “clear” state implicitly without sending a corresponding invalidation fact.

Specific fixes:

- emit explicit “left actor range” fact when focused actor disappears or leaves threshold
- reset bootstrap latch when backend connectivity/runtime state requires re-seeding

### Backend Shared Layer

#### `backend/app/models/raw_fact.py`

Extend `RawFactEvent` with:

- `effect_kind`
- `subject_key`
- `ttl_ms`

#### `backend/app/services/fact_router.py`

Keep thin.

No new inference logic should move here.

### Backend Family Handlers

#### `backend/app/services/fact_handlers/spatial_access_fact_handler.py`

Move from “fact_type-specific ad hoc mutation” toward:

- apply effect semantics
- update projected snapshot deterministically
- support explicit clear and replay-safe set/replace behavior

This handler should still remain a low-level projection layer, not a relationship inference layer.

## Testing Strategy

### Backend Tests

Add failing tests first for:

1. `nearby_actor_refs` clears when approach evidence is explicitly invalidated
2. approach evidence for actor B replaces actor A deterministically
3. reconnect/bootstrap reseeds current zone state
4. privacy band cycles through `public -> local -> private -> public`
5. repeated environment alert cycles are not suppressed permanently

### Contract Tests

Add coverage that shared payload fields:

- serialize from Godot correctly
- validate in `RawFactEvent`
- route without breaking legacy `visual_fact` compatibility

### Integration Tests

Keep or extend coverage in:

- `backend/tests/test_raw_fact_router.py`
- `backend/tests/test_visual_fact_pipeline.py`
- `backend/tests/test_debug_narration.py`

### Validation Commands

Primary verification target after implementation:

```bash
python -m pytest -v
```

Minimum focused verification during development:

```bash
python -m pytest -v tests/test_raw_fact_router.py tests/test_visual_fact_pipeline.py tests/test_debug_narration.py
```

## Migration Rules

### Backward Compatibility

The legacy `visual_fact_event` ingress should remain supported during this hardening pass.

Reason:

- current Phase 0 verification and compatibility paths still rely on it
- the goal is to strengthen the shared L1 contract, not force a risky one-shot removal of the old ingress

### Scope Limits

This pass should not:

- redesign higher-level character interpretation
- add membership inference
- rewrite all visual fact projection logic
- expand into generic event sourcing/history replay

It should:

- make low-level L1 facts explicit about projected-state effects
- eliminate the known stale/one-shot/reconnect weaknesses
- establish a reusable pattern for future fact families

## Success Criteria

This design is successful when:

1. `L1` facts can explicitly set, clear, replace, or pulse projected low-level state.
2. `spatial_access_fact` no longer leaves stale actor proximity state behind.
3. environment alert facts can fire again after reset cycles.
4. reconnect/bootstrap can re-seed current spatial baseline deterministically.
5. the router stays thin and higher-level inference remains above `L1`.
6. the pattern is reusable for future L1 fact families.
