# P5D RPG Investigation Vertical Slice Implementation Plan

Status: `design-only; implementation not authorized`

1. Require fresh P5A-C, P4D and P1/P2 evidence.
2. Fixture one bounded investigation using existing profiles, item/effect/status,
   skill, relation and quest references; no fake truth state.
3. Run success, hidden-clue failure, alarm and nonlethal consequence through
   `GameplayCommandEnvelope` and owner settlement.
4. Add Harness evidence for privacy, replay, explanation and zero-write reject.

P6 cannot start until the slice is fresh-green and its ruleset toggles are
demonstrably reversible.
