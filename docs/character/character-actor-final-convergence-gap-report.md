# Character Actor Final Convergence Gap Report

Date: `2026-06-16`

## Purpose

This report explains what still blocks the shared `CharacterActor` stack from being treated as a final-state local embodiment host for the full character-agent runtime.

It exists because the repository now has:

- a completed near-term cleanup pass
- a full character-agent design that explicitly depends on final actor-substrate convergence

but still needs a clear record of what remains after the first Stage 2 landing batch.

This report is the Stage A audit artifact updated after the first convergence batch landed.

## Current State Summary

The repository already proves a strong shared actor direction:

- one shared visible role stack is reused across player and agent-driven roles
- `CharacterMotor` owns normal world displacement
- `CharacterPresentationInput` exists as a shared presentation contract
- control-mode terminology is frozen
- root-motion and hybrid terminology are frozen
- player raw input ownership has been narrowed
- direct actor feedback clutter has been reduced

So the repository is not missing the actor architecture itself.

What it is missing is the explicit final-state convergence plan that says:

- what the final shared actor substrate should become
- which remaining transitional seams are acceptable temporary bridges
- which remaining transitional seams must be resolved before full character-agent `L4` can claim final convergence

## Final-State Target

The intended final local embodiment host is:

```text
CharacterActor
-> ControllerPort
-> CharacterMotor
-> CharacterRuntimeState
-> CharacterPresentationInput
-> KnightRoleSkin
-> post-animation embodiment modifier stack
```

This target is already described in architecture docs.

What is still required is finishing convergence work against that already-written target and plan.

## What Is Already Good Enough To Reuse In Stage B

The following current surfaces are acceptable temporary bridges while Stage B starts:

### 1. Shared lower-half local embodiment host chain

The current lower-half path is already sufficiently unified to serve as a temporary host:

```text
CharacterReplica
-> CharacterMotor
-> CharacterPresentationInput-style payload
-> KnightRoleSkin
-> KnightCombatModifier
```

This is acceptable as a Stage B bridge because:

- player and agent roles already share it
- world displacement still belongs to `CharacterMotor`
- the visible body path is unified enough to prevent parallel species drift

### 2. Existing actor-facing contract vocabulary

These are acceptable bridge contracts:

- `CharacterIntentFrame`
- normalized local motion-state publication on the motor-owned path
- `CharacterPresentationInput`

They are not fully converged, but they are the correct ingress family for character-agent execution.

### 3. Current control-mode vocabulary

These are already stable enough:

- `human_controlled`
- `agent_controlled`
- `program_controlled`

They can be used immediately by Stage B without waiting for more architecture work.

### 4. Current actor-side role shell

`CharacterReplica.gd` is still transitional, but it can act as the temporary actor-shell ingress for Stage B provided:

- Stage B does not deepen its transitional responsibilities
- new character-agent code targets shared actor contracts instead of writing direct imperative scene behavior

## Remaining Transitional Seams That Still Exist

These are the major unresolved transitional seams on the actor side.

### 1. `CharacterBase` outer shell vs `CharacterReplica` visible actor shell split

Current player embodiment still flows through:

```text
CharacterBase.tscn
-> nested CharacterReplica
```

while `CharacterA/B` instantiate `CharacterReplica` directly.

This proves shared direction, but it is still a transitional layering rather than the final scene/runtime shape.

### 2. `Phase0PlayerBridge.gd` still mixes adaptation with demo-specific helpers

The near-term cleanup reduced its scope, but the migration doc still explicitly says:

- demo sync
- autotest-oriented helpers
- bridge utility behavior

are still present.

This means the actor-side adaptation seam is still only partially converged.

### 3. `CharacterReplica.gd` still owns too much actor-runtime aggregation

It still acts as:

- actor runtime shell
- current command status sink
- focus/runtime-state application point
- partial player-shell sync point
- root-motion coordination point
- current character-agent output consumer

This is acceptable as a bridge, but not a final-state boundary.

### 4. `CharacterPresentationInput` is still used through near-term dictionary bridging

The contract exists, but the migration doc explicitly says the runtime still assembles it through a near-term dictionary bridge rather than a stronger typed pipeline.

That means the presentation seam is conceptually correct but not yet converged.

### 5. `ControllerPort` / adapter family is now landed as a first seam, but not yet fully expanded across every actor-side consumer

The repository now has:

- `HumanControllerAdapter`
- `AgentControllerAdapter`
- `ProgramControllerAdapter`
- `CharacterControllerPort`

but the broader actor-side ecosystem is not yet fully normalized onto the same formal seam.

So the remaining gap is no longer "missing seam exists nowhere"; it is "first seam exists, broader convergence is still incomplete."

### 6. Root-motion and hybrid execution are still only vocabulary-plus-guard

The repository has correctly frozen:

- `physics`
- `root_motion`
- `hybrid`

and motor-owned displacement rules.

But the actual mid-term execution stack is not yet implemented.

This is not a blocker for all Stage B work, but it is still a final-convergence gap.

## Which Transitional Seams Are Acceptable Temporary Bridges For Stage B

The following are acceptable temporary bridges:

### Acceptable Bridge A: `CharacterReplica` as temporary actor-shell ingress

Allowed only if Stage B:

- routes outputs through actor-facing contracts
- does not add more direct scene-node imperative behavior
- treats `CharacterReplica` as a bridge toward `CharacterRuntimeState`, not as final truth

### Acceptable Bridge B: `CharacterBase -> CharacterReplica` player path layering

Allowed only if Stage B:

- does not hardcode this split as final architecture
- keeps `char_c` using the same lower-half shared actor substrate as `A/B`

### Acceptable Bridge C: `CharacterPresentationInput` near-term dictionary transport

Allowed only if Stage B:

- keeps the formal contract object as the intended boundary
- does not collapse back into arbitrary node-specific side-channel writes

## Which Gaps Must Be Resolved Before Stage B Can Claim Final-State `L4` Convergence

These are the minimum actor-side final-convergence blockers.

### Blocker 1: The final actor-convergence implementation plan is not fully landed yet

This is now an implementation-closeout blocker, not a planning blocker.

The repo has the target doc and implementation plan; Stage B still cannot claim final `L4` convergence until the remaining actor-side items are actually closed.

### Blocker 2: No explicit final `L4 -> CharacterActor` ingress seam is frozen in code planning

The architecture docs name the concepts, but the plan still needs to freeze:

- what exact actor-facing packet/frame family Stage B must target
- which current code surface temporarily hosts that seam
- what will replace that host in the final-state runtime

### Blocker 3: `CharacterRuntimeState` extraction is started, but `CharacterReplica` still remains the outer runtime shell

The risk is no longer missing planning; the risk is stopping at the first extraction seam and letting `CharacterReplica` keep too much long-term ownership.

### Blocker 4: No explicit convergence path for player outer shell unification is planned

The player path still has an outer shell difference.

Stage B can start while that exists, but final-state convergence cannot be claimed until the plan states how that split resolves.

## Mapping From Current Actor Surfaces To Final-State Agent Execution Ingress

This is the concrete current-to-final mapping Stage B should assume.

### Current ingress family

- backend agent execution output
- websocket actor output envelope
- current actor output consumer in `CharacterReplica`

### Temporary local actor host

- `CharacterReplica.gd`

### Shared execution truth layer

- `CharacterMotor.gd`

### Shared presentation boundary

- `CharacterPresentationInput`

### Shared composition/modifier host

- `KnightRoleSkin.gd`
- `KnightCombatModifier.gd`

### Final-state ingress target

```text
CharacterAgent L4
-> AgentControllerAdapter / ControllerPort family
-> CharacterIntentFrame
-> CharacterRuntimeState
-> CharacterPresentationInput
-> CharacterActor shared embodiment host
```

This means Stage B should target:

- `CharacterIntentFrame`-compatible control adaptation
- `CharacterPresentationInput`-compatible presentation adaptation
- shared control-mode aware actor execution

and should avoid:

- direct scene-node imperative control from backend agent outputs
- agent-only local body paths
- permanent reliance on raw `CharacterReplica`-specific side effects

## Recommended Current Outcome

The current repo should continue using the existing final actor-convergence implementation plan to:

1. declares the final shared actor scene/runtime target
2. names the acceptable temporary bridges for Stage B
3. names the required preconditions for Stage B final-convergence claims
4. splits final actor convergence into executable tasks
5. keep migration status and repo-local summaries aligned with verified state

## Summary

The shared actor substrate is already strong enough to host early Stage B work.

But it is not yet converged enough to let Stage B honestly claim final-state `CharacterAgent L4` convergence.

The immediate missing artifact is no longer another architecture idea or another top-level plan.

What remains is closing the still-transitional actor/runtime surfaces without overstating Stage B or full `L4` completion.
