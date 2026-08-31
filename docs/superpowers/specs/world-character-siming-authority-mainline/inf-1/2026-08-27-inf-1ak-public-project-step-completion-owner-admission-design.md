# INF-1AK Construction Public-Project Step Completion Owner-Admission Contract

Status: `implemented and verified narrow vertical; generic project/task lifecycle remains blocked`

## Exact Row

```text
committed Organization work_order_fulfilled@1
  work_order_ref = work-order:public-project:workshop-bench@1
-> existing ConstructionProductionAuthority
-> one construction_public_project_step_completed@1 fact
```

This closes one named public-project work step for the facility's Construction
project projection. It changes only the Construction-owned set of completed
project-step references and the facility revision. It does not change facility
kind, public-use status, condition, production output, inventory, material,
payment, wage, permit, technology, weather, maintenance, social, population,
or generic task truth.

## Fixed Contract

| Field | Rule |
| --- | --- |
| capability / outcome | `capability:construction-public-project-step-completion@1` / `outcome:construction-public-project-step-completed@1` |
| owner | existing `ConstructionProductionAuthority` (`actor_gameplay.construction_production_domain`) |
| source | one committed project-visible `gameplay.organization.work_order_fulfilled` event, organization-summary scoped, with the exact literal `work-order:public-project:workshop-bench@1` |
| source pins | source Organization stream/event revision and head, accepted event/revision, source Production evidence/revision, schedule event/revision, facility/project binding |
| target stream / event | `gameplay:construction_production:{facility_ref}` / `gameplay.construction_production.public_project_step_completed@1` |
| privacy | project-scoped; the Organization source is read only and no private actor detail is copied |
| subject | facility/project refs are derived from the committed source; fixed `project_step_ref=project-step:public-project:workshop-bench@1` |
| policy / predicate | `policy:construction-public-project-step-completion@1`; `predicate:organization-public-project-work-order-fulfilled@1` |
| idempotency | owner-derived `construction:public-project-step:{source_event_id}:{source_revision}:{facility_revision}:{target_head}:v1` |
| receipt / replay | append-derived `GameplayEventStore.append_batch()` receipt; existing Construction projector full/checkpoint-tail replay |
| fixed payload | facility/project, fixed step ref, source Organization event/revision/head, accepted/source/schedule pins, prior and next facility revision, expected target head, policy and descriptor pins |
| lifecycle | v1 terminal for this step; no duplicate completion, reopen, cancel, reversal, compensation, payment, wage, fanout, or generic task route |

## Zero-Write Rules

Reject before append for unknown/private/non-summary/wrong event, wrong literal
work order, missing or ambiguous source, stale Organization or Construction
head, missing facility/project binding, source revision conflict, step already
completed, descriptor/catalog mismatch, duplicate or changed duplicate, and any
caller-selected owner/stream/event/privacy/revision/receipt or non-fixed step.
The exact duplicate returns the original Construction receipt.

## Conflict Matrix

Disposition: `new` fixed cross-owner source-to-existing-owner extension. The
Organization owner retains work-order truth; Construction owns the project-step
projection. INF-1AJ public-use status, INF-4V/W work history, Economy wage, and
all generic task/settlement paths remain separate. No new owner, router,
registry, coordinator, writer, or second runtime is introduced.
