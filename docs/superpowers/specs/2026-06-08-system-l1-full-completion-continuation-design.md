# System L1 Full Completion Continuation Design

## Goal

Define the continuation target after the currently finished ordered `System L1 Phase 1` plan tree.

This spec exists to prevent a false stop condition.

The ordered plan tree is now complete, but the repository must continue until `System L1` is complete as a full domain, not merely:

- structurally present
- minimally routable
- verification-green on a narrow slice

The purpose of this spec is to define the remaining work required to turn the current repository from:

- `plan-tree-complete System L1`

into:

- `full-volume System L1`

for this repository’s `Phase 1` scope.

## What “Full-Volume L1” Means Here

For this repository, `full-volume System L1` means:

1. all named `System L1` subdomains from the main `Phase 1` design exist as explicit repository-local implementation surfaces
2. those surfaces are not only file-level placeholders or route-only seams
3. they are wired deeply enough that the repository can honestly claim the domain is implemented rather than merely scaffolded
4. the verification surface proves that implementation in a repeatable way

This spec does **not** mean:

- finish `System L2`
- finish `Character Agent L1-L4`
- finish full `Siming`
- finish all future `L6` infrastructure

The boundary remains: `System L1` only.

## Why The Finished Plan Tree Is Not Yet The Same As Full Completion

The ordered plan tree was the right execution path because it:

- preserved the architecture boundaries
- kept the shared raw-fact spine stable
- prevented collapsing `L1`, `L2`, and character-private layers
- built a provable minimum `System L1` domain

But a plan tree can be complete while the domain it targets is still uneven.

Right now the repository contains:

- strong `visual_fact` and `spatial_access_fact` seams
- stronger `ESM` than before
- an explicit first auditory route
- explicit remaining emitter shells
- a stronger verification surface

But it still does not yet justify the claim:

> "`System L1` is fully complete as a domain."

The gap is not in architecture identity anymore.
The gap is in domain depth, runtime wiring, and breadth across the full `L1` fact surface.

## Completion Principles For The Next Specs

All continuation specs written after this one must follow these principles:

### 1. Full-L1 completion over shell completion

A spec must not stop at:

- file exists
- one method exists
- one route exists

unless that domain is explicitly declared complete by design.

### 2. Runtime truth over static existence

When a domain represents a world-facing `L1` capability, the preferred target is:

- runtime-wired
- structured
- authority-safe
- verification-visible

not just statically present.

### 3. No boundary erosion

The continuation must not:

- move candidate compilation into Godot
- move `Per-Character` filtering into Godot
- make `fact_router` cognitive
- let `System L1` emit character-private conclusions
- create new ad hoc transport paths

### 4. Full-volume does not mean fake completeness

If the repository cannot honestly finish a subdomain in this repo without violating scope, the spec must say so explicitly.

In that case, the subdomain must be made:

- explicit
- bounded
- verified
- clearly non-final

instead of silently pretending it is “done”.

## Remaining Full-Completion Gaps

### 1. Remaining five fact families are not full-volume yet

These families now exist as emitter shells:

- tactile
- thermal
- olfactory
- physiology-state
- role-state

That is not enough for full completion.

At full-completion level, each family needs:

- a stable raw-fact shape
- an emitter contract
- at least one intentional runtime trigger path or an explicit explanation for why the repository stops one step earlier
- verification that proves the family is real in repository terms

The five families do **not** all need the same runtime depth.
But they cannot remain only “one file, one method” and still count as a full `L1` domain.

### 2. Auditory facts are present but not yet a full auditory `L1` subdomain

The repository now has:

- auditory raw-fact structure
- a Godot-side emitter
- an authority route
- verification proof of emission

That is substantial progress, but still not the same as a full auditory `L1` domain.

The remaining auditory completion questions are:

- what is the stable auditory fact family set
- which auditory facts stay `L1`-only
- which auditory facts become candidate-compilable
- what propagation and reachability semantics are real in this repo
- how coarse or rich the human-output/audio-runtime coupling should be

These questions need explicit specs.

### 3. `ESM` is no longer tiny, but still not a complete domain

Current `ESM` work now covers:

- interaction settlement
- constraint result shape
- minimum environment field state

But full-volume `ESM` still requires a clearer repository-local definition of:

- supported settlement classes
- supported state-machine template classes
- supported environment-field classes
- supported propagation rules
- supported replay/debug surfaces

Without that, `ESM` remains stronger than before but still incomplete as a named `L1` subdomain.

### 4. Multi-sensory ingress into the `L1 -> L2` seam is still incomplete

Today the candidate compiler only handles:

- `visual_fact`
- `spatial_access_fact`

That is acceptable for the finished plan tree, but not sufficient for a full-volume claim across all meaningful `L1` sensory families.

This does **not** mean every family must immediately compile upward.

It means the repository must explicitly decide, per family:

- `L1-only for now`
- `candidate-compilable now`
- `blocked until more runtime truth exists`

That policy itself is part of full completion.

### 5. Verification truth and repository truth still need sync discipline

The verification surface is now much stronger, but repository-level summary docs can still drift from implementation truth.

That is a quality problem because:

- future work will trust those summaries
- review quality drops if repo-local docs lag behind current evidence

A full-volume `L1` repository must keep:

- implementation truth
- verification truth
- summary truth

aligned.

## Required Follow-On Spec Set

To complete `System L1` as a full-volume domain, the next spec set should cover at least these four areas.

### A. Runtime-Wired Remaining Emitters Design

Purpose:

- take the five remaining emitter families beyond shell level

Must answer:

- which two or more families become fully runtime-wired in this repo
- which others stay bounded but still explicit
- what runtime source each family depends on
- what proof is required for each one

### B. Auditory Domain Completion Design

Purpose:

- turn the current auditory route into a full auditory `L1` subdomain

Must answer:

- fact taxonomy
- propagation semantics
- loudness/speech/reachability semantics
- candidate-compiler policy
- runtime verification evidence requirements

### C. Repository-Local ESM Full-Domain Design

Purpose:

- define what “complete enough `ESM`” actually means in this repository

Must answer:

- supported settlement matrix
- supported state-machine templates
- supported environment fields
- propagation limits
- replay/debug boundary

### D. Verification Truth Sync Design

Purpose:

- keep code truth, verification truth, and repository truth aligned

Must answer:

- which reports are authoritative
- which checklists are normative vs informational
- what must be updated when a new `L1` fact family lands

## Non-Goals

This continuation spec must not be read as permission to:

- re-open the already finished child-plan order
- collapse `L1` and `L2`
- treat shell existence as enough for full completion
- over-expand into higher layers
- make “full-volume” mean “infinite scope”

## Success Criteria

This spec is successful when future specs written from it clearly guide the repository toward:

1. a fully claimed `System L1` domain
2. deeper runtime truth for weak subdomains
3. stronger breadth across the full L1 sensory/state surface
4. no boundary confusion with `System L2` or character cognition

## Final Summary

The ordered `System L1 Phase 1` plan tree is complete.

That is a milestone, not the final definition of `L1` completion.

The next spec set must explicitly guide the repository through the remaining distance from:

- `plan-tree-complete`

to

- `full-volume System L1`

without reopening solved boundary questions or faking maturity where only shells exist.

