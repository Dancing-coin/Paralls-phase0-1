# Godot Mirror, Persistence, And Migration Plan

Status: `Phase 3/4 trusted-local live delivery implemented and verified; durable persistence and broader migration remain planned`

## Execution Update (2026-08-04)

The bounded configured Phase 3 source and policy-filtered Godot projection now
have real trusted-local WebSocket evidence, not only static/local-consumer
proof. The current `godot-gameplay-mirror` report covers authorized initial
bind/subscription, committed after-commit projection, fresh-enrollment
reconnect with narrowed scope, gap/resync, bounded backpressure recovery,
stamina prediction confirmation/rejection rollback, controlled close, and
final filtered-revision convergence. The launcher report separately proves
the server-issued enrollment reaches a real Godot `BackendBridge` without
leaking the bootstrap secret.

This advances only the listed trusted-local snapshot/delta/prediction surface.
Durable storage adapters, persistent executable-upcaster manifests, general
schema migration, generic inventory/equipment UI consumers, production
identity, and durable transport queues remain outside this plan.

## 2026-08-03 Implementation Status

The initial safe delivery contract is written and backend/static-test verified:
the backend only serializes policy-filtered Godot views, and the local consumer
rejects forbidden authority/private/physics fields at every nesting depth. The
implementation must remain fixture-independent: scene names, node paths,
default-scene actor IDs, and object/container references cannot grant mirror
access or select a state group. The `/ws` endpoint now accepts bounded
`websocket_session_bind`, `gameplay_mirror_subscribe`,
`gameplay_mirror_snapshot_request`, and `gameplay_mirror_unsubscribe` flows,
and the focused mirror profile includes a local Godot bridge scope/disconnect
probe. `GAMEPLAY_MIRROR_PHASE3_ACTORS_JSON` now supplies explicit backend-owned
actor configuration: supported Phase 3 definitions, Godot field allowlists,
revision identities, and optional tag/stat definitions. The application
composes a read-only source only from committed Gameplay events, then installs
it into the existing projection publisher. No scene, fixture actor, client
request, or default object participates in that configuration. This remains a
bounded resource/body/status/effective-stat snapshot source, rather than a
claim of production identity issuance, end-to-end reconnect/resync, broad live
delivery, delta/prediction, or complete gameplay-façade closure.

The event-store layer now has a versioned JSON snapshot export/import primitive
with atomic file replacement. It restores committed events, batches, stream
heads, idempotency outcomes, current outbox delivery state, and the opt-in
event-schema registry that governed guarded writes; it rejects corrupt,
unsupported, or registry-inconsistent snapshots. `DurableGameplayEventStore`
persists each successful batch and outbox state update. A first trusted,
in-process upcaster seam now permits only registered, digest-matched,
continuous `vN -> vN+1` transformations during `GameplayProjectionReplay`.
The minimum recovery slice now also persists projection checkpoints and can
select the newest checksum-valid checkpoint compatible with a projector/schema
identity and active patch, registry, and world-config revisions. It checks the
historical event prefix and revision vector before replaying the tail. The
opt-in single-store startup coordinator keeps writes closed until this replay
succeeds and returns retriable `projection_not_ready` while it is closed. It is
not a database adapter, persistent executable-upcaster manifest, full schema
migration, global multi-projector readiness coordinator, or production startup
control plane.

## Delivery Contract And Current Coverage

Do not emit an internal `CharacterGameRuntimeState` merely because a client is
connected. The implemented foundation provides items 1, the snapshot half of
2, 4, and 5 below. Item 3 and production-grade connection recovery remain
planned.

1. A backend-owned actor-to-session authorization scope. The client supplies a
   requested actor reference, but backend policy decides whether that session
   can receive the actor's Godot view.
2. A backend façade projection source that creates
   `StateGroupViewProjector.godot_view(...)`, then serializes it through
   `project_godot_runtime_state(...)`. Authority façades, raw domain event
   payloads, and arbitrary group payloads must never bypass this path.
3. Explicit `snapshot` and `resnapshot_required` envelopes. Exact-base delta
   conflict, checksum failure, or unsupported capability must trigger a new
   snapshot request; Godot must not assemble a best-effort state.
4. After-commit delivery from the Gameplay outbox/dispatcher only. A local
   action attempt or uncommitted domain batch cannot update the mirror.
5. A local consumer that accepts only `gameplay_runtime_state.godot.v1`, rejects
   authority/private/physics fields and stale revisions, and has no command or
   event-store write path.

`WebSocketSessionAuthService` issues an opaque, connection-bound read scope for
the trusted-local bootstrap; production `authenticated_session` still fails
closed until an external issuer is selected. `Phase3MirrorSource` composes a
configured actor's enabled supported groups from committed backend events, and
`install_phase3_mirror_sources(...)` registers it with the application
publisher. The transport-neutral after-commit seam accepts only
authority-authored affected actor refs, fans out only to authorized
subscriptions, and isolates failed session delivery from the already committed
batch. `GameplayMirrorOutboxRefreshConsumer` runs only after all outbox entries
in a transaction are delivered; it does not infer actor scope from payloads or
fixtures. The local bridge probe is a Godot runtime check of the presentation
consumer, not proof of a production WebSocket deployment.

## Dependencies

Event/projection spine, facade, patch lifecycle, and at least one completed
gameplay group. This plan consumes current backend/Godot routing but does not
replace it.

## Work

1. Extend the implemented JSON snapshot, compatible checkpoint selection,
   single-store startup gate, and one-step replay-upcaster seam with durable
   storage adapters, persistent executable upcaster manifests, complete
   event-family registration, schema migrations, general patch/state-group
   migration policy, global multi-projector readiness, and recovery diagnostics.
   The bounded resource maximum-reduction Patch migration is separately
   replay-covered by the Patch and Gameplay replay profiles; it is not a
   general persistence migration closure.
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
