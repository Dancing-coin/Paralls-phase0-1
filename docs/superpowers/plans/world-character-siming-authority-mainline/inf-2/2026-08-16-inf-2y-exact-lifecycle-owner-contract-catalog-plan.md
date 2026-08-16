# INF-2Y Exact Lifecycle Owner-Contract Catalog Plan

Status: `implemented and independently verified; broader INF-2 remains incomplete`

1. [x] Add focused RED tests for the five exact immutable catalog rows and
   retirement of the synthetic lifecycle placeholder.
2. [x] Add zero-write tests that force the pre-append catalog gate to reject
   for Survival and one non-Survival owner path.
3. [x] Replace the catalog placeholder with the five fixed existing-owner rows
   and add only pre-append gate calls in the affected existing authorities.
4. [x] Add a dedicated Harness profile with independent success, zero-write,
   and full/checkpoint-tail replay assertions.
5. [x] Synchronize the formal audit, implementation plan, August analysis and
   Harness documentation, then run focused tests, continuation gate,
   `git diff --check`, and the full test suite.

No step may add a policy registration API, settlement coordinator write path,
clock, scheduler, store, or new truth owner.
