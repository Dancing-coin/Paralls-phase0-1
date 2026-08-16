# INF-4A Schedule-Gated Supply Design

Status: `superseded in part by INF-4C; direct schedule row remains verified`

This is one real schedule input, not generic population truth. The existing
`SocialFactAuthority` household view and `OrganizationAuthority` schedule view
are frozen with their scoped digest and revision vector. `PopulationPlanner`
is proposal-only and combines those inputs with the existing social view.
`ContinuityMergeAuthority.merge_schedule_gated_supply()` revalidates all three
pins and the recipient, organization, work-order and privacy scope, then calls
only the existing `OrganizationAuthority.build_commerce_commitment_fragment()`.

The sole production stream/event family is `gameplay:organization:{organization_ref}` /
`gameplay.organization.commerce_commitment_accepted`; the receipt is the
single existing `GameplayEventStore.append_batch()` result. The original
activation-lock statement is superseded by INF-4C for one event-derived,
released `schedule_gated_supply` pending row; every other lock/pending payload
remains fail-closed. Generic `work` remains zero-write rejected. No
population/NPC/social owner, generic queue or promotion path is added.
