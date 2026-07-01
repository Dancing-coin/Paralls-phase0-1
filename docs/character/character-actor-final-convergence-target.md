# Character Actor Final Convergence Target

Date: `2026-06-15`

## Purpose

This document freezes the final shared `CharacterActor` target that Stage 2 convergence work must land before full character-agent Stage B can honestly claim final `L4` convergence.

It exists so the repository stops treating the current transitional actor layering as oral-history knowledge.

## Final Shared Actor Host Choice

For this repository, the final shared actor host converges from the current `CharacterReplica` lineage, not from the current `CharacterBase` wrapper.

That means the architectural truth is:

```text
CharacterActor host
-> ControllerPort
-> CharacterMotor
-> CharacterRuntimeState
-> CharacterPresentationInput
-> KnightRoleSkin
-> post-animation embodiment modifier stack
```

The current `CharacterBase.tscn` remains a player-shell wrapper during migration only.
It may keep:

- raw human input ownership
- camera ownership
- player-shell movement shell concerns that have not yet been folded down

It must not remain the long-term architecture truth for the shared actor substrate.

## Final Runtime Chain

The final shared execution chain is:

```text
human / agent / program source
-> source-specific adapter
-> CharacterControllerPort
-> CharacterIntentFrame
-> CharacterRuntimeState
-> CharacterMotor
-> CharacterPresentationInput
-> KnightRoleSkin
-> KnightCombatModifier and future modifier stack
```

This chain must be valid for:

- `char_a`
- `char_b`
- `char_c`

with control source changing the ingress path, not the embodied runtime species.

## ControllerPort Role

`CharacterControllerPort` is the final ingress seam between control source semantics and shared actor runtime execution.

Its job is to:

- accept normalized source-specific adapter output
- preserve explicit control-mode identity
- emit one actor-facing intent/control shape
- stop `PlayerShell`, agent output consumers, and harness/program entry points from each inventing separate direct actor mutation paths

The initial Stage 2 implementation may stay narrow, but it must become the only intended long-term ingress family for:

- `HumanControllerAdapter`
- `AgentControllerAdapter`
- `ProgramControllerAdapter`

## CharacterIntentFrame Role

`CharacterIntentFrame` is the active shared local actor ingress contract.

It is where per-frame local embodiment intent is staged after controller adaptation and before runtime-state and motor execution.

Stage 2 work must move the repo toward:

- explicit `CharacterIntentFrame` use at the actor ingress seam
- fewer ad-hoc actor-specific side effects
- no permanent direct scene-node imperative control from agent outputs

## CharacterRuntimeState Role

`CharacterRuntimeState` is the extracted shared local state object for actor-side execution state.

It owns the parts that are currently spread through `CharacterReplica.gd`, including:

- command status
- focus state
- nearby refs and interaction feasibility state
- current action/runtime status
- presentation-input assembly state

`CharacterReplica` may temporarily own or forward to this state object during migration, but it must stop being the unbounded owner of all actor-runtime state.

## CharacterPresentationInput Role

`CharacterPresentationInput` is the final shared presentation egress contract.

It is the only intended actor-to-presentation seam for:

- motion state
- focus state
- action state
- equipment state
- expression hints
- physiology hints
- speech state

Stage 2 may still carry compatibility normalization for the current near-term payload shape, but the final-state direction is:

- formal contract first
- compatibility bridge second
- no return to arbitrary node-specific side-channel writes as architecture truth

## Player / Agent / Program Unification Rule

All three control families must enter the same actor-side ingress family:

- human player control
- backend character-agent control
- program / harness / scripted control

Allowed differences:

- control mode
- adapter logic
- policy arbitration

Forbidden long-term differences:

- player-only body species
- agent-only local embodiment path
- harness-only direct runtime mutation path

## Scene Convergence Rule

The current `CharacterBase -> CharacterReplica` layering is transitional.

The Stage 2 convergence choice for this repo is:

```text
current CharacterReplica lineage
-> converges into final CharacterActor host
current CharacterBase
-> reduced to wrapper / shell responsibilities only
```

This means downstream work must not treat the nested player-only wrapper split as the final architecture.

## Stage B Dependency Rule

Character-agent Stage B may scaffold against temporary bridge surfaces while Stage 2 is in progress.

It may not claim final `L4 -> CharacterActor` convergence until all of the following are true:

1. `CharacterControllerPort` and the adapter family exist as real code seams
2. player / agent / program paths enter one shared actor ingress family
3. `CharacterRuntimeState` has been extracted enough that `CharacterReplica` is no longer the unbounded runtime owner
4. `CharacterIntentFrame` and `CharacterPresentationInput` are the active shared actor contracts
5. the final shared actor host choice is both documented and implemented clearly enough that the player wrapper no longer defines architecture truth

## Current Stage 2 Status

As of `2026-06-15`, this target is frozen in docs but not yet fully landed in code.

The current repo status is:

- Stage 1 near-term cleanup: completed
- Stage 2 final-convergence planning: completed
- Stage 2 final-convergence implementation: not yet completed
- Character-agent Stage B final `L4` convergence: not yet allowed to claim completion

As of `2026-06-17`, the current repo truth is tighter than the initial freeze point:

- the actor-side prerequisite seams required for honest Stage B continuation are now present and verified
- Stage B may continue against this target and the landed shared-ingress/runtime-state seams
- Stage B still may **not** claim final `L4 -> CharacterActor` convergence until the remaining Stage 2 implementation items are closed
