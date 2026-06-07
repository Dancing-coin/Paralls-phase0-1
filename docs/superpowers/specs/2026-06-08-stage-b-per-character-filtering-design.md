# Stage B Remaining Design: Per-Character Filtering And Character-Agent L1 Consumption

## Goal

Define the remaining work for Stage B of the migration from the current demo repo toward the main-project perception architecture.

Stage A is already completed enough to prove:

- system-level `L1` raw fact production exists
- system-level `L2` candidate percept compilation exists
- a first `Per-Character` filter boundary exists
- a `CharacterPerceivedEvent` object exists

So this spec does **not** redesign those pieces.

This spec only covers what still remains for Stage B:

1. make the `Per-Character` filter do real role-private filtering
2. move character-facing consumption toward `CharacterPerceivedEvent`

## What Is Already Done

The current repository already has:

- `CandidatePerceptEvent`
- `compile_candidate_percepts(...)`
- `CharacterPerceivedEvent`
- `filter_candidate_for_actor(...)`
- non-breaking parallel wiring behind `raw_fact_event`

That means the remaining problem is no longer “how do we create the new middle-layer objects”.

The remaining problem is:

> how to make those new middle-layer objects actually matter to character-facing behavior.

## Stage B Remaining Scope

This spec covers only these missing capabilities:

### 1. Real Per-Character Filtering Rules

The current `Per-Character` filter is only a boundary placeholder.

It currently does little more than:

- accept if the target actor matches
- otherwise drop

That is not yet the role-private world version required by the main project.

The next version must become a true role-private filter.

### 2. Character-Agent L1 Consumption Switch

The current repo still primarily behaves as though character-facing downstream logic is anchored in:

- raw fact handling
- shared runtime projection
- shared candidate-style state

That means `CharacterPerceivedEvent` exists, but has not yet become the true default character-facing input boundary.

The next stage must begin shifting character-facing consumption toward:

- role-private perceived events

## Scope Boundary

This spec does **not** include:

- full all-senses rollout
- full role profile system
- complete line-of-sight simulation
- full memory rewrite
- complete L2 understanding redesign
- full character-agent `L1-L4` refactor

It covers only the smallest meaningful Stage B closure.

## The Main Problem To Solve

The main-project architecture requires:

- raw world facts
- candidate percepts
- role-private perceived events

to be distinct.

The current repo now has those objects,
but only the first two layers have meaningful behavior.

The final missing step for Stage B is:

> make role-private perceived events the real boundary that begins to matter in the runtime, not just a model that exists.

## Required Behavioral Upgrade

## 1. Candidate Percepts Must Become Role-Variant

The filter must stop being a target-id gate only.

At minimum it should be able to vary results by actor using:

- distance
- orientation / facing
- zone / privacy band
- current focus / attention

These do not need to become a full realism engine.

They just need to become enough to produce:

- different perceived outputs for different actors

from the same candidate percept.

## 2. Character-Facing Consumption Must Stop Reading Shared Candidate-Like State First

The character-facing path should begin to prefer:

- `CharacterPerceivedEvent`

instead of:

- direct shared candidate outputs
- shared raw-fact-adjacent state

This does not require removing all old paths immediately.

But it does require introducing at least one real path where:

- a filtered perceived event becomes the authoritative input for the next stage

## Minimum Filtering Dimensions

The minimum useful Stage B filter should consider:

### Distance

If a candidate percept implies a target too far away for the given actor:

- drop it
- or downgrade it

### Facing / Orientation

If the actor is not oriented toward the candidate target, and the percept channel requires forward awareness:

- drop it
- or classify it as weaker / absent

The initial version can use a coarse facing rule.

### Zone / Privacy

The filter should be able to consume:

- `current_zone_id`
- `privacy_band`

from the low-level projected state and use them as context for whether a candidate survives.

### Focus / Attention

If the actor’s current focus makes a candidate more plausible or more immediate:

- preserve it
- potentially prefer it over other simultaneous candidates

This should still be simple in the first Stage B pass.

## Suggested First Runtime Target

The first runtime target should be narrow and explicit:

- take `visual_fact` and `spatial_access_fact`
- compile them into candidate percepts
- filter them for `char_a`, `char_b`, and `char_c`
- expose at least one downstream path where a character-side service consumes `CharacterPerceivedEvent`

This is enough to prove the architecture seam without pretending the entire role cognition chain is done.

## Recommended New Objects / Services

### PerActorPerceptionContext

Introduce a small context object or function input describing the minimum filter context for one actor:

- `actor_id`
- current zone
- privacy band
- current focus target
- optional coarse position / facing info

This keeps the filter logic explicit and keeps the service from reaching into too many globals.

### Filter Result Policy

The filter should be allowed to:

- emit one `CharacterPerceivedEvent`
- emit none

The first Stage B pass should avoid introducing complex probabilistic outputs or scores unless clearly needed.

## Consumption Shift Strategy

Do not cut over the whole repo at once.

Instead:

### Step 1

Introduce one explicit downstream bridge:

- `CharacterPerceivedEvent -> character-facing input adapter`

### Step 2

Use that adapter in one narrow path first, for example:

- visual target awareness
- or spatial approach awareness

### Step 3

Keep the old raw/candidate side-paths alive only as temporary compatibility paths.

### Step 4

Only after the new path is stable, start removing direct shared-state dependence.

## What Stage B Remaining Must Not Do

It must not:

- re-open the settled raw-fact contract
- push filtering back into Godot
- turn runtime projection into the private-perception layer
- let `CandidatePerceptEvent` become “close enough” and skip the real private-perception cut

## Success Criteria

This remaining Stage B work is successful when:

1. The filter uses real actor-specific context instead of only target-id gating.
2. The same candidate percept can produce different outcomes for different actors.
3. At least one real character-facing path now consumes `CharacterPerceivedEvent`.
4. The repo is no longer only “architecturally ready” for private perception, but actually begins using it.
5. Existing Phase 0 and L1 verification flows remain green.

## Final Summary

Stage A built the new middle-layer objects.

The remaining Stage B work must make them operational.

In plain language:

> candidate percepts must stop being a neat intermediate artifact and start becoming the real source for actor-specific world versions.
