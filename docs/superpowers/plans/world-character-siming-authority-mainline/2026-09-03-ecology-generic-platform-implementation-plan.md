# General Ecology Platform Implementation Plan

Status: `implemented-and-verified`

## Gates

1. v3/2.0 typed content and exact admission.
2. Ecology region/grid/environment/resource/crop/species runtime.
3. Hazard lifecycle, recovery and bounded propagation.
4. Owner-bound consumer contracts for six target domains.
5. Population signal and procedural presentation.

Each gate is RED → GREEN, then focused Harness, full/checkpoint-tail replay,
privacy, revision, idempotency, receipt, tamper and zero-write evidence. A
failed gate blocks all later gates.

## Work Packages

1. `region-topology-and-grid-state`: strict content and region/cell records.
2. `weather-climate-and-water-cycle`: deterministic temperature, moisture and
   water-cycle projections.
3. `soil-resource-regeneration`: soil, contamination and resource lifecycle.
4. `crop-and-habitat-lifecycle`: crop stages, health, yield potential and habitat.
5. `species-community-and-food-web`: wild species biomass and typed trophic edges.
6. `multi-hazard-lifecycle`: seven typed hazards and lifecycle transitions.
7. `recovery-and-resilience`: explicit recovery policies and terminal outcomes.
8. `regional-period-close-and-propagation`: period close, graph propagation and
   WorldMode cadence integration.
9. `owner-bound-ecology-consumers`: six exact target-owner admission families.

## Constraints

- Reuse `GameplayEventStore`, `SettlementPlan`, existing replay and `WorldModeProfile`.
- Preserve existing narrow Ecology/INF rows and all August INF status.
- Do not add scheduler, clock, generic consumer registry, router, coordinator,
  writer, owner or second runtime.
- Do not infer facts from names, fixtures, biome tags or caller paths.
- Any unknown, multiple, stale, private, conflicting or unadmitted input is
  zero-write before mutation.

## Completion

Completion requires all nine packages, all five gates, six consumer contracts,
Population signal restrictions, procedural presentation evidence and repository
regression. The final audit must cite focused tests, Harness reports,
full/checkpoint-tail replay and `August INF A-D = not complete`.

Completion evidence: [Ecology Generic Platform Completion Audit](../../specs/world-character-siming-authority-mainline/2026-09-03-ecology-generic-platform-completion-audit.md),
Ecology Harness `57 passed`, repository pytest `4481 passed`, compileall and
diff check green.
