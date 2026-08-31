# Autonomous Row Resolution Mandate

Status: `approved standing authorization; Goal active; August INF A-D not complete`

The [upstream fact creation mandate](2026-08-27-autonomous-upstream-fact-creation-mandate.md)
extends this authorization: a required product input may be created as a
strictly row-specific committed source/projection under an existing owner, with
complete business literals and decision trace. A new owner remains permissible
only under conflict-matrix proof and a complete row-specific contract.

## Authorization

The main thread may autonomously select, contract, implement, verify, and
document the next product-significant mainline row. It may make business choices
when the repository has several legal paths, including admitting a strictly
row-specific new truth owner when the conflict matrix proves no existing owner
can legally own the fact.

This authority is not limited to least-privilege semantics. Decisions must
balance product value, coherent world behavior, future content leverage,
ownership clarity, privacy, replay, verification cost, and implementation risk.

## Mandatory Workflow

```text
product opportunity or row blocker
  -> owner-operation conflict-matrix preflight
  -> decision record with alternatives and product rationale
  -> row-specific contract and plan
  -> immutable package/digest and descriptor/catalog admission when needed
  -> RED tests -> implementation -> independent Harness
  -> receipt, privacy, idempotency, full/tail replay, zero-write proof
  -> audit, remaining-scope, README, taxonomy, and checkpoint update
```

The main thread owns integration. Bounded subagents may own product-contract,
package-admission, owner-vertical, verification, or independent-audit work.
Each must preserve the conflict matrix and report evidence to the main thread.

## Ordinary Blocker Handling

Ordinary missing-row blockers do not pause execution. The loop examines the
next viable product row, records rejected alternatives, and continues through
the ordered mainline. It does not repeat an exhausted existing-owner discovery
audit merely to avoid a decision.

Only a true contradiction, unavailable external fact, unavailable credential,
or irreconcilable evidence/replay/privacy failure is escalated. Test failures
are repaired and rerun; they are not a substitute for a decision record.

## Autonomous Gap Resolution

The main thread must actively resolve ordinary product, content, contract,
verification, replay and presentation gaps that arise while delivering a row.
It does not wait for a human to restate a blocker or to ask it to repair a
missing link already visible in the repository. It must apply the same standard
to gap resolution as to any other autonomous decision:

- choose a concrete solution that fits the project mission and the current
  product loop, rather than the smallest technically legal placeholder;
- weigh user-visible value, world coherence, future content leverage, existing
  owner boundaries, privacy, replay, verification cost, implementation risk,
  and the impact on adjacent INF lanes;
- preserve traceability by recording the rejected alternatives, source facts,
  owner/outcome partition, remaining limitations, and verification evidence;
- repair code, contracts, tests, Harnesses and documentation together when the
  gap is inside an already admitted row; and
- retain zero-write only for a genuine missing fact/owner/outcome contract, not
  as a way to defer a solvable implementation or design task.

This authority remains bounded by the permanent prohibitions below. It cannot
turn a gap into a generic owner, generic payment/transfer/transform/promotion,
router, registry, coordinator, writer, settlement authority or second runtime.

## Permanent Boundaries

This mandate does not authorize generic owners, writers, routers, registries,
coordinators, payment/transfer/transform/promotion/settlement authorities,
caller-selected authority coordinates, combined cross-owner receipts, frozen
package mutation, or a second runtime/store/bus/clock/scheduler. Every write
continues through `GameplayCommandEnvelope -> SettlementPlan ->
GameplayEventStore.append_batch()`.

See the [owner-operation conflict matrix](2026-08-26-owner-operation-conflict-matrix-design.md)
and its [baseline inventory](2026-08-26-owner-operation-conflict-matrix-baseline.md)
for duplicate, overlap, supersession, and new-owner rules.
