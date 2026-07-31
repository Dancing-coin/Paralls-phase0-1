# Character Gameplay Foundation Implementation Plan

Status: `drafted-for-spec-review`

Date: `2026-07-29`

## Goal

Implement the approved gameplay-foundation first closure as authoritative,
replayable domain state, then prove it through the five `adventure-basic`
scenarios. This plan adds game-state infrastructure; it does not extend the
current LLM closure.

## Preconditions

- The matching spec tree is approved.
- Existing character-agent, authority, world-runtime, and Godot regression
  profiles pass before work begins.
- Shared contracts are owned by one implementation lane. Backend and Godot
  work may parallelize only after their schemas and fixture revisions freeze.

## Dependency Graph

```text
contracts + event batches + harness
  -> state-group registry + runtime facade
  -> resource/status/body/effective-stats minimum vertical slice
  -> inventory/containers -> equipment
  -> ownership/economy
  -> ability graph/current affordance
  -> Rule IR/capabilities
  -> persistence + Godot mirror
  -> adventure-basic end-to-end closure
```

## Phases

### Phase 0: Contract Freeze And Proof Skeleton

Define gameplay IDs, command/result/error envelopes, event metadata, atomic
batch rules, projection health, privacy views, and focused verifier/profile
skeletons with meaningful failing behavior. Do not reuse the in-memory
authority-event bus as durable truth.

### Phase 1: Event And Projection Spine

Implement append-only event streams, idempotency, expected-revision checks,
atomic batch append, projection rebuilding, checkpoints, and typed failure.
Prove replay and batch rollback before a domain command writes new truth.

### Phase 2: Dynamic State Composition

Implement state-group registration/validation, eligibility, materialization,
enable/disable lifecycle, and read-only `CharacterGameRuntimeState` snapshots
and deltas. Keep each group write owner separate.

### Phase 3: Minimal Gameplay Vertical Slice

Implement resources, status tags, body function, effective-stat explanation,
stable skill state, and current affordance. Prove one action is blocked by
injury or insufficient stamina without deleting learned skill knowledge, then
replay and mirror the result.

### Phase 4: Possession And Equipment

Implement item/container/encumbrance truth first, then slot/grant/modifier
lifecycles. Prove equipment removal cannot lose item or grant state.

### Phase 5: Rights And Transactional Economy

Implement accounts, balances, offers, title/right separation, transactions,
debts, and contracts. Prove purchase and failure paths append all-or-nothing
event batches.

### Phase 6: Extension Runtime And Delivery

Implement patch manifest/Rule IR/capabilities, persistence/migration, and
Godot snapshot/delta/prediction. No patch or Godot consumer may write domain
stores directly.

### Phase 7: `adventure-basic` Closure

Install and exercise the reference package's sword, injury/stamina, storage
ring, land-right/deed, and gift/debt/contract scenarios. Run the aggregate and
repository-wide harness profiles, retain evidence, and update the status
baseline without promoting deferred work.

## Completion Criteria

`gameplay-foundation-all` and `python scripts/verification/harness.py --profile all`
pass with fresh reports. Godot-specific claims additionally require a real
editor/runtime probe, screenshot/log evidence, and a visible result.
