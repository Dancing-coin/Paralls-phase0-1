# L1 TTL Nearby Actor Expiry Design

## Goal

Turn `ttl_ms` from a passive schema field into a real L1 capability by applying it to the `spatial_access_fact` path for `nearby_actor_refs`.

This pass does not attempt to make every L1 fact family time-aware.
It only proves one concrete, low-risk, high-value behavior:

- `actor_approached_actor` can expire automatically if no follow-up evidence arrives

## Why This Exists

The current L1 hardening pass already added:

- `effect_kind`
- `subject_key`
- `ttl_ms`

But `ttl_ms` is still inert.

Right now, `nearby_actor_refs` is safe when:

- Godot emits `actor_left_actor_range`

But it still depends on the explicit clear arriving.

For a low-level evidence layer, that leaves one structural weakness:

- if an explicit clear is missed, delayed, or never emitted, the backend can keep stale nearby-actor state alive too long

`ttl_ms` should solve exactly that class of problem.

## Scope

This design applies `ttl_ms` only to:

- `fact_family = spatial_access_fact`
- `subject_key = nearby_actor_refs`
- fact types that write the nearby-actor state, especially `actor_approached_actor`

This design does not yet apply TTL behavior to:

- `privacy_band`
- `current_zone_id`
- environment state projection
- visual facts generally

## Behavioral Rule

### Primary rule

`nearby_actor_refs` remains driven by explicit facts:

- `replace` on approach
- `clear` on explicit leave

### New fallback rule

If the most recent `nearby_actor_refs` write carried `ttl_ms`, and no newer write or clear replaced it before expiry, the backend should automatically clear the projected `nearby_actor_refs` state once the TTL window is exceeded.

This is a fallback safety net, not the main path.

## Contract Semantics

### Emission

For `actor_approached_actor`, Godot should emit:

- `effect_kind = "replace"`
- `subject_key = "nearby_actor_refs"`
- `ttl_ms = <short window>`

Recommended initial TTL:

- `1500 ms`

Reason:

- long enough to tolerate normal frame/update jitter
- short enough to prevent stale proximity from surviving for multiple seconds

### Explicit clear still wins

If `actor_left_actor_range` arrives before TTL expiry:

- clear immediately
- do not wait for TTL

### New writes reset TTL

If a fresh `actor_approached_actor` fact arrives before expiry:

- update `nearby_actor_refs`
- reset the expiry deadline using the new `producer_ts` and `ttl_ms`

## Backend Design

## Spatial state model

The current `SpatialAccessRuntimeStateSnapshot` should continue exposing:

- `nearby_actor_refs`
- `privacy_band`
- `current_zone_id`

TTL support should not force public API churn unless needed.

If extra internal expiry bookkeeping is needed, prefer keeping it inside the handler instead of exposing it in the outward snapshot model.

### Handler-owned expiry bookkeeping

`SpatialAccessFactHandler` should maintain internal expiry metadata per actor for the `nearby_actor_refs` slot.

Recommended internal shape:

- actor_id -> `{subject_key: expiry_deadline_ms}`

At minimum:

- `nearby_actor_refs` expiry per actor

This keeps expiry mechanics local to the handler and avoids pushing low-value timing internals into the public runtime-state schema.

### Expiry enforcement points

Expiry should be checked when the handler processes new events for the same actor.

That means:

1. before applying a new event, prune expired `nearby_actor_refs`
2. then apply the incoming event

This does not create background timers.

That is acceptable for this pass because:

- it keeps complexity low
- it is sufficient to prevent stale state from surviving past the next relevant event boundary

## Godot Design

### SpatialAccessFactEmitter

`emit_actor_approached_actor()` should start populating `ttl_ms`.

Recommended initial value:

- `1500`

### MainDemoController

No new timing logic should be added here for TTL itself.

`MainDemoController` should keep doing:

- approach sampling
- explicit leave emission

TTL is backend-side fallback behavior, not another client-side timer policy.

## Verification Strategy

## Backend tests

Add tests proving:

1. approach fact with `ttl_ms` stores nearby actor state normally
2. expired nearby actor state is cleared on a later event for the same actor
3. a fresh approach before expiry resets the expiry window
4. explicit clear still removes nearby actor state immediately

### Focused proof shape

Use handler-level tests with explicit `producer_ts` values instead of sleeping in real time.

Example structure:

- first event at `1000` with `ttl_ms=1500`
- later event at `2601` should observe expiry before new application

## Godot-side verification

The runtime probe does not need a full timer-based end-to-end TTL proof in this pass.

Why:

- the TTL mechanism is backend-local fallback logic
- explicit leave is already runtime-proved
- handler-level deterministic tests are the strongest proof for the expiry math itself

If future runtime behavior requires proving TTL without a follow-up clear, add a dedicated probe later.

## Non-goals

This pass must not:

- introduce a generic scheduler service
- create background expiry threads or tasks
- apply TTL to every fact family
- convert all runtime snapshots to event-sourced stores

## Success Criteria

This design is successful when:

1. `ttl_ms` is no longer inert for `nearby_actor_refs`
2. stale nearby-actor state can self-clear even if an explicit leave fact is missed
3. explicit clear still remains the primary fast path
4. TTL logic stays local to the spatial-access handler and does not bloat the rest of L1
