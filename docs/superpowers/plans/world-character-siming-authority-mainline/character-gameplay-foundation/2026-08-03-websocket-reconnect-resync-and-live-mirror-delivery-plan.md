# WebSocket Reconnect, Resync, And Live Gameplay Mirror Delivery Plan

Status: `planned; implementation-not-started`

Date: `2026-08-03`

## Goal / Objective

Complete Phase 4 of the WebSocket session-identity and gameplay-mirror work:
reliable, bounded, backend-scope-constrained mirror delivery to a real Godot
runtime. The result must recover presentation after disconnect, expiry,
revocation, delivery loss, and queue pressure without changing Gameplay
authority truth or allowing the client to expand what it can read.

This is a delivery and recovery plan. It extends the existing backend-owned
session, projection publisher, subscription registry, committed-outbox fanout,
and Godot mirror bridge. It must not replace or duplicate any of them.

## Current Implemented Boundary

### Implemented and verified

- `WebSocketSessionAuthService` issues opaque bindings from one-time,
  expiring `trusted_local_launch` credentials, rejects replay and non-loopback
  peers, and keeps `authenticated_session` fail-closed.
- A binding contains the backend-selected principal and explicit multi-actor
  read scope. `/ws` retains one `WebSocketConnectionContext`, receives the
  actual peer host, and passes it to relevant WebSocket handlers.
- Bind, subscribe, snapshot, and unsubscribe use the bound backend scope;
  client actor fields can select only an actor already granted by that scope.
- The configured Phase 3 source rebuilds the supported
  resource/body/status/effective-stat Godot view only from committed Gameplay
  events and backend configuration. Publication, filtering, and source failure
  handling are backend-owned.
- After-commit fanout occurs only after all outbox entries of an atomic
  transaction are delivered. The existing connection registry has a bounded
  local queue, and connection/queue failure is isolated from the committed
  transaction.
- `godot-gameplay-mirror` currently has a passing report for focused backend
  tests, a trusted-local `/ws` bind/subscribe/snapshot test, and the local
  Godot bridge probe. `gameplay-foundation-event-spine` has a passing focused
  report.

### Implemented but only static or local-probe evidence

- `GameplayMirrorBridge` accepts launcher-provided enrollment material,
  accepts only server-granted actors, and clears its allowed scope and
  confirmed consumer projections on `backend_disconnected`.
- The Godot bridge probe is a local presentation/runtime probe. It is not a
  connection to a live backend WebSocket and does not prove server fanout,
  reconnect enrollment, resync, delivery ordering, or backpressure recovery.
- The queue is bounded at the current WebSocket endpoint, but it has no
  specified overload state, delivery receipt protocol, sequence ledger,
  coalescing rule, or controlled-close policy.
- `StateGroupSyncService` already has backend-only exact-base snapshot/delta,
  checksum, capability, and removed-group contracts. It is not yet adapted to
  the policy-filtered gameplay-mirror WebSocket envelope or the Godot consumer;
  its current tests are not live transport evidence.

### Planned by this document

- Server-issued reconnect enrollment, binding lease renewal and revocation.
- Snapshot-plus-delta resync, delivery sequence and receipt semantics.
- Duplicate, old-epoch, gap, and out-of-order handling.
- Bounded outbound delivery with explicit overload behavior.
- Capability negotiation and Godot live recovery evidence.

### Explicitly unstarted

- End-to-end reconnect/resync through a real Godot WebSocket connection.
- Real Godot receipt/gap/ordering behavior against a running backend.
- Production identity adapter, external account login, federation, durable
  session storage, prediction/rollback completion, and persistent delivery
  queues.

### External-condition dependencies

- A trusted server-side issuer for a fresh local enrollment must be identified
  and exercised by the runtime proof. The current code creates a credential
  through an in-process service; it does not establish how a launcher receives
  a replacement credential after disconnect. Until that issuer and its launch
  handoff are evidenced, no phase may claim live reconnect completion.
- Production `authenticated_session` remains outside this plan. It requires a
  separately approved upstream identity adapter; this plan must continue to
  fail closed when that adapter is absent.
- Phase 6 requires a runnable Godot executable and a reproducible local
  backend launch. A headless script parse or a local bridge-only probe is not
  a substitute.

## This Plan Does Not Own

- Reimplementation of one-time trusted-local binding, opaque session creation,
  peer-host checks, existing session-scoped subscription filtering, the
  Gameplay event store, the committed outbox, or the authority event bus.
- New actor/player/fixture authorization, scene-derived identity, arbitrary
  container or inventory access, or client-selected projection fields.
- Gameplay settlement, world-state persistence, session login/federation,
  production durable transport, client-side prediction/rollback, or a second
  mirror source/event bus/session contract.
- Making Godot local presentation, cached projection, delivery receipt,
  snapshot, delta, animation, or predicted overlay into authority evidence.

## Source Specs

- `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-08-03-websocket-session-identity-and-mirror-scope-design.md`
- `docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/2026-08-03-websocket-session-identity-and-mirror-scope-plan.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-31-coupled-event-store-and-authority-bus-design.md`
- `docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-31-coupled-event-store-and-authority-bus-plan.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/character-gameplay-foundation/2026-07-23-godot-runtime-mirror-and-prediction-design.md`
- `backend/app/gameplay/state_group_sync.py` and its focused contract tests,
  as an implementation dependency rather than a source-of-truth design spec
- `docs/superpowers/plans/world-character-siming-authority-mainline/character-gameplay-foundation/README.md`
- `docs/harness.md`
- `docs/kimi分析/2026-08-03-活跃plan与spec进度分析.md` as a progress analysis only, not design authority.

## Preconditions

1. Preserve the existing source-of-truth hierarchy and the implemented
   `WebSocketSessionAuthService -> WebSocketConnectionContext ->
   GameplayMirrorSessionAccessService` boundary.
2. Run the focused current baseline before the first code change; read its
   generated report rather than relying on an old passing status.
3. Add failing focused tests before each behavior change. No phase begins its
   implementation tasks until its listed failing tests genuinely fail for the
   missing behavior.
4. No new dependency. Use the existing FastAPI, asyncio, Pydantic, Godot,
   pytest, and harness surfaces.
5. Before adapting delta transport, collect evidence for the present
   `gameplay_runtime_state_projection` revision fields, the existing
   `StateGroupSyncService` exact-base/checksum/capability contract, and the
   `GameplayRuntimeStateMirrorConsumer` replacement semantics. The current
   projection lacks a delivery sequence and the consumer has no delta applier;
   the existing backend sync model cannot simply bypass Godot view filtering.
6. Before Phase 1 is considered implementable, record the authoritative local
   enrollment issuer and the launcher-to-Godot handoff in the runbook and
   focused proof. Do not invent a client-side credential refresh source.

## Non-Negotiable Invariants

- The Gameplay event store and authority projections remain the only gameplay
  truth. Transport failure, disconnect, queue saturation, receipt loss,
  renewal failure, resync, or Godot state may not mutate, reverse, retry, or
  block a committed authority batch.
- The existing committed-outbox/authority-bus pipeline remains the sole
  committed-event delivery source. The existing configured Phase 3 publisher
  remains the sole mirror-view source.
- A connection context owns only transport facts. A session binding owns only
  backend-issued reader identity and scope. Neither owns gameplay authority.
- A reconnect never restores a prior actor scope merely because it presents an
  old `session_ref`, connection reference, actor ID, player ID, receipt,
  cached snapshot, or Godot node/fixture identity. It needs a fresh,
  server-issued enrollment and a new binding.
- Client messages never grant actor, player, fixture, container, inventory,
  state group, projection field, capability, world fact, or authority command.
  Client capability offers and revision/receipt values are preferences or
  observations only and are validated fail-closed.
- Snapshots and deltas are disposable policy-filtered transport projections,
  not persisted truth, event replay, command receipts, or a Godot authority
  cache. Godot consumes them read-only.
- An unsupported schema/capability, mismatched actor, foreign session,
  revoked/expired binding, stale epoch, invalid sequence, unknown receipt, or
  malformed message produces a typed rejection and no scope expansion.
- Queue limits cover every retained outbound payload and metadata structure.
  No unbounded retry list, per-actor cache, receipt ledger, task set, or
  reconnect loop may be introduced.

## Protocol And Lifecycle Decisions

### Owner and lifecycle table

| Item | Sole owner | Lifecycle | Client input is allowed to do | Reject when | Required evidence |
| --- | --- | --- | --- | --- | --- |
| enrollment credential | backend enrollment issuer | `issued -> consumed`, `expired`, or `revoked` | present an opaque value only | unknown, replayed, expired, revoked, peer mismatch, unsupported protocol | issuer/replay/expiry/peer focused tests and live issuance trace |
| session binding | `WebSocketSessionAuthService` | `bound_active -> renewal_due -> revoked`, `expired`, or `disconnected` | receive opaque reference; request renewal only with a backend-issued renewal enrollment | foreign/old binding, lease elapsed, revoked binding, missing renewal enrollment | binding state-machine tests and WebSocket trace |
| connection epoch | WebSocket connection context | assigned once per accepted socket; invalid on close | echo only in receipts/resync requests | stale/foreign epoch | old-epoch and reconnect WebSocket/Godot tests |
| allowed actor scope | enrollment issuer and binding service | fixed for one binding; discarded on disconnect/revocation | select one already granted actor | actor not in active binding scope | multi-actor and reconnect scope-narrowing tests |
| negotiated capabilities | backend policy at bind | immutable for one binding; renegotiated only by new binding | offer supported versions/features | missing mandatory snapshot support, invalid offer, no compatible required schema | capability matrix and downgrade tests |
| snapshot/delta projection | existing backend publisher and projection repository | generated after authorized subscription or committed refresh; discarded after send | request resync for a subscribed actor | unbound/unsubscribed/out-of-scope actor, incompatible negotiated schema | filtered payload, snapshot replacement, delta/resync tests |
| delivery sequence and receipt | connection delivery service | sequence increases per connection epoch; bounded receipt window is discarded on close | acknowledge an already sent sequence or report a gap | no matching sent sequence/epoch, duplicate-invalid receipt, receipt outside retained window | server sequence and Godot duplicate/order tests |
| outbound queue | connection delivery service | bounded `ready -> overloaded -> resync_required -> closing/closed` | no direct mutation | queue full, disconnected, revoked or expired session | saturation and controlled-close trace |

### Enrollment, renewal, revocation, and reconnect

1. Keep `trusted_local_launch` as the only implemented development enrollment
   kind and retain its loopback, one-time, and expiry checks. Do not turn an
   old binding or Godot cache into an enrollment credential.
2. Add a backend-owned, opaque one-time **renewal enrollment** record rather
   than renewing a `session_ref` in place. The issuer selects its principal,
   allowed actors, expiry, issuance reason, and optional replacement scope;
   the client receives no authority-bearing subject fields.
3. A client asks for renewal only through its currently active, unrevoked
   connection. The server returns a replacement enrollment material or a typed
   denial. The next socket must bind that replacement material and undergo the
   same peer and replay checks. It receives a new `session_ref` and a new
   connection epoch.
4. The exact local issuer integration is a Phase 1 evidence gate, not an
   assumption. If only a launcher can issue enrollment, the protocol must
   expose a launcher handoff, not a browser/Godot self-issuance route. If a
   server endpoint is proposed, it must prove which pre-existing trusted
   server-side context authorizes it; otherwise it is rejected from scope.
5. Revocation is server-initiated. It invalidates the binding, removes its
   subscriptions and connection registration, drops queued mirror data, and
   sends a typed control notification when the socket is still writable; a
   controlled close follows if continued delivery is unsafe. Revocation never
   changes Gameplay events/projections or creates a new scope.
6. Disconnect clears connection-local state immediately. Reconnect begins
   `unbound`; it must bind a fresh enrollment, negotiate capabilities, receive
   only the new backend-selected scope, subscribe again, and obtain snapshots.

### Delivery envelope, resync, and ordering

1. Preserve the existing filtered `gameplay_runtime_state_projection` as the
   one projection family. Add a versioned transport wrapper or explicitly
   versioned fields only after Phase 0 contract tests pin the compatibility
   shape. Do not create a parallel mirror event or replay protocol.
2. Every sent snapshot or delta must carry a server-assigned
   `connection_epoch`, monotonically increasing `delivery_sequence`,
   `delivery_kind` (`snapshot` or `delta`), actor reference, negotiated
   projection schema, and source revision information. The server assigns all
   of these fields after filtering and before enqueue.
3. A snapshot atomically replaces the consumer's confirmed projection for its
   actor. Omitted groups are removed. A delta can apply only to a snapshot base
   that matches its actor, epoch, negotiated schema, configuration/facade
   revision, group base revision, and delivery predecessor rule.
4. Deltas are optional after capability negotiation. If a compatible, bounded
   delta cannot be constructed from the already published backend view, the
   server sends a snapshot. It must not fabricate a delta from Godot state or
   create another projection source.
5. The consumer ignores an already accepted `(connection_epoch,
   delivery_sequence)` as a duplicate. It rejects old epochs and buffers no
   unbounded out-of-order data. Any forward gap, invalid base revision, or
   incompatible group marks that actor `resync_required`, stops applying its
   later deltas, and requests one scoped snapshot.
6. A delivery receipt is transport telemetry, not authority acknowledgement.
   It confirms only that a specific already-sent sequence was consumed. It may
   drive queue release, loss detection, trace diagnostics, and resync choice;
   it cannot acknowledge Gameplay settlement, authorize a command, widen a
   scope, or cause event replay.
7. The server retains only a configured bounded receipt window per live
   connection. A receipt outside that window forces a fresh snapshot (or typed
   denial after expiry/revocation); it never causes an unbounded replay search.

### Backpressure and capability policy

1. Replace the current anonymous `Queue(maxsize=128)` behavior with a named,
   configuration-owned delivery policy: separate bounded control capacity from
   bounded projection capacity, maximum dirty actors, receipt window, and
   close threshold. Defaults, validation, and operational limits must be
   explicit and tested.
2. On a full projection queue, mark only that connection/actor dirty and
   coalesce subsequent projection updates into the latest server-built view.
   Do not enqueue every missed delta, grow an unbounded backlog, or invoke
   authority code. Queue recovery sends a resync-required control notice and
   one fresh snapshot per affected subscribed actor.
3. If the control notice or replacement snapshot cannot be queued within the
   bounded policy, revoke delivery for that connection and close it with a
   documented transport reason. Its next attempt still requires a fresh
   enrollment; other connections and authority truth continue normally.
4. Capability offer fields are preferences only: protocol version, supported
   projection schemas, snapshot support, delta support, and receipt support.
   The backend chooses an intersection constrained by its projection policy
   and must require snapshot support. It may disable delta/receipts for a
   compatible older client. It never treats a capability as permission to add a
   state group or field.

### Godot local recovery state machine

```text
disconnected
  -> enrollment_available
  -> binding
  -> scope_granted
  -> synchronizing (subscribe + complete snapshots)
  -> live
  -> resync_required (gap, invalid delta, queue notice, schema transition)
  -> synchronizing

Any disconnect / expiry / revocation
  -> disconnected (clear scope, confirmed projection, delivery counters,
                    pending projection requests, and presentation-only cache)
```

The bridge may show a presentation-only stale/synchronizing state, but it must
not reuse an old actor scope, convert stale cached data into confirmed data,
or automatically retry a consumed credential. Prediction work remains out of
scope; any pre-existing local overlay must remain separate from confirmed
projection and be cleared or marked unknown by the existing prediction design.

## Phase 0: Failing Tests And Contract Completion

### Objective

Freeze the extension contract before altering live delivery. Establish exact
owners, message fields, state transitions, typed error codes, compatibility
rules, and evidence boundaries for renewal, revocation, sequence, receipt,
snapshot/delta, queue overload, and capabilities.

### Allowed file scope

- `backend/app/services/websocket_session_auth_service.py`
- `backend/app/services/gameplay_mirror_session_access_service.py`
- `backend/app/gameplay/godot_mirror_delivery.py`
- `backend/app/ws_protocol.py` and `backend/app/main.py` only for typed
  envelope parsing/serialization seams
- `backend/tests/test_websocket_session_auth_service.py`
- `backend/tests/test_websocket_connection_context.py`
- new focused WebSocket/mirror protocol tests under `backend/tests/`
- `scripts/interaction/GameplayMirrorBridge.gd`,
  `scripts/interaction/GameplayRuntimeStateMirrorConsumer.gd`, and their
  existing static/probe tests only for contract-facing assertions
- `scripts/verification/verify_godot_gameplay_mirror.py`,
  `.harness/profiles/godot-gameplay-mirror.json`, `docs/harness.md`, and
  `docs/INDEX.md` only if the profile contract/output changes

### Failing tests to write first

- A renewal request cannot accept `principal_ref`, actor/player/fixture refs,
  scope, or client-issued credential material.
- A binding/session/receipt model rejects unknown fields and lacks no owner,
  expiry, epoch, state, sequence, or error-code contract.
- Snapshot and delta envelope compatibility rejects an unnegotiated schema,
  absent required sequence fields, malformed base/target revisions, and
  forbidden fields before Godot receives a payload.
- A receipt for a foreign, stale, unsent, or out-of-window sequence is typed
  rejected without changing authority state or read scope.
- A full queue/controlled-close result cannot mutate the committed store,
  outbox state, source view, or another connection's delivery state.
- The Godot consumer test fails for a duplicate, stale epoch, gap, and delta
  before a compatible snapshot base exists.

### Implementation tasks

1. Add narrow typed request/result/error models and protocol-versioned
   envelope fixtures. Document the owner/lifecycle/rejection table in the
   session/mirror design before extending code.
2. Define version compatibility: old bind/subscribe/snapshot behavior remains
   available only for an explicitly supported baseline capability profile;
   new semantics are opt-in by negotiated capability.
3. Define a finite set of error codes and control messages for `renewal_*`,
   `session_*`, `mirror_sequence_*`, `mirror_receipt_*`,
   `mirror_resync_required`, `mirror_backpressure`, and
   `mirror_capability_*`. No handler returns an ambiguous success/failure
   string.
4. Add a focused Phase 4 section to the mirror verifier/profile describing
   what is backend-only, WebSocket-integrated, local-Godot, and live-Godot
   evidence. Do not upgrade the profile claim yet.

### Exit criteria

- All listed tests fail before implementation, then pass only after the
  corresponding behavior exists.
- Every new field, state, sequence, receipt, and capability has exactly one
  owner, finite lifecycle, typed denial path, and named evidence test.
- The design explicitly identifies the local enrollment issuer evidence gap;
  no invented refresh path appears in an implementation task.

### Evidence artifacts

- Focused pytest log and protocol fixture assertions under
  `.harness/verification/`.
- Updated `godot-gameplay-mirror` report with an explicit Phase 4 contract
  boundary, still marked as not live delivery proof.

## Phase 1: Reconnect / Enrollment Lifecycle

### Objective

Introduce server-owned renewal enrollment, binding lease, explicit revocation,
and reconnect lifecycle without reusing a prior binding or widening scope.

### Allowed file scope

- Phase 0 backend files
- `backend/app/config.py` and `backend/tests/test_config_runtime_modes.py` for
  bounded server-owned lease/credential policy only
- `backend/app/main.py` for WebSocket routing and disconnect cleanup
- relevant backend focused tests and the Godot bridge/probe files listed in
  Phase 0
- verification/profile/docs files only when the new evidence is implemented

### Failing tests to write first

- Consumed, expired, revoked, remote-peer, and unknown replacement enrollments
  cannot bind a new socket.
- A renewal request produces only a server-selected one-time replacement
  enrollment; it cannot preserve or widen the old actor tuple by client input.
- New binding after reconnect receives a new session reference and epoch; the
  old binding cannot subscribe, snapshot, receipt, or receive fanout.
- Revocation removes subscription and connection registration, drops its
  pending delivery state, and leaves the related Gameplay transaction/outbox
  unchanged.
- A narrowed replacement scope rejects an actor allowed by the old binding.
- Godot disconnect/reconnect unit/probe behavior fails if it binds before a
  new enrollment arrives or retains any old confirmed projection/scope.

### Implementation tasks

1. Extend the session service with bounded records for binding lease, revocation
   reason/time, replacement enrollment, and cleanup. Existing direct-handler
   compatibility must remain explicitly unbound test behavior.
2. Implement the previously evidenced trusted issuer integration. It must
   mint a short-lived one-time replacement enrollment from backend-held
   principal/scope policy, never from Godot payload fields.
3. Route typed renewal and revocation control handling through the connection
   context. On close, expiry, or revocation, remove the exact matching session
   registration, subscriptions, queue/receipt state, and any scheduled mirror
   send task.
4. Modify the Godot bridge to wait for a newly supplied enrollment, bind it,
   accept only the new `websocket_session_bound` scope, and enter
   synchronizing. Do not add autonomous retry of a consumed credential.
5. Emit redacted lifecycle trace records containing opaque binding/connection
   correlation references and reason codes, never raw enrollment credential.

### Exit criteria

- Reconnect is demonstrably a fresh enrollment plus fresh binding, not session
  resurrection.
- Lease expiry and revocation revoke transport delivery only; backend truth,
  event-store sequences, and outbox delivery are unchanged.
- Replacement scope is entirely backend selected and can be narrower than its
  predecessor.

### Evidence artifacts

- Backend state-machine and WebSocket reconnect/revocation pytest logs.
- Redacted renewal/revocation trace demonstrating old/new epoch and old/new
  scope denial.
- Godot probe report marked local-only until Phase 6.

## Phase 2: Snapshot + Delta Resync

### Objective

Deliver authorized complete snapshots and optional bounded deltas from the
existing backend view, with snapshot convergence as the only recovery path.

### Allowed file scope

- `backend/app/gameplay/godot_mirror_delivery.py`
- `backend/app/gameplay/godot_mirror_projection.py`
- `backend/app/gameplay/phase3_mirror_source.py`
- `backend/app/services/gameplay_mirror_session_access_service.py`
- `backend/app/main.py` and typed protocol models
- focused mirror/source/WebSocket tests
- Godot bridge/consumer and their runtime probe only

### Failing tests to write first

- A scoped snapshot atomically replaces groups and removes groups omitted by
  the replacement snapshot.
- A delta generated from a committed refreshed view applies only to its
  matching actor, epoch, negotiated schema, configuration/facade revision, and
  group base revision.
- Source unavailable, subscription removed, scope revoked, or schema mismatch
  returns a typed snapshot/resync denial with no stale cached payload.
- A resync request for an unsubscribed/out-of-scope actor cannot create a
  subscription or return a projection.
- Snapshot equivalence after missed delta matches a fresh projection from the
  existing backend publisher; no test reads Godot cache as its oracle.

### Implementation tasks

1. Reuse `StateGroupSyncService` exact-base, checksum, capability, and
   removed-group semantics through a narrow adapter over successive already
   policy-filtered backend views. The adapter must be constructed after the
   existing Godot field policy has filtered the view; it is not a second mirror
   source. Limit operations and payload bytes; when a safe typed diff is
   absent, send a complete snapshot. Do not derive a delta from raw events.
2. Add source facade/configuration and group revision metadata required to
   validate a base. Reuse the existing source revision vector and group
   projection revision where sufficient; document any added server-owned
   field and its compatibility version.
3. Make resync request a read operation through the existing session access
   service: it validates active binding, negotiated capability, allowed actor,
   and subscription, then requests a fresh source publication and snapshot.
4. Have the Godot consumer atomically replace confirmed state on snapshots.
   It applies only allowlisted delta operations to a copied confirmed base and
   changes no authority/prediction state. On any validation failure it marks
   that actor `resync_required` and sends one bounded request.

### Exit criteria

- A lost/malformed/incompatible delta converges by an authorized fresh
  snapshot, with no retained omitted group or guessed value.
- Delta delivery remains optional; snapshot-only clients stay correct.
- All payloads still originate from the existing configured publisher and
  policy filter.

### Evidence artifacts

- Source-to-snapshot/delta focused pytest log including filtered-field,
  snapshot-equivalence, and denial cases.
- Local Godot consumer runtime artifact showing atomic snapshot replacement and
  resync-required transition, explicitly labelled not live WebSocket evidence.

## Phase 3: Sequence Gap, Duplicate, Ordering, And Idempotency

### Objective

Make delivery observations deterministic per connection epoch and prove that
duplicate, old, out-of-order, and gap messages cannot corrupt confirmed local
projection or affect authority truth.

### Allowed file scope

- Phase 2 backend delivery/protocol/session-access files
- `backend/app/main.py`
- focused backend/WebSocket tests
- `scripts/interaction/GameplayMirrorBridge.gd`
- `scripts/interaction/GameplayRuntimeStateMirrorConsumer.gd`
- existing local Godot probe and verification files

### Failing tests to write first

- Server delivery sequences are strictly monotonic per connection epoch and
  cannot be supplied by a client or reused after reconnect.
- Duplicate receipt/delta is idempotently ignored; stale epoch is rejected;
  a forward gap or out-of-order base produces exactly one actor-scoped resync
  transition.
- A resync snapshot clears that actor's stale/gap state and advances the
  confirmed baseline; unrelated actor mirrors remain live.
- Receipt of an accepted message cannot mark a command, transaction, outbox
  entry, or source projection delivered/settled.
- A reconnect never accepts old-epoch delivery or receipt even when actor and
  facade revisions happen to match.

### Implementation tasks

1. Add a connection-local sequencer and bounded sent-receipt ledger owned by
   the delivery service. Assign sequence only after a payload is authorized,
   filtered, and accepted for that live connection's queue.
2. Serialize same-connection mirror sends through one ordered path. Preserve
   existing cross-connection isolation and after-commit boundary.
3. Add typed receipt and resync handling. A receipt is checked against the
   current binding and bounded ledger; it frees delivery bookkeeping only.
4. Extend Godot bridge/consumer per-actor sync state with current epoch,
   last accepted delivery sequence, confirmed revision baseline, and one
   pending resync flag. Bound all maps to currently granted/registered actors.
5. Record redacted sequence and resync reason in server and Godot traces for
   runtime comparison.

### Exit criteria

- The same test proves all four paths: duplicate ignored, stale rejected, gap
  resync requested, and snapshot convergence.
- No out-of-order payload can partially overwrite confirmed state.
- Every receipt is observably non-authoritative.

### Evidence artifacts

- Backend unit and real WebSocket ordering/receipt trace.
- Godot local runtime sequence trace containing epoch, last accepted sequence,
  duplicate/gap rejection, requested resync, and post-snapshot convergence.

## Phase 4: Backpressure, Queue Bounds, And Disconnect Handling

### Objective

Turn the current bounded queue into an explicit bounded delivery policy that
coalesces presentation updates, signals recovery, and disconnects safely when
recovery cannot be queued.

### Allowed file scope

- `backend/app/gameplay/godot_mirror_delivery.py`
- `backend/app/main.py`
- `backend/app/config.py`
- session service and protocol models only for lifecycle integration
- focused backend/WebSocket tests
- Godot bridge/consumer and probe only for control-message recovery
- mirror verifier/profile/docs only when its proof becomes stronger

### Failing tests to write first

- Saturating one connection's projection capacity does not block or mutate
  another connection, the event store, dispatcher, outbox, or publisher.
- Full queue coalesces to a bounded dirty-actor set; it does not retain every
  delta or allocate an unbounded retry task/list.
- Recovery emits one scoped resync requirement followed by one fresh snapshot
  per affected actor when capacity returns.
- Unqueueable control/snapshot recovery cleanly removes the connection and
  drops only its delivery state; a later reconnect has no old scope/queue.
- Queue/backpressure errors have deterministic telemetry and no raw payload or
  credential leakage.

### Implementation tasks

1. Introduce a validated, backend configuration-owned delivery-limit model and
   replace anonymous queue constants with named policy values. Keep it in
   memory and bounded; do not add persistence.
2. Split ordered control and projection queues with reserved finite control
   capacity. Provide exact ownership of enqueue/dequeue/cleanup and prevent
   a producer from bypassing the sequencer.
3. On projection pressure, record the actor as dirty once, discard superseded
   presentation payloads, and transition the connection to resync-required.
   The next successful recovery is a publisher-built snapshot, not a replay of
   cached raw authority events.
4. On impossible recovery, unregister the exact session/connection pair,
   invalidate its receipt ledger, and use the documented controlled-close path.
   Do not revoke world truth or cause outbox retry.
5. Update Godot control handling to stop applying deltas while resync is
   required and to clear local state on disconnect as already required.

### Exit criteria

- Queue memory, actor-dirty set, receipt window, and sender tasks have tested
  finite limits and cleanup paths.
- One slow/disconnected connection cannot delay committed authority delivery or
  starve a healthy authorized connection.
- Recovery either converges by snapshot or terminates the connection with a
  fresh-enrollment reconnect requirement.

### Evidence artifacts

- Deterministic saturated-queue backend/WebSocket test trace with two
  authorized sessions and event-store/outbox before/after hashes.
- Redacted backpressure/controlled-close report and local Godot recovery probe.

## Phase 5: Capability Negotiation

### Objective

Negotiate a server-selected, immutable per-binding delivery profile without
letting a client capability offer alter read scope, visibility, or authority.

### Allowed file scope

- session auth and access service models
- `backend/app/ws_protocol.py`, `backend/app/main.py`, and delivery code
- `backend/app/config.py` only for server-supported capability policy
- focused backend/WebSocket tests
- Godot bridge/consumer/probe and mirror verification files

### Failing tests to write first

- Missing snapshot support, unknown required capability, malformed version,
  and empty compatible schema set are rejected before subscription.
- A client that offers delta/receipt cannot obtain an unauthorized group,
  actor, field, or a new protocol behavior outside backend policy.
- A snapshot-only negotiated client receives snapshots and remains resync-safe;
  an incompatible client has no active subscription/delivery registration.
- Capability profile is immutable for its binding and cannot be changed by a
  later subscribe, receipt, resync, or reconnect message.
- Godot refuses a projection/control message outside the capability profile
  received from the current binding.

### Implementation tasks

1. Include a small explicit capability offer in bind and a backend-selected
   capability result in `websocket_session_bound`. Preserve the original
   protocol-version validation and make new fields optional only for the
   explicitly supported baseline.
2. Store the selected profile with the binding/context, not in a Godot node or
   client cache. It is discarded on disconnect/revocation and renegotiated for
   every fresh binding.
3. Gate delta/receipt/resync control behavior on the selected profile while
   retaining safe snapshot-only operation.
4. Have the bridge expose only the negotiated local feature switches; it must
   neither advertise nor emulate a server-disabled feature.

### Exit criteria

- Every active mirror connection has one server-selected finite capability
  profile, and no profile grants identity, scope, groups, or fields.
- Snapshot-only fallback and incompatible denial are both covered by focused
  backend, WebSocket, and Godot tests.

### Evidence artifacts

- Capability negotiation matrix report with accepted intersection and denial
  paths.
- Godot probe output proving snapshot-only fallback and incompatible refusal,
  marked local-only until Phase 6.

## Phase 6: Godot Runtime Recovery And Live WebSocket Proof

### Objective

Produce reproducible real backend-to-Godot evidence for initial bind, live
after-commit delivery, disconnect, fresh enrollment/reconnect, resync, and
local presentation recovery.

### Allowed file scope

- Existing backend delivery/session/protocol/configuration files only for
  defects revealed by the runtime proof
- `scripts/autoload/BackendBridge.gd`
- `scripts/autoload/LocalPresentationBus.gd`
- `scripts/interaction/GameplayMirrorBridge.gd`
- `scripts/interaction/GameplayRuntimeStateMirrorConsumer.gd`
- `scenes/phase0/GameplayMirrorBridgeProbe.tscn` or a narrowly named live
  mirror runtime probe under `scenes/phase0/`
- corresponding `scripts/verification/` Godot probe and mirror verifier
- `.harness/profiles/godot-gameplay-mirror.json`, `docs/harness.md`, and
  `docs/INDEX.md` only to describe the newly real runtime proof

### Failing tests to write first

- A real Godot process connected through `BackendBridge` fails until it proves
  live bind, allowed subscription, and a server after-commit projection.
- The live test fails if disconnect leaves old scope, confirmed groups,
  sequence state, or pending resync state in the Godot consumer.
- The live test fails if reconnect uses an old credential/session/epoch, or if
  the new server scope excludes an old actor but Godot still requests/renders
  it.
- The live test fails if intentionally dropped/duplicated/out-of-order
  delivery does not reach `resync_required` and then converge through a fresh
  server snapshot.
- The live test fails if an induced client delivery overload affects the
  committed Gameplay transaction or a healthy subscriber.

### Implementation tasks

1. Build a deterministic live probe using the existing backend launcher and
   `BackendBridge`, with an explicit server-issued enrollment handoff. It must
   create committed Gameplay source changes through backend test/setup code,
   not Godot local mutation.
2. Capture initial snapshot, one after-commit update, forced disconnect,
   replacement enrollment/new binding, changed/narrowed scope, full snapshot
   recovery, and one controlled gap/backpressure scenario.
3. Compare backend-filtered projection revisions and actor/group contents with
   the Godot consumer's final confirmed state. The comparison must exclude
   presentation-only counters and must not inspect a Godot cache as authority.
4. Persist a run-id evidence package: backend WebSocket trace, redacted
   enrollment/epoch/sequence trace, Godot log, Godot runtime JSON, final
   projection comparison, and screenshot or scene-runtime assertion.
5. Update the mirror harness report scope only after the live probe passes.
   Keep production identity, persistence, and prediction explicitly excluded.

### Exit criteria

- A real Godot runtime proves authorized live WebSocket mirror delivery and
  recovery after disconnect/reconnect with a new enrollment.
- It proves sequence gap/duplicate safety, snapshot convergence, and bounded
  backpressure isolation against the running backend.
- The resulting Godot presentation state is demonstrably a read-only filtered
  projection matching the backend result at the declared final revision.

### Evidence artifacts

- `.harness/verification/godot-gameplay-mirror-report.json` and Markdown
  report with `live WebSocket-to-Godot` evidence explicitly named.
- Run-id archive containing backend WebSocket trace, Godot runtime log/JSON,
  final revision comparison, and runtime screenshot or target-node assertion.
- Focused pytest log covering all backend and WebSocket fault paths.

## Failure-Mode Matrix

| Failure mode | Backend required behavior | WebSocket delivery behavior | Godot required behavior | Authority outcome |
| --- | --- | --- | --- | --- |
| replayed/expired/remote enrollment | deny before binding; preserve audit reason | no registration or projection | remain unbound; do not retry consumed credential | unchanged |
| renewal issuer unavailable | typed renewal denial; retain only still-valid active binding | no replacement scope sent | show presentation-only renewal failure; clear on terminal expiry | unchanged |
| binding expired/revoked | invalidate binding, subscriptions, queue, receipt ledger | best-effort typed control then close/unregister | clear scope/projections/counters; wait for fresh enrollment | unchanged |
| client asks foreign actor/group/field | deny using binding/policy | no payload and no subscription | do not create a consumer route | unchanged |
| source unavailable/filter rejects | remove stale publisher view; typed snapshot denial | do not send old cached projection | mark actor unavailable/resync required, not confirmed | unchanged |
| delta base/schema invalid | no server fallback based on client data; require fresh snapshot | send scoped resync/snapshot when allowed | stop deltas, retain no guessed value, request resync once | unchanged |
| duplicate delivery/receipt | validate bounded ledger; idempotently ignore known duplicate | no repeated state application | ignore duplicate sequence | unchanged |
| old epoch/out-of-order/gap | reject old epoch; detect unsatisfied predecessor | resync-required, then fresh snapshot | reject old; mark actor stale; converge only by snapshot | unchanged |
| projection queue full | mark only connection/actor dirty; bounded coalesce | issue control/snapshot or controlled close | stop deltas and resync; clear on close | unchanged |
| socket send/disconnect failure | unregister exact connection; discard delivery-only state | no retry against authority path | clear local confirmed state/scope | unchanged |
| receipt lost/outside window | bounded ledger expires it; snapshot resync or typed denial | never replay unbounded history | request/reapply fresh snapshot | unchanged |
| capability mismatch | deny or select snapshot-only intersection | no unnegotiated feature messages | reject incompatible messages; retain no data | unchanged |

## Authority Truth And Mirror Projection Boundary Matrix

| Concern | Authority owner | Mirror transport may do | Godot may do | Forbidden |
| --- | --- | --- | --- | --- |
| event commit, revisions, idempotency, outbox | Gameplay event store and settlement pipeline | observe only after full outbox delivery | display result only | transport/Godot rollback, retry, or settle event truth |
| actor/session scope | enrollment issuer and session auth service | route only binding-approved selection | request allowed actor only | client selecting actor/player/fixture/container/inventory scope |
| view construction and field privacy | configured backend source and Godot projection filter | enqueue already filtered projection | read confirmed fields | raw event/private field delivery or local field-policy expansion |
| snapshot/delta | backend publisher/delivery service | assign sequence, queue, resend by fresh snapshot | atomically replace/apply validated confirmed projection | treating projection as durable truth or replaying raw event history |
| gap/receipt/backpressure | connection delivery service | mark delivery state, coalesce, resync/close | report receipt/gap, enter stale/synchronizing state | receipt affecting event/outbox delivery or authority success |
| local presentation/prediction | Godot local runtime | signal presentation state only | animate/UI/cache transient state | cached/predicted state becoming world fact or command authorization |
| disconnect/reconnect | session/connection lifecycle services | discard transport state and require fresh bind | clear scope/confirmed state then resynchronize | restoring old scope/session/epoch from client cache |

## Required Verification Commands

Run focused tests at the end of each phase, read their generated evidence, and
fix failures before advancing. After any documentation/profile change, run the
documentation profile before relying on its index claim.

```powershell
# Phase-local baseline and focused tests (replace/add exact focused files as phases land)
python -m pytest -q
python scripts/verification/harness.py --profile gameplay-foundation-event-spine
python scripts/verification/harness.py --profile godot-gameplay-mirror
```

After Phase 6 has passed its live WebSocket-to-Godot proof and all predecessor
profiles above are green, run the dependent aggregate checks in this order:

```powershell
python scripts/verification/harness.py --profile embodied-interaction-foundation-all
python scripts/verification/harness.py --profile mainline-unified-runtime
python scripts/verification/harness.py --profile docs
git diff --check
```

Run the repository-wide aggregate only last, after every required focused and
dependent profile above has passed:

```powershell
python scripts/verification/harness.py --profile all
```

Required evidence review paths include:

```text
.harness/verification/godot-gameplay-mirror-report.json
.harness/verification/gameplay-foundation-event-spine-report.json
.harness/verification/mainline-unified-runtime-report.json
.harness/verification/runs/<run-id>/harness-run-report.json
```

## Acceptance Criteria

1. A server-issued one-time replacement enrollment is required for every
   reconnect; an old session, actor ID, receipt, cached projection, or scene
   fixture cannot restore scope.
2. Binding expiry/revocation removes only delivery/session state and never
   changes committed Gameplay truth, event-store sequence, outbox state, or
   publisher authority.
3. Active sessions can receive authorized snapshot-only delivery; negotiated
   capable sessions can receive validated deltas. Both converge by a fresh
   backend snapshot after loss.
4. Each projection/receipt has server-owned epoch and sequence semantics;
   duplicates are harmless, old epochs reject, and gaps/out-of-order delivery
   enter deterministic actor-scoped resync.
5. Queue/receipt/dirty-actor/sender resources are bounded and cleaned up;
   one slow connection cannot affect healthy delivery or authority settlement.
6. Negotiated capabilities are server-selected per binding and grant neither
   identity nor scope nor fields; incompatible clients fail closed.
7. Godot clears local scope and confirmed projection on disconnect/revocation,
   receives a new backend scope after reconnect, and never displays an old
   actor as confirmed under a narrowed replacement scope.
8. A real Godot process connects to a running backend and proves initial
   snapshot, after-commit update, disconnect, fresh enrollment/reconnect,
   resync convergence, and bounded backpressure isolation with reviewable
   run-id artifacts.
9. `godot-gameplay-mirror`, `gameplay-foundation-event-spine`,
   `embodied-interaction-foundation-all`, `mainline-unified-runtime`, `docs`,
   and finally `all` pass with fresh evidence.

## Deferred Work

- Production account/federated identity adapter and persistent session store.
- Cross-process or durable transport delivery queue, guaranteed mirror-event
  replay, and delivery exactly-once semantics.
- Client-side prediction/rollback completion, prediction receipt/recovery, and
  generic state-group delta support beyond the explicitly configured Phase 3
  source.
- General gameplay domain closure, persistence/checkpoint migration, inventory
  UI, container visibility policy, and arbitrary actor/observer roles.
- Production metrics/alerting and remote deployment policy beyond the bounded
  redacted traces needed for this local runtime proof.

## Rollout / Migration Considerations

1. Keep the existing trusted-local bind/subscribe/snapshot route compatible
   behind an explicit baseline capability profile while Phase 4 fields are
   added. Do not silently reinterpret a legacy message as a renewal, receipt,
   or scope grant.
2. Land protocol models, server behavior, Godot consumer behavior, focused
   tests, and profile assertions in the same small phase slice. Version any
   outward-facing envelope shape before a Godot runtime consumes it.
3. Roll out snapshot-only recovery first. Enable delta/receipt behavior only
   when both server and Godot negotiate it and the Phase 3 source has evidence
   for that actor/group.
4. Make queue limits conservative and configuration validated. A lower limit
   that triggers snapshot resync is safer than retaining unbounded projection
   history.
5. Preserve the existing after-commit observer and generic publisher seams;
   migrate the current queue callback into the new delivery service rather
   than operating two fanout mechanisms in parallel.
6. Retain legacy direct-handler tests only as explicitly unbound compatibility
   coverage. They must never be counted as network-authentication or live
   Godot delivery evidence.

## Final Definition Of Done

This Phase 4 plan is complete only when all of the following are true:

- The approved server-side local enrollment issuer is documented and proven;
  reconnect creates a new opaque binding and backend-owned scope.
- Session lease, renewal, revocation, disconnect cleanup, delivery sequence,
  receipt, capability profile, queue state, and resync state all have one
  owner, finite lifecycle, typed denial behavior, and focused evidence.
- Snapshot/delta behavior uses only the existing filtered backend publisher;
  loss, duplication, ordering failure, and pressure converge by snapshot or
  terminate delivery without changing authority truth.
- Every outbound delivery-related resource is bounded and one failed client is
  isolated from the committed outbox/event-bus/authority pipeline and other
  authorized clients.
- A live Godot WebSocket runtime, not a static check or local bridge probe,
  proves initial delivery, after-commit delivery, reconnect with fresh
  enrollment, scope recovery, resync, and failure isolation.
- The required focused, dependent, documentation, and final aggregate commands
  pass in the stated order with fresh `.harness/verification/` run-id evidence.
- Production identity, durable transport, prediction, and other deferred work
  remain explicitly excluded from the completion claim.
