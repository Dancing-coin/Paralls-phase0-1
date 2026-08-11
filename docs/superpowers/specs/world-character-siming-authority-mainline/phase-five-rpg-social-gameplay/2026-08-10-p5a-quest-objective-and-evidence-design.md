# P5A Quest, Objective And Evidence

Status: `implemented; focused Harness green; P5D closure complete`

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

## Authority And Event Boundary

This phase is governed by the
[`2026-08-11 P5 authority contract`](2026-08-11-p5-authority-contract-design.md).
`QuestEvidenceAuthority` is the sole P5 owner for validating a quest package,
evidence provenance, objective prerequisites, and an allowed objective
transition. It may append only the canonical streams
`gameplay:quest:<quest_instance_ref>` and
`gameplay:evidence:<evidence_ref>` using
`gameplay.quest.evidence_registered@1` and
`gameplay.quest.objective_transitioned@1`.

The request and every resulting fragment must pin the package revision/digest,
policy registry revision/digest, provenance source, subject scope, event
schema, read-set revisions, write-set revisions, and explicit event visibility.
Evidence facts are private (`actor:<actor_ref>`) or public only as registered;
the authority never uses a broad project visibility default. A stale, foreign,
hidden, expired, duplicate-conflicting, or wrong-subject request is a typed
`rejected_zero_write` receipt. A legal duplicate returns the existing receipt
without a second append.

A reward is a proposal inside the quest transition, not a quest-owned fact. It
is valid only when a registry-approved existing skill, inventory, economy, or
relationship owner adapter returns an `OwnerAuthorizedFragment`; rejection by
that owner rejects the whole atomic settlement with zero writes.

## Gate

Test duplicate evidence, wrong subject, stale objective, hidden evidence,
partial objective failure, reward rejection and replay-equivalent progression.
No narrative text is canonical fact. The focused closure profile is
`phase5a-quest-objective-evidence`. It must run after fresh P4D, P3, P2, and
P1D predecessor evidence and prove provenance, visibility/expiry,
receipt/decision fields, failure zero-write, and full/checkpoint-tail replay
hash equivalence.
