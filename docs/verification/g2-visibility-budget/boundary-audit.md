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

### Existing evidence sources traced on 2026-11-10

`L1RuntimePerceptionBridge` builds actor-specific frames from projected raw
facts and occupancy, including capture clock and target references. The
inspected adapter does not itself establish a committed, replayable session
field disclosure or identity-recognition grant. Its inputs and producer trust
must be traced before using a frame as authorization.

The inspected `/ws` raw-fact path calls `_admit_local_coordination_signal`,
which authenticates the optional coordination signal and strips that signal
when admission fails; it does not by itself reject the enclosing raw fact.
`_ingest_l1_world_fact_foundation` can update the in-memory occupancy service
from spatial-access facts, and `_messages_from_projected_l1_facts` supplies
its current snapshot to the perception bridge. `SpatialOccupancySnapshot`
contains field and zone state but no world, scene-instance identity or
authority revision. This static trace does not prove an external exploit or
assess all upstream gates. It does establish that an adapter which treats the
current snapshot or bridge frame alone as historical, authenticated session
perception would not satisfy the approved provenance requirement.

`EmbodiedSpatialSource` is a stronger, separate position source: it checks a
controller binding and deployment scope, commits sampled position and scene
instance, and returns event and stream-revision evidence. Its `read` accepts
only the current process epoch, current binding and fresh sample, using a
process monotonic clock. It is consequently a current position input, not a
historical world-time perception or identity-recognition record. The social
target catalog combines current position with a snapshot's visible-target
lineage; that combination does not on its own establish a committed session
field disclosure. B3 client sampling remains unaccepted.

`SocialDeliveryAuthority.record_delivery` commits a source event reference,
recipient and effective window. It checks `world_now` against that window but
does not record `world_now` in the delivery event. Consequently the window's
`effective_from` cannot establish when a later delivery actually occurred;
even its sequence-cut replay cannot reconstruct that time from this payload.
Its production caller found in this audit is the government public milling
notice caller, not an embodied-session delivery path. A delivery source and
trusted time for session fields must be established before reuse; existing
historical deliveries must not be assigned an invented delivery time.

The social handshake authority validates a completed session's exact event
history before producing actor-private shared-experience facts. This is useful
source provenance for that specific operation, but it is not a general
per-field disclosure or historical observer authorization for session pulls.
These observations are static code inspection, not an end-to-end authorization
test; they do not implement or accept the approved product rule.

The session owner has several actual writers: the harness handshake coordinator,
handoff authority and carry/place authority. `InteractionSession` carries a
scene revision but no world, scene-instance identity or event time. The
handshake harness itself automatically accepts for the other participants and
uses fixed trace timestamps; neither those actions nor timestamps establish
authenticated participant disclosure or historical perception. Handoff also
automatically invokes acceptance. Any disclosure provenance must be integrated
with the relevant real command and trusted clock boundary, not inferred from
this harness flow or added solely to one caller. Existing historic sessions
lacking that evidence must remain unknown under the approved rule.

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
