# INF-4AL Public Milling Activity Owner-Admission Contract

Status: `implemented narrow vertical; generic activity, attendance and social truth remain blocked`

## Exact Product Row

```text
committed authority-only Contract record_fulfilled@1
  terms = service:industrial-facility-public-milling-session@1
  provider = organization:district-milling-cooperative
  facility_kind = mill_reinforced
-> existing OrganizationAuthority
-> one project-scoped gameplay.organization.public_milling_activity_recorded@1
```

The fact records only that the fixed provider completed one public milling
session for one facility/project. It does not assert attendance, participant
identity, relationship, reputation, population, payment, inventory, output,
material, permit, technology, weather, maintenance, or generic activity truth.

## Fixed Contract

| Field | Rule |
| --- | --- |
| capability / outcome | `capability:organization-public-milling-activity@1` / `outcome:organization-public-milling-activity-recorded@1` |
| owner / catalog | existing `OrganizationAuthority`; `inf:organization-public-milling-activity@1`; descriptor `descriptor:organization-public-milling-activity@1` |
| source | one committed authority-only INF-2AL `gameplay.contract.record_fulfilled` plus its exact created/completion pair; terms, v6 package, provider, receiver, facility and project pins must match |
| predicate | `predicate:contract-public-milling-session-fulfilled@1`; only one fulfilled record and one matching service-completion event |
| target | `gameplay:organization:{organization_ref}` where organization is fixed provider `organization:district-milling-cooperative`; event `gameplay.organization.public_milling_activity_recorded@1` |
| privacy / subject | project; subject slot binds committed `facility_ref` and `project_ref` from Contract source |
| idempotency | `organization:public-milling-activity:{contract_id}:{contract_revision}:{organization_head}:v1` |
| receipt / replay | append-derived `GameplayEventStore.append_batch()` receipt; `public_milling_activity_view_for` full/checkpoint-tail replay |
| payload | fixed activity ref/kind/status, provider, facility/project, service, Contract source ids/revisions, v6 package pin, policy/descriptor/catalog pins |
| lifecycle | terminal `completed`; no reopen, cancellation, compensation, reversal, retry-as-new, fanout or cross-domain write |

## Zero-Write Rules

Unknown/missing/private/stale/wrong Contract source, wrong terms/provider,
wrong package or facility kind, missing completion, binding conflict, multiple
source records, stale Contract/Organization head, invalid or reused
idempotency key, duplicate/changed duplicate, catalog mismatch, caller-selected
organization/event/stream/privacy/receipt, or any attendance/social/population/
payment/material/output extension rejects before append.

## Conflict Matrix Result

Disposition: `new`, disjoint from INF-4AG because its source service, provider,
activity kind, package and event family are distinct. Existing Organization
truth is reused; no generic activity writer or social/population owner is added.

## Evidence

Focused tests and independent `inf4al-public-milling-activity` Harness verify
source binding, privacy, revision, idempotency, receipt, zero-write and
full/checkpoint-tail replay.

The activity reader validates the immutable service, v6 package, provider,
policy, descriptor/catalog, subject and source-event partition before returning
either full or checkpoint-tail state. A forged canonical activity event fails
closed with `public_milling_activity_replay_invalid`.
