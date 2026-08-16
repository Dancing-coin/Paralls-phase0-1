# INF-3A Ecology Seasonal Process Design

Status: `implemented and checkpoint-verified; narrow ecology process only`

`EcologyHazardAuthority` is the sole owner. The closed
`policy:ecology_seasonal_cycle@1` consumes only its project-visible regional
records and advances exactly one region per command. It writes four canonical
events on `gameplay:ecology:{region_ref}`: corrected environment, resource,
crop, and `seasonal_process_advanced`. No ecology code writes economy, body,
social, population, inventory or construction truth.

The policy is deliberately fixed: for elapsed ticks it rotates `weather:clear`
to `weather:rain`, increases moisture, regenerates each registered resource,
and grows each registered crop. The target tick is monotonic and bounded by the
caller-selected command. A process event retains `last_tick`, policy revision,
and a per-command step budget of one region. This is a budgeted progressive
process, not generic regional fanout or hazard propagation.

All writes are `EcologyHazardAuthority -> GameplayCommandEnvelope ->
GameplayEventStore.append_batch() -> outbox -> scoped projection`. Required
evidence: success, duplicate, stale revision, private scope, forged principal,
public projection, and full/checkpoint-tail replay. It does not admit a
non-frost consumer edge; that remains INF-3Y.
