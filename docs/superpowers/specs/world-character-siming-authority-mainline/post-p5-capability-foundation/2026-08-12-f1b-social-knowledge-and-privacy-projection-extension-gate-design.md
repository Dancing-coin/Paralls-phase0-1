# F1B Social Knowledge And Privacy Projection Extension Gate

Status: `implemented-and-verified; complete profile fresh-green`

## Objective

Formalize the unfinished relationship, reputation, identity, family,
knowledge, belief, perception, information propagation, and privacy guidance as
projections over Character Core and Gameplay authority.

## Contract shape

Each projection declares source events, subject and actor scope, visibility
policy, provenance, revision, retention/forgetting behavior, redaction rules,
and whether it is public projection, actor memory, or private evidence. A
proposal is authorized by the existing Gameplay path and settles atomically;
Godot receives only a scoped mirror.

## Work packages

1. relationship/identity projection vocabulary;
2. knowledge provenance, propagation, expiry, and belief uncertainty;
3. family/social-structure projection boundaries;
4. perception and privacy filtering matrix;
5. replay, stale/duplicate, denial, and zero-write fixtures.

## Dependencies

F0 is required. F1B may be designed in parallel with F1A/F1C. P6 authoring
scopes consume F1B visibility rules. P7 read-only cross-jurisdiction reports
consume F1B filters but never become a social truth owner.

## Evidence gate

Focused tests must prove same-scope visibility, cross-scope denial, provenance
preservation, stale revision rejection, duplicate idempotency, full and
checkpoint-tail replay, privacy redaction, and zero writes for rejected or
over-scoped requests. Character Core and existing profile identity are the only
character truth sources.

## Non-goals and stop conditions

No synthetic NPC population, omniscient knowledge, client-side relationship
truth, second social event store, unbounded family simulator, or unrestricted
cross-jurisdiction projection. Missing provenance or privacy proof keeps F1B
`planned` or `blocked`.
