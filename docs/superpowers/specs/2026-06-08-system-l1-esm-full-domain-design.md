# System L1 ESM Full-Domain Design

## Status

- Date: `2026-06-10`
- Status: active alignment spec
- Current repo truth:
  - this spec is no longer purely prospective
  - a substantial subset is already implemented and verified
  - recent visibility-state-family and result-identity alignment slices are now committed
  - current worktree also includes verified-but-uncommitted request-lineage, thermal-field, and capability-manifest alignment slices

## Goal

Define what it means for `ESM` to be complete enough as a full `System L1` subdomain in this repository.

## Problem

The repository now has a stronger `ESM` than before, but it is still only a narrow slice.

Without a repo-local full-domain definition, future work will either:

- overclaim completion
- or keep growing `ESM` without a stop condition

## Required Domain Parts

Repository-local `ESM` completion must define:

1. supported settlement classes
2. supported constraint classes
3. supported object/environment state templates
4. supported environment fields
5. supported field propagation behavior
6. replay/debug proof expectations

## Minimum Settlement Matrix

At minimum the repo should explicitly support:

- interaction success
- interaction rejection by constraint
- environment-state shift

and define whether it also supports:

- object-use variants
- environment-trigger variants
- actor-state-affecting variants

## Minimum Field Set

The repo should explicitly state which field dimensions are real:

- light
- noise
- thermal
- visibility-affecting conditions

Each field does not need a full solver, but the contract must say whether it is:

- real and active
- real but coarse
- planned but not yet active

## Replay / Debug Requirement

`ESM` is not complete enough unless its outputs are replay-visible and audit-visible in a stable way.

That does not require a giant workbench, but it does require:

- stable result identity
- stable result fields
- explicit verification coverage

## Current Alignment Register

### Already Implemented And Verified

- supported settlement classes:
  - interaction success
  - interaction rejection by constraint
  - environment-state shift
- supported constraint classes:
  - explicit `distance_constraint`
  - explicit `out_of_range` code
  - explicit `unsupported_environment_request`
  - explicit `unsupported_change_type` code for repo-local unsupported environment variants
- supported result families:
  - `ActionResolutionResult`
  - `ConstraintStateResult`
  - `BodyStateResult`
  - `ObjectStateResult`
  - `EnvironmentStateResult`
  - `StateMachineTransitionEvent`
- result-to-state-machine linkage:
  - `ObjectStateResult.machine_id`
  - `EnvironmentStateResult.machine_id`
- explicit environment machine templates:
  - `light_source`
  - `heat_source`
  - `smoke_source`
  - `noise_source`
- result-entity identity:
  - `ActionResolutionResult.entity_id`
  - `ConstraintStateResult.entity_id`
  - `StateMachineTransitionEvent.entity_id`
  - `ObjectStateResult.entity_id`
  - `EnvironmentStateResult.entity_id`
- supported environment fields:
  - `light_level`
  - `noise_level`
  - `thermal_level`
  - `smoke_density`
  - `visibility_level`
- field-state identity and freshness:
  - `field_id`
  - `updated_at`
- thermal-field behavior:
  - `thermal_level` is real but coarse in this repo-local slice
  - `alerted` environment shifts raise it to `warm`
  - adjacent propagation softens it to `mild_warm`
- environment-state replay identity on result objects:
  - `EnvironmentStateResult.field_id`
  - `EnvironmentStateResult.source_environment_id`
  - `EnvironmentStateResult.updated_at`
- coarse field propagation to adjacent zones
- canonical `world_result` envelope fields with compatibility preservation
- audit/replay-visible stable ids and proof coverage
- phase verification now explicitly proves:
  - success-path follow-on results preserve shared request lineage
  - environment-state evidence carries the coarse thermal-field contract
- explicit repo-local capability manifest now states:
  - supported settlement classes
  - supported constraint classes
  - supported environment change types
  - supported / unsupported environment-request variant families
  - explicit rejection behavior for unsupported environment-request variants
  - current supported environment change types are `light_level_drop`、`light_level_restore`、`thermal_level_rise`、`smoke_density_rise`、`noise_level_rise`
  - current environment machine catalog includes `light_source`、`heat_source`、`smoke_source`、`noise_source`
- minimal repo-local workbench snapshot now exposes:
  - state-machine template ids
  - material template ids
  - environment machine ids
  - supported / unsupported environment change types
  - current environment field state for the queried zone
  - latest environment request
  - latest environment resolution
  - latest environment result
  - latest state-machine transition
  - bounded recent environment-request / resolution / result / transition history window
  - bounded recent environment-request / resolution / result / transition history window

### Repo-Local Stop Condition Reached

- the repository-local completion target defined by this spec is now satisfied on the current worktree:
  - supported settlement classes are explicit
  - supported constraint classes are explicit
  - object/environment template surfaces are explicit enough for runtime-used ids
  - supported environment fields and propagation behavior are explicit
  - replay/debug proof expectations are explicit and covered

### Beyond This Repo-Local Target

- broader settlement matrix beyond the current repo-local quintet of `light_level_drop`、`light_level_restore`、`thermal_level_rise`、`smoke_density_rise`、`noise_level_rise`
- deeper alignment for template richness and workbench-facing debug surfaces beyond the current minimal snapshot/catalog/recent-history surface

These are future expansion directions, not blockers for closing this repo-local `ESM` full-domain plan.

## Non-Goals

- full persistent simulation
- full material system
- final production workbench
- full cross-system orchestration
