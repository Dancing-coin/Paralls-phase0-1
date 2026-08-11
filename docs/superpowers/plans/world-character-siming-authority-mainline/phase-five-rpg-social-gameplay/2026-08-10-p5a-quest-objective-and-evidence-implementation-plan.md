# P5A Quest, Objective And Evidence Implementation Plan

Status: `implemented; focused Harness green`

Authority design: [P5 authority contract](../../../specs/world-character-siming-authority-mainline/phase-five-rpg-social-gameplay/2026-08-11-p5-authority-contract-design.md).

1. Confirm fresh P4D, P3, P2, and P1D profiles. Write focused RED tests for
   evidence provenance, wrong subject, visibility/expiry, duplicate receipt,
   stale objective, reward-owner rejection, and failure zero-write.
2. Implement only `QuestEvidenceAuthority`: immutable package/registry pins;
   quest/evidence read-set and write-set vectors; explicit `actor:<actor_ref>`
   or `public` event visibility; and canonical `gameplay:quest:*` /
   `gameplay:evidence:*` events through the existing `SettlementPlan` and
   `GameplayEventStore` append path.
3. Require rewards to arrive as registered existing-owner fragments. Reject an
   owner, event-schema, visibility, or revision failure before any append; do
   not introduce a quest-specific event store or reward writer.
4. Run the focused tests then `phase5a-quest-objective-evidence`; retain
   receipt/decision, provenance, permission/redaction, zero-write, replay-hash,
   and full/checkpoint-tail evidence in the Harness report.

Advance only after the focused P5A report and predecessor profiles are green.
