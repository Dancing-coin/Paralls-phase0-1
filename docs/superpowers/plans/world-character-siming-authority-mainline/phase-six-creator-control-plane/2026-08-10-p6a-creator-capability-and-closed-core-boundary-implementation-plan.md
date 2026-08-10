# P6A Creator Capability And Closed-Core Boundary Implementation Plan

Status: `design-only; implementation not authorized`

1. Threat-model current package, Patch and authorization boundaries; write
   reader/editor/admin allow/deny tests before a surface is exposed.
2. Define the server-side decision contract and signed capability manifest;
   closed modules expose service endpoints, not mutable imports.
3. Add classified projections and append-only audit evidence through existing
   governance/event paths, with explicit retention/redaction policy.
4. Run authorization bypass, stale grant, cross-project and replay tests.

Stop for any direct event-store writer, private-memory export, secret exposure or
client-enforced-only rule.
