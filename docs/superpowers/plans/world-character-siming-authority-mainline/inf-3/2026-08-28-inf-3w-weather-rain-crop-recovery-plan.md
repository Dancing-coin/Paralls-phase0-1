# INF-3W Weather Rain To Crop Recovery Plan

Status: `implemented narrow vertical; generic crop recovery remains blocked`

1. Register one immutable Ecology descriptor/catalog operation.
2. Read the exact rain front and derive exactly one damaged target-region crop.
3. Append one fixed `crop.recorded` provenance partition through the existing
   envelope/fragment/EventStore spine.
4. Prove zero-write, duplicate receipt replay, revision/privacy fences and
   full/checkpoint-tail replay with focused tests and an independent Harness.
5. Fail closed during regional replay when a recovery row's weather or crop
   provenance no longer matches its immutable partition.
6. Require exact source and target binding for duplicate receipt replay; changed
   binding under the same idempotency key is zero-write.
7. Require both existing full and checkpoint-tail regional replay entrypoints
   to execute the row-specific provenance validation before hashing replay
   output; forged canonical recovery records must fail closed.
