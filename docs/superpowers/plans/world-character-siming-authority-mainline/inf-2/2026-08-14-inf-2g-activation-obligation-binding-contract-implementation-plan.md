# INF-2G Activation-Obligation Binding Contract Implementation Plan

Status: `implemented and independently verified 2026-08-14`

1. [x] Re-run the existing cold, dehydrated, overheated and schedule pending
   focused tests; record that they remain predecessor evidence, not generic
   binding proof.
2. [x] Add focused RED tests for an immutable four-row reader, unknown lookup,
   forged binding metadata zero-write, event-derived binding reference,
   duplicate behavior, receipt separation, privacy and replay.
3. [x] Add only a finite `ActivationObligationBindingContract` reader. Make
   `ProfileActivationAuthority.record_pending()` derive and persist its
   binding reference. Make released Survival and schedule consumers recheck
   their matching row before their existing owner methods run.
4. [x] Do not add a scheduler, queue writer, new owner, target stream/event
   selection, generic fragment dispatch, second store, or a combined receipt.
5. [x] Add a dedicated Harness profile, verifier and report with one explicit
   assertion per capability. Synchronize INF-2, root dependency records,
   August analysis and `docs/harness.md`.
6. [x] Run predecessor profiles, full suite and final diff verification.
   Focused tests, the independent Harness, predecessor profiles and broad
   verification are green; generated evidence is retained under
   `.harness/verification/`.
