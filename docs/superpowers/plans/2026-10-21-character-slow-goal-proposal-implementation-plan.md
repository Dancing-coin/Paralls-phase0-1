# Character slow goal proposal implementation plan

Goal: close the slow-goal subitem of R01/R07 without blocking lawful Laya action selection or bypassing the original Character goal owner.

Design: [slow proposal lifecycle](../specs/2026-10-21-character-slow-goal-proposal-design.md). Execution remains part of the [October stages 1–3 plan](2026-10-20-october-stages-1-3-implementation-plan.md). Status: batches 1–2 implemented and verified; batch 3 has the durable `goal_proposal/provider_pending` progress state and frozen-request retry preparation, while lawful source derivation, bounded actor admission, owner acceptance/terminal recovery and fast/slow driver coexistence remain open; batches 4–5 are planned. Product scope is covered by the user's standing authorization; unresolved technical review findings must be resolved before their affected code batch.

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
