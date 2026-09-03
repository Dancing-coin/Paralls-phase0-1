# Population Signal And Explicit Materialization State

Status: `implementation-authorized`

Date: `2026-09-03`

Population contributes public signals only. The state machine is
`signaled -> accepted -> materialized -> projected -> archived`, and every
materialization is explicit, typed and read-side only.

Population signals never settle accounts, inventory, ownership, permits,
policy, or social facts. Any admitted projection uses `gameplay.population.signal`
and a precompiled owner recipe; no generic population truth owner is created.

