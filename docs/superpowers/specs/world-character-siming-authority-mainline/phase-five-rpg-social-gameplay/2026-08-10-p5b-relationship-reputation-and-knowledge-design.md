# P5B Relationship, Reputation And Knowledge

Status: `implemented; focused Harness green; P5D closure complete`

## Contract

Separate objective relationship facts from actor-private beliefs. A relationship
change proposal pins source evidence, participants, relation kind, direction,
confidence, privacy class, policy revision and expected revisions. Knowledge
projection distinguishes stable ability knowledge, observed fact and current
affordance; it does not expose private memory by default.

Character Core memory/affect/goal remains the actor owner. P5B only records
governed public/social consequences through existing event and projection paths.
Relationship, ability and Siming graphs share governance values, not a universal
graph runtime.

## Authority And Event Boundary

This phase is governed by the
[`2026-08-11 P5 authority contract`](2026-08-11-p5-authority-contract-design.md).
`SocialFactAuthority` owns only governed public relationship and public
knowledge facts. It does not own, coordinate, or mutate Character Core private
memory, affect, belief, or goal state. Directed relationships use opaque refs;
it appends only `gameplay:relationship:<opaque_ref>` and
`gameplay:knowledge:<knower_ref>:<fact_ref>` through
`gameplay.social.relationship_fact_recorded@1`,
`gameplay.social.knowledge_observed@1`, and
`gameplay.social.visibility_revoked@1`.

Every proposal pins source evidence, participant scopes, confidence/decay
policy, policy-registry revision/digest, read-set and write-set revisions, and
per-event visibility. Recipient views are constructed only from authorized,
non-revoked fields; redaction and revocation use the existing filtered mirror
resync path. Reputation is deterministic projection from those visible facts,
never a canonical score or an AI writer. Invalid visibility, stale policy or
revision, conflicting foreign source, and unauthorized commands return typed
`rejected_zero_write` results.

## Gate

Verify privacy redaction, conflicting observations, decay/revision, revoked
visibility, replay and no direct belief mutation. Reputation is a projection of
committed facts, not an AI score writer. The focused closure profile is
`phase5b-relationship-reputation-knowledge`. It requires fresh P5A plus the
predecessor profiles and proves receipt/decision fields, failure zero-write,
and recipient-authorized full/checkpoint-tail replay.
