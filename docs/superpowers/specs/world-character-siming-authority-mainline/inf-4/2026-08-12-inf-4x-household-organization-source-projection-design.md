# INF-4X Household And Organization Source Projection Design

Status: `implemented bounded; existing owner extensions and planner source projections verified 2026-08-13`

## Purpose and inherited baseline

INF-4X replaces the verified INF-4 preview's caller-supplied family/
organization digest with a revisioned, scoped source-projection contract. It
inherits CharacterProfile identity, `PopulationPlanner`, activation merge,
branch isolation, `SocialFactAuthority.view_for`, and the production append
spine. It does not create family, organization, social, population or NPC truth.

## Required owner and boundary

`SocialFactAuthority` in `backend/app/gameplay/p5/social_knowledge.py` is the
sole admitted extension owner for household membership/visibility facts because
it already owns scoped social relationship/knowledge streams and `view_for`.
`OrganizationAuthority` in `backend/app/gameplay/organization_government_runtime.py`
is the sole admitted extension owner for organization membership, role/term,
shift offer and work-order schedule facts because it owns the organization
stream and those domain models. This is an extension of existing owners, not a
family, organization, social, or population truth store.

Before code starts, these owners must add canonical household/organization
event families and revisioned scoped readers for membership, time-window
commitments and visibility. `PopulationPlanner` cannot synthesize or persist
either source fact; a missing source event/reader remains a zero-write reject.

Once supplied, its reader freezes `HouseholdScheduleInput` and
`OrganizationScheduleInput` with source owner/stream revisions, recipient
scope, observation tick, policy context and digest. Planner output remains
deduplicated `GameplayCommandEnvelope`s for existing authorities; no planner
event asserts membership, kinship, organization policy or social truth.

## Data, safety and replay

Inputs carry stable household/organization/member refs, role/term refs,
time-window commitments, visibility labels, source event refs/vector and
expected revision. They cannot expose unobserved relationships or private
obligations. A schedule plan pins world-mode, seed, source vector and
activation lock. Unknown source owner, changed projection digest, stale vector,
unauthorized recipient, lock conflict, altered idempotency key or owner-declined
intent yields zero production writes and a redacted rejection.

Production write path is caller-selected mode -> frozen scoped input -> pure
batch plan -> existing owner validation/fragment -> `append_batch` ->
outbox/replay/projection. Branches consume copied scoped inputs in their
isolated buffer and cannot promote them to family/organization truth.

Full and checkpoint-tail replay reproduce scoped input digest, plan ordering,
lock/defer/requeue and receipts. Readers have explicit versioned migration;
source corrections are new owner events, not rewrites. Rollback retires future
schedule activation or uses a named source-owner correction event; it cannot
rewrite membership history or branch-promote a preview.

## Harness and completion

## Admission audit 2026-08-13

The admission blocker was resolved by extending only the named owners. `SocialFactAuthority`
now records `gameplay.social.household_membership_recorded` on the existing
hashed relationship stream and exposes `household_view_for` with recipient
filtering and a source revision vector. `OrganizationAuthority` now records
membership, role-term, shift-offer and work-order schedule rows on the existing
`gameplay:organization:{organization_ref}` stream and exposes
`schedule_view_for` with recipient filtering and a revision vector. All writes
use `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch`.

Population continuity freezes these reads as immutable `HouseholdScheduleInput`
and `OrganizationScheduleInput`; the planner validates source revisions and
recipient scope, pins digests/vectors, and emits only existing owner intents.
Corrections are append-only owner events. Evidence is independently recorded by
`infra-household-org-source-projection`.

`infra-household-org-source-projection` independently proves owner provenance,
actor/other-recipient privacy, effective-window filtering, forged provenance /
digest zero-write, stale source zero-write, duplicate, source revision
correction, production replay and checkpoint-tail replay. Branch
promotion and organization/household truth creation remain out of scope.
Non-goals: kinship/care/budget/inventory/inheritance, generated social graph,
free-running population, civilization consumer binding, INF-4Z, P6/P7.
Completion covers only the proven reader-to-existing-owner plan paths; naming
the extension owners does not itself prove household or schedule behaviour.
