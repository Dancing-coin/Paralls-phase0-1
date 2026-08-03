# Trusted-Local Gameplay Mirror Launcher Enrollment Handoff Plan

Status: `approved-for-implementation`

Date: `2026-08-04`

## Purpose

Supply the missing prerequisite for the WebSocket reconnect, resync, and live
mirror delivery plan. This is a narrow development-only issuer and launcher
handoff. It does not add a production identity adapter, a second session
contract, or client-controlled gameplay scope.

## Ownership

```text
backend configuration -> trusted-local launch profile
backend issuer -> opaque one-time enrollment credential
local launcher -> authenticated profile request and Godot child environment
Godot -> present opaque enrollment to websocket_session_bind only
```

The configured profile is the sole source of `principal_ref`, allowed actors,
credential lifetime, and issuance reason. The launcher request contains only a
known profile reference. Godot receives only the resulting opaque enrollment
and cannot request a profile, actor, scope, renewal, or credential lifetime.

## Contract

1. The backend accepts launch profiles only from
   `GAMEPLAY_MIRROR_TRUSTED_LOCAL_LAUNCH_PROFILES_JSON` configuration.
2. The internal loopback issuer accepts a profile reference only after a
   launcher bootstrap secret check. The secret is never handed to Godot,
   logged, or returned by an API.
3. The issuer delegates opaque credential creation to the existing
   `WebSocketSessionAuthService`; it does not create bindings or authorize
   mirror subscriptions itself.
4. The launcher passes one issued enrollment to the Godot child through a
   child-only environment variable. It does not place credentials on the
   command line, scene data, persistent settings, or regular logs.
5. Every issue result is redacted and carries only a correlation reference,
   configured profile reference, reason, and expiry. The credential never
   appears in a trace.
6. A reconnect request requires a newly issued enrollment. Existing session
   references, epochs, actor IDs, receipts, cache data, and Godot fields never
   become issuer input.

## TDD Gates

1. Write and run failing issuer/handoff tests before implementation.
2. Prove profile-only issuance, loopback/bootstrap rejection, opaque output,
   one-time binding, and no client subject/scope fields.
3. Prove the launcher child environment contains enrollment only, not the
   bootstrap secret or server configuration.
4. Run focused tests, full pytest, `gameplay-foundation-event-spine`, and
   `godot-gameplay-mirror`; read every resulting report.
5. Only after a live launcher-to-Godot trace proves initial issue and fresh
   issue on reconnect may the parent reconnect plan enter Phase 0.

## Non-Goals

- Production authenticated-session issuance, federation, durable credentials,
  or external login.
- A public browser or Godot credential minting endpoint.
- Changes to event store, outbox, authority bus, mirror source, filtering, or
  existing WebSocket binding semantics.
