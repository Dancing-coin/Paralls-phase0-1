# P5 Authority Contract Design

Status: `implementation-authorized`

## Decision

P5 adds one QuestEvidenceAuthority, one SocialFactAuthority for governed public
facts, and one bounded investigation/conflict resolution policy. They reuse the
existing Gameplay event store, SettlementPlan, owner fragments, replay, and
filtered mirror path. They do not create a second store, a universal
coordinator, a Godot truth writer, or a Character Core private-memory writer.

## Shared Contract

`GameplayCommandEnvelope` carries separate `expected_revisions` for writes and
`read_revisions` for non-writing dependencies. An owner fragment has the same
split. The merged batch validates both vectors atomically; only write streams
advance. A stale, missing, conflicting, or foreign-owner vector returns a
typed `rejected_zero_write` result.

Fragments carry explicit per-event visibility. Legacy fragments default to
`project`; P5 fragments must explicitly use `authority_only`, `public`, or
`actor:<actor_ref>`. The merged idempotency digest includes the command,
fragments, owner provenance, read/write/pinned vectors, event schemas,
visibility, and payloads.

`P5PolicyRegistry` is immutable per ref, revision, and digest. It registers
trusted evidence providers, package/ruleset revisions, allowed owner adapters,
event namespaces, and stream grammars. Its revision and digest are present in
all P5 requests, events, checkpoints, and idempotency inputs.

## Canonical Facts

- Quest: `gameplay:quest:<quest_instance_ref>`
- Evidence: `gameplay:evidence:<evidence_ref>`
- Directed relationship: `gameplay:relationship:<opaque_ref>`
- Public knowledge: `gameplay:knowledge:<knower_ref>:<fact_ref>`
- Investigation: `gameplay:investigation:<case_ref>`
- Conflict attempt: `gameplay:conflict:<attempt_ref>`

Reputation is a deterministic projection of visible, non-revoked relationship
facts. Character Core retains private memory, affect, beliefs, and goals.

## Event Catalog

All P5 events begin at schema version 1:

- `gameplay.quest.evidence_registered`
- `gameplay.quest.objective_transitioned`
- `gameplay.social.relationship_fact_recorded`
- `gameplay.social.knowledge_observed`
- `gameplay.social.visibility_revoked`
- `gameplay.investigation.observation_resolved`
- `gameplay.conflict.attempt_resolved`
- `gameplay.conflict.alarm_raised`

Only `gameplay.status_tag.applied@1`, `gameplay.status_tag.removed@1`, and
`gameplay.resource.adjusted@1` are accepted owner consequence events in P5
version 1. P5D uses `gameplay.status_tag.applied@1` for the nonlethal `alerted`
outcome. Unknown event schemas fail replay.

## Outcomes And Privacy

Invalid, stale, unauthorized, hidden, expired, or malformed requests return
`rejected_zero_write`. Valid in-world detection, resistance, alarm, and
nonlethal outcomes return `committed_adverse_outcome` and append canonical
events. Projectors expose only recipient-authorized fields and revision vectors.
Visibility revocation invalidates the recipient view and uses the existing
mirror resync path without emitting previously private fields.

## P5D Scope

The only vertical slice is a bakery-theft investigation: a private clue, a
public relationship fact, a skill-gated observation, a stealth alarm, one
nonlethal `alerted` status consequence, and an objective transition. Survival
is `DISABLED` or `NARRATIVE` only. Full, checkpoint-tail, and live replay must
produce equal canonical hashes and authorization-equivalent mirrors.
