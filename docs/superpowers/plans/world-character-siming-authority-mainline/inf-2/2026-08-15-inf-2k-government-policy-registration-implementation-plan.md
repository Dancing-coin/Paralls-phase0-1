# INF-2K Government Policy Registration Implementation Plan

Status: `implemented bounded and verified 2026-08-15`

1. [x] Add focused failing tests for the fixed Government policy lifecycle:
   registration, revoke, exact and changed duplicates, stale revision, privacy,
   unknown kind, projection replay and zero writes.
2. [x] Extend only existing `GovernmentAuthority` and its existing organization
   government stream with typed policy events, envelope/SettlementPlan append,
   redacted project outbox and replay view.
3. [x] Add one independent Harness selector per capability and rerun Government
   predecessor evidence.
4. [x] Synchronize INF-2, root formal documents and August analysis. Keep generic
   payment, arbitrary cross-domain settlement and unbound consumers blocked.

Closure evidence is `infra-government-policy-registration`: eight independent
selectors, including separate register and revoke append checks. This does not
admit a caller-open policy registry or a generic settlement writer.
