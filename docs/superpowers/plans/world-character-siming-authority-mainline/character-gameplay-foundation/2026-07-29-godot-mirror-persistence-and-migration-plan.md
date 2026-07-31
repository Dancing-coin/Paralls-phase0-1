# Godot Mirror, Persistence, And Migration Plan

Status: `drafted-for-spec-review`

## Dependencies

Event/projection spine, facade, patch lifecycle, and at least one completed
gameplay group. This plan consumes current backend/Godot routing but does not
replace it.

## Work

1. Implement durable event storage adapters, checkpoints, upcasters, schema
   migrations, patch/state-group migration policy, and recovery diagnostics.
2. Implement per-actor snapshot/delta envelopes, revision tracking,
   consumer-filtered views, prediction IDs, confirmation/rejection, rollback,
   gap detection, and full resync.
3. Add typed Godot mirror consumer APIs for HUD, inventory, equipment,
   affordance, and transaction presentation; prohibit raw payload ownership.
4. Build backend and real Godot probes for reconnect, stale/duplicate delta,
   unknown schema, rejected prediction, and resync.

## Exit Criteria

Godot never establishes gameplay truth. A mirror can recover from a revision
gap using one authoritative snapshot without duplicating visible effects.
