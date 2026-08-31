# INF-4AK Public-Project Execution Acknowledgment Plan

Status: `implemented narrow vertical; generic project lifecycle remains blocked`

1. Add one exact Government descriptor/catalog operation.
2. Verify the fixed INF-4AJ execution, INF-2AI source, reservation/acquisition
   provenance, project/facility binding, privacy and heads before append.
3. Append one authority-only acknowledgment via
   `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`.
4. Prove success, zero-write, idempotency, receipt and full/checkpoint-tail
   replay with focused tests and the independent Harness.
5. Reject replay when the stored acknowledgment no longer matches its execution,
   consumed-budget, reservation, or acquisition provenance.
