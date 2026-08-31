# INF-4AM Public Milling Notice Owner-Admission Contract

Status: `implemented narrow vertical; generic notification and permit semantics remain blocked`

## Exact Product Row

```text
committed project-visible Organization
  gameplay.organization.public_milling_activity_recorded@1
  provider = organization:district-milling-cooperative
  facility_kind = mill_reinforced
-> existing GovernmentAuthority
-> one project-scoped gameplay.government.public_milling_notice_recorded@1
```

The row emits one public notice that the fixed milling session completed. It
does not grant a permit or certificate and does not assert payment, attendance,
participant, relationship, reputation, population, material, inventory,
production output, weather, maintenance, or generic notification truth.

## Fixed Contract

| Field | Rule |
| --- | --- |
| capability / outcome | `capability:government-public-milling-notice@1` / `outcome:government-public-milling-notice-recorded@1` |
| owner / catalog | existing `GovernmentAuthority`; `inf:government-public-milling-notice@1`; descriptor `descriptor:government-public-milling-notice@1` |
| source | one committed project-visible INF-4AL milling activity plus its exact INF-2AL Contract created/fulfilled pair and INF-1AL acquisition binding |
| predicate | `predicate:organization-public-milling-activity-completed@1` |
| jurisdiction | derived only from committed `facility_acquired@1.payload.jurisdiction_ref`; caller cannot choose it |
| target | `gameplay:government:public-notice:{jurisdiction_ref}` / `gameplay.government.public_milling_notice_recorded@1` |
| privacy / subject | project; facility_ref and project_ref are copied from committed source activity |
| idempotency | `government:public-milling-notice:{activity_event_id}:{activity_revision}:{government_revision}:v1` |
| receipt / replay | append-derived `GameplayEventStore.append_batch()` receipt; `public_milling_notice_view_for` full/checkpoint-tail replay |
| payload | notice ref/kind/status, jurisdiction, fixed provider, facility/project, source activity and Contract revisions, policy/descriptor/catalog pins; no account/participant/payment payload |
| lifecycle | terminal completed; no reopen, cancellation, compensation, reversal, retry-as-new, fanout or cross-domain write |

## Zero-Write Rules

Unknown/missing/private/stale/wrong activity, wrong provider/activity kind,
wrong terms/package/facility kind, missing Contract provenance, acquisition or
jurisdiction binding conflict, stale Government head, invalid/reused key,
duplicate/changed duplicate, catalog mismatch, caller-selected jurisdiction/
stream/event/privacy/receipt, or permit/certificate/payment/attendance/social/
population extension rejects before append.

## Conflict Matrix Result

Disposition: `new`, disjoint from INF-4AH because its source service, provider,
activity kind, event family and notice policy are distinct. Existing Government
notice owner and public-notice stream are reused; no generic notification or
permit authority is introduced.

## Evidence

Focused tests and the independent `inf4am-public-milling-notice` Harness verify
source binding, jurisdiction derivation, privacy, revision, idempotency,
receipt, zero-write and full/checkpoint-tail replay.

The notice reader validates its immutable notice kind, jurisdiction, provider,
policy, descriptor/catalog, subject and source-event partition before returning
either full or checkpoint-tail state. A forged canonical notice fails closed
with `public_milling_notice_replay_invalid`.
