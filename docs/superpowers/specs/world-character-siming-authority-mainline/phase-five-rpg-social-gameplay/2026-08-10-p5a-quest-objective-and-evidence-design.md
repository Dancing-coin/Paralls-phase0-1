# P5A Quest, Objective And Evidence

Status: `design-only; implementation not authorized`

## Contract

A versioned quest package defines objective refs, prerequisite facts, evidence
kinds, visibility, expiry, transition policy and reward proposal. Quest
projection may index committed evidence, but a CharacterAgent statement or
Godot animation is never completion proof. Quest authority validates evidence
refs, actor scope, current revision and policy before producing a typed
`SettlementPlan`.

Evidence retains causation, source owner, subject scope, revision and digest.
Rewards use existing economy/inventory/skill/relationship settlement adapters;
they cannot be granted by a quest script directly.

## Gate

Test duplicate evidence, wrong subject, stale objective, hidden evidence,
partial objective failure, reward rejection and replay-equivalent progression.
No narrative text is canonical fact.
