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
On 2026-11-10, `D:/Temp/paralls-g0-py312/Scripts/python.exe -m pytest
backend/tests/test_embodied_interaction_session.py -q` reported 7 passed with
6 deprecation warnings; this is backend test evidence, not a Godot run.

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
