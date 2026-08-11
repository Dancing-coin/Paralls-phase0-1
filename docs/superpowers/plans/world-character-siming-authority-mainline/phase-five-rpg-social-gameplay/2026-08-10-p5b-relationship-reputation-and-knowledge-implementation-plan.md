# P5B Relationship, Reputation And Knowledge Implementation Plan

Status: `implemented; focused Harness green`

Authority design: [P5 authority contract](../../../specs/world-character-siming-authority-mainline/phase-five-rpg-social-gameplay/2026-08-11-p5-authority-contract-design.md).

1. Require fresh P5A and predecessor evidence. Write RED tests for public and
   private views, redaction, conflicting observation, confidence decay, revoked
   visibility, stale revision, derived reputation, and zero-write failure.
2. Implement only `SocialFactAuthority` for governed public relationship and
   knowledge events on `gameplay:relationship:*` and `gameplay:knowledge:*`.
   Pin registry policy/digest, provenance, opaque relationship refs, read-set
   and write-set vectors, and explicit per-event visibility.
3. Project reputation from visible, non-revoked canonical facts. Use the
   existing filtered mirror resync for revocation; never directly mutate
   Character Core private memory, affect, belief, or goals, and do not add a
   universal graph coordinator or AI reputation writer.
4. Run focused tests then `phase5b-relationship-reputation-knowledge`; record
   permission/redaction, receipt/decision, replay hash, full/checkpoint-tail,
   and failure zero-write evidence in the Harness report.
