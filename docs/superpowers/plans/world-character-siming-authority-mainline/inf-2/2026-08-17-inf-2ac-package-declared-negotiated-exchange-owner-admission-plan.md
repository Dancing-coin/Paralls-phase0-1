# INF-2AC Package-Declared Negotiated Exchange Owner-Admission Plan

Status: `implemented narrow vertical; focused and independent Harness verification recorded`

## Preconditions

1. The federated owner/capability governing decision is approved.
2. The three existing-owner audits remain terminal evidence; no fourth audit is
   permitted.
3. The companion INF-2AC contract is explicitly approved without widening its
   single-outcome, single-source-mode, authority-only, or no-compensation
   boundary.
4. An active immutable package fixture exists with exactly one declared outcome,
   canonical currency, fixed/bounded price-policy revision, one source mode,
   and only committed eligibility refs supported by the contract.

## Executed Sequence

1. Focused RED tests were written for every admitted source mode. They prove the package,
   price/consent/eligibility pins, Economy-derived party-account opening pins,
   one source proof, and one atomic vector.
2. The independent Harness profile was written before runtime implementation. Its
   selectors cover success for every mode; zero-write fences; authority-only
   privacy; stale package/source/account/eligibility revisions; exact and
   changed duplicates; receipt; full replay; and checkpoint-tail replay.
3. Add only immutable catalog row
   `inf:package-declared-negotiated-exchange@1` and the fixed typed intent.
   There is no caller registration, dynamic capability lookup, or caller-
   supplied fragment.
4. Add the fixed Economy operation and its ledger/settlement fragment. Account
   selection uses only the contract's explicit internal party-account binding
   rule, never a default account lookup.
5. Add the one selected source-owner fragment for inventory custody or
   ownership right. Completed-service mode rereads the committed contract proof
   and contributes no new source event. `SettlementPlan` only composes already-
   authorized fragments into one existing append.
6. Prove the batch cannot omit a ledger or settlement event, cannot split source
   transfer from payment, and cannot append more than one source mode.
7. Add authority-only outbox/projection and receipt replay readers. Prove exact
   full/checkpoint-tail reconstruction against the fixed event vector.
8. Record the no-retry/no-compensation terminal decision in tests, Harness,
   completion audit, package README, and checkpoint. No refund or generic
   correction path is permitted.

## Required RED Cases

- unknown/inactive package, content digest, active-set, and policy revisions;
- unknown tradeable/service, source mode, currency, eligibility, or consent;
- missing/stale/forged Inventory, Ownership, Contract, Economy-account, or
  CivilizationCapability proof;
- price outside fixed/bounded immutable policy;
- caller-supplied account, currency, owner, event type, stream, scope, receipt,
  fragment, compensation, or more than one exchange value;
- marker-only, ledger-only, source-only, split-batch, and mixed-mode attempts;
- exact duplicate replay and changed duplicate zero-write; and
- authority-only privacy, receipt, full replay, checkpoint-tail replay, and
  rejected retry/compensation.

## Verification Evidence

- focused INF-2AC tests: `11 passed`;
- affected Adventure Basic, patch, Economy, catalog, tax-payment, and INF-2AC
  regressions: `53 passed`;
- the independent `infra-package-declared-negotiated-exchange` Harness is the
  durable `11 selector` evidence for success, zero-write fences, authority-only
  privacy, pins, idempotency, receipt, full replay, and checkpoint-tail replay.
- repository-wide pytest with repo-local `--basetemp` reached `916 passed`
  before the known environment-only failure in
  `backend/tests/test_config_runtime_modes.py`, which attempts to write the
  workspace-parent `D:\Users\User\Documents\.env`.

## Forbidden Scope

- generic payment, transfer, barter, market pricing, treasury, settlement, or
  compensation authority;
- package/mod runtime writer, registry, router, coordinator, or dynamic event-
  family selector;
- a new truth owner, runtime, store, bus, clock, scheduler, or branch store;
- treating a need, dossier, agreement, proposal, client state, or opaque input
  as a committed source fact; and
- any implementation before explicit approval of the companion contract.
