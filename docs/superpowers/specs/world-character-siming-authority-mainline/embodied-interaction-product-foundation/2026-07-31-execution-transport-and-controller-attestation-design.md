# Execution Transport And Controller Attestation Design

Status: `implemented-foundation; production-credential-and-resync-closure-planned`

Date: `2026-07-31`

## Purpose

Define the only typed bridge path for an embodied request, local phase/outcome,
authority settlement, cancellation, and resynchronization. It closes the
current gap where the generic WebSocket accepts a basic envelope and
`CharacterReplica` status is acknowledgement-only. It adds no new authority to
Godot: the bridge authenticates a controller report so backend authority can
decide whether its bounded observation is admissible evidence.

The trusted-local bridge foundation is now implemented: `/ws` routes the
allowlisted embodied bind/request/phase/outcome/settlement/cancel/resync
messages, loopback-only `trusted_local_launch` credentials are enforced, and
grant/epoch/nonce/sequence validation is part of the ingress path. The
production `authenticated_session` credential path and end-to-end reconnect
resume closure remain deferred.

## Controller Authentication Ownership

The current generic WebSocket does not authenticate a controller, so it is not
an adequate starting point for embodied execution. This foundation introduces
the following backend-owned surfaces; `main.py` only hands validated envelopes
to them and must not become an ad hoc identity store:

- `EmbodiedControllerAuthService` owns `ControllerPrincipal`, signed enrollment
  credential verification, controller-instance binding, epoch rotation, and
  revocation. Its planned module is
  `backend/app/services/embodied_controller_auth_service.py`.
- `EmbodiedExecutionIngress` owns allowlisted phase/outcome dispatch and calls
  the auth service before settlement. Its planned module is
  `backend/app/services/embodied_execution_ingress.py`.
- `EmbodiedControllerEnrollment` is the only input to an
  `embodied_controller_bind` message. It has `credential_kind`, `credential`,
  `actor_id`, `controller_instance_id`, and protocol version. The backend derives
  the principal from the credential; the client cannot name a principal.

There are two specified credential kinds. `trusted_local_launch` is the sole
first-closure/demo path: a backend process generates a one-time enrollment
secret for one actor/controller and the local launcher injects it directly into
that Godot process; it is never accepted on a non-loopback listener and expires
on first bind or process stop. `authenticated_session` is the production path:
an upstream authenticated-session issuer signs a short-lived enrollment
credential with actor and host authorization claims, and the auth service
verifies it against configured issuer keys. This repository has no such
upstream issuer today. Therefore production embodied execution is fail-closed
until an adapter is explicitly configured and verified; the feature gate cannot
silently fall back to the local launch credential. A test profile may mint a
test-only principal, but that path must be compiled/configured out of normal
runtime enablement.

## Controller Binding And Grant

The backend returns a `ControllerBinding` containing a server-generated
`controller_instance_id` and monotonically increasing `connection_epoch`.
Preflight then creates an opaque, server-stored `ControllerExecutionGrant`:

```text
grant_id, authenticated_principal_ref, controller_instance_id, connection_epoch
interaction_attempt_id, session_id?, actor_id, target_ref, affordance_id
request_digest, scene_revision, binding_revision, policy_revision
issued_at, expires_at, one_time_outcome_nonce, allowed_phase_range
state: issued | consumed | revoked | expired
```

The grant is sent only in `embodied_action_request` to its bound controller.
It is opaque to normal presentation/read-model consumers. The backend validates
principal, controller, epoch, expiry, request digest, sequence and nonce in one
atomic consume-or-return-original operation. Cancellation, expiry, disconnect,
scene/binding invalidation, controller replacement, and terminal settlement
revoke the grant. Attempt IDs, status messages, timestamps, and client-provided
hashes alone never attest an outcome.

## Message Contract And Routing

All messages use the existing WebSocket envelope and add only these allowed
`message_type` values. Payloads are versioned typed schemas; unknown fields are
rejected.

| Message type | Direction | Owner / handler | Required result |
| --- | --- | --- | --- |
| `embodied_controller_bind` | Godot -> backend | bridge auth + controller-binding handler | create/rebind epoch after principal validation |
| `embodied_controller_bound` | backend -> Godot | `BackendBridge` controller registry | install current epoch; no action starts |
| `embodied_action_request` | backend -> Godot | `BackendBridge` -> `EmbodiedActionController` | validate route/grant then start one controller |
| `embodied_phase_event` | Godot -> backend | embodied execution ingress | append/ack legal ordered local phase evidence |
| `embodied_local_outcome` | Godot -> backend | attestation + settlement ingress | atomically consume grant or return stored result |
| `embodied_settlement_result` | backend -> Godot | `BackendBridge` -> mirror/presentation | project authority result; never execute physics |
| `embodied_cancel_directive` | backend -> Godot | controller | cancel/recover; report one terminal outcome if required |
| `embodied_resync_request` | either direction | bridge resync handler | request state after loss/gap |
| `embodied_resync_projection` | backend -> Godot | controller/mirror | return authoritative route, phase, terminal, or no-resume state |

`BackendBridge` routes the four execution messages to a dedicated embodied
adapter; it must not overload `character_actor_status`, generic
`action_request`, or a TTS/dialogue envelope. The backend dispatches only the
allowlist to dedicated handlers. An unknown inbound type is rejected with a
typed protocol error and no state change. An unknown outbound type is logged as
a compatibility error, does not start a controller, and triggers resync only
when it names a known attempt. Version incompatibility rejects the grant before
local execution.

## Ordering, Reconnect, And Idempotency

`embodied_phase_event` includes `grant_id`, `connection_epoch`, continuous
`source_sequence`, and `payload_digest`. `embodied_local_outcome` additionally
includes the one-time nonce and its terminal sequence. The server assigns the
attempt ledger sequence described by the replay spec.

On a socket loss, the backend revokes the old epoch's grants and marks active
attempts `interrupted_pending_resync`. A reconnect never resumes local motion
by itself. The controller asks for `embodied_resync_projection`; authority then
returns terminal state, a cancel/recover directive, or a new grant with a new
epoch and explicit next sequence. Delayed old-epoch traffic is audit-rejected.
An exact retransmission with the stored digest is idempotently acknowledged;
different bytes at an already accepted sequence fail closed.

## Acceptance Criteria

1. A client that knows only an attempt ID cannot submit an outcome, cancel an
   attempt, or obtain a settlement.
2. A valid controller outcome is accepted once only when the bound principal,
   controller instance, epoch, grant, nonce, request digest, and sequence all
   match; replay returns the original result without a second mutation.
3. Unknown, old-version, stale-epoch, revoked-grant, nonce-reused, and
   out-of-order messages have typed rejection and zero world mutation.
4. A reconnect proves old grants are unusable, resync does not auto-resume
   motion, and only an authority-issued replacement grant can continue.
5. The bridge contains no embodied use of `character_actor_status`, raw bones,
   rigid-body streams, TTS, or streamed dialogue messages.

## Dependencies

- Existing WebSocket envelope and `BackendBridge` dispatch surface.
- New `EmbodiedControllerAuthService` and `EmbodiedExecutionIngress`; current
  socket handling has no controller credential validation, so no existing
  session/bridge owner is a dependency or an implied implementation surface.
- Controller, settlement, and replay specifications in this tree.
- Gameplay mirror connection-epoch convention for resynchronization semantics.
