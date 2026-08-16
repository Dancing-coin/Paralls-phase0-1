# F1A Semantic Rule And Causal Extension Gate Plan

Status: `contract-sample complete; implementation work packages pending`

## Work packages

1. Map August tags/entity/effect/causal/time concepts to existing world,
   ESM, Gameplay and Patch/runtime owners.
2. Define typed proposal fields, schema/digest, dependency graph, revision pin,
   capability budget, causal reference and time-request semantics.
3. Define deterministic validation and failure codes for stale revision,
   dependency cycle, conflict, unsupported effect, and unauthorized write.
4. Define full/checkpoint-tail replay, explanation projection, idempotency and
   rejected zero-write fixtures.
5. Review the contract against F0 and F1C package dependencies.

## Verification plan

Before implementation authorization, register a focused profile covering
accept/reject, stale/cycle/conflict denial, causal trace, replay hash,
duplicate idempotency, and zero committed events on rejection. The plan must
prove the existing `GameplayEventStore.append_batch()` path remains the only
settlement path.

## Done/blocked

Done means the contract and evidence manifest are reviewed. Missing owner,
nondeterminism, or any proposal that needs a second scheduler/runtime keeps F1A
blocked. Do not implement a generic Rule IR as a shortcut.
