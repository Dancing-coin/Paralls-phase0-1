# INF-3I Weather-Front Organization Supply Edge

Status: `implemented bounded and verified 2026-08-15`

INF-3I admits one exact third target-owner edge. A project-visible existing
`gameplay.ecology.weather_front.propagated` event may propose a weather-response
supply commitment. `EcologyHazardAuthority` only issues opaque source evidence;
the existing `OrganizationAuthority` alone validates its existing commerce
budget authorization and writes its existing commitment event.

| Concern | Contract |
| --- | --- |
| source owner | existing `EcologyHazardAuthority` / `authority:ecology` |
| source stream/event | `gameplay:ecology:{region_ref}` / existing `gameplay.ecology.weather_front.propagated` |
| target owner | existing `OrganizationAuthority` / `actor_gameplay.organization_domain` |
| target stream/event | `gameplay:organization:{organization_ref}` / existing `gameplay.organization.commerce_commitment_accepted` |
| target fragment | existing `OrganizationAuthority.build_commerce_commitment_fragment` |
| privacy | source and target are both project-visible; non-project source or target is zero-write rejected |
| revisions | exact source ecology event/head and target organization head are read/pinned before append |
| idempotency | one fixed weather-event plus organization plus commitment identity; exact duplicate replays, changed duplicate rejects |
| receipt/replay | sole `GameplayEventStore.append_batch()` result and existing Organization production replay |

The source proposal names a single organization, counterparty, commitment,
policy revision, grant and reservation identifiers. Those fields are only
candidate intent. The Organization owner validates the exact existing
authorization/budget projection before using its existing fragment. The
resulting event carries source event identity and revision as provenance but
does not expose ecology internals in the project outbox.

No generic consumer registry, Organization schedule truth, payment settlement,
new event family, retry/compensation, scheduler, or Ecology-to-Organization
direct write is admitted. All other consumer candidates remain zero-write.

Evidence: `.harness/verification/infra-ecology-weather-front-organization-supply-edge-report.json`.

Required evidence: independent success, forged/missing admission zero-write,
changed and exact duplicate handling, stale source and target revisions,
privacy, redacted project outbox, and full/checkpoint-tail production replay.
