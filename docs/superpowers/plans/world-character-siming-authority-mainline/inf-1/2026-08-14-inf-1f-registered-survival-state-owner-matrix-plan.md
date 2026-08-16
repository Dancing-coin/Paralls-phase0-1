# INF-1F Registered Survival State Owner Matrix Plan

Status: `implemented and verified`

1. Add failing tests for state/effect pair lookup, deterministic enumeration and
   unregistered-owner denial. Complete.
2. Make `effect_ref` part of the registered lifecycle policy and replace the
   duplicate semantic-bridge mapping with one registry lookup. Complete.
3. Preserve the existing Survival owner append/replay/privacy/idempotency
   boundary; add a dedicated independent Harness report. Complete.

The plan does not authorize new owner rows or generic cross-domain lifecycle
execution.
