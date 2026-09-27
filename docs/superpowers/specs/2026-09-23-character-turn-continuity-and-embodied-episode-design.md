# Character Turn Continuity and Embodied Episode Design

Status: `implemented-in-part; repository-wide-verification-pending`

Date: `2026-09-23`

## Purpose

Close the remaining CharacterAgent continuity gap before further generic
character-action-foundation work. The runtime already has L1--L4, five-pool
memory, a durable session timeline, behavior-turn graph projections, local
embodied slices, and authority settlement. It does not yet make one behavior
turn the canonical identity from perception through recovery, nor does it
persist policy consumption and execution recovery strongly enough to survive a
restart.

This design also incorporates the useful, bounded part of the VLA/RPent
analysis: an advisory may nominate a candidate action, but each attempt must
be connected to a post-action observation, typed outcome, recovery decision,
and evidence-qualified strategy learning. It does not turn VLA into a body
controller.

## Governing Sources

- `docs/superpowers/specs/2026-06-29-complete-character-mind-core-design.md`
- `docs/superpowers/specs/2026-09-14-unified-character-action-foundation-and-inf-tag-contract-design.md`
- `docs/superpowers/specs/world-character-siming-authority-mainline/embodied-interaction-product-foundation/README.md`
- CharacterAgent diagnosis and solution recorded in Codex thread
  `01a0c9ca-d077-7cc1-a149-ae339420b29c`.
- VLA/RPent boundary analysis recorded in Codex thread
  `01a0c8ff-d69f-7f50-b7ff-65a4f5168afd`.

If this design conflicts with a governing authority boundary, the authority
boundary wins. In particular, Godot remains local embodiment/presentation;
ESM, Gameplay, or an admitted Composite owner remains the sole owner of world
consequences.

## Problem Statement

The current runtime can reconstruct a behavior-turn projection after a
settlement by searching timeline entries with correlation fields. That is
valuable audit evidence, but it is not a canonical in-flight turn. The
consequences are:

- L1, L2, L3, L4, settlement, evaluation, and policy do not all receive one
  required `turn_id` at creation time;
- a pending execution and its recovery state are not a first-class durable
  state machine;
- L3 consumes candidate behavior policies through an in-process set, so
  restart, TTL, supersession, and repeated-failure rules are not durable;
- evaluation is mainly a scalar `behavior_score`, which cannot distinguish
  misunderstanding, stalled goals, role inconsistency, or a poor recovery;
- memory recall is bounded and useful but does not yet expose relationship,
  causal, conflict, perspective, and incompleteness semantics as one typed
  recall result;
- the L4-to-actor path still permits legacy `CharacterGoalCommand` shaped
  execution as a production-shaped compatibility path;
- VLA advisory findings and post-action observation are not connected as a
  single actor-owned episode.

## Scope

### In scope

1. A durable `CharacterTurnContext` and monotonic turn lifecycle.
2. Turn-scoped timeline events, turn receipts, restart reconciliation, and
   recovery-required handling.
3. A durable actor-private behavior-policy record with idempotent consumption,
   expiry, supersession, and failure-window accounting.
4. Evidence-backed, multi-dimensional behavior evaluation.
5. A graph-aware, bounded semantic recall facade for L2/L3.
6. One canonical `CharacterExecutionContract` with a legacy command adapter.
7. Multi-modal/VLA candidate normalization, post-action observation, typed
   failure/recovery, and actor-private episode evidence.
8. A narrow `obj_archive_door` proof vertical using existing authority and
   presentation boundaries.
9. Updating the action-foundation plan so all later embodiment work consumes
   the resulting contracts rather than recreating them.

### Explicitly out of scope

- A new world, action, physics, inventory, or settlement authority.
- Direct VLA control of transform, velocity, bones, rigid bodies, animation
  state, damage, status, or world truth.
- Full Siming story/obligation migration, a generic knowledge-graph product,
  or a new global cognition runtime.
- Generic navigation, IK, motion warping, weapon systems, broad asset
  qualification, raw-pose networking, rollback, or server physics.
- Replacing five-pool memory stores or moving actor cognition into Heavenly
  Graph.

## Ownership Rules

| Concern | Sole owner | May contribute | Must not do |
| --- | --- | --- | --- |
| Turn state and cognition | `CharacterAgentRuntime` | L1/L2/L3/L4, memory, VLA advisory | settle world truth |
| Durable actor continuity | existing session/graph continuity stores | runtime checkpoint writer | infer an authority result |
| Semantic/world consequence | ESM, Gameplay, admitted Composite | Character execution contract | accept a local animation as success |
| Local body and presentation | Godot action/Motor path | accepted execution contract | write actor cognition or world truth |
| VLA | existing advisory provider | candidate action, uncertainty, re-observe hint | select a Motor command or settle result |
| Long-term strategy learning | actor-private policy store | evaluator, authority receipt, episode evidence | overwrite authored profile truth |

## Canonical Turn Contract

`CharacterTurnContext` is created before L1 processing and is carried in every
stage event. It is an actor-private, append-only logical record; it does not
require a cross-store ACID transaction.

```text
CharacterTurnContext
├── turn_id                    # stable: turn:<actor_id>:<source-event-id>
├── actor_id
├── causation_id / correlation_id
├── story_branch_id?
├── source_event_ref
├── input_revision_vector
├── memory_revision_vector
├── policy_revision
├── snapshot_revision
├── lifecycle
├── stage_refs
├── pending_execution_ref?
├── authority_receipt_ref?
├── recovery_ref?
└── checkpoint_ref?
```

The lifecycle is closed and monotonic:

```text
prepared -> running -> awaiting_settlement -> settled -> evaluated -> committed
                       |                       |
                       v                       v
                 recovery_required          rejected
                       |
                       v
                   abandoned
```

`failed` is allowed only for an internal stage error with an explicit error
record. A duplicate request returns the original context/receipt; changed
payload under the same idempotency key is rejected before any mutable write.

Every `BehaviorTurnStage` has a required `turn_id`:

```text
context (carries the L1 input snapshot) -> interpretation -> goal -> intent
                                      -> execution -> settlement -> evaluation
                                      -> policy
```

The existing `BehaviorTurnRecord` remains the queryable graph projection, but
it consumes canonical stage records instead of reconstructing an implicit turn
from a post-settlement timeline scan.

The post-policy checkpoint is a durable continuity snapshot and turn-receipt
record, not an additional `BehaviorTurnStage`; it also carries the same
`turn_id`.

## Commit and Recovery Protocol

The implementation must use existing actor session and graph continuity
stores, with reconciliation rather than a fabricated distributed transaction:

```text
1. Create/return idempotent CharacterTurnContext in session timeline.
2. Append validated stage records in lifecycle order.
3. Persist execution contract and set awaiting_settlement.
4. Submit the existing authority request with turn/causation/correlation IDs.
5. Persist the authority receipt or typed rejection.
6. Write evaluation and policy records.
7. Project the completed stage chain through BehaviorTurnRecorder.
8. Write a complete continuity snapshot and turn receipt.
```

On restart, the runtime reconciles the latest context against its timeline,
authority receipt, graph projection, and complete continuity snapshot:

- a received receipt advances the original turn only;
- an unresolved authority request becomes `recovery_required`, never a silent
  resend;
- a missing/invalid snapshot, graph revision mismatch, or broken stage order
  produces an auditable recovery record and blocks new execution for that
  actor until reconciliation;
- a committed turn is replay-safe and never creates a second policy use,
  evaluation, or action request.

## Policy and Evaluation Contract

`BehaviorPolicyRecord` is actor-private and only changes future candidate
selection. It cannot change authored profile truth, authority state, or a
past settlement.

```text
BehaviorPolicyRecord
├── policy_id / actor_id / source_turn_id
├── policy_type                # recovery | recall | skill_calibration | cadence
├── failed_intent / hypothesis
├── status                     # candidate|accepted|applied|expired|superseded|rolled_back|rejected
├── created_at / expires_at
├── max_consumptions / consumed_count
├── failure_window / failure_count
├── policy_revision / supersedes_policy_id?
├── evidence_refs
└── idempotency_key
```

One failed execution may create a `candidate`; it does not become active
strategy until the policy gate finds sufficient evidence. Consumption is
idempotent by `(actor_id, policy_id, turn_id)`. Repeated compatible failures
within the declared window may raise a policy's weight; success, expiry, or
supersession lowers/removes it.

`BehaviorEvaluation` replaces scalar-only decisions with independent values:

```text
comprehension_score
goal_progress_score
role_consistency_score
execution_quality_score
social_consequence_score
recovery_quality_score
confidence
evidence_refs
unknown_dimensions[]
```

An unprovable dimension is `unknown`, not a default midpoint. Policy admission
requires score, confidence, and evidence completeness, not settlement success
alone.

## Semantic Recall Contract

`CharacterSemanticRecallService` wraps, rather than replaces,
`CharacterMemoryRecallPolicy` and `CharacterGraphMemoryStore`.

It first selects bounded five-pool candidates using attention, active goal,
actor scope, valid time, certainty, salience, and branch. It may then make
bounded graph expansions using existing behavior-turn, causal-path,
conflict-set, perspective, and source-impact query facilities. It returns:

```text
SemanticRecallResult
├── cards[]                    # selected actor-visible evidence only
├── selected_refs / omitted_refs
├── relation_refs / causal_refs / conflict_refs / perspective_refs
├── context_hash / revision_vector
├── truncated / incomplete_reason
└── evidence_status             # confirmed|disputed|superseded|unknown
```

No expansion may cross actor-private scope, branch, visibility, or valid-time
boundaries. Graph distance and conflicts reduce ranking; they do not silently
overwrite subjective memory.

## Execution and Episode Contract

`CharacterExecutionContract` is the only production-shaped output of L4. It
contains semantic intent, selected action/target, admissible local realization
hints, expected authority revisions, and causation/correlation/turn identity.
It contains no transform, velocity, raw animation state, world mutation, or
client-settled result.

Legacy `CharacterGoalCommand` remains a one-way compatibility adapter:

```text
legacy command -> translator -> CharacterExecutionContract -> existing ingress
```

The reverse conversion is disallowed for a new production execution. During
migration, dual observation compares legacy and contract delivery without
issuing two authority requests.

VLA and other perceptual sources may produce a `CandidateActionObservation`:

```text
candidate action + target + preconditions + expected observation
+ confidence/uncertainty + evidence refs + reobserve recommendation
```

The actor runtime normalizes it into a normal `IntentProposal`; neither VLA
nor a provider bypasses L3, the actor action arbiter, local controller, or
authority route.

An `EmbodiedEpisodeRecord` joins the candidate with existing evidence:

```text
pre-action capture -> candidate -> execution contract -> local observation
-> authority result -> post-action capture -> expected/observed comparison
-> typed failure or recovery -> evaluation/policy update
```

The first vertical is deliberately one reviewed archive-door affordance. Its
successful result is the authority-confirmed door-state transition plus a
post-action observation consistent with it. A local open animation, VLA
claim, or second capture alone cannot be promoted to success.

## Input Conflict Rules

Multi-modal inputs are merged by a stable identity envelope:

```text
capture_root_id, capture_id, world_anchor_id, subject_ref, target_ref,
source_ref_lineage
```

Priority is fixed:

```text
committed authority fact > structured percept > provider advisory > model inference
```

A conflict records `percept_conflict`, updates uncertainty, and may request a
new observation. It must never silently replace a committed fact or become
long-term knowledge merely because a provider proposed it.

## Interaction-Session WebSocket Projection Recovery

`embodied_interaction_session_probe` is an authority-owned verification route,
not a local completion signal. A Godot consumer must receive each public-safe
session projection in strict global-sequence order without relying on a burst
of server frames being retained by the local WebSocket transport.

The route therefore acknowledges proposal admission only. Godot then pulls
one projection at a time with:

```text
embodied_interaction_session_projection_pull
├── session_id
└── after_global_sequence
```

The backend rereads the existing Gameplay session stream, validates the
cursor, projects only the first later event through the established public
filter, and returns that one event. An empty later range returns a typed
`embodied_interaction_session_projection_exhausted` response. Godot advances
its cursor only after the slot consumer accepts the projection. Repeating a
cursor is safe: the backend returns the same next projection; reconnecting
from the last accepted sequence resumes from that point.

This protocol is flow control and replay for public projections only. It does
not add a truth owner, let Godot acknowledge or mutate authority state, expose
private participant terms, or turn a local terminal observation into a
settlement result.

## Action-Foundation Sequencing

This work is a prerequisite for the remaining unified character-action
foundation plan. Its outputs are consumed as follows:

| This design output | Later action-foundation consumer |
| --- | --- |
| `CharacterExecutionContract` | Task 9 semantic Actor/INF ingress |
| `turn_id`, causation, correlation, expected revision | Task 10 `ActionAttempt` and `AuthorityResult` |
| episode local/authority/post-observation record | Task 13 replay proof and Task 14 runtime proof |
| typed recovery | Motor/action controller recovery and Mode B transport behavior |
| candidate-action boundary | Task 9 provider/Siming/Agent input validation |

Asset qualification, `RolePresentationAdapter`, broad Motor realization, and
two-character delivery remain later action-foundation work. They are not
implemented by this design.

## Acceptance Criteria

1. One actor turn has one `turn_id` from initial input through its checkpoint.
2. Restart never duplicates execution, settlement, policy consumption, or
   evaluation; uncertain execution becomes `recovery_required`.
3. Policy lifecycle survives restart and changes a later L3 candidate only
   under evidence/TTL/window rules.
4. Evaluation reports each defined dimension or `unknown` with evidence refs.
5. Semantic recall exposes bounded relationship/causal/conflict/perspective
   context without leaking private, future, or branch-only information.
6. L4 production delivery goes through `CharacterExecutionContract`; legacy
   commands are compatibility input only.
7. Provider/VLA candidates cannot write a body or world state and can only
   enter via normal actor intent admission.
8. The archive-door episode proves expected-versus-observed comparison after
   a real authority result, including a typed failure/recovery case.
9. The action-foundation plan declares this design as a completion dependency
   before its remaining implementation tasks resume.
10. A live Godot session consumer receives the four public handshake lifecycle
    projections through the pull/replay cursor, in sequence, without private
    participant terms or a client world write.

## Verification Boundaries

Focused backend tests must cover lifecycle order, idempotency, restart
reconciliation, missing authority receipt, policy TTL/consumption/supersession,
multi-dimensional evaluation, recall scope/conflict/truncation, legacy
execution rejection, input conflicts, and episode success/failure. The final
archive-door proof requires a running backend, a real boundary message, a
committed authority result, and a visible Godot scene result. Static tests or
a local animation alone are insufficient for that claim.
