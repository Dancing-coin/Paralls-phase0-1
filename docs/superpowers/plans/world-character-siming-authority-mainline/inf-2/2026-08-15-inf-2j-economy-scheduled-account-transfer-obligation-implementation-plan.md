# INF-2J Economy Scheduled Account Transfer Obligation Plan

Status: `implemented and verified; one fixed Economy owner row only`

1. Re-run the account settlement and generic obligation predecessor profiles;
   confirm their replay/privacy evidence remains valid.
2. Add a focused failing test for one owner-opened scheduled transfer that
   settles debit, credit and terminal obligation events through one append
   batch.
3. Add only fixed Economy owner methods, fixed policy registration, and
   event-derived fragment builders on `gameplay:economy`.
4. Add separate focused assertions for cancellation/expiry, idempotency,
   revision, insufficient funds, privacy, forged fragments and replay.
5. Add an independent Harness profile/report; then synchronize the INF-2
   tree, root formal documents, August analysis and harness guide.
6. Run focused tests, predecessor tests, docs check, `git diff --check` and
   full `python -m pytest -q`.

Completion evidence: the focused RED test preceded the final owner validation;
the dedicated Harness profile contains thirteen individual selectors and the
report is stored at
`.harness/verification/infra-economy-scheduled-transfer-obligation-report.json`.
