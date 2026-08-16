# INF-3R-B Production Recipe Admission Design

Status: `implemented and verified; no frost consequence write is authorized`

Date: `2026-08-13`

## Purpose

INF-3R-B resolves the final identified input-owner gap before INF-3R can call
the sole admitted construction fragment. `ConstructionProductionAuthority.
build_due_finish_fragment` requires `ProductionRun` and `Recipe`; verified
INF-3R-A supplies only the committed run and production stream revision.

## Required owner contract

`ConstructionProductionAuthority` is the existing owner: it already receives
and validates `Recipe` while committing the existing
`gameplay.construction_production.run_started` event to
`gameplay:construction_production:{facility_ref}`. R-B extends that existing
event payload with an immutable recipe snapshot limited to the fragment inputs:
`recipe_ref`, `output_item`, and `duration_ticks`. It does not create a recipe
stream, registry, or separate truth store.

`ConstructionProductionProjector` rebuilds that snapshot from committed
`run_started` facts and exposes a read-only recipe result keyed by `run_ref`.
The source revision is the committed run-started event stream revision; callers
must supply the expected source revision and receive a zero-write rejection if
it is stale. The existing event remains `project`-visible: the public view is
rejected, while the internal authority view receives the immutable recipe.
Full reconstruction uses the existing projector's committed prefix plus ordered
tail mechanism. Older run-started events without the snapshot are a
compatibility read rejection, never a caller fallback.

No ecology, semantic bridge, obligation coordinator, client, Godot, LLM,
Siming, creator, or MCP caller may construct the recipe from proposal data.
No new recipe truth store, runtime, scheduler, or event stream is authorized.

## Completion condition

Completion requires focused failing-to-passing tests and an independent
`infra-frost-production-recipe-admission` Harness profile, with separate
assertions for committed retrieval, privacy, missing/legacy/stale rejection,
idempotency, and full/checkpoint-tail rebuild. It admits recipe input only; it
does not settle a frost consequence or complete INF-3R.

## Verification record

On 2026-08-13, `infra-frost-production-recipe-admission` independently passed
five declared assertions. The focused construction/ecology regression passed
25 tests, repository pytest passed `2556 passed`, and `git diff --check`
passed. Evidence is at
`.harness/verification/infra-frost-production-recipe-admission-report.json`.
