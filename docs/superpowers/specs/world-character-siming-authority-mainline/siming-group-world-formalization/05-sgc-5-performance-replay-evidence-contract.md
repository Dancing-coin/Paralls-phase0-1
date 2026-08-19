# SGC-5 Performance And Replay Evidence Contract

Status: `proposed; complete vertical required before baseline`

## Scope

This package defines reproducible performance evidence and load-shedding
behavior for one complete SGC vertical. It makes no global real-time,
concurrency or scale claim.

## Contract

Every profile pins environment label, synthetic dataset version/size,
world-mode/cadence/source vectors, policy/mapping revision, seed, budget,
warm-up count, repeat count and selector name. It records plan size, owner
append count, projection latency, activation count and full/tail replay time,
including median and high percentile.

Profiles are `population-batch-baseline`, `activation-handoff`,
`presentation-tail-replay` and `privacy-load-shed`. Each has a recorded local
baseline, regression threshold and explicit failure disposition.

Overload may lower far-field precision, defer graph work, use deterministic LOD
or return no-op/requeue. It may not drop receipts, weaken privacy, erase audit
fields, fabricate a settlement or silently change source/revision inputs.

## Evidence contract

Harness must reject incomplete profile metadata and must preserve the same
input/result digests across repeated runs. Threshold failures remain evidence
failures unless an existing documented degradation path is exercised and
audited.

## Dependencies and non-goals

Depends on one verified SGC-1..4 vertical and the existing Harness/replay
substrate. It does not introduce a benchmark database, scheduler, event store
or production data access to private memory.
