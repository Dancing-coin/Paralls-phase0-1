# INF-4Q Government Promotion Owner-Contract Catalog Design

Status: `planned; RED admission test required before runtime change`

INF-4Q does not widen branch promotion. It brings the already verified single
Government passed-inspection promotion row under the immutable governed
authority contract catalog that already fences the equivalent Organization
supply row and the named ecology consumer rows.

| Concern | Fixed contract |
| --- | --- |
| Contract ref | `inf:government-inspection-promotion@1` |
| Contract kind | `branch_promotion` |
| Sole writer | `GovernmentAuthority` / `actor_gameplay.government_domain` |
| Destination | `gameplay:government:{organization_ref}` |
| Event family | `gameplay.government.inspection_recorded` only |
| Projection/privacy | existing `project` government inspection projection only |
| Receipt | existing `GovernmentBranchPromotionReceipt`, derived only from the one `GameplayEventStore.append_batch()` result |
| Replay reader | existing `BranchPreviewAuthority.production_replay` |

`GovernmentAuthority.promote_branch_inspection()` must validate this exact row
after it has resolved the named production stream and before it creates a
fragment or calls `GameplayEventStore.append_batch()`. A mismatched catalog
owner, stream, event or scope is a zero-write rejection. Existing durable
branch admission, scenario, policy, evidence, revision and idempotency fences
remain mandatory and unchanged.

This package creates no registration API, promotion coordinator, receipt store,
branch-domain settlement stream, second event store, runtime, clock, scheduler,
population owner, NPC truth store or social truth store. It does not admit
other Government events, Organization supply changes, remediation, work,
civilization, simulation promotion or generic owner fragments.

Completion requires a focused RED/GREEN test for catalog pre-append rejection,
the prior INF-4N success/duplicate/revision/privacy/replay tests, an independent
Harness profile/report with distinct assertions, synchronized August/formal
status, `git diff --check`, and full pytest.
