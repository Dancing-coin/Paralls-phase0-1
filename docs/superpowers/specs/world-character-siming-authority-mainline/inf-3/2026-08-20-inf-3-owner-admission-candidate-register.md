# INF-3 Owner-Admission Candidate Register

Status: `INF-3W implemented narrow vertical; remaining unlisted consumer edges remain formally blocked`

## Shared Contract Requirements

Ecology may commit a source event and bounded propagation only. The target
owner must validate the exact source event/revision, privacy and subject/region
binding, build its own fixed fragment, append through its existing owner, and
provide owner-derived idempotency, append receipt, full/tail replay, and
terminal/reversal/compensation rules. C4 is read-only and cannot register or
write a consumer. All malformed, multiple, unadmitted, digest/privacy/stale/
binding/revision/duplicate inputs are zero-write.

## Candidate INF-3R (implemented and verified)

| Field | Fixed contract |
| --- | --- |
| source/outcome | project-visible `weather:drought` front plus exact target Region/jurisdiction pin -> one Government drought advisory issuance |
| owner/stream/event | existing GovernmentAuthority; `gameplay:government:advisory:{jurisdiction_ref}`; `gameplay.government.drought_advisory_issued@1` |
| privacy/replay | project only; append-derived receipt; Government full/checkpoint-tail advisory reader |
| boundary | historical advisory only; no restriction, payment, material, production, population, compensation, retry, revocation, or fanout |
| evidence | [contract](2026-08-26-inf-3r-drought-government-advisory-owner-admission-design.md), focused tests, and `infra-weather-front-government-drought-advisory` Harness |

## Candidate INF-3W (implemented and verified)

| Field | Fixed contract |
| --- | --- |
| source/outcome | project-visible `weather:rain` front plus exactly one owner-derived damaged crop in its target region -> one fixed Ecology crop recovery |
| owner/stream/event | existing EcologyHazardAuthority; `gameplay:ecology:{target_region_ref}`; one provenance-pinned `gameplay.ecology.crop.recorded` partition |
| privacy/replay | project only; append-derived receipt; existing Ecology regional full/checkpoint-tail replay validates weather/crop/policy provenance |
| boundary | fixed `+5` health capped at `100`; no drought-process source, fanout, inventory, output, payment, material, compensation, or generic crop recovery |
| evidence | [contract](2026-08-28-inf-3w-weather-rain-crop-recovery-owner-admission-design.md), focused tests, and `inf3w-weather-rain-crop-recovery` Harness |

## Candidate INF-3-SLOT-A (remaining unlisted source -> existing target; blocked)

The terminal INF-3Q audit found no further committed Ecology source/target
pair. Missing exact source event and `source_revision`, target owner/stream/
event/write revision, privacy and subject binding, idempotency, receipt,
full/tail replay, lifecycle/reversal/compensation, and package/declaration/
binding/policy/descriptor/catalog pins. Recommendation: approve one exact edge
before naming weather or fanout semantics.

## Candidate INF-3-SLOT-B (drought process substitute; rejected)

`drought_process_advanced` cannot substitute for the already implemented
weather-front dehydration source. Treating it as a new consumer fact would
violate source provenance and reopen discovery. Missing a separately committed
source-to-target decision; preserve zero-write.

## Candidate INF-3-SLOT-C (additional weather-front edge; blocked)

The finite Construction, Organization, Economy, Survival, Government, and
Ecology recovery map is terminal evidence. No additional target-owner contract exists. Missing target owner,
event vector, privacy, subject binding, idempotency, receipt, replay,
terminal/reversal/compensation, and admission pins. Do not create a consumer
registry, fanout writer, or Ecology-to-owner router.
