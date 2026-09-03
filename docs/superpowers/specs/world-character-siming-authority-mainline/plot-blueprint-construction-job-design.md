# Plot, Blueprint And Construction Job Design

Owner: `ConstructionProductionAuthority`.

`Plot` remains the jurisdiction/ownership anchor. `Blueprint` content declares
component tree, grid footprint, allowed discrete orientations, material/tool/
skill requirements, permit/zoning refs, duration and target facility
definition. `ConstructionJob` transitions `planned -> started -> completed |
failed` and stores only owner-issued reservation refs and revision pins. The
terminal `construction_job_failed@1` path records an explicit failure reason
without cancelling reservations or adding compensation.

Occupancy is a deterministic grid projection keyed by plot, footprint and
orientation. Multiple occupancy or stale plot/permit/owner evidence rejects
before append. Local visual offsets are presentation-only. Events use the
existing Construction stream and append spine; full and checkpoint-tail replay
must produce identical occupancy and job projections. Old narrow event payloads
remain read-only compatibility records. Package-bound placement uses the exact
immutable Blueprint descriptor, persists permit/component/content provenance,
and validates optional zoning evidence when declared.

Zero-write covers unknown package/content, malformed components, out-of-bounds
footprint, overlap, missing/private/stale evidence, revision conflict,
duplicate and caller-selected stream/event/owner.

The runtime slice implements plot-scoped `construction_job_started@1`, terminal
`construction_job_completed@1`, and terminal `construction_job_failed@1`
events, with source-controlled schema registrations, deterministic occupancy and
checkpoint-tail replay. Zoning remains optional package content; no default
zoning fact is inferred for legacy packages.

Replay requires `occupied_cells` to be an explicit canonical sequence of unique
integer coordinate pairs. Malformed cells are rejected with the stable
`construction_job_occupied_cells_invalid` error rather than filtered.

Job-start replay also requires project privacy and the canonical
`gameplay:construction_production:plot:{plot_ref}` stream; cross-plot or private
events fail closed.

Job completion and terminal failure replay apply the same plot-scoped stream
and project-privacy fence before changing Job status.
Plot identity mismatches remain identity conflicts; stream or privacy tampering
uses the separate stable source-conflict errors.

Job completion and failure events therefore retain the same owner-bound
plot-stream/privacy fence as job start, while preserving existing identity
error classification for payload mismatches.
