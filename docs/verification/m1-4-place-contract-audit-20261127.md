# M1-4 Place contract audit

## Scope

This is a static audit of the formal Place primitive and the current A worktree. No Place implementation was added.

## Findings

- The formal contract requires occupancy exclusivity at a declared location and time, semantic arrival/departure commits, path and occupancy revisions, independently committed passability changes, and references into a space registry.
- The formal command/event set includes `occupy`, `vacate`, `move_to`, and `block`, with `place.occupied`, `place.vacated`, `place.departed`, `place.arrived`, `place.blocked`, `place.rerouted`, and `place.intercepted` events.
- The current `place_passability_runtime.py` is a Presence-specific passability assessment path. It does not provide a general occupancy, movement, or space-registry authority.
- `place_event_schema.py` registers Presence passability events only. `FactTypeRegistry` accepts the `place` primitive and validates `place_kind`, but no general Place runtime or space registry was found in the inspected A code and tests.

## Decision

M1-4 cannot be implemented as an independent safe slice from the current inputs. Adding a general Place runtime would require a space-registry contract, Owner/authority mapping, persistence event contract, and producer/reader scope. Reusing Presence would conflate two distinct authorities. M1-4 remains queued pending those contracts.

## Verification level

Static-only. No code or tests changed. The current worktree retains its unrelated untracked `Godot/` directory.
