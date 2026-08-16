# INF-4AA P3D Schedule-Gated Supply Reclosure Plan

Status: `implemented and independently verified; one existing Organization supply row only`

1. [x] Add focused assertions that expose the retired generic P3D merge as an
   invalid completion claim.
2. [x] Drive the fixture through the existing released activation pending row
   and `merge_released_schedule_gated_supply()` instead.
3. [x] Preserve the Organization owner fragment and its single append path;
   assert idempotency, revision, privacy, and zero-write fences.
4. [x] Assert full and checkpoint-tail replay from the resulting owner events.
5. [x] Refresh the independent P3D Harness profile and record evidence.

No generic population writer, new population/social/NPC owner, branch
promotion, complete group simulation, or additional Organization contract row
is in scope.
