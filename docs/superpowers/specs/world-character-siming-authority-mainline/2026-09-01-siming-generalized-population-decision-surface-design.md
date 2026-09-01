# Siming Generalized Population Decision Surface

Status: `approved; implementation plan follows`

Date: `2026-09-01`

## 1. Intent

The current three-actor/two-cadence implementation is a proof fixture. It
proves that one Siming-governed cohort can pass through an existing Owner and
Character Core, but it must not become the population simulator's permanent
control flow.

The durable design is an open-ended simulation candidate space governed by a
closed authority boundary:

```text
scoped committed projections
  -> Siming evaluates candidate actions and fidelity tiers
  -> Siming selects, orders, defers or requeues candidates under policy/budget
  -> static capability admission
  -> existing domain Owner and/or Character Core settlement
  -> receipts and new projections
  -> Siming re-plans the next cadence
```

Rules classify possibilities. Siming is responsible for deciding how the
world should be advanced within those rules. A fixture may pin actors and
expected outcomes for regression, but production code must not require one
actor list, one behavior chain, or one scenario script.

## 2. Scope Of Generalization

Generalization means:

- candidate cohorts may come from any authorized region, organization,
  household or public bucket projection;
- multiple registered behavior rows may compete in one cadence;
- Siming may allocate budget across candidates, choose B0/B1/B2/B3 fidelity,
  defer work, request activation, or submit an Owner-bound intent;
- one decision may emit several independently admitted candidates, or emit no
  candidate when evidence, budget or policy does not justify progress;
- a new behavior is added through a source-controlled capability and Owner
  contract, not by changing the core simulator's actor-specific branch.

Generalization does not mean arbitrary world writes, arbitrary event families,
dynamic unreviewed behavior registration, hidden-memory access, or a second
runtime/event store.

## 3. Authority Invariants

These invariants remain hard requirements:

1. `SimingRuntime.tick(...)` is the only Siming decision and dispatch path.
2. `PopulationPlanner` is a pure evaluator. It reads an immutable scoped
   `PopulationReadSet` and returns candidates plus explanations; it never
   writes, invokes an Owner, calls Character Core, or advances a clock.
3. Every objective candidate names a source-controlled capability mapping and
   one existing domain Owner. The caller cannot choose a stream, event family,
   or replacement Owner.
4. Owner receipts are required before objective results enter Character Core.
5. Character Core is the only writer of actor continuity, SeedDelta, memory
   candidates/materialization and actor revision.
6. `char_c`-style activation-only outcomes never create an implicit cognition
   turn. Player input is required for activation of the existing record.
7. Branch/private/cross-actor/stale/unknown/malformed/duplicate-mismatch and
   budget-exhausted inputs fail closed with auditable zero production write.
8. Full replay and checkpoint-plus-tail replay agree for world projections,
   Owner receipts, actor continuity and Siming decision summaries.

## 4. Decision Model

The generic candidate contract contains only bounded, typed information:

```text
candidate_ref
actor_ref or cohort_ref
behavior_kind
fidelity_tier
source_projection_refs
source_revision_vector
evidence_refs (scoped references, never raw private memory)
estimated_cost
objective_risk
player_proximity
narrative_obligation_pressure
unresolved_owner_consequence
propagation_pressure
starvation_credit
allowed_outputs
policy_revision
selector_revision
ruleset_revision
idempotency_key
```

Siming evaluates these fields and produces a deterministic decision summary:

```text
selected_candidates
deferred_candidates
rejected_candidates
unprocessed_buckets
budget_used / budget_remaining
fidelity_counts
decision_reasons (bounded aggregate codes)
```

The decision may use a deterministic policy scorer or a bounded model-assisted
ranking step, but the final selected set must be reproducible from the pinned
source vectors, revisions, seed, policy and budget. Model output is a ranking
input, never a truth write or an unvalidated action.

## 5. Fidelity And Outputs

The simulator chooses the least expensive output that preserves the required
world/character continuity:

| Tier | Use | Output |
| --- | --- | --- |
| B0 | routine aging and low-risk pressure | presentation seed or deferred result |
| B1 | scoped propagation or bounded routine | presentation seed, activation hint, or typed candidate |
| B2 | high-attention actor/cohort consequence | Character Core candidate and, when admitted, Owner-bound intent |
| B3 | player-critical or exceptional event | activation request plus statically admitted capability only |

The tier is a decision variable, not a behavior identity. A routine behavior
may be deferred or promoted by policy when its evidence and consequences
justify the cost; promotion never bypasses Owner or Character Core.

## 6. Capability Boundary

The capability catalog is closed at runtime and extensible in source control.
Each entry declares:

```text
capability_id
accepted_behavior_kinds
required_scopes
required_source_domains
target_owner
allowed_output_kinds
revision and policy pins
```

Admission rejects any candidate whose behavior, actor/cohort, scope, source
vector, revision, target or output is not declared. Adding a new behavior is a
separate vertical: source projection, capability admission, named Owner,
receipt, Character Core mapping, replay, privacy tests and Harness evidence.

## 7. Replanning Protocol

After each cadence, Siming consumes only committed receipts and projections.
It may:

- continue a candidate with a new expected revision;
- select a different candidate because pressure, proximity or budget changed;
- defer or requeue stale/failed work;
- lower fidelity when the budget is exhausted;
- request player activation for an existing record.

An `accepted` result means the selected outputs completed their declared
settlement path. A partial failure must identify dependent candidates and stop
their writes; it must not be upgraded to `accepted` by an earlier success.

## 8. Fixture And Harness Policy

The existing three-actor W0/W1 vertical remains a regression fixture. It may
assert exact actor order, behavior rows and receipts because those are the
fixture's inputs. It is not the generic simulator contract.

Generic Harness checks must assert invariants rather than one golden result:

- no authority bypass or second runtime/store/bus;
- candidate decisions stay within pinned scope and capability catalog;
- every objective write has the correct Owner receipt;
- Character Core commands are actor-local and revision-safe;
- alternative valid candidate selections remain valid;
- fixed inputs replay identically;
- stale, malformed and adversarial inputs produce zero writes;
- budget/fidelity changes affect selection without changing authority.

Scenario fixtures should cover at least: competing candidates, budget
exhaustion, stale receipt, Owner rejection, player proximity, propagation
pressure and no-op/defer decisions. They must not require a background LLM
loop for every actor.

## 9. Migration From The V1 Fixture

The current `plan_three_actor_cohort` path is retained only as a compatibility
fixture and direct evidence profile. The next implementation plan must:

1. extract generic candidate and decision contracts without removing the V1
   fixture;
2. move actor-specific disposition logic into fixture data;
3. add a Siming decision evaluator that can rank multiple admitted candidates;
4. route selected candidates through the existing capability/Owner/Core path;
5. update Harness checks to invariant/scenario assertions;
6. add one additional non-supply capability vertical only after its Owner
   contract is approved.

## 10. Explicit Non-Goals

This design does not authorize:

- a population truth owner, global social graph or free-form world writer;
- arbitrary dynamic action registration;
- direct mutation of inventory, employment, wages, relationships, markets,
  households, ecology, migration, government or civilization facts;
- a new scheduler, clock, event bus, event store or per-actor background LLM;
- claiming complete population, society, civilization, multi-region or
  million-agent simulation capacity.

Those domains require independent source-controlled verticals with their own
Owner contracts, receipts, privacy rules, replay evidence and Harness profiles.
