# INF-4I Government Branch Scenario Settlement Plan

Status: `implemented and verified`

1. Define the closed Government owner, stream, event, privacy, revision and
   failed-inspection zero-write boundary. Complete.
2. Add focused failing tests for append, duplicate, changed duplicate, privacy,
   unknown input, failed inspection, revision conflict, scoped outbox, replay
   isolation, checkpoint-tail replay and unsupported promotion. Complete.
3. Add Government-owned scenario append/projection only; keep
   `BranchPreviewAuthority` proposal-only. Complete.
4. Add independent Harness evidence and synchronize INF documentation. Complete.

No generic branch writer, branch store, branch receipt, remediation obligation,
promotion or production writeback is authorized by this package.
