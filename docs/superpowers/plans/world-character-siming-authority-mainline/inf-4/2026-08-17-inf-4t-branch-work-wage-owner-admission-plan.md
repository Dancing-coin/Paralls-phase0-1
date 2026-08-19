# INF-4T Branch Work To Economy Wage Owner-Admission Plan

Status: `approved; implemented and independently verified narrow vertical`

## Preconditions

1. The federated owner/capability admission mechanism remains approved.
2. The INF-4T audit and this design remain explicit that a branch candidate is
   not Production completed-work truth.
3. This exact branch-to-Economy row received separate approval; no approval
   was inferred from INF-4Z's existing non-branch wage consumer.

## Approval-Gated Sequence

1. Write RED tests first for branch/Production source separation,
   worker-scoped source view and pins, zero-write missing-source behavior,
   Economy target revisions, privacy, idempotency, receipt, and independent
   branch plus Economy full/checkpoint-tail replay.
2. Add one immutable catalog entry only after row approval. The entry must fix
   both existing owners, target stream/event, scopes, receipt reader and replay
   readers; no runtime registration is allowed.
3. Extend only the existing typed intent/admission surface if the branch
   request can be validated against the canonical Production evidence view.
   Never turn branch events into Production events or accept caller-selected
   owner/stream/event/revision/privacy values.
4. Reuse the existing Economy wage owner fragment and append spine. The target
   append remains one Economy batch; branch replay remains isolated and does
   not participate in a combined receipt.
5. Preserve the existing terminal boundary: wage accrual only. Do not add
   payroll payment, retry, correction, reversal, compensation or reopen.
6. Add and run an independent Harness profile after approval, then run focused
   tests, the profile, affected regressions, and full pytest with writable
   repository-local `--basetemp` as environment permits.

## Forbidden Scope

- no branch truth owner, population/social owner, generic promotion writer,
  router, registry, coordinator, or second runtime/store/bus/clock/scheduler;
- no branch candidate as a substitute for committed Production evidence;
- no cross-stream combined receipt or implicit rollback from branch deletion;
- no generic work, payroll, payment, fanout, group simulation, or compensation;
  and
- no implementation before explicit approval of this exact row.

## Completion Evidence

- RED-first focused suite:
  `backend/tests/test_infra_branch_work_wage_owner_admission.py` (`5 passed`);
- affected INF-4Z/catalog regression suite (`29 passed` combined);
- independent `infra-branch-work-wage-owner-admission` Harness (`5` selectors
  passed); and
- the capability uses only the existing Production completed-evidence view and
  existing Economy wage append. It has no branch append after snapshot, no
  branch/Production/Economy combined receipt, and no payroll or compensation
  event vector.
