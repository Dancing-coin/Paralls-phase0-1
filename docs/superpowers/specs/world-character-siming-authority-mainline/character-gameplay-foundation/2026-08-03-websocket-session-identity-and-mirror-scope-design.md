# WebSocket Session Identity And Gameplay Mirror Scope Design

Status: `implemented-foundation; live-mirror-delivery-planned`

Date: `2026-08-03`

## Purpose

Define a backend-owned connection identity and read-scope seam for WebSocket
clients. It exists so that gameplay mirror visibility can be granted from a
trusted server-side binding rather than from client payload fields, Godot node
names, default-scene fixtures, or local controller grants.

This design is intentionally independent from `EmbodiedControllerAuthService`.
Controller enrollment governs a locally attested embodiment executor; it does
not establish a player principal, a gameplay reader, or a general WebSocket
session.

## Invariants

- The backend generates opaque `session_ref` values and owns their lifecycle.
- A binding contains a backend-selected `principal_ref` and an explicit,
  multi-actor `allowed_actor_refs` tuple. A client never expands that tuple.
- `actor_id`, `player_id`, `session_ref`, scene path, node name, default-scene
  object ref, container ref, custody ref, and definition ID received from the
  client are requests or untrusted labels, never authorization evidence.
- A mirror subscription only selects an actor from the already granted scope.
  It cannot grant, infer, or widen scope.
- Snapshot/resync output is built from policy-filtered backend projections.
  Godot remains a presentation consumer and never stores authoritative truth.
- `MainDemo`, `char_c`, and the default-scene interaction routes are validation
  fixtures only. They must not appear in authorization, session, or routing
  policy.
- `trusted_local_launch` is a narrow development enrollment: one-time,
  expiring, and bound to the actual loopback peer address. It is not a
  production login scheme.
- `authenticated_session` remains fail-closed until an upstream identity adapter
  is explicitly installed. There is no anonymous fallback.
- A controller binding, its epoch, grant, and nonce cannot be used as a
  gameplay mirror session credential.

## Components

```text
WebSocket connection (actual peer host)
  -> WebSocketConnectionContext
  -> WebSocketSessionAuthService.bind_session(...)
  -> SessionBinding(session_ref, principal_ref, allowed_actor_refs)
  -> GameplayMirrorSubscriptionRegistry (only server-granted scopes)
  -> filtered snapshot / later after-commit delivery
  -> Godot read-only mirror consumer
```

`WebSocketConnectionContext` is connection-local. It retains the actual peer
host and an optional `SessionBinding`; it is passed to WebSocket-only handlers.
The existing direct `_handle_envelope` test seam remains unbound compatibility
input until each legacy route receives its own authorization migration.

## Protocol Boundary

The initial typed requests are:

- `websocket_session_bind`: presents an enrollment credential and requests a
  session binding. The response returns only the generated session reference,
  principal reference, and granted actor refs.
- `gameplay_mirror_subscribe`: requests a subscription for one actor already in
  the binding scope. Optional requested state-group capabilities are treated as
  preferences and filtered by server policy.
- `gameplay_mirror_unsubscribe`: removes a same-connection subscription.
- `gameplay_mirror_snapshot_request`: asks for a full filtered snapshot for one
  already subscribed, already granted actor. It is a read/resync request, not
  an event-replay or truth-rebuild command.

No request transports a trusted world claim, authority command, private mind
state, physics state, or mirror projection policy.

## Delivery Sequencing

The existing after-commit fanout foundation remains authoritative for its
ordering rule: a refresh can run only after every outbox entry for an atomic
transaction is durably delivered. Future live WebSocket delivery attaches a
connection transport after this boundary; a failed or disconnected client may
lose its presentation update, but cannot affect committed gameplay truth or
outbox delivery.

## Non-goals

- Full account login, token issuance, refresh, federation, or persistence.
- Client-side prediction, rollback, or a production Godot mirror completion.
- Reusing controller execution credentials for session or reader authority.
- Granting input/interaction authority merely because a mirror read scope was
  granted.
- Default-scene-specific authorization rules.

## Current Delivery Status

`WebSocketSessionAuthService`, `WebSocketConnectionContext`, the
transport-neutral `GameplayMirrorSessionAccessService`, and an internal
`GameplayGodotProjectionRepository` are implemented and focused-test verified.
The `/ws` endpoint creates a connection context, passes the actual peer host to
controller enrollment, and routes bind/subscribe/snapshot/unsubscribe reads;
the direct handler seam is explicitly a compatibility test path. The repository
accepts only already policy-filtered backend Godot views and fails closed for
actors with no published view. Mirror access can only create/read/remove
subscriptions from a pre-bound session's explicit actor tuple. This establishes
initial WebSocket snapshot reads plus bounded after-commit fanout plumbing:
the Gameplay dispatcher invokes a transport-neutral observer only once its full
atomic transaction outbox is delivered, and registered WebSocket sessions
receive prepared views through bounded private queues. A missing connection or
full queue is isolated from the already committed batch. This does not prove an
external production identity issuer, end-to-end reconnect/resync policy, or a
live WebSocket/Godot deployment for this path.

`GameplayGodotProjectionPublisher` now provides the production-facing refresh
seam: authority-owned code explicitly registers an actor view source; a
completed transaction with explicit `godot_mirror` actor refs refreshes that
source before fanout. Missing or failing sources remove their previous view, so
the client can only resync after a fresh backend publication. The application
now accepts explicit `GAMEPLAY_MIRROR_PHASE3_ACTORS_JSON` configurations and
installs a bounded Phase 3 source that rebuilds supported
resource/body/status/effective-stat groups from committed events and applies
configured Godot field allowlists. Configuration is backend-owned and never
derives an actor from a scene, fixture, or client payload. The live `/ws`
trusted-local bind/subscribe snapshot test proves this read path, but does not
make `trusted_local_launch` a production identity adapter or prove a live
WebSocket-to-Godot deployment.

Godot's reusable `GameplayMirrorBridge` has now been written and editor-parsed:
it accepts launcher-provided enrollment material, routes only server-granted
actor selections, and clears local allowed scope plus confirmed mirror state on
disconnect. It deliberately does not retry a consumed credential or infer a
new session; reconnect requires a new backend-issued binding. The focused
Godot headless probe now proves those local routing and disconnect semantics;
it remains distinct from an end-to-end live mirror proof.

## 2026-08-04 Phase 4 Contract Boundary

The reconnect extension now has a typed fail-closed contract before transport
behavior is enabled. Bindings expose backend-owned lifecycle, lease, and epoch
fields; renewal requests carry no subject, actor scope, or credential material;
capability offers cannot request fields or scope; and receipts carry only a
server epoch and sent delivery sequence. Delta wrappers require exact facade
base, checksums, and source revision metadata.

The receipt ledger is bounded connection-local telemetry. It rejects stale,
unknown, and expired-window receipts and cannot write Gameplay truth, alter an
outbox entry, or expand a binding. The local Godot consumer rejects duplicate,
old-epoch, gap, and base-less-delta delivery without changing confirmed state;
it enters presentation-only `resync_required` instead.

This is contract and local-probe evidence only. It does not enable renewal,
delta application, queue recovery, reconnect, or live WebSocket mirror
delivery. Those remain subject to the Phase 1 through Phase 6 gates.
