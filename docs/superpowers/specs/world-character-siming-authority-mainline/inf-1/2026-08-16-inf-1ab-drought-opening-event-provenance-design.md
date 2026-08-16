# INF-1AB Drought Opening-Event Provenance

Status: `implemented and verified repair of the existing finite INF-1AA row`

INF-1AA records its drought-process source in the committed
`gameplay.ecology.drought_state_obligation_opened` event. INF-1AB makes the
existing Ecology owner derive settlement provenance from that committed opening
event rather than accepting a caller-provided source identifier.

`EcologyHazardAuthority.build_drought_state_fragment()` becomes an owner
instance method. It accepts only the existing event-derived obligation, region,
and expected ecology revision. It requires exactly one `opening_event:{id}`
source reference, reads that committed opening event, and validates its event
type, project visibility, stream, obligation/policy identity, region, and
stored drought-process event ID/revision before emitting the existing expiry
and settled events.

No event family, owner, stream, projection, scheduler, coordinator writer, or
generic lifecycle capability is added. Missing or forged opening provenance is
zero-write rejected before the existing owner append.
