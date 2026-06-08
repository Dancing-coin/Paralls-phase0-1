# System L1 ESM Full-Domain Design

## Status

- Date: `2026-06-09`
- Status: active alignment spec
- Current repo truth:
  - this spec is no longer purely prospective
  - a substantial subset is already implemented and verified
  - recent visibility-state-family and result-identity alignment slices are now committed

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
- result-entity identity:
  - `ActionResolutionResult.entity_id`
  - `ConstraintStateResult.entity_id`
  - `StateMachineTransitionEvent.entity_id`
  - `ObjectStateResult.entity_id`
  - `EnvironmentStateResult.entity_id`
- supported environment fields:
  - `light_level`
  - `noise_level`
  - `smoke_density`
  - `visibility_level`
- field-state identity and freshness:
  - `field_id`
  - `updated_at`
- environment-state replay identity on result objects:
  - `EnvironmentStateResult.field_id`
  - `EnvironmentStateResult.source_environment_id`
  - `EnvironmentStateResult.updated_at`
- coarse field propagation to adjacent zones
- canonical `world_result` envelope fields with compatibility preservation
- audit/replay-visible stable ids and proof coverage

### Still Open

- broader settlement matrix beyond the current demo slice
- deeper alignment for template richness and workbench-facing debug surfaces
- a clearer positive/negative statement of what this repo intentionally does not implement inside `ESM`

## Non-Goals

- full persistent simulation
- full material system
- final production workbench
- full cross-system orchestration
