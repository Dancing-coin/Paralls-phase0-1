# INF-3R Government Drought Advisory Presentation Plan

Status: `implemented and verified narrow presentation extension`

1. Add RED tests for a server-issued, jurisdiction-scoped WebSocket binding and
   the fixed advisory subscribe/snapshot/delivery behavior. Prove that no actor
   scope can be used as an advisory scope and that all rejected cases preserve
   the event store.
2. Extend only the existing trusted-local enrollment and WebSocket binding with
   `allowed_government_drought_advisory_jurisdiction_refs`. Preserve the
   existing actor scope unchanged and carry the fixed advisory scope through
   renewal.
3. Add a dedicated, read-only Government advisory presentation service. It may
   subscribe/snapshot/deliver only `GovernmentAuthority.drought_advisory_view_for`
   output for one granted jurisdiction.
4. Add the exact advisory message to the existing WebSocket queue/connection
   transport and Godot bridge. Do not use an actor reference as a surrogate for
   jurisdiction scope.
5. Wire the existing dispatcher post-commit callback to the fixed consumer,
   which filters the already committed Government advisory outbox topic.
6. Add an independent Harness, run focused tests plus the existing Government
   advisory and continuation profiles, run documentation and diff checks, then
   synchronize the matrix, audit, remaining scope, INF-3 README, taxonomy, and
   checkpoint. August INF A-D remains `not complete`.

Stop only if an existing boundary cannot express the fixed scope without a
generic authority or if tests demonstrate a privacy/replay leak. Neither is
present in the established WebSocket binding and dispatcher seams.

Verification completed with `79 passed` across the focused Government,
WebSocket, transport, and presentation-static tests. The independent
`infra-weather-front-government-drought-advisory-presentation` Harness, the
continuation gate, and the docs profile passed. This establishes backend and
static Godot-contract evidence only; no Godot editor/runtime presentation claim
is made here.
