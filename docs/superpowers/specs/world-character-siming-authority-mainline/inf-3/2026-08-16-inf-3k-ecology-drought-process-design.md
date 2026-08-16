# INF-3K Ecology Drought Process

Status: `implemented and verified bounded ecology process`

`EcologyHazardAuthority` alone advances a bounded, caller-driven drought cursor on the existing `gameplay:ecology:{region_ref}` stream. One append batch corrects only existing environment moisture, resource quantity and crop health records, then emits `gameplay.ecology.drought_process_advanced`. The event-derived scoped projection retains tick and policy identity. No consumer, scheduler, new truth owner or cross-domain write is admitted.

Evidence: `.harness/verification/infra-ecology-drought-process-report.json`.
