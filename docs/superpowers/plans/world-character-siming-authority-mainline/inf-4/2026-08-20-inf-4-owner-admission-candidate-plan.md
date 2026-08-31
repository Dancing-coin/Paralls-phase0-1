# INF-4 Owner-Admission Candidate Plan

Status: `formal blocker disposition: no new approval-ready branch consequence; no branch promotion or population truth`

1. Keep branch replay and branch preview evidence isolated from production.
2. Require one committed Production/branch evidence vector and one existing
   owner consequence; reject branch-only proposals as truth.
3. Fix owner stream/event/revision, actor/privacy binding, idempotency, receipt,
   independent replay, and terminal/correction/compensation semantics.
4. Sequence package/declaration/binding/policy/descriptor/catalog admission,
   then seek a separate implementation approval.
5. Keep slots B/C as reference-only existing rows and slot A blocked until a
   new business fact is explicitly approved. Do not treat branch-only evidence
   as Production truth or introduce generic promotion/group simulation.
