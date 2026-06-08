# Architecture Realignment And Downlink Preparation Design

## Goal

Define a repository reorganization strategy for `paralls-phase-0-demo` that:

1. aligns the current project structure with the main-project system architecture,
2. prepares stable merge seams for the enhanced `ESM`, `Siming`, and event-bus branches,
3. preserves current Phase 0 behavior while the structure is being cleaned up, and
4. creates the minimum architecture needed to later connect a real downlink execution path from intelligence layers back into Godot / `ESM`.

This spec is intentionally about **structure and integration seams first**.
It does **not** attempt to finish the full downlink execution stack in one pass.

## Why This Spec Exists

The current repository grew from a runnable Phase 0 demo slice.
That gave it working behavior, but the file layout still reflects incremental implementation history more than the main-project architecture.

Right now the repo has three simultaneous realities:

1. a real and useful `L1` raw-fact production path,
2. a partially aligned `L2` perception / character-input path,
3. a repository structure that does not yet cleanly separate:
   - `L1` world execution,
   - `L2` intelligence,
   - `L6` event-bus concerns,
   - and future downlink execution seams.

At the same time, `ESM`, `Siming`, and event-bus capabilities are being strengthened on separate branches and are expected to merge back later.

That means the immediate problem is **not** "rewrite the whole codebase now".
The immediate problem is:

> how to reorganize the repo just enough that future branch merges land into stable architectural slots instead of colliding with ad hoc paths.

## Main Constraints

This spec must respect the following main-project rules already reflected in the local reference docs:

1. `L1` contains local embodiment execution, world-adjacent fact production, and `ESM` world-fact resolution.
2. `L2` contains intelligence systems, especially character-agent logic and Siming.
3. `L3` visual enhancement exists in the main-project architecture but is not implemented in this repo yet.
4. `L4` and `L5` are not implemented yet, but must still have explicit placeholders so the architecture does not collapse upward.
5. `L6` contains the event-bus system, including the backend authority bus, Godot local presentation bus, perception-chain compilation/filtering, and replay/audit surfaces.
6. Godot local presentation must remain separate from backend authority and replay truth.
7. Current demo behavior must remain runnable during the cleanup.
8. The future merge of enhanced `ESM`, `Siming`, and event-bus logic must be able to replace implementations without forcing another architecture rewrite.

## Current Repo Assessment

The current repo already contains meaningful pieces of the target architecture:

### Already Real

- Godot-side `L1` fact emission:
  - `scripts/l1/facts/*`
- Godot local presentation bridge:
  - `scripts/autoload/BackendBridge.gd`
  - `scripts/autoload/LocalPresentationBus.gd`
- backend authority ingress:
  - `backend/app/main.py`
- system-level candidate percept compilation and filtering:
  - `backend/app/services/candidate_percept_service.py`
  - `backend/app/services/per_character_percept_filter.py`
- minimal character-facing input layer:
  - `backend/app/services/character_perceived_input_service.py`
- minimal `ESM` authority:
  - `backend/app/services/esm_service.py`
- minimal Siming slice:
  - `backend/app/services/siming_service.py`

### Still Mixed Or Poorly Positioned

- `backend/app/main.py` still mixes:
  - API entrypoint,
  - bus ingress,
  - routing,
  - orchestration,
  - and message emission.
- `backend/app/services/` is still a flat bucket instead of architecture-specific lanes.
- Godot-side scripts are grouped by implementation surface (`character`, `object`, `player`, `environment`) rather than by system role (`L1`, `presentation`, `L6 bridge`, etc.).
- There is no formal backend-side namespace separation for:
  - `L1` world execution,
  - `L2` intelligence,
  - `L6` bus/perception-chain infrastructure.
- There are no explicit repository placeholders for `L3`, `L4`, or `L5`, which makes the current architecture look more complete than it is.

### Most Important Current Limitation

The repo has a working **uplink** chain:

`Godot/L1 -> L6 authority bus -> candidate percepts -> filtered perceived events -> L2 consumers`

But it does **not** have a proper architectural **downlink** chain:

`L2 -> L3 -> L4 -> L5 -> L1/ESM execution`

Some local demo response paths exist, but they are not yet the formal downlink architecture of the main project.

## Problem Statement

The repository needs two things in the correct order:

1. a structure cleanup that introduces stable architectural slots without destabilizing Phase 0,
2. then a controlled downlink implementation that can grow into the main-project stack instead of becoming another temporary shortcut.

If we do a full physical move of files now, before the enhanced `ESM`, `Siming`, and event-bus branches merge, we will likely create unnecessary path conflicts and rework.

If we do nothing now, those merges will return into a repository that still lacks architecture seams, which will make the later cleanup messier and riskier.

So the correct strategy is:

> perform a light, interface-first architecture realignment now, then perform the heavier physical reorganization after the enhanced branches return.

## Design Principles

### 1. Interface-First Before Physical Reorganization

Before moving large files, create the stable import paths, contracts, and facade seams that future implementations should target.

This means:

- new architecture directories may appear before their implementations fully move there,
- forwarding modules are acceptable in the first pass,
- old file paths may temporarily continue to exist as compatibility surfaces.

### 2. Separate Structure Cleanup From Behavior Change

The first cleanup pass should not attempt to simultaneously:

- reorganize the repo,
- merge branch enhancements,
- and implement the first real downlink path.

Those are three different risk classes and should not be collapsed into one commit stream.

### 3. Stabilize Import Boundaries Around The Future Merge Seams

The enhanced branches are expected to strengthen:

- `ESM`,
- `Siming`,
- event-bus logic.

So the cleanup should define stable top-level slots such as:

- `app.l1.esm.*`
- `app.l2.siming.*`
- `app.l6.*`

even if the current implementation still forwards to older files behind the scenes.

### 4. Keep Main-Project Layer Names Explicit

The repo should visibly reflect:

- `L1`
- `L2`
- `L3`
- `L4`
- `L5`
- `L6`

even where layers are not implemented yet.

Unimplemented layers must be represented as explicit placeholders, not silent omissions.

## Target Repository Shape

The target shape is:

```text
backend/app/
  api/
  bootstrap/
  contracts/
    l1/
    l2/
    l6/
  l1/
    esm/
    godot_edge/
  l2/
    character_agent/
    siming/
  l3/
  l4/
  l5/
  l6/
    authority_bus/
    perception_chain/
    replay_audit/
  adapters/
    godot/
    branch_merge/
```

```text
scripts/
  l1/
    facts/
    embodiment/
    world/
  l6/
    backend_bridge/
    local_presentation_bus/
  presentation/
    character/
    object/
    environment/
    audio/
  phase0/
    demo/
    probes/
```

```text
scenes/
  phase0/
  shared/
    character/
    object/
    environment/
```

This shape is not intended to be reached in one risky move.
It is the north star the cleanup should move toward.

## Structural Mapping Rules

### Backend Mapping

- `ESM` world-resolution code belongs under `backend/app/l1/esm/`
- character-agent logic belongs under `backend/app/l2/character_agent/`
- Siming logic belongs under `backend/app/l2/siming/`
- authority-bus ingress/router/message surfaces belong under `backend/app/l6/authority_bus/`
- candidate compilation and per-character filtering belong under `backend/app/l6/perception_chain/`
- debug/replay/audit surfaces belong under `backend/app/l6/replay_audit/`
- shared event and command objects belong under `backend/app/contracts/`

### Godot Mapping

- structured fact emission remains under `scripts/l1/facts/`
- backend websocket bridge and presentation bus become explicit `scripts/l6/*`
- visible role/object/environment behavior becomes `scripts/presentation/*`
- Phase 0 demo-specific composition stays under `scripts/phase0/`

## Cleanup Strategy

This cleanup should happen in two distinct structural stages.

### Stage 0: Spec And Naming Freeze

Deliverables:

- this spec,
- the target layer vocabulary,
- the target directory map,
- the import-boundary strategy for future merges.

No production behavior changes happen here.

### Stage 1: Interface-Layer Realignment (Do Now)

This is the first implementation stage that should happen **before** the enhanced branches merge back.

Its purpose is not to fully relocate the repo.
Its purpose is to create stable architecture seams.

#### What Stage 1 Should Do

1. create the architecture directories,
2. create placeholder packages for `l3`, `l4`, and `l5`,
3. create contract modules for:
   - world execution requests/results,
   - intelligence outputs,
   - bus envelopes and perception-chain events,
4. create facade or forwarding entrypoints for:
   - `ESM`
   - `Siming`
   - event-bus ingress/router
5. keep current implementations working under their old locations if needed,
6. avoid deep internal rewrites of enhanced subsystems that are still changing on other branches.

#### What Stage 1 Must Not Do

- move every service file immediately,
- deeply split `main.py` yet,
- rewrite Godot scene wiring,
- implement the first real downlink execution flow yet.

Stage 1 is about **stability of shape**, not completion of movement.

### Stage 2: Physical Reorganization (After Enhanced Branch Merge)

This happens **after** the strengthened `ESM`, `Siming`, and event-bus branches merge back.

Its purpose is to make the file layout actually match the architecture once the new implementations are present.

#### What Stage 2 Should Do

- move the merged implementations into their architecture slots,
- simplify or delete temporary forwarding modules,
- split `main.py` into API/bootstrap/router pieces,
- move Godot bridge/presentation scripts into their final directories,
- align tests with the new architecture layout.

#### Why Stage 2 Must Wait

If we move too many implementation files before those branches return, we will create merge noise in exactly the subsystems most likely to change.

That would force either:

- painful path conflict resolution,
- or a second reorganization immediately after merge.

Both are avoidable.

## Downlink Preparation Strategy

The repo should prepare for downlink execution **before** implementing full `L3/L4/L5`.

That means defining the minimum execution contracts now.

### Minimum Required Contracts

The cleanup should introduce the following architecture objects, even if some are only placeholders:

#### `ActionRequest`

Represents a world-meaningful execution request coming from intelligence layers toward execution layers.

Examples:

- `speak_to_actor`
- `orient_to_target`
- `inspect_object`

This is not yet the final full `L4` expression object.
It is the minimum downlink seam needed to stop hardcoding behavior as ad hoc side effects.

#### `PresentationCommand`

Represents a Godot-facing local expression / presentation command that does not itself claim world success.

This is a local presentation-layer command, not an `ESM` result.

#### `ExecutionAck`

Represents an execution-lane acknowledgment that an `ActionRequest` was:

- accepted,
- rejected,
- or translated into a downstream `ESM` attempt.

#### `WorldExecutionResult`

Represents the `ESM` or world-execution outcome that comes back after the request path finishes.

### Why These Contracts Must Exist Early

Even if `L3/L4/L5` are still placeholders, these contracts create the seam where those layers will later sit.

Without them, the project risks implementing another shortcut like:

- `L2 decides`
- directly mutate Godot presentation
- or directly call `ESM`

That would make later replacement harder.

## First Downlink Scope

The first real downlink slice, after structure cleanup and branch merge, should stay narrow:

1. `speak_to_actor`
2. `orient_to_target`
3. `inspect_object`

These are enough to prove:

- intelligence can emit a structured execution request,
- the execution lane can route it,
- Godot and/or `ESM` can respond through the formal path,
- and the result can re-enter the bus/replay surfaces cleanly.

This should be treated as **downlink v0**, not as the full `L3/L4/L5` rollout.

## Merge-Readiness Requirements

The cleanup is successful only if it improves branch-merge safety.

That means:

### Required Merge Seams

The repo must expose stable entrypoints for:

- `app.l1.esm`
- `app.l2.siming`
- `app.l6.authority_bus`

and downstream code should begin depending on those entrypoints instead of flat direct imports into temporary service locations.

### What Must Stay Stable Across Merge

- bus envelope shapes,
- candidate-percept and perceived-event identities,
- world-result contract naming,
- the distinction between authority truth and local presentation,
- the distinction between intelligence output and execution result.

### What Is Allowed To Change Across Merge

- the internal implementation of `ESM`,
- the internal implementation of Siming policies,
- the internal implementation of authority-bus routing,
- the internal implementation of replay/audit helpers.

## Non-Goals

This spec does **not** attempt to:

- finish `L3`,
- finish `L4`,
- finish `L5`,
- redesign the entire role cognition system,
- rewrite all tests at once,
- replace every old file path immediately,
- merge the enhanced branches preemptively.

## Success Criteria

This spec is implemented successfully if:

1. the repo visibly reflects system-level `L1-L6`,
2. `L3/L4/L5` exist as explicit placeholders instead of silent gaps,
3. `ESM`, `Siming`, and event-bus code have stable architecture entrypoints before merge,
4. current Phase 0 behavior still runs after Stage 1,
5. the enhanced branches can merge into pre-defined architecture slots,
6. the repo is ready to implement a first formal downlink execution slice without inventing another temporary path.

## Final Recommendation

Do **not** perform a full physical reorganization immediately.

Do this instead:

1. write and freeze the target architecture,
2. implement a light interface-first cleanup now,
3. merge back the enhanced `ESM`, `Siming`, and event-bus branches,
4. then perform the deeper physical relocation,
5. then implement downlink execution v0 on top of the cleaned architecture.

In plain language:

> build the sockets now, plug the upgraded modules into them when they return, then wire the first real downlink path.

## Stage 1 Closeout Notes

- Stage 1 introduced stable architecture entrypoints without relocating the legacy runtime files.
- Backend verification in this repo must run from `backend/` so the `app` package resolves correctly; repo-root invocations that point directly at `backend/tests/...` are not reliable in the current environment.
- Enhanced `ESM`, `Siming`, and authority-bus branches should merge into:
  - `app.l1.esm`
  - `app.l2.siming`
  - `app.l6.authority_bus`
  instead of extending the legacy flat `backend/app/services/` bucket further.
- The new `contracts/` modules are now the preferred merge seam for shared runtime objects, especially:
  - `contracts/l1/*`
  - `contracts/l2/*`
  - `contracts/l6/*`
- Godot-side architecture shell paths now exist under:
  - `scripts/l6/*`
  - `scripts/presentation/*`
  but scene references still point at the legacy runtime scripts on purpose until the enhanced branches are merged and the physical relocation phase begins.
