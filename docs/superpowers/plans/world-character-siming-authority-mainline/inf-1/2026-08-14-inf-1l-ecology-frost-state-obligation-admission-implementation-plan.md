# INF-1L Ecology Frost State Obligation Admission Plan

Status: `implemented and verified closed Ecology owner row; generic matrix remains incomplete`

1. [x] Re-run the continuation gate and INF-1K predecessor Harness; retain
   their full/checkpoint-tail evidence before changing the next row.
2. [x] Fix the owner/event/projection/receipt table for exactly
   `effect:frost -> state:frosted@1` in the existing Ecology authority and
   ecology stream.
3. [x] Add focused failing tests for the fixed apply/refresh and due-expiry
   lifecycle, including duplicate, changed-key, revision, privacy, unknown-row,
   outbox, full replay, and checkpoint-tail replay cases.
4. [x] Extend only `EcologyHazardAuthority` and the existing coordinator
   registration to build owner fragments and append through the one event
   store. Do not route semantic proposal evaluation directly to the new events.
5. [x] Add one dedicated Harness assertion per stated capability and generate
   its report.
6. [x] Re-run focused regression groups, predecessor Harnesses, full suite,
   docs/continuation gates, and `git diff --check`.
7. [x] Update the August guidance, root dependency spec/plan, INF-1 README,
   and this package to `implemented and verified` only after all evidence is
   green. Retain the generic owner-matrix blocker.

The package is intentionally one closed Ecology row. It cannot be used to add
another effect/state owner, an ecology scheduler, a third consumer edge, or a
generic lifecycle router.
