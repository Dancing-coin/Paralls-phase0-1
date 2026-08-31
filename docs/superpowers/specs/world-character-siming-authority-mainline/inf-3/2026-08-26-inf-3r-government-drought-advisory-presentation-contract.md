# INF-3R Government Drought Advisory Presentation Contract

Status: `implemented and verified narrow presentation vertical; generic subscription remains blocked`

## Purpose And Matrix Preflight

This contract closes the user-facing delivery gap for the already implemented
INF-3R Government advisory truth row. It is not a second Government operation
and writes no fact. Its sole product loop is: a project-authorized client can
see an already committed, project-visible drought advisory for one backend
granted jurisdiction.

Matrix preflight result: `existing_row_extension` of
`government:jurisdiction:drought-advisory@1`.

| Check | Result |
| --- | --- |
| fact/source/outcome collision | none: this reads the existing advisory projection and appends no event |
| owner collision | none: `GovernmentAuthority` remains the only truth owner |
| event/stream collision | none: no event or stream is created |
| privacy | fixed project scope; binding may only narrow to named jurisdictions |
| receipt/replay | authority receipt and Government full/tail reader remain unchanged; transport acknowledgement is disposable telemetry |
| lifecycle/package pins | no package or lifecycle interpretation is added |

## Fixed Contract

| Field | Literal rule |
| --- | --- |
| operation key | `presentation:government:drought-advisory@1` |
| source | committed `gameplay.government.drought_advisory_issued@1` only |
| source reader | `GovernmentAuthority.drought_advisory_view_for` full and checkpoint-tail reader |
| source scope | event and projected view must be `project` |
| authority | existing `GovernmentAuthority`; presentation code is read-only and cannot call an append method |
| client scope | `allowed_government_drought_advisory_jurisdiction_refs` is server-issued in the opaque WebSocket enrollment/binding; the client never supplies it |
| selection | a client may request exactly one jurisdiction already in its binding; unknown, missing, duplicate, expired, revoked, or unbound scopes fail closed |
| delivery | exact `government_drought_advisory_delivery` message through the existing WebSocket connection and queue |
| projection | fixed `government_drought_advisory.project.v1`, containing only jurisdiction, advisory refs, source revision vector, and projection hash |
| pin | every snapshot/delivery is rebuilt from the Government view and carries that view's source revision vector and hash |
| lifecycle | disposable subscription and transport state only; disconnect/renewal/revocation drops it without modifying committed advisory truth |

The local launcher profile is the only trusted-local source of the jurisdiction
scope. It may issue an empty advisory scope for actor-only sessions; it may not
accept scope fields from the HTTP launch request, WebSocket enrollment, or
subscription request.

## Exact Delivery Rules

1. `gameplay_government_drought_advisory_subscribe` accepts a single
   `jurisdiction_ref` as a selection, verifies it against the current binding,
   and returns a snapshot only when a project-visible Government view exists.
2. After the existing outbox dispatcher has marked every entry in a committed
   transaction delivered, the presentation consumer inspects only the exact
   topic `world.government.drought_advisory_projection` with audience `project`.
   It re-reads the fixed Government view, rather than trusting the outbox
   payload as authority truth.
3. Only sessions already subscribed to the same server-granted jurisdiction
   receive the rebuilt delivery. A wrong topic, audience, event type,
   jurisdiction, view, or source vector produces no delivery and no mutation.
4. The existing connection sequence/receipt ledger is used. A transport failure
   removes the disposable presentation subscription and triggers the existing
   transport revocation path; it never retries, compensates, reverses, or
   changes the advisory event.

## Zero-Write / No-Leak Cases

All of these are read-side rejections and preserve both the event store and
Government projection: missing session, no granted jurisdiction, caller-picked
foreign jurisdiction, inactive subscription, malformed scope, stale/closed
binding, unavailable or non-project view, wrong outbox topic/audience,
malformed event/vector, duplicate scope selection, and a connection delivery
failure. A reconnect must obtain a fresh backend-issued enrollment and then
subscribe again.

## Explicit Exclusions

This does not create a generic project subscription, router, registry,
coordinator, writer, bus, owner, settlement path, policy engine, or Godot
truth cache. It cannot deliver actor state through the advisory channel or
deliver advisories through an actor facade. It does not create water controls,
permits, tax, payment, material, inventory, production, weather, maintenance,
social, population, fanout, compensation, revocation, or enforcement facts.

## Verification Evidence

Focused RED-to-green tests must prove authorized snapshot/delivery, foreign
scope zero-leak, exact outbox filtering, disconnect/renewal scope disposal,
delivery failure isolation, source revision/hash retention, and no authority
write. The independent Harness must exercise the full committed Government
advisory -> dispatched outbox -> authorized presentation path and a
checkpoint-tail Government read.

## Main Scene Boundary

The production transport/consumer contract is implemented and testable through
the existing mirror probe surface. `MainDemo` does not instantiate the generic
Gameplay mirror bridge, so this row does not claim a visible MainDemo alert UI.
Adding a user-facing advisory panel is a separate presentation-product contract:
it must select a fixed project/jurisdiction display scope and cannot widen the
session grant or alter Government truth. This limitation does not weaken the
verified backend/WebSocket/Godot consumer boundary.

Godot headless probe evidence: `GameplayMirrorBridgeProbe.tscn` passed with
`godot-runtime-gameplay-mirror-bridge-verified`, including foreign-jurisdiction
rejection, granted advisory snapshot/delivery, sequence handling, and cache
clear on disconnect.
