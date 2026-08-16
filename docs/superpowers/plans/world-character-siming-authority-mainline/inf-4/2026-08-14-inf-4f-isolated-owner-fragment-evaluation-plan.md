# INF-4F Isolated Owner-Fragment Evaluation Plan

Status: `implemented and independently verified; builder validation only`

1. [x] Add focused RED tests for the two closed owner-evaluation rows and each
   zero-production-write rejection path.
2. [x] Extend only `BranchPreviewAuthority`'s isolated records/reducer. Invoke
   existing fragment builders for validation only; do not call settlement or
   append APIs.
3. [x] Add a distinct Harness assertion for every advertised capability and retain
   the existing unsupported-promotion proof.
4. [x] Synchronize INF-4, August analysis, Harness documentation and evidence.
5. [x] Run focused profiles, `git diff --check` and full pytest.
