# INF-4AJ Public Project Execution Owner-Admission Contract

Status: `implemented and verified narrow vertical; generic project execution remains blocked`

## Exact Row

```text
committed project-scoped INF-4AG
  gameplay.organization.public_workshop_activity_recorded@1
  (activity_kind=public_workshop_session, status=completed)
+ committed authority-only INF-2AI
  gameplay.economy.public_project_budget_consumed@1
  (fixed reservation consumed for the same facility/project)
-> existing OrganizationAuthority
-> one project-scoped gameplay.organization.public_project_execution_recorded@1
```

The fixed semantic is `funded_and_executed`: one public-workshop project step
has both the project-visible activity and its authority-only consumed budget
marker. This row does not create payment, debit, release, refund, material,
inventory, production output, attendance, social, population, or generic
project/task semantics.

## Fixed Contract

| Field | Rule |
| --- | --- |
| capability/outcome | `capability:organization-public-project-execution@1` / `outcome:organization-public-project-execution-recorded@1` |
| owner | existing `OrganizationAuthority` (`actor_gameplay.organization_domain`) |
| sources | exact project-visible INF-4AG activity and authority-only INF-2AI consumed marker |
| predicate | `predicate:economy-public-project-budget-consumed-and-workshop-activity@1` |
| target | `gameplay:organization:{organization_ref}` / `gameplay.organization.public_project_execution_recorded@1` |
| privacy | `project`; no account, amount or currency is copied into the target payload |
| idempotency | owner-derived source refs/revisions plus Economy and Organization heads |
| receipt/replay | append-derived `GameplayEventStore.append_batch()` receipt; Organization full/checkpoint-tail execution reader |
| lifecycle | v1 terminal `funded_and_executed`; no compensation, reopen, retry-as-new or fanout |

The owner re-reads exact source event types, provider/service/policy/descriptor
and catalog pins, source revisions, facility/project binding and privacy before
constructing the command envelope. Caller-supplied owner, stream, event,
semantic status, source coordinates or privacy are not trusted.

## Zero-Write Rules

Unknown, private, stale, malformed, mismatched, duplicate, changed-duplicate,
or forged activity/budget evidence rejects before append. Exact duplicate
delivery replays the original receipt. Requests for payment, debit, release,
refund, material, inventory, output, attendance, social, population,
compensation or reopening are outside this fixed row.

## Conflict Matrix

INF-4AG owns the provider activity fact and INF-2AI owns the authority-only
consumed budget fact. INF-4AJ only records the project-scoped organization
execution consequence for the same fixed facility/project. No generic router,
registry, coordinator, writer, authority or second runtime is introduced.
