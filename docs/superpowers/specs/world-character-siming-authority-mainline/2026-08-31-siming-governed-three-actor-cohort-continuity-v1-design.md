# Siming-Governed Three-Actor Cohort Continuity V1 Design

Status: `approved; implementation plan follows`

Date: `2026-08-31`

## 1. Intent

Extend the verified one-actor bakery seed vertical into a bounded, Siming-
governed three-actor, two-cadence cohort continuity vertical. This is the next
step toward a complete population simulation, not a claim that complete
population, society, economy, civilization, or multi-region simulation exists.

The implementation must preserve the approved authority split:

```text
committed world-mode and Organization schedule projections
  -> population_cadence_event
  -> SimingRuntime.tick(...)
  -> PopulationSimulationCapability
  -> internal PopulationPlanner cohort calculation
  -> Siming policy and static capability admission
  -> existing Organization Owner settlement when world truth changes
  -> Character Core seed/continuity settlement
  -> same CharacterRecord prewarm or player-triggered active cognition
```

`SimingRuntime.tick(...)` remains the only Siming decision and dispatch path.
The planner remains an internal pure calculator. No participant in this
vertical may introduce a second runtime, event bus, event store, truth owner,
clock, scheduler, generic writer, dynamic behavior registry, or background
LLM-per-actor loop.

## 2. Source Of Truth

This design extends, but does not replace:

- `2026-08-29-siming-led-population-simulation-design.md`;
- `2026-08-22-character-simulation-memory-seed-continuity-design.md`;
- `docs/8月分析/司命与群体世界补充设计/01-司命受控能力面.md`;
- `docs/8月分析/司命与群体世界补充设计/03-群体模拟与角色分级连续性.md`;
- `docs/8月分析/司命与群体世界补充设计/12-角色模拟记忆种子与连续性设计.md`;
- `docs/8月分析/司命与群体世界补充设计/13-群体模拟生产纵切与推进闭环设计.md`.

If this document conflicts with those documents, their ownership, privacy and
no-second-runtime constraints win. This document only specifies the next
bounded cohort implementation slice.

## 3. Decision Summary

The first slice proved one actor can receive an owner-mediated seed. Cohort
Continuity V1 proves that Siming can govern a deterministic three-actor cohort
across two frozen cadence windows without turning the cohort into a world
truth owner.

The V1 cohort is exactly these existing records:

| Actor | Cohort disposition | Admitted result | Forbidden result |
| --- | --- | --- | --- |
| `character:char_a` | bakery supply principal | `schedule_gated_supply` owner-bound intent, Organization receipt, Character Core seed | direct inventory, employment, price, account or world write |
| `character:char_b` | routine bakery worker | `routine_work` presentation-only Character Core seed | Owner call, world fact, memory candidate, social fact |
| `character:char_c` | high-attention social participant | `relationship_negotiation` activation candidate only | relationship fact, Character Core state/memory seed, implicit LLM turn |

The names above are closed V1 dispositions, not a general role system. Their
sources are frozen Organization schedule projections for the same bakery
window, not generated profiles or an NPC population database.

The two windows are `W0` and `W1`:

1. `W0` freezes three allowed projections and permits one Organization supply
   settlement for `char_a`; it emits a presentation-only seed for `char_b` and
   an activation candidate for `char_c`.
2. `W1` is derived only from the receipts/projections committed by `W0` plus a
   new committed Organization schedule projection. It repeats the same closed
   authority path with distinct source revisions and idempotency keys.

The accepted vertical is therefore a three-actor continuity test, not a rule
that every actor must advance every cadence. Budget exhaustion must leave the
unselected cohort members in the report's `unprocessed_cohort_refs` with zero
world, Character Core or memory write.

## 4. Ownership And Allowed Effects

### 4.1 Siming

Siming may:

- consume the committed, scope-filtered world-mode and Organization schedule
  projections;
- authorize the fixed cadence, selector, policy revision and budget;
- call the internal planner through `SimingRuntime.tick(...)`;
- retain a bounded report/audit/read-model summary;
- submit only the statically admitted `schedule_gated_supply` intent to the
  existing Organization Owner;
- request Character Core continuity settlement for a valid seed;
- publish prewarm/activation priority through the existing activation policy.

Siming may not:

- read raw five-pool memory or hidden relationship knowledge;
- make an objective world write, SeedDelta append or memory append itself;
- make a relationship, work, wage, household, inventory or market fact true;
- promote a branch result, choose a new Owner, stream or event family;
- create an actor, mutate an authored profile or run a background LLM loop.

### 4.2 PopulationPlanner

`PopulationPlanner` receives only one immutable `PopulationReadSet` per
cadence. It may select the fixed cohort and classify candidates. It cannot
append events or invoke any Owner. Its output is always one of:

```text
presentation_seed
activation_candidate
owner_bound_intent
rejected_candidate / unprocessed_cohort_ref
```

### 4.3 Organization Owner

The existing Organization Owner is the only V1 writer of objective truth. It
handles exactly the already-admitted `schedule_gated_supply` row for
`character:char_a`. Its receipt is necessary before the associated objective
seed reaches Character Core.

The Owner is not called for `char_b` presentation or `char_c` activation-only
results. A rejected, stale or duplicate Owner input never causes a substitute
Owner call.

### 4.4 Character Core

Character Core remains the sole owner that may admit a
`CharacterContinuityCommand`, update actor continuity state, append SeedDelta,
retain pending candidates, materialize a five-pool record or advance a
character revision.

The permitted V1 Character Core requests are:

| Actor | Command condition | Allowed content |
| --- | --- | --- |
| `char_a` | exact Organization receipt was committed/replayed for this projection | state delta, presentation seed, activation hint, eligible memory candidate |
| `char_b` | non-objective `routine_work` presentation disposition | presentation seed and activation hint only; empty `state_deltas` and empty memory candidate list |
| `char_c` | none from cohort simulation | no continuity command; a player event may later trigger activation on the same record |

The `char_b` command remains a Character Core request, not a planner write. It
must be rejected on stale actor revision, scope/privacy failure, duplicate
input or malformed projection. It must never cause a five-pool materialization
because it has no memory candidate.

## 5. Frozen Cohort Input

V1 does not add a population roster store. The caller obtains three committed
Organization schedule rows and publishes only a read-set payload with these
closed semantic fields:

```text
cohort_ref                 = cohort:bakery:W0 or cohort:bakery:W1
cohort_actor_refs          = [character:char_a, character:char_b, character:char_c]
organization_ref           = org:bakery
recipient schedule inputs  = frozen existing Organization schedule views
world_mode projection      = committed simulation mode
base_revision_vector       = exact Organization source vector
report_scope               = organization:summary
selector_revision          = selector:cohort-bakery:v1
ruleset_revision           = rules:cohort-bakery:v1
deterministic_seed         = seed:cohort-bakery:<window>
```

The input may contain only public or `organization:summary` values needed for
the existing schedule source. It must not contain branch, private, actor-other
or nested private metadata. It must not include raw actor memory, social
beliefs, relationship facts, financial accounts or an inferred household
truth.

The cohort selector is deterministic:

```text
1. sort by fixed cohort actor order: char_a, char_b, char_c
2. accept only a source row whose actor ref matches that position
3. apply the fixed cost table below while budget remains
4. report every skipped actor in unprocessed_cohort_refs
```

| Disposition | Cost | Output classification | World write |
| --- | --- | --- | --- |
| `char_a / schedule_gated_supply` | 1 | owner-bound intent | only Organization Owner after admission |
| `char_b / routine_work` | 1 | presentation seed | none |
| `char_c / relationship_negotiation` | 1 | activation candidate | none |

The V1 default batch budget is `3`. A lower externally committed budget may
produce fewer results, but never changes the actor ordering or upgrades a
skipped actor into a write.

## 6. Two-Cadence Protocol

### 6.1 W0

```text
committed world-mode + three Organization schedule projections
  -> population_cadence_event(W0)
  -> SimingRuntime.tick
  -> frozen three-actor read-set
  -> planner report:
       char_a owner_bound_intent(schedule_gated_supply)
       char_b presentation_seed(routine_work)
       char_c activation_candidate(relationship_negotiation)
  -> Organization Owner receipt for char_a only
  -> Character Core commands for char_a and char_b only
  -> bounded cycle audit/read-model summary
```

`char_a` may receive an `event_experience` candidate only when the frozen
projection declares `exposure_basis=affected_directly` or
`public_propagation` and the Character Core admission rules accept it. `char_b`
and `char_c` receive no memory candidate in W0.

### 6.2 W1

`W1` must use a new cadence id, new window range, new deterministic seed and
the exact source revision vector after W0's committed Organization outcome.
It must not reuse W0's read-set, plan, Owner request digest or Character Core
expected revision.

For each actor, the capability obtains the Character Core revision before it
submits any Owner intent. For multiple same-actor seeds in one cycle, the next
expected revision advances monotonically after a `committed` receipt. An old
`idempotent_replay` receipt must not lower that actor's current revision.

If an Owner or Character Core receipt is `requeued` or `rejected`, the cycle
must report that outcome and stop subsequent continuity writes that would rely
on the failed actor state. It must not return `accepted` merely because an
earlier seed committed.

## 7. Player Activation

The cohort simulation only creates an `activation_candidate` for `char_c`.
It does not activate the agent by itself.

When player focus, dialogue or a supported actor-targeted interaction occurs:

```text
structured player input
  -> ActivationPolicy.evaluate
  -> activation lock
  -> eligible pending memory materialization
  -> synchronous L1/L2/L3/L4 cognition callback
  -> lock release and activation receipt
```

The activated agent is the existing `CharacterRecord` for `char_c`; no second
agent, no transfer of world authority and no `control_mode` substitution is
allowed. This V1 keeps the callback synchronous. A detached or resumable
activation session is out of scope until it has an explicit lease contract.

## 8. Rejection And Privacy Matrix

The following inputs must stop before the planner, Owner or Character Core as
shown. All production writes are zero.

| Input | Required result |
| --- | --- |
| branch marker, private marker or mismatched actor ref anywhere in a nested projection | `requeue: projection_scope_denied` |
| stale cadence/source vector, changed read-set digest or changed policy/selector/ruleset pin | `requeue: stale_read_set` |
| unregistered behavior or an attempt to make `relationship_negotiation` objective | rejected candidate; no Owner or Character Core command |
| missing, throwing, boolean, negative or non-integer character revision reader | `requeue: continuity_revision_reader_invalid`; no Owner write |
| missing Owner receipt for `char_a` objective result | `owner_settlement_required`; no `char_a` continuity command |
| Owner rejection or request digest mismatch | no settled seed; no Character Core command |
| duplicate W0/W1 cadence with identical frozen input | Owner `duplicate_replayed` and Character Core `idempotent_replay`; no progression |
| duplicate key with changed plan/source/context/actor | `idempotency_key_reused`; no Owner/Character Core progression |
| `char_b` presentation-only seed memory materialization attempt | no candidate exists; no five-pool write |
| `char_c` cohort candidate without player event | `activation_candidate` only; no Character Core command or LLM call |

## 9. Replay And Audit

The V1 Harness must compare full history with checkpoint plus tail for:

- Gameplay/Organization projection digest;
- all three actor continuity snapshots;
- each actor's revision, seed projection, pending candidates, materialization
  receipts and semantic timeline;
- cohort report ordering, unprocessed actors, selected actor refs and budget;
- Owner receipt references and cycle status.

The existing Siming audit/read model must expose only bounded aggregate fields:

```text
cohort_ref
window
selected_count / unprocessed_count
presentation_seed_count
activation_candidate_count
owner_intent_count / owner_committed_count
continuity_committed_count / continuity_requeue_count
read_set_digest / result_digest / reason
```

It must not expose a character's five-pool content, hidden relationship
evidence, raw private source payloads or non-mainline branch values.

## 10. Acceptance Criteria

The implementation is accepted only when all are true:

1. one `population_cadence_event` for W0 and W1 enters the existing
   `SimingRuntime.tick(...)`; no second Siming decision path exists;
2. each W0/W1 report deterministically contains all three fixed cohort refs
   under budget `3`;
3. `char_a` is the only actor for which Organization Owner writes objective
   truth and returns the exact existing event family/receipt;
4. `char_a` and `char_b` get separate actor-local seeds through Character
   Core, while `char_c` gets only an activation candidate;
5. `char_b` never receives a memory candidate or five-pool materialization;
6. a player dialogue/focus for `char_c` activates the same identity and runs
   only while the existing activation lock is held;
7. W1 observes W0's committed source revision and all per-actor revisions
   advance monotonically;
8. full replay equals checkpoint plus tail across world and all three actor
   continuity projections;
9. stale, branch/private, cross-actor, unknown behavior, owner rejection,
   duplicate mismatch and budget exhaustion all produce the stated zero-write
   result;
10. focused tests and one direct Harness profile prove the vertical; the
    profile remains excluded from aggregate `all` until it has independent
    green evidence and project policy promotes it.

## 11. Non-Goals

This V1 explicitly does not implement:

- a general population or NPC truth owner;
- arbitrary behavior registration or runtime capability discovery;
- relationship, household, wage, inventory, market, migration, ecology,
  government or civilization world effects;
- a global social knowledge graph;
- branch promotion or preview-to-production movement;
- multi-region sharding, unbounded catch-up or a background scheduler;
- an LLM loop for each far-field actor;
- detached activation leases or a second agent identity;
- a complete population or civilization simulation claim.

Every future behavior must be introduced independently through the existing
source-controlled capability/catalog, one named Owner, receipt, privacy,
idempotency, replay and Character Core admission contract.
