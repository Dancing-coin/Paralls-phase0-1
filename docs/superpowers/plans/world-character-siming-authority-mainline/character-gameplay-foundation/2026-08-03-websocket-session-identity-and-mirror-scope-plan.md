# WebSocket Session Identity And Gameplay Mirror Scope Plan

Status: `foundation-core implemented and runtime-verified; production identity, durable transport, persistence, and migration remain deferred`

Date: `2026-08-03`

## Objective

Replace fixture- and client-asserted gameplay mirror scope with a backend-owned
WebSocket session binding while preserving existing authority, controller, and
event-spine boundaries.

## Phases

1. **Session contract and service**
   - Add typed binding/request models and `WebSocketSessionAuthService`.
   - Support only one-time, expiring `trusted_local_launch` credentials that
     check the actual loopback peer; keep `authenticated_session` fail-closed.
   - Test opaque session generation, multi-actor grants, expiry, replay, remote
     peer rejection, and no dependence on fixture identities.

2. **Connection context**
   - Create one `WebSocketConnectionContext` per `/ws` connection.
   - Thread the actual `websocket.client.host` into WebSocket-specific handlers.
   - Correct `embodied_controller_bind` so its existing local controller policy
     receives that actual host instead of a hardcoded loopback value.
   - Preserve direct handler tests as explicitly unbound compatibility calls;
     do not imply they are authenticated network flows.

3. **Restricted mirror read path**
   - Bind, subscribe, unsubscribe, and snapshot only through a valid context.
   - Grant registry scope from `SessionBinding`, never from client actor/player
     fields or scene fixtures.
   - Apply the existing Godot projection filter and reject non-subscribed,
     out-of-scope, unknown, or malformed requests.

4. **Live delivery and recovery**
   - Attach connection-safe transports to after-commit fanout.
   - Add reconnect/resync semantics, backpressure bounds, capability negotiation,
     and real Godot runtime proof.
   - Verify it through a real BackendBridge/Godot process, not a local consumer
     probe alone.

## Progress Record

Phase 1 is implemented and focused-test verified. The backend-owned binding
service issues opaque sessions from a one-time loopback credential and retains
an explicit multi-actor read scope; production authenticated sessions remain
fail-closed. Phase 2 has its connection-context foundation implemented, and
the existing controller bind now receives the actual WebSocket peer host. The
transport-neutral portion of Phase 3 is also implemented and focused-test
verified: it converts only a bound session's already granted actor selection
into registry subscription/snapshot/unsubscribe calls. `/ws` now routes those
typed read commands through a backend-published generic Godot-view repository;
unpublished views fail closed. The existing after-commit observer is now wired
to a bounded session transport registry, so only a fully delivered atomic
transaction can enqueue a subscribed actor refresh and disconnect/backpressure
cannot affect authority truth. Source publication now has a generic implemented
seam: per-actor backend sources refresh only from explicit transaction actor
refs and stale views are removed on source absence/failure. An explicit
backend-owned `GAMEPLAY_MIRROR_PHASE3_ACTORS_JSON` configuration now installs
the first bounded Phase 3 source. It rebuilds configured
resource/body/status/effective-stat groups from committed Gameplay events and
applies only configured Godot fields; it cannot derive actor identity or scope
from Godot fixtures or client payloads. A live `/ws` trusted-local
bind/subscribe snapshot test verifies the source-to-transport read path.
The live trusted-local closure is now verified through a real BackendBridge and
running backend: fresh enrollment/reconnect with narrowed scope, scoped
snapshot recovery after a sequence gap, bounded-queue/backpressure recovery,
server-issued stamina prediction confirmation and rejection rollback, and a
typed revocation envelope before controlled WebSocket `4403` close. These
flows are server-issued and presentation-only; they do not provide production
identity, client authority, persistence, migration instructions, or a durable
transport queue.

The Godot side clears local session scope and confirmed projection state on
disconnect. Automatic retry remains intentionally absent because the current
trusted-local credential is one-time; every reconnect uses a new server-issued
enrollment. The live runtime proof covers that explicit renewal path rather
than disguising it as automatic reconnection.

## Required Evidence

- Focused unit tests for session binding and scope enforcement.
- WebSocket tests for peer-host propagation and bind/subscribe/snapshot denial
  paths.
- Existing `godot-gameplay-mirror` and `gameplay-foundation-event-spine`
  profiles after each relevant phase.
- Full repository regression/harness before broad completion claims.

## Guardrails

- Do not change `CharacterModelGateway -> CharacterModelProvider ->
  CharacterStructuredOutputValidator`.
- Do not change `SimingRuntime.tick() -> SimingEventProducer ->
  AuthorityEventBus`.
- Do not make `EmbodiedActionController` an authority decider.
- Do not treat a successful unit or WebSocket test as Godot runtime validation.
