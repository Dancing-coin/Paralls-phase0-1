# INF-4AK Public-Project Execution Acknowledgment Owner-Admission Contract

Status: `implemented narrow vertical; generic project lifecycle remains blocked`

## Exact Row

```text
committed project-visible INF-4AJ public_project_execution_recorded@1
  status = funded_and_executed
+ its exact authority-only INF-2AI consumed-budget provenance
-> existing GovernmentAuthority
-> one authority-only public_project_execution_acknowledged@1
```

Government records a fixed administrative acknowledgment only. It derives the
jurisdiction from the consumed marker's acquisition provenance. It creates no
permit, certification, payment, account, release, refund, material, output,
attendance, social, population, or generic project-completion fact.

## Fixed Contract

| Field | Rule |
| --- | --- |
| capability / outcome | `capability:government-public-project-execution-acknowledgment@1` / `outcome:government-public-project-execution-acknowledged@1` |
| owner | existing `GovernmentAuthority` |
| source | exact project-visible INF-4AJ execution plus its fixed INF-2AI consumed marker and reservation/acquisition provenance |
| target | `gameplay:government:public-project:{jurisdiction_ref}` / `gameplay.government.public_project_execution_acknowledged@1` |
| privacy | authority-only |
| idempotency | owner-derived execution/revision/head/government-head key |
| receipt / replay | `GameplayEventStore.append_batch()` receipt; Government full/checkpoint-tail acknowledgment reader |
| lifecycle | v1 terminal acknowledgment; no re-open, retry-as-new, compensation, fanout, permit, or settlement semantics |

Unknown, private, stale, forged, mismatched, duplicate, changed-duplicate, or
unadmitted evidence rejects before append. Caller selects neither jurisdiction,
stream, event, privacy, receipt, policy, nor fragment.

The replay reader revalidates every stored acknowledgment against the committed
execution, consumed marker, reservation, and acquisition records. A forged or
missing provenance link fails closed rather than rebuilding an acknowledgment
from its own payload.
