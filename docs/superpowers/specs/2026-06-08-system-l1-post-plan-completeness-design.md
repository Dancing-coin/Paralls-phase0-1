# System L1 Post-Plan Completeness Design

## Goal

Define the next completeness target for `System L1` in this repository after the current ordered `Phase 1` plan tree has been executed to green.

This spec does **not** reopen the already-finished plan tree.
It defines the remaining gap between:

- `plan-complete System L1`

and

- `mature, domain-complete-enough System L1`

for this repository.

## Why This Spec Exists

The current repository can now legitimately claim:

- the ordered `System L1` plan tree is implemented
- backend tests pass
- `verify_phase1_slice.py` passes
- `verify_phase0.py` passes
- `verify_l1_runtime_edges.py` passes

However, passing the ordered plan tree does **not** mean every `System L1` subdomain is equally mature.

Some domains are now:

- present as explicit seams
- verified as structured outputs

but are still only:

- minimal slices
- runtime-light shells
- authority-only routes

This spec defines how to close that maturity gap without widening scope upward into:

- `System L2` full-domain work
- `Character Agent L1-L4`
- `Siming` full implementation
- large `L6` infrastructure work

## Current Repository Reality

As of the current repository state:

### Already strong

- shared `raw_fact_event` cross-boundary spine
- visual fact path
- spatial-access fact path
- reconnect / reseed / runtime-edge verification
- minimum `L1 -> L2` candidate / per-character separation

### Present but still shallow

- auditory facts
- `ESM` field and settlement contracts
- remaining five fact families
- verification and checklist truth sync

These are the maturity gaps this spec addresses.

## Completeness Model

For this repository, a `System L1` subdomain is not considered mature just because a file exists.

Use four levels:

### 1. Shell-complete

The domain has:

- a named emitter / handler / model
- one minimal structured method

This is the lowest acceptable engineering presence.

### 2. Route-complete

The domain has:

- a real shared-contract payload shape
- an authority path
- tests that prove the route exists

### 3. Runtime-complete

The domain has:

- a real runtime trigger or sampling path
- scene/runtime evidence that the fact can actually occur
- verification proof, not only static existence proof

### 4. Domain-complete-enough

The domain has:

- explicit contract
- authority route
- runtime trigger
- verification proof
- a documented statement of what is still intentionally out of scope

This spec is about moving weak domains from:

- shell-complete

to at least:

- runtime-complete

or

- domain-complete-enough

depending on the family.

## Remaining Maturity Gaps

### 1. The Five Remaining Fact Families Are Only Shell-Complete

These currently exist as emitter shells:

- tactile
- thermal
- olfactory
- physiology-state
- role-state

But for this repository they are not yet mature enough, because they still lack one or more of:

- runtime trigger paths
- scene wiring
- authority-route proof beyond static existence
- runtime verification evidence

#### Required maturity target

Each of these five families must reach at least `route-complete`.

At least two of the five should reach `runtime-complete` in this repository, chosen by:

- best current fit with the demo runtime
- lowest ambiguity
- lowest risk of fake semantics

The default recommendation is:

- `role-state`
- `physiology-state`

because both can be derived from already-running low-level runtime state without inventing extra world simulation.

### 2. Auditory Facts Are Route-Complete But Not Yet Domain-Complete-Enough

The repo now has:

- a shared auditory payload shape
- a Godot-side auditory emitter
- an authority route
- verification proof that the auditory emitter is observed

But the domain is still shallow because:

- the route is authority-only
- no candidate-percept policy exists for auditory facts
- no explicit documented rule explains whether auditory facts remain authority-only for now, or which subset should later compile into `System L2`

#### Required maturity target

Auditory facts must become `domain-complete-enough`.

That requires a documented repo-local policy that freezes:

1. which auditory fact types are allowed now
2. whether they are:
   - authority-only
   - candidate-compilable
   - verification-only
3. what the repo intentionally does **not** support yet

This prevents the current authority-only auditory route from being mistaken for a finished auditory perception chain.

### 3. ESM Is Stronger Than Before But Still Not A Full Repository-Local L1 Subdomain

The current `ESM` slice now has:

- stable settlement fields
- stable constraint fields
- minimum environment field state
- verification coverage

But it is still minimal in at least three ways:

- object/environment state-machine templates are thin
- field propagation is effectively limited to a single local light/noise case
- no repo-local workbench or replay-oriented inspection surface exists beyond generic debug traces

#### Required maturity target

`ESM` should become `domain-complete-enough` for this repo by freezing:

1. supported settlement classes
2. supported state-machine template classes
3. supported field dimensions
4. supported propagation granularity
5. explicit non-goals for this repository

This is a design/documentation completion step, not necessarily a large implementation step.

### 4. Multi-Sensory Candidate Compilation Is Still Intentionally Incomplete

The current candidate compiler only promotes:

- `visual_fact`
- `spatial_access_fact`

This is acceptable for the completed plan tree, but it means the repo is not yet a complete multi-sensory `System L1 -> System L2` ingress surface.

#### Required maturity target

Do **not** automatically widen candidate compilation for all new sensory families.

Instead, define a repo-local multi-sensory ingress policy:

- which families remain `L1 authority / replay evidence only`
- which families are allowed into candidate compilation
- what new evidence would be required before promoting a family upward

This avoids overclaiming maturity and also avoids fake completeness.

### 5. Verification Truth And Repository Truth Must Match

The repository currently contains summary/checklist material that can drift from implementation truth.

That drift is itself a completeness problem.

#### Required maturity target

The repo must maintain one authoritative repository-local status surface that is consistent with:

- the actual code
- the actual verification triad
- the current maturity interpretation

That status surface may be:

- one checklist document
- one audit-facing status doc
- one generated report source

but it must not contradict the current codebase state.

## Recommended Follow-On Spec Structure

This spec intentionally does **not** explode the problem into many new top-level features.

The next spec/plans should be organized around maturity closure, not around re-listing everything already built.

### Recommended next spec A

`System L1 Runtime-Wired Remaining Emitters Design`

Focus:

- move selected remaining emitters from shell-complete to runtime-complete

Suggested scope:

- `role-state`
- `physiology-state`

### Recommended next spec B

`System L1 Auditory And Multi-Sensory Ingress Policy Design`

Focus:

- freeze which sensory families can compile upward
- keep `System L1` / `System L2` boundaries explicit

### Recommended next spec C

`System L1 Repository-Local ESM Completion Boundary Design`

Focus:

- define what “ESM complete enough for this repo” actually means
- avoid pretending one light/noise field equals full domain completion

### Recommended next spec D

`System L1 Verification Truth Sync Design`

Focus:

- make checklist / audit / verification outputs agree

## Non-Goals

This spec does **not** authorize:

- moving candidate compilation into Godot
- moving per-character filtering into Godot
- making `fact_router` a cognition layer
- making new sensory facts automatically produce character-private conclusions
- adding ad hoc new transport channels
- treating `System L1` as the place to finish character cognition

## Success Criteria

This spec is satisfied when the repository no longer treats “plan tree complete” as identical to “System L1 mature enough”.

More concretely:

1. the remaining maturity gaps are explicitly named
2. shell-complete vs route-complete vs runtime-complete is distinguished
3. the next follow-on specs can target maturity closure cleanly
4. no upward-scope confusion is introduced

## Final Summary

The current repository has finished the ordered `System L1 Phase 1` plan tree.

What remains is not “redo the same plans”.

What remains is to close the maturity gap between:

- explicit seams that exist

and

- subdomains that are complete enough to be trusted as stable `System L1` building blocks

for continued `Phase 1` work in this repository.
