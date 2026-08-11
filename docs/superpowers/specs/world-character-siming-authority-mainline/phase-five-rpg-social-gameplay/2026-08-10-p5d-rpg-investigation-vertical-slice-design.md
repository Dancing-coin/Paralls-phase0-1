# P5D RPG Investigation Vertical Slice

Status: `implemented; focused Harness green; P6 may be requested but is not started by this phase`

## Purpose And Acceptance

A small investigation demonstrates a private clue, public relationship,
skill-gated observation, stealth failure/alarm and an authoritative
nonlethal consequence that advances a quest objective. It may optionally use
Survival, but ruleset configuration must allow it to be disabled or narrative
only.

Acceptance requires evidence provenance, objective transition, social visibility,
structured failure, permission-filtered mirror, atomic settlement and
full/checkpoint-tail replay. This slice is not a complete RPG, combat or
story-authoring platform.

## Composition Boundary

This phase is governed by the
[`2026-08-11 P5 authority contract`](2026-08-11-p5-authority-contract-design.md)
and composes no new authority. The bakery-theft slice uses only a P5A private
evidence fact, a P5B public relationship fact, a P5C skill-gated observation
and stealth alarm, an existing-owner nonlethal `alerted` status fragment, and
a P5A objective transition. Its canonical streams are the corresponding
entity-scoped quest, evidence, relationship, investigation, and conflict
streams. `Survival` is required to be `DISABLED` or `NARRATIVE`; it must not
become resource truth.

All request and fragment visibility is explicit and recipient-authorized. The
same immutable policy-registry package/ruleset revision and digest, provenance,
read-set and write-set revisions must survive full replay and checkpoint-tail
replay. Hidden clues, unregistered owners, stale dependencies, or invalid
ruleset selections return structured `rejected_zero_write`; valid stealth
detection is a committed adverse outcome, never an animation or fixture fact.

The composed write is all-or-nothing across its P5A, P5B and P5C component
settlements. The slice may prepare component batches on a clone, but any late
`append_batch()` rejection restores the pre-request event-store snapshot; no
social fact, quest transition, alarm or owner consequence may remain after a
`rejected_zero_write`. Checkpoint-tail replay first verifies the checkpoint
projector/schema, event-id prefix, source revision vector, state and hash, then
replays the real post-checkpoint transaction batches. A forged or partial
checkpoint is rejected before projection output is returned.

The focused closure profile is `phase5d-investigation-vertical-slice`. It
requires fresh P5A-P5C and all predecessor profiles and proves success,
hidden-clue rejection, structured failure, public/private mirror split,
nonlethal alarm consequence, duplicate recovery, full replay, checkpoint-tail
replay, replay hash, and ruleset reversibility.
