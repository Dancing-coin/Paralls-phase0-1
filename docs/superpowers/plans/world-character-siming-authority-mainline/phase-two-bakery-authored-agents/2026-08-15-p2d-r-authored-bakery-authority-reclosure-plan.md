# P2D-R Authored Bakery Authority Re-closure Plan

Status: `implemented-and-verified; bounded owner re-closure`

1. Re-run and read the P1D, P2A, P2B and P2C Harness reports, then replace historical P2D
   completion language with the accurately limited status.
2. Add focused RED tests for the fixed two-worker vertical before production edits. Cover success,
   invalid/forged schedule evidence zero-write, exact duplicate and changed-key rejection, stale
   schedule revision, scoped views, and full/checkpoint-tail replay.
3. Add only the fixed Economy procurement-from-scheduled-work command. It must recompute and pin
   the Organization-owned schedule before producing its Economy envelope/plan/append result and
   counter-scoped outbox entry.
4. Compose Organization window, Construction production evidence, the fixed procurement command,
   and existing Economy wage/account commands in the focused test. Do not add a P2D coordinator or
   make multiple owner commands appear as one atomic receipt.
5. [x] Add an independent P2D-R Harness, sync August evidence mapping and formal readmes, then run
   focused tests, predecessor Harnesses, P2D-R Harness, docs Harness, `git diff --check`, and the
   full suite (`3207 passed`).
6. [x] Add RED tests and enforce the review-required fixed `org:bakery-authored` /
   `character:char_c` / `work:flour` / actor-scoped source fence. The narrow re-review approved
   the remediation; the final full suite passed (`3209 passed`).
