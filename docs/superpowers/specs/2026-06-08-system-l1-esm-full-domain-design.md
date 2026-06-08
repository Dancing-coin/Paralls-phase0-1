# System L1 ESM Full-Domain Design

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

## Non-Goals

- full persistent simulation
- full material system
- final production workbench
- full cross-system orchestration

