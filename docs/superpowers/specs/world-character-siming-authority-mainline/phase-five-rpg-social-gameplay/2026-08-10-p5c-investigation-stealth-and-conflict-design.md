# P5C Investigation, Stealth And Conflict

Status: `implemented; focused Harness green; P5D closure complete`

## Scope

Start with an evidence-driven investigation/stealth slice. An action envelope
pins actor, target, affordance, skill/ability, perception facts, material/effect
resistance, status revision, risk policy and expected revisions. Authority
revalidates constraints and emits success or structured failure; conflict
consequences use existing resource/status/body/effect, ownership and relation
owners.

Godot cannot be evidence, hit truth or stealth truth. CharacterAgent cannot
declare discovery, damage, capture or escape. Real-time combat, pathfinding,
animation authority and unbounded AI are excluded.

## Authority And Event Boundary

This phase is governed by the
[`2026-08-11 P5 authority contract`](2026-08-11-p5-authority-contract-design.md).
The bounded investigation/conflict policy is a discrete resolver, not a new
state owner. It revalidates an action envelope that pins actor, target,
affordance, skill/ability, perception evidence, resistance, effect/status
revision, risk policy, policy registry revision/digest, and read/write
revisions before it builds one `SettlementPlan`.

The policy appends only `gameplay:investigation:<case_ref>` and
`gameplay:conflict:<attempt_ref>` using
`gameplay.investigation.observation_resolved@1`,
`gameplay.conflict.attempt_resolved@1`, and
`gameplay.conflict.alarm_raised@1`. A nonlethal consequence is an explicit,
registered existing-owner fragment such as `gameplay.status_tag.applied@1`;
direct body, resource, status, effect, ownership, or relation writes are
forbidden. Valid in-world detection, resistance, or alarm is a committed
`committed_adverse_outcome`; malformed, hidden, stale, unauthorized, or
unregistered inputs are `rejected_zero_write` with no append.

## Gate

Prove hidden/visible clue, failed affordance, resistance, alarm, nonlethal
consequence, privacy, idempotency and atomic multi-domain result with replay.
The focused closure profile is `phase5c-investigation-stealth-conflict`. It
requires fresh P5A/P5B and predecessor evidence and proves receipt/decision
fields, failure zero-write, and full/checkpoint-tail replay hash equivalence.
