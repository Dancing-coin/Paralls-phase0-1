# INF-1W Closed State Lifecycle Adapter Matrix Plan

Status: `implemented and verified bounded matrix closure; not INF-1 completion`

1. [ ] Re-run `infra-continuation-gate`, the finite lifecycle-contract profile and
   relevant owner-row focused tests; record current replay/privacy evidence.
2. [x] Add focused failing tests for the read-only matrix lookup, operation
   admission, unsupported-operation zero write and forged adapter input.
3. [x] Implement only a closed adapter descriptor and pure selector/decision
   admission. Do not add an owner callback or an append path.
4. [ ] Migrate the existing semantic Survival and Construction apply entrypoints
   and separately migrate their action routes only after their distinct action
   command contracts can be keyed to the matrix. Ecology and Economy remain
   blocked because they have no semantic proposal adapter.
5. [x] Add one selector per admitted capability plus duplicate, revision, privacy,
   full replay and checkpoint-tail replay evidence. Add a dedicated Harness
   profile/report and synchronize the INF-1 tree, August analysis and audit.
6. [x] Run focused tests, `git diff --check`, documentation checks and the full
   pytest suite. Mark complete only when every operation in the formal matrix
   is independently evidenced.

## Stop Conditions

Stop the affected adapter at design-only status if an operation cannot name an
existing owner command/fragment, canonical event family, projection, receipt
and replay reader. It must remain unsupported-input zero-write; do not add a
generic writer.
