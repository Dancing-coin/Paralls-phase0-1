# G2 boundary audit

Status: investigation; no G2 enforcement has been installed or accepted.

The measured fixture in this directory is not a visibility contract. In
particular, its four policies and four principals are synthetic. The current
`GameplayEvent` carries a nonempty `visibility_policy` string and arbitrary
payload, but does not provide a universal event time, holder, delay, scope,
fact type or trusted debug grant. Existing policies include `project`,
`public`, `authority_only`, `organization:summary` and `actor:<ref>`; their
meaning cannot safely be inferred from a synthetic principal name.

Both `GameplayEventStore` and `DurableGameplayEventStore` expose raw
`read_stream`, `read_events` and `get_event`. Those are used by authority
rebuild and recovery as well as application code. Treating a new wrapper as
enforcement while consumers retain those routes would not meet G2. Separate
trusted authority recovery from principal-facing projection, trace actual
callers, and verify each exposed path. For example,
`CharacterCombatTargetCatalog.project_character_targets` reads presence,
faction and life streams, while
`_handle_embodied_interaction_session_projection_pull` reads a session stream
and emits an allowlisted projection. The latter currently receives no
connection context; whether any additional outer gate applies needs a full
route-specific test before drawing an access-control conclusion.

The session-pull route is also used by the Godot verification probe and its
backend runner; those currently connect without a session binding. Its domain
service labels these events `session_public_safe`, publishes a room-scoped
outbox projection, and excludes participant private terms. This establishes a
compatibility dependency and a field allowlist, not principal/time-aware G2
authorization. Neither the custom policy name nor the room audience alone
specifies the v2 visibility class, observer eligibility or delivery delay.
Changing this route needs a documented trusted binding and a compatible probe,
plus tests of both the bus and stored-event fallback projections.
On 2026-11-10 a two-connection `TestClient` probe against `component_app`
created a handshake on one unbound `/ws` connection and pulled its first
projection by session ID on a second unbound connection. The response included
the initiator and participant references. The production ASGI wrapper forwards
ordinary envelopes to the runtime; this component test does not establish
network exposure or prove the production process path. `session_public_safe`
alone does not establish whether this audience is authorized. Treat this as an
unresolved access boundary, not proof that the projection is secret or that
principal-aware enforcement is installed.
On 2026-11-10, `D:/Temp/paralls-g0-py312/Scripts/python.exe -m pytest
backend/tests/test_embodied_interaction_session.py -q` reported 7 passed with
6 deprecation warnings; this is backend test evidence, not a Godot run.

## Session audience contract (product approved)

On 2026-11-10 the user supplied the session audience rules and subsequently
approved them as product rules for implementation. They distinguish authenticated participants,
observers with authoritative perception, recipients with authorized delivery,
and separately authorized and audited debug access. Each fact requires
principal-specific field eligibility and known time; missing evidence denies
access. Public action does not imply identity disclosure. Historical replay
uses historical perception and delivery, not a reader's current location.
Bindings, leases and permission must be checked on pull and immediately before
send. Denial, response and cursor must not reveal protected session existence.
An unbound connection, client-supplied actor or session ID, fixed demo room,
and the drought-advisory jurisdiction scope are not authorization evidence.

The existing binding has a backend-issued principal, actor scope, connection
epoch and lease; the session owner's proposed event includes participant refs.
These two facts alone do not establish which other identities or fields were
disclosed to each participant, a per-principal known time, historical perception
or authorized delivery. The session's `participant_observed` event concerns
terminal participant observation, not proof of a third party's perception.
The projection pull currently receives no connection context. Before changing
the route, trace authoritative disclosure, world and scene instance, perception
and delivery records and their historical revisions, plus the actual send-time
binding recheck. Freeze participant, observer, delayed delivery, private field,
revocation, expiry, reconnect and historical replay cases. Product approval does
not establish implementation or acceptance; performance expansion remains
paused under the recorded gate, and D2–D10 remain open.

The session binding in `websocket_session_auth_service.py` carries a
backend-issued `principal_ref`, actor scope, connection epoch and lease. A
caller-supplied principal or a hardcoded debug name cannot replace that
binding. `event_schema_registry.py` currently registers event identities and
digests, not FactType visibility, delivery, or time policies. Existing world
time structures have their own timeline and exact coordinate semantics.
Unknown time and unknown authorization inputs must not become immediate
visibility or a default permission.

For the first implementation unit, identify one real principal-facing route
and its authoritative source of scope, policy, time and permitted fields;
freeze allowed, denied, unknown, delayed, replay and durable-store behavior
before implementation. Verify that no sibling endpoint bypasses that boundary.
Only then extend coverage by domain. General authority epoch fencing needs a
persisted stream/scope writer registration and an atomic check in both store
implementations, including handoff, crash recovery and exact-retry semantics.
Connection epochs are not a substitute for that authority epoch.

The previously proposed 10% / 40 ms figures are an authorized provisional
engineering budget for the synthetic fixture, not evidence that any real
principal-facing implementation meets it. D6 remains open for production
volume, tail latency, caching and paired measurements; D2-D5 and D7-D10 are
also open. G1 remains complete only for its selected twelve-unit batch.
