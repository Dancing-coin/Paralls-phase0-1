# INF-1AA Ecology Drought State Obligation Plan

Status: `implemented and verified seventh finite lifecycle row with opening-event-derived settlement provenance; generic lifecycle closure remains incomplete`

1. [x] Add the RED owner-obligation suite before production changes.
2. [x] Implement only the fixed Ecology drought StateDefinition row and its
   project-scoped owner event family on the existing ecology stream.
3. [x] Add strict `SemanticEcologyDroughtCommand` admission without using
   `settle_registered_state` or introducing a generic writer.
4. [x] Route due expiry through the existing obligation coordinator and Ecology
   owner fragment; keep receipt/outbox/replay append-derived.
5. [x] Extend the immutable finite registry and existing obligation lifecycle
   registration with the seventh row only.
6. [x] Add one Harness profile with one independent selector per capability and
   refresh the evidence report.
7. [x] Re-run focused, related finite lifecycle/adapter tests and `git diff --check`
   before describing the row as verified.

The package is intentionally one closed Ecology row. It does not admit another
state/effect pair, scheduler, generic lifecycle router, retry/compensation,
consumer edge, or cross-domain write.
