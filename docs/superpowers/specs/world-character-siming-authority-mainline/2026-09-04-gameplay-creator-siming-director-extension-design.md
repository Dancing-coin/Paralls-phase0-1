# Gameplay Creator Skill and Siming Director Extension Design

Status: `planned; depends on 3D scripted-mystery action platform contracts`

## Purpose

Provide the creator-facing and runtime-director layer for the shared gameplay
platform. A creator describes a game in natural language; a Creator Skill turns
that brief into typed package drafts, tests, scenes and review artifacts. A
Siming Director chooses or proposes already admitted content while the game is
running. Neither layer becomes a world-truth owner.

## Creator Skill contract

The public input is a typed `GameBrief` containing setting, player roles,
desired loops, content references, presentation preferences, target platforms,
performance budget and completion evidence requirements. The skill compiles it
to a `GameplayAuthoringBundle`:

```text
GameBrief
→ family selection
→ typed content drafts
→ package/dependency/conflict declarations
→ descriptor and binding candidates
→ Godot scene/asset references
→ focused tests and Harness profile
→ preview/replay report
```

The skill reuses existing Manifest v3/platform 2.0, canonical digest,
descriptor/catalog, owner adapters, projection and replay rules. It may create
draft files and validation artifacts, but freeze, activation, migration,
rollback and production writes remain governed operations.

When a brief fits an admitted family, the skill generates content only. When it
introduces a new fact, owner or event vector, it emits an extension packet with
the missing contract and stops at that admission boundary; it never invents a
default owner or generic writer.

## Siming Director contract

The director consumes only committed, scope-filtered world/player signals and
returns a `SimingDirectorProposal`:

```text
proposal_ref
world_ref / session_ref
trigger_event_refs
target_actor_ref
candidate_package_ref / candidate_content_ref
adjustment_bounds
policy_revision
expected_revision_vector
deterministic_seed
expiry
explanation_digest
```

Allowed decisions include selecting an admitted gameplay variant, changing
bounded difficulty/tempo, prefetching dependencies, activating a safe-boundary
package, and offering an alternative route after repeated failure. The
proposal is revalidated by the target owner before `append_batch()`.

The director cannot inject graph nodes, choose an owner/stream/event/receipt,
read private facts outside its scope, alter a score/balance/inventory/skill or
delete history. “Real-time” means event/window/session boundaries, not
unbounded per-frame rule mutation.

## Presentation and marketplace boundary

UI panels, system voice and transition effects are revisioned projections of
committed transition state. The creator marketplace, demand publication,
delivery acceptance, usage metering and revenue settlement are separate
platform services; they do not write gameplay facts directly.

## Acceptance criteria

- A brief can be compiled into an admitted existing-family content draft.
- A brief requiring a new fact produces a concrete extension packet instead of
  a fabricated implementation.
- A director can choose two admitted variants at a safe boundary and replay the
  choice deterministically.
- Out-of-scope, private, stale, expired or unadmitted proposals are zero-write.
- Creator drafts, director proposals and production facts remain separately
  auditable and replayable.
