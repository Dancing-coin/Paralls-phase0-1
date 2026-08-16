# INF-3R-A Frost Production Admission Design

Status: `implemented and verified; no production propagation write is authorized`

Date: `2026-08-13`

## Purpose

INF-3R-A resolves only the owner-admission gap that blocked INF-3R. It does
not settle a production outcome, add a propagation bridge, create a world
runtime, or authorize any additional hazard consumer.

The prerequisite has two existing-owner read contracts:

| Contract | Existing owner | Canonical source | Result |
| --- | --- | --- | --- |
| Frost source | `EcologyHazardAuthority` | committed `semantic.effect.settled` on the crop stream, carrying the ecology frost provenance payload | `FrostPropagationSource` |
| Production target | `ConstructionProductionAuthority` | committed facility-acquisition and run-started events rebuilt by its existing projection | `FrostProductionTargetSelection` |

`FrostPropagationSource` records the hazard, crop, plot, region, source event
and revision, causal/evidence refs, due tick, semantic/rule/policy revisions,
and visibility. The source is derived only from a committed ecology frost
event; caller data cannot manufacture it.

The construction query deterministically selects exactly one `started` run for
the source plot whose `finish_tick <= due_tick`. It returns the target stream
and its committed revision. Missing, ambiguous, or not-due targets return a
structured read-only rejection. The query writes nothing.

## Boundaries

`CropRecord.plot_ref` is optional for compatibility with the existing
frost-to-crop vertical. A frost settlement lacking this owner-supplied fact is
not an INF-3R-A source and cannot proceed to INF-3R.

The R-A source payload is carried by the existing crop semantic event, not a
new ecology stream. The target query is an existing construction projection,
not a scheduler or a target-selection owner. Only INF-3R may later assemble a
validated source and accepted target into the existing construction fragment
and one append batch.

No source or target query writes a production result. Godot, client, LLM,
Siming, creator, and MCP inputs remain proposals/evidence only.

## Required evidence

`infra-frost-production-admission` must independently assert:

1. committed frost source provenance and redacted public view;
2. source missing a plot is unavailable without an extra write;
3. one due production target is selected from committed construction facts;
4. missing, ambiguous, and not-due targets are zero-write read rejections;
5. source revision/privacy rejection remains zero-write;
6. duplicate source settlement remains idempotent;
7. full and checkpoint-tail replay remain equal for the source and target
   input facts. The construction projector's checkpoint is its immutable
   committed projection prefix, rebuilt with only the ordered tail events;
   it is not a second event store or construction truth owner.

Completion only admits the source and target contracts. It does not complete
INF-3R or claim any frost-to-production event has been committed.

## Verification record

On 2026-08-13, `infra-frost-production-admission` independently passed all
nine declared capability assertions. Focused backend evidence passed 18 tests;
the repository regression suite passed `2551 passed`; and `git diff --check`
passed. The profile report is
`.harness/verification/infra-frost-production-admission-report.json`.
