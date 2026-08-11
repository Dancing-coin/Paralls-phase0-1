# P5C Investigation, Stealth And Conflict Implementation Plan

Status: `implemented; focused Harness green`

Authority design: [P5 authority contract](../../../specs/world-character-siming-authority-mainline/phase-five-rpg-social-gameplay/2026-08-11-p5-authority-contract-design.md).

1. Require fresh P5A/P5B and predecessor evidence. Write RED tests for
   perception evidence, affordance/skill gate, resistance, status revision,
   alarm, registered nonlethal effect, structured failure, atomicity,
   idempotency, privacy, and failure zero-write.
2. Extend only the bounded resolver. Pin actor, target, affordance, skill,
   perception, resistance, effect/status/risk policy, registry revision/digest,
   and read/write revision vectors in the action envelope. Revalidate all pins
   before constructing a single `GameplayCommandEnvelope` -> `SettlementPlan`.
3. Append investigation/conflict events only to `gameplay:investigation:*` and
   `gameplay:conflict:*`; pass body/resource/status/effect/ownership/relation
   consequences only as registered existing-owner fragments. Treat valid alarm
   or resistance as `committed_adverse_outcome`, but reject malformed, stale,
   hidden, or unauthorized inputs with zero writes.
4. Run focused tests then `phase5c-investigation-stealth-conflict`; record
   evidence provenance, permission/redaction, receipt/decision, replay hash,
   full/checkpoint-tail replay, and failure zero-write evidence. Do not add a
   real-time battle loop, second conflict store, or Godot truth writer.
