# P5D RPG Investigation Vertical Slice Implementation Plan

Status: `implemented; focused and predecessor Harness green; eligible to request P6`

Authority design: [P5 authority contract](../../../specs/world-character-siming-authority-mainline/phase-five-rpg-social-gameplay/2026-08-11-p5-authority-contract-design.md).

1. Require fresh P5A-P5C plus P4D, P3, P2, and P1D. Write RED tests for one
   success, hidden-clue rejection, structured failure, public/private mirror
   split, alarm and nonlethal consequence, duplicate recovery, replay and
   `DISABLED`/`NARRATIVE` Survival rulesets.
2. Compose the bakery-theft case only from committed P5A evidence, P5B public
   social facts, P5C resolution, registered existing-owner status effects, and
   a P5A quest transition. Pin policy package/ruleset and registry digest,
   provenance, explicit visibility, read-set and write-set revisions; do not
   fixture canonical truth or create a new writer.
3. Submit the case through `GameplayCommandEnvelope` -> `SettlementPlan` ->
   `append_batch()`. A hidden clue, stale input, or invalid ruleset must be
   `rejected_zero_write`; a valid stealth detection remains a committed
   nonlethal adverse outcome.
4. Keep the composed request atomic across component owners: restore the
   pre-request event-store snapshot on any late component append failure, and
   add a regression proving no partial social/quest write survives.
5. Validate checkpoint-tail replay against the checkpoint's event-id prefix,
   source revision vector, state and projection hash before replaying actual
   tail batches; add a corrupted-checkpoint regression.
6. Run focused tests then `phase5d-investigation-vertical-slice`; retain
   receipt/decision, permission/redaction, full/checkpoint-tail replay hash,
   zero-write, and survival-toggle reversibility evidence. P6 remains gated
   until the resulting report and every predecessor profile are fresh-green.

P6 cannot start until the slice is fresh-green and its ruleset toggles are
demonstrably reversible.
