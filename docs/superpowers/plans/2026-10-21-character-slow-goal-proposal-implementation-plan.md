# Character slow goal proposal implementation plan

Goal: close the slow-goal subitem of R01/R07 without blocking lawful Laya action selection or bypassing the original Character goal owner.

Design: [slow proposal lifecycle](../specs/2026-10-21-character-slow-goal-proposal-design.md). Execution remains part of the [October stages 1–3 plan](2026-10-20-october-stages-1-3-implementation-plan.md). Status: batches 1–2 verified; batch 3 durable preparation, bounded admission, source eligibility and coordinator/store owner acceptance are implemented in slices. A first batch 4 driver integration attempt failed the existing driver suite (7 failed, 2 passed) and its uncommitted driver changes were removed; the baseline path still fails the same tests, so dispatch/root-cause diagnosis is open. Production trigger derivation, fast/slow coexistence, live Laya closure and formal quality remain open. Product scope is covered by the user's standing authorization; unresolved technical review findings must be resolved before their affected code batch.

Current status correction (2026-10-21): the diagnostic failure in the historical
status paragraph above has since been repaired; the existing driver baseline
passes. Trigger construction/source binding and dispatch/terminal guards are
implemented in bounded slices. Stale goal-proposal progress now uses the
coordinator terminal receipt when activation is available, deferring otherwise;
the nine-file focused selection passed **78 tests**, exit 0. Production
expiry/source-revocation cleanup, genuine delayed-provider fast coexistence,
live goal receipt/recovery and downstream Laya closure remain open. Historical
batch notes below describe their original evidence boundaries.

Production lifespan follow-up (2026-10-21): `backend/tests/test_character_slow_goal_main.py`
now exercises the composed runtime with a delayed controlled provider. A committed
repeated-failure trigger is dispatched by the production driver, the provider is
released, and the original Character goal owner writes one `goal_state_event`
(`producer_ts=103`) with a completed terminal receipt. Focused result: **1 passed
in 4.54s**. This is a composition/terminal subitem only; it does not establish
real Laya action selection, downstream L4/domain-owner execution, fast/slow
coexistence under a real provider, fresh-process replay, formal model quality, or
Godot evidence.

## Batch 1: explicit generative proposal contract

Own `gateway/model_gateway.py`, `gateway/model_provider.py`, `gateway/prompt_policy.py`, `gateway/output_validator.py`, the adjacent `gateway/goal_proposal.py` contract and `backend/tests/test_character_slow_goal_contract.py`. Provider dispatch must bypass ordinary L3 action coercion for this explicit contract. Preserve existing dirty hunks using a clean HEAD overlay for verification and selective staging. Do not alter global goal models or action-choice behavior for this batch.

- RED: a goal-proposal request uses l3_planning with output_contract=goal_proposal:v1, carries the frozen lawful request envelope and demands only active_goal_frame and evidence_refs. A valid output contains no selected action or fabricated candidate list. Verify ordinary L3 and Laya choice contracts are unchanged by adjacent selected tests.
- RED: reject unknown contract versions, Laya/local routes, malformed/blank goals, extra output fields, unknown/duplicate evidence refs, invalid portfolio fields and attempts to supply actor/request/expiry/source identity in model text. Refuse malformed proposal context before provider invocation.
- GREEN: explicit contract dispatch and JSON validation; route remains the explicitly configured slow reasoning provider. Preserve exact immutable input during provider completion. Do not manufacture defaults from L2 goal_hints or current continuity goal.
- Evidence: focused tests plus relevant gateway/router/prompt tests and backend-contract if that profile covers modified contracts. This batch proves request/response semantics only; it cannot upgrade R01/R07 to implemented.

## Batch 2: original goal transition calculation

Own `runtime/runtime_loop.py`, `runtime/session_recovery.py`, `models/goal_provenance.py` and focused goal event/recovery tests. Extract the frame-based calculation shared by existing action decisions and a goal-only proposal. Keep original action event fields and behavior intact. The proposal path adds explicit provenance and must not synthesize selected_intent or schedule L4.

- RED/GREEN: original action goal transitions remain identical; valid proposal produces the same owner-calculated changed fields/transition/reasons; no action/command/world event appears.
- Verify goal history/private projection with session recovery and unchanged action consumers. Reject a proposal provenance contract unknown to recovery rather than silently treating it as an action.

## Batch 3: durable internal child admission and atomic owner acceptance

Own `services/cognition_admission.py`, `services/cognition_coordinator.py`, `storage/session_store.py`, `services/cognition_frame.py` only where its existing reference contract is reused, and dedicated lifecycle tests. Extend the original session store's receipt/index lifecycle; do not introduce another persistence owner. Existing linear admission progress remains valid and is not reinterpreted as a parallel branch.

- Define internal source validation from admitted source/frame and finite trigger allowlist. One pending child per actor; exact retry returns original request, changed retry rejects. Preserve business tick, original expiry and source/revision identity.
- RED/GREEN: exact state transition and digest validation; atomic receipt/index migration rollback; stale/cancelled/expired terminal semantics and pending enumeration. Use SQLite close/reopen and corrupt-history rejection tests.
- Owner acceptance reacquires original activation, validates original read set/expiry/current source and completion identity, plans through batch2 helper and commits goal event + terminal receipt + progress CAS in one existing store transaction. Recheck pins before commit. Reject changed session head with zero effects.
- Crash tests before and after transaction; recovery returns original receipt and goal projection, never a second goal event. Distinguish Character goal receipt from domain authority receipt.

## Batch 4: dispatch and fast-loop coexistence

Own `services/cognition_driver.py`, existing runtime composition in `backend/app/main.py`, and focused driver/production ingress tests. Use existing provider slots and owner queue, with bounded child polling. Do not create an independent scheduler, lock or actor write task. Release activation after freeze and reacquire for acceptance, never hold it throughout slow provider execution.

- RED/GREEN: event-controlled pending slow provider and same-actor lawful fast work progress concurrently; provider text alone does not write goal/world state. With no intervening pin changes a valid completion commits once. With a newer fast frame the old completion zero-writes; do not refresh its read set to pass.
- Explicit cancel versus shutdown/restart generation are separate tests; pending slots release only when actual workers finish. Missing model/provider error does not inject an old floor or suppress the fast action.
- Test bounded one-child-per-actor, shared-slot capacity and fast progress under slow load. Record stale-discard frequency as an operational limitation; do not relax exact pins without another reviewed design.

## Batch 5: live development and recovery

Reuse the valid sourced use/finish evidence for existing ESM behavior. Run a new model call only after a sourced trigger can reach the new slow path and contract/coordinator/driver gates pass. Freeze exact revision, source, request, route/model identity, input budget and evidence export location before dispatch.

Prove real backend source → slow provider → original Character goal receipt → later Laya action+target → L4 → actual domain owner receipt, then fresh-process recovery with no duplicate goal/domain writes. Preserve all failed archives. This engineering run is development-only and unscored; formal Q01-Q04 require their isolated source/reviewer/freeze process. No final/holdout data access, training, Godot launch or scene changes in this batch.

## Verification and commits

Use RED then GREEN per behavioral batch, with a separate small commit for each coherent owner/contract change. Build verification overlays from exact HEAD plus owned files when existing dirty changes affect dependencies. Export evidence using the existing runner and run_scope; inspect cleanup result and actual `.harness` contents. Do not run full pytest or Harness all merely to supplement evidence. Explain any concrete final gate requiring them before running.

After each batch update R01/R07 and any affected D/Q/G rows in the unified matrix with exact scope, source revision, command, exit code, run ID, evidence path and limitations. No component/service/contract success closes the full character loop. Keep Goal active until backend, formal quality, complete role closure and final Godot A/B/C all meet the matrix.

Rollback: revert only the committed batch; preserve user changes and historical evidence. New receipt/schema versions must fail closed on unsupported readers and migrate transactionally. A failed later batch cannot invalidate or erase already accepted older owner receipts.

Batch 2 evidence: exact HEAD `374ca1fd` plus owned overlays, RED 8 new failures plus 1 pre-existing static call-count failure / 55 passed (`89c60da603d04c8793293fd8aa94e6b3`). Final GREEN 64 passed (`7c8e2eab239a454b90ffa11025709ed4`); backend-contract passed (`18597a01002046009e9ce94c98a24e97`). Original action and goal-only calculations compared directly; session reopen preserves event and projection. No atomic proposal receipt, admission or driver is claimed. Evidence prefix `slow-goal-transition-` at the unified external root; cleanup passed.

Batch 3 progress (2026-10-21): `62d74aa7` adds the goal-proposal durable progress stage/status and SQLite reopen/exact-pending retry coverage; `9c48b5e6` makes preparation retries return the original frozen request without rerouting; `281b734c` rejects an uncommitted or cross-actor trigger source; the current batch adds a transactional one-pending-goal-proposal-per-actor guard while preserving fast cognition admission. Focused admission tests passed 24, and prior slow-goal lifecycle/atomic tests passed 58. This does not close Batch 3: the trigger still needs authorized frozen-frame and eligible outcome binding, and coordinator acceptance/cancel/failure/stale recovery is not implemented. No model call, formal quality run, Godot work, full pytest or Harness all.

Source eligibility follow-up (2026-10-21): admission rejects a missing/ineligible committed source contract or caller mismatch before writes, and coordinator rechecks the persisted source when preparing a proposal. The combined admission/coordinator focus is 31 passed. No production trigger producer currently creates the metadata, so live slow trigger creation remains open. This is a fail-closed preparation guard only; complete frozen-frame reconstruction, owner acceptance and terminal recovery remain open.

Source readability follow-up (2026-10-21): `prepare_goal_proposal` now fails closed when the original session store does not expose a callable `read_event`, returning `cognition_goal_proposal_source_unreadable` before progress or provider calls. The focused admission/coordinator command passed **32 tests**. This hardens the existing guard but does not change the open status: no production trigger producer, frozen MindFrame reconstruction, owner terminal acceptance/CAS, recovery, or driver coexistence is claimed.

Source eligibility recheck follow-up (2026-10-21): coordinator preparation now rechecks `eligible is true` and the registered trigger-kind allowlist from the persisted source contract. A source with `eligible: false` is rejected before provider preparation or progress writes. Focused admission/coordinator verification passed **33 tests**. Production trigger derivation and owner acceptance remain open.

Owner acceptance follow-up (2026-10-21): coordinator now exposes `accept_goal_proposal` and `terminate_goal_proposal`. Acceptance reconstructs the frozen request context, revalidates the original provider pin, plans through `_plan_goal_proposal_event`, and uses the existing `commit_cognition_goal_proposal` transaction for goal event, terminal receipt, progress CAS and recovery projection. Terminal stale/cancelled/failed paths commit no goal event and exact terminal retries return the original receipt. Focused coordinator, transition and atomic-store verification passed **32 tests**. This closes the coordinator/store owner-acceptance implementation slice only; production trigger derivation, driver coexistence, live Laya closure, formal model quality and Godot A/B/C remain open.

Driver integration diagnostic and baseline repair (2026-10-21): a first attempt to release the actor activation during slow provider work broke existing slot/lease/retry/cancellation expectations (7 failed, 2 passed), and the patch was removed. Root cause was then isolated: L2/L3 converted the frozen `CharacterMindFrame` to a JSON dict before gateway validation, so provider preparation failed with `gateway requires a frozen mind frame`. Keeping the model instance through gateway validation and letting freeze serialization perform JSON conversion restored `python -m pytest -q backend/tests/test_character_cognition_driver.py` to **9 passed**. The combined coordinator/store/transition/driver focus is **41 passed**. This restores the driver baseline only; production trigger derivation, fast/slow coexistence, live Laya closure, formal quality and Godot remain open. No model call, formal split access, training, full pytest, Harness all or Godot operation.

Driver coexistence follow-up (2026-10-21): slow goal dispatch now releases the actor activation after freezing the provider request, reacquires it before accepting the result, and keeps a completed future/provider slot pending when activation is temporarily unavailable. Provider errors terminate the slow proposal instead of entering the ordinary L2/L3 fallback path. The focused slow-goal lifecycle selection passed **37 tests**; the existing shared-slot/owner-thread/retry/cancel/worker-lifetime suite passed **9 tests**. This verifies the driver dispatch seam and preserved baseline contracts; same-actor lawful fast progress during a real delayed proposal and production trigger creation remain open. No live model call, formal split access, training, full pytest, Harness all or Godot operation.

Production composition pin repair (2026-10-21): `_build_conflict_cognition` now
reads the policy revision from `CognitionPolicy.revision_pins` and includes the
committed trigger event ref in `evidence_refs`, matching the admission and
coordinator contracts. The focused slow-goal selection passed **74 tests**.
This is a fail-closed wiring correction; it does not constitute a live backend
provider run, original goal-owner receipt/recovery, Laya closure, formal model
quality, or Godot evidence.

Runtime trigger seam regression (2026-10-21): a runtime-level test now drives
three committed actor-private rejected settlements and verifies one committed
`character_goal_proposal_trigger`, final source-ref/evidence binding, and exact
frame digest handoff to the admission bridge. The combined selection passed
**75 tests**. This closes only trigger construction at the runtime seam; live
provider execution, terminal owner receipt/recovery, Laya closure, formal
quality, and Godot remain open.

Driver terminal-state guard (2026-10-21): the provider driver now treats the
durable slow-proposal terminal states `cancelled` and `failed` like `stale` and
`completed` when preparing or accepting work. Late provider results therefore
cannot reacquire an actor activation or write after a terminal cancellation or
failure. Focused slow-goal/driver selection passed **77 tests**. This is a
fail-closed lifecycle boundary; same-actor fast/slow live coexistence, live
provider dispatch, full Laya/domain closure, formal quality and Godot remain
open.

Same-actor fast-admission seam (2026-10-21): a new driver-level regression holds a slow goal proposal at `provider_pending`, verifies the proposal lease is released, and advances a same-actor fast cognition admission to its L2 provider boundary. The focused selection passed **71 tests**. This uses controlled coordinator/admission collaborators and proves the scheduling seam, not real delayed-provider coexistence, unchanged-pin acceptance, original goal receipt/recovery, downstream Laya, model quality or Godot. No provider call or formal evaluation was made.

Recovery probe diagnosis (2026-10-21): the saved `goal_proposal` crash probe also
leaves an earlier `percept:100` canonical turn with completed execution stage
but no real authority receipt/settlement. Startup recovery correctly records
`recovery_required`; that transition changes the proposal's captured actor pin,
and the proposal is then rejected as stale without a resumed provider call or
goal write. This confirms the stale guard, but the setup cannot establish
whether a valid proposal can resume and receive its original goal-owner receipt.
Do not weaken pin checks or synthesize a receipt. Rebuild the probe around a
proposal source with no unrelated unsettled turn, or settle that turn through
the real authority boundary before the crash. Probe artifacts are on D: and
remain pending cleanup because the available cleanup command was rejected by
execution policy; no cleanup fallback was attempted.
