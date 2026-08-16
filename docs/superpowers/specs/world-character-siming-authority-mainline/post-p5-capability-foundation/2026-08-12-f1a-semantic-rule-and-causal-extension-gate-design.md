# F1A Semantic Rule And Causal Extension Gate

Status: `contract-sample verified; production semantic/causal mainline remains planned`

## Objective

Turn the unfinished world-infrastructure guidance into typed, revisioned
contracts over existing owners. F1A covers tags, entity definitions, rule
dependencies, causal references, explainable settlement, and cross-domain time
requests without creating a second world loop.

## Contract shape

Every proposal declares `owner`, schema/digest, dependencies, capability
budget, input revision, effective revision, causal references, requested time
window, and failure behavior. Evaluation is proposal-only; accepted effects
enter the existing Gameplay authority and `GameplayEventStore.append_batch()`
path. Siming may emit a high-level catalyst, never a world write.

## Work packages

1. semantic tag/entity schema and digest rules;
2. dependency, conflict, cycle, and stale-revision validation;
3. causal trace and explanation projection;
4. time/scheduling request contract that delegates to existing authority;
5. replay and rejection fixtures.

## Dependencies

F0 is required. F1A can be designed beside F1B/F1C, but F1C may not rely on an
unreviewed semantic revision format. P6 package validation and P7 proposal
channels consume F1A; neither may bypass it.

## Evidence gate

Focused tests cover deterministic accept/reject, dependency-cycle denial,
stale revision, causal trace, duplicate idempotency, full/checkpoint-tail
replay equivalence, scoped explanation, and zero committed events on rejection.
The future profile must be registered in Harness before implementation.

## Non-goals and stop conditions

No general Rule IR, arbitrary code execution, second scheduler/clock, direct
client/model/Siming write, full ecology/disaster simulation, civilization
runtime, or world-mode runtime is included. Unknown owner, nondeterministic
evaluation, or missing replay proof keeps F1A `planned` or `blocked`.
