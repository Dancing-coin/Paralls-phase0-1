# INF-2P Payroll And Organization Operating-Window Closure Implementation Plan

Status: `completed and verified 2026-08-15`

1. Completed: formalize the owner split first. `OrganizationAuthority` owns
   `gameplay:organization:window:{window_ref}` open/close/due events and
   replayable projection state; `EconomyAuthority` owns only wage and account
   writes.
2. Completed: write RED focused tests for success, invalid or unverified
   evidence zero-write, duplicate idempotency, changed-key reuse
   `revision_conflict` on open/close/due, stale revision zero-write, privacy
   scope, compatibility-wrapper delegation, paid and overdue terminal paths,
   independently asserted paid-wage command-plan materialization, wage outbox
   scope, and full/checkpoint-tail replay.
3. Completed: add the minimal Organization window owner methods and projection,
   then convert Economy window helpers into compatibility-only delegates so no
   Economy principal can append organization-window facts.
4. Completed: let the event store arbitrate changed-key window reuse by
   removing owner-local early terminal returns for those stale
   expected-revision cases while preserving the compatibility wrapper surface.
5. Completed: add the independent Harness profile and verifier plus matching
   INF-2 formal documentation and profile documentation.
6. Completed: rerun the focused pytest file and the focused Harness profile.

Do not widen this package to scheduler logic, generic payroll policy, a new
obligation registry, a second receipt layer, or arbitrary cross-domain atomic
settlement.
