# M2-2 Selector Qualification Source Audit

Date: 2026-11-28

## Scope

Static review of the formal Architecture v2 visibility contract and current A-worktree source code. No source code changed and no tests ran.

## Findings

`GameplayReadAs.read_as` requires an integer `as_of_tick` and currently admits only the two recipient-private Information FactTypes. Its reader dispatch validates the exact `recipient_of(subject)` selector and delegates to Information methods that check event time against the requested tick.

Organization has a replayable membership/delegation stream. `OrganizationMembershipDelegationIntent` contains `organization_ref`, `member_ref`, `role_ref`, and `delegation_state`, but no effective world tick. `organization_garrison_roster_at` rebuilds state at a `global_sequence`, validates stream revisions and transaction ownership, and treats only `delegation_state == "active"` as a current roster member. `record_admitted_platform_organization_membership` appends that event without supplying `event_time`.

This is a historical sequence-position roster source, not yet a qualification source queryable at `read_as(as_of_tick)`. The event also does not express faction membership, and the writer contract describes membership/delegation rather than a complete organization roster. Reusing it for faction or general role authorization would infer semantics the event does not establish.

## Required Domain Input

The Organization domain owner must define or provide replayable qualification facts with an authoritative effective world tick and stream revision semantics. The contract must state whether active membership establishes the relevant `role:<ref>` selector and whether it establishes any `faction:<ref>` selector. If membership delegation is intentionally narrower than full membership, its visibility semantics must remain narrower.

After that contract exists, A can add the corresponding historical qualification reader and register only selectors with a verified source. Until then, unsupported selector reads remain unavailable rather than being treated as allowed.

## Evidence

- `backend/app/gameplay/read_as.py:53-120` accepts `as_of_tick`, checks the Information-owned selector, and dispatches only registered Information FactTypes.
- `backend/app/gameplay/organization_government_social_platform_runtime.py:95-103` defines the membership/delegation payload without an effective world tick.
- `backend/app/gameplay/organization_government_social_platform_runtime.py:115-176` reconstructs active roster membership at `global_sequence`.
- `backend/app/gameplay/organization_government_runtime.py:6921-6987` validates and appends the Organization membership/delegation event without passing `event_time`.
- `backend/app/gameplay/models.py:92` shows `GameplayEvent.event_time` is optional at the shared event model boundary.

Conclusion: static-only. No tests ran. M2-2 remains incomplete; this audit narrows the dependency identified in H-A-191 and does not claim a generic `read_as` implementation.
