# Character Gameplay Foundation Implementation Plan

Status: `execution-active-for-foundation-core`

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
  -> coupled event-store outbox + authority-bus delivery
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
atomic batch append, committed outbox entries, authority-bus delivery,
projection rebuilding, checkpoints, and typed failure. Prove replay, batch
rollback, delivery retry, and store-backed resync before a domain command
writes new truth.

### Phase 2: Dynamic State Composition

Implement state-group registration/validation, eligibility, materialization,
enable/disable lifecycle, and read-only `CharacterGameRuntimeState` snapshots
and deltas. Keep each group write owner separate.

### Phase 3: Minimal Gameplay Vertical Slice (in progress)

Implement resources, status tags, body function, effective-stat explanation,
stable skill state, and current affordance. Prove one action is blocked by
injury or insufficient stamina without deleting learned skill knowledge, then
replay and mirror the result.

The backend-only resource/body gate, status-tag lifecycle, deterministic
effective-stat resolver, and minimum stable ability/affordance core are now
implemented. The ability core records learned skill truth through Gameplay
events and resolves current availability from body/resource projections without
mutating either state. Promotion, equipment/inventory predicates, full
replay/checkpoint equivalence, and mirror delivery remain Phase 3 work.

### Phase 4: Possession And Equipment (in progress)

The first inventory/encumbrance truth slice is implemented: item definitions,
container creation, single event-derived location, sealed/capacity rejection,
atomic move, and flat carried-container encumbrance. It is exposed only through
the read-only runtime façade. Nested containers, storage-ring propagation,
ownership, grants, modifiers, and presentation binding remain work in this
phase. The first equipment placement/activation slice is now implemented:
source inventory placement, one compatible/available/exclusive slot activation,
activation-scoped ability-path grants, registered modifier sources, and the
minimum outgoing-to-incoming swap settle as a single batch and have focused
backend evidence. It does not close learned-skill promotion, generic modifier
sources, container access, presentation, equipment-aware affordance settlement,
or replay/checkpoint equivalence.

Implement equipment slot/grant/modifier lifecycles only as cross-domain atomic
batches over the inventory stream. Prove equipment removal cannot lose item or
grant state.

### Phase 5: Rights And Transactional Economy

The implemented foundation contains event-derived same-currency account
balances, exclusive full-title grant/transfer, a backend-only fixed-offer
purchase, and a zero-consideration gift. Purchase pins the offer revision and
accepted price, then commits debit, credit, cross-actor item transfer, title
transfer, offer consumption, and a transaction record in one batch or none.
Gift commits the applicable item/title transfer and a zero-consideration record
in one batch or none. `simple_debt` issues principal funds, an active contract,
a claim, and an issue record together; partial/final payment is bounded by
outstanding and final payment closes claim/contract atomically. Neither treats
item placement or custody as title truth. Credential links issue/revoke/supersede
independently from title, so a deed's link lifecycle does not transfer its right.
Each issue/supersede event records its declared holder and pinned inventory
stream revision as historical evidence, not as current holder truth. Their
read-only presentation gate requires current item presence and holder identity
together.

Implement broader cross-domain contract terms execution, transport
authorization, persistence/checkpoint replay, and Godot delivery after preserving this
all-or-nothing boundary. Payment-record correction is implemented for active
and satisfied simple debt; a final-payment correction explicitly reopens the
claim/contract pair. The separate cancellation reversal restores only the
original cancellation's pinned outstanding amount and never moves funds.
Registered `simple_service` terms can now atomically record matching typed
completion evidence and fulfill their contract, without cross-domain
settlement. Prove each new settlement keeps the relevant domain streams atomic.

### Phase 6: Extension Runtime And Delivery

Implement patch manifest/Rule IR/capabilities, persistence/migration, and
Godot snapshot/delta/prediction. No patch or Godot consumer may write domain
stores directly.

Data-transform stateful Patch migration has a dedicated follow-on plan:
`2026-08-02-stateful-patch-data-migration-plan.md`. It remains deliberately
separate from the implemented identity-rebind lifecycle path because a generic
state-group layer cannot own or mutate domain projection data.

The first persistence/migration seam is implemented: guarded stores can retain
their immutable schema identities in durable snapshots, and replay can apply a
registered digest-matched trusted `vN -> vN+1` upcaster for one fixed fixture.
The minimum recovery continuation is now implemented and focused-test
verified: snapshots retain projection checkpoints; replay selects the newest
checksum-valid checkpoint compatible with projector/schema plus patch,
registry, and world-config revisions; invalid candidates fall back to full
replay; and an opt-in per-store startup coordinator closes writes until replay
succeeds. Executable upcaster persistence, full registry rollout, patch
migration, global multi-projector readiness, and Godot live delivery remain
Phase 6 work.

### Phase 7: `adventure-basic` Closure

Install and exercise the reference package's sword, injury/stamina, storage
ring, land-right/deed, and gift/debt/contract scenarios. Run the aggregate and
repository-wide harness profiles, retain evidence, and update the status
baseline without promoting deferred work.

## Completion Criteria

`gameplay-foundation-all` and `python scripts/verification/harness.py --profile all`
pass with fresh reports. Godot-specific claims additionally require a real
editor/runtime probe, screenshot/log evidence, and a visible result.
