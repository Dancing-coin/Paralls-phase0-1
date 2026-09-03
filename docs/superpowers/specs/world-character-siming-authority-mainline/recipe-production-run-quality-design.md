# Recipe, Production Run And Quality Design

Owner: `ConstructionProductionAuthority` for run facts and production
evidence; `InventoryAuthorityService` for custody.

Recipe content declares inputs, tools, skills, duration, explicit `batch_size`,
output definition, quality/capacity/wear policy refs and failure policy.
`ProductionRun` remains one owner fact with `started -> completed | lost |
released`; a package revision and all source reservation revisions are pinned
at start. Finish validates the pins and writes quantity/quality/provenance
evidence only. Inventory consumes that committed evidence independently.

Quality, capacity and wear are policy-defined; no platform formula or caller
amount is allowed. Missing policy, output definition or reservation proof is
zero-write. Full/checkpoint-tail replay must reproduce run status, batch,
quality and provenance exactly. Multi-run combined receipt and fanout remain
forbidden.

When a committed Facility projection is available, `run_started` replay must
remain project-visible on the exact facility stream and match the facility,
project and facility-revision pins. Legacy run-start records without a
materialized Facility remain readable without reinterpretation.

`run_finished` replay likewise requires project privacy, the exact facility
stream, and matching facility identity; when a Facility projection exists, any
declared project binding must match its plot.

Replay also validates optional output quantity and quality bounds: quantity is
a positive integer and quality is numeric within `[0,1]`; malformed values are
rejected before run completion is projected.
