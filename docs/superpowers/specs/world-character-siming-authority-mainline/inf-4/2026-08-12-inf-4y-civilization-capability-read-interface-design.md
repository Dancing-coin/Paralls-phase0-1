# INF-4Y Civilization Capability Read Interface Design

Status: `INF-4Y-A owner admission verified; the approved supply and inspection edges are independently verified`

## Purpose and non-authorization

INF-4Y defines the narrow read-only handoff from institutional/civilization
truth to semantic and population eligibility. The user has separately
authorized **INF-4Y-A**, a minimal lifecycle owner-admission package. It is
not P7 work and does not authorize progression, six-axis propagation,
institution systems, eligibility consumers, or a creator control plane. The
August guidance requires capability to be governance/civilization authority
context, not a semantic tag or planner-owned fact.

## Admission gate

INF-4Y-A admits exactly one new domain owner, not a second runtime or truth
store:

- principal: `authority:civilization_capability`;
- stream: `gameplay:civilization_capability:{jurisdiction_ref}`;
- canonical event family: `activated`, `revoked`, and `corrected` under
  `gameplay.civilization_capability.*`;
- read surface: revisioned jurisdiction-scoped `CivilizationCapabilityView`.

All mutations must pass `GameplayCommandEnvelope` -> owner fragment/
`SettlementPlan` -> the existing `GameplayEventStore.append_batch()` ->
outbox/replay -> scoped projection. There is no generic policy writer,
scheduler, automatic advancement, population owner, social truth store, or
consumer mutation. Unsupported inputs remain zero-write rejects.

## Future read contract

The admitted owner publishes immutable `CivilizationCapabilityView(
capability_ref, jurisdiction_ref, capability_revision, policy_revision,
effective_tick, status, visibility, source_event_refs, digest)`. A consumer
may later read a scoped view only to gate eligibility in a frozen
`PolicyActivationContext`; it cannot activate, revoke, upgrade, infer, or
persist a capability. The user has now separately approved exactly the
consumer edge defined below. Any later world mutation must still flow through
its existing domain authority -> envelope/
SettlementPlan -> `append_batch` -> outbox/replay -> scoped projection.

## Approved INF-4Y consumer edges

The first admitted capability consumer is a narrow eligibility input for the
already-admitted `supply` row. It does not make capability a semantic tag,
general population input, or a new write owner.

| Contract element | Approved value |
| --- | --- |
| Read owner | `authority:civilization_capability` |
| Read stream | `gameplay:civilization_capability:{jurisdiction_ref}` |
| Read projection | active, effective, authority-scoped `CivilizationCapabilityView` frozen with its canonical digest, capability revision, source-event refs and exact stream revision vector |
| Consumer | `PopulationPlanner`, proposal-only; it may validate and pin the frozen input only |
| Eligible intent | one `supply` candidate whose declared capability/jurisdiction exactly matches the frozen view |
| Target owner | `actor_gameplay.organization_domain` |
| Target fragment | `OrganizationAuthority.build_commerce_commitment_fragment` |
| Target stream/event | `gameplay:organization:{organization_ref}` / `gameplay.organization.commerce_commitment_accepted` |
| Write path | planner proposal -> existing owner fragment -> `GameplayCommandEnvelope`/`SettlementPlan` -> `GameplayEventStore.append_batch()` -> outbox/replay -> scoped projection |
| Capability privacy | source is authority-scoped; the organization event may retain only opaque eligibility provenance digest, never capability ref, jurisdiction, source-event refs or capability view payload |
| Receipt | existing append result with `actor_gameplay.organization_domain` owner receipt/provenance |

The user's 2026-08-13 instruction to proceed pragmatically is recorded as a
second, equally narrow approval. It is not blanket permission for capability
consumers, civilization progression, or a Government capability owner:

| Contract element | Approved inspection value |
| --- | --- |
| Read owner/projection | the same authority-scoped, active, effective frozen `CivilizationCapabilityView` contract above |
| Eligible intent | exactly one `inspection` candidate whose required capability and jurisdiction match the frozen view, and whose target jurisdiction exactly matches that view |
| Target owner | `actor_gameplay.government_domain` |
| Target fragment | `GovernmentAuthority.build_commercial_inspection_fragment` |
| Target stream/event | `gameplay:government:{organization_ref}` / `gameplay.government.inspection_recorded` (and the existing remediation event only for a failed inspection) |
| Policy/revision pins | the frozen capability policy must occur in `active_revision_refs`; the plan pins capability stream vector plus the existing Government target stream revision |
| Privacy | Government event/outbox retains only opaque capability eligibility and inspection-plan digests. The existing target `jurisdiction_ref` remains required inspection data, but capability ref, capability source-event refs, and capability view payload never cross the boundary. |
| Receipt/replay | existing Government append receipt, actor-scoped `world.government.inspection.scoped_projection` outbox and replay; changed duplicate compares the opaque inspection-plan digest before any write |

The inspection evidence and commercial inspection policy remain the existing
Government fragment's responsibility. Capability is an eligibility gate only;
it neither upgrades opaque evidence into civilization truth nor creates a
Government-side capability store.

The frozen capability input is rejected with zero writes if it is revoked,
not-yet-effective, non-authority-scoped, digest-forged, source-event-forged,
has a stale capability stream revision, has a changed capability revision or
does not match the candidate's required capability/jurisdiction. The input is
also rejected for `work`, semantic, unknown intents, every target owner other
than the two named rows, and an inspection whose target jurisdiction differs
from the frozen view. A valid input grants neither generic supply nor generic
inspection permission: all existing target-owner revision, evidence, policy,
privacy and idempotency checks still apply.

## Failure, privacy, replay, rollback, Harness and completion

Unknown/expired/revoked capability, jurisdiction mismatch, stale source vector,
unauthorized scope, changed idempotency digest or a consumer attempting write
is a zero-write result. Authority views retain source-event lineage;
actor/public/creator views are explicitly visibility-filtered or redacted by
the owner. Replay pins activation and policy revisions; rollback is future
revocation/correction events, never historical deletion.

The profile `infra-civilization-capability-read` must separately prove scope,
jurisdiction, effective tick, revocation, source revision conflict, duplicate,
privacy and full/checkpoint-tail replay. Consumer no-write behavior remains a
separate INF-4Y binding acceptance condition. INF-4Y-A completes only when its
focused tests, independent Harness report, replay evidence, privacy evidence,
and documentation synchronization all pass.

All capability consumer paths other than the named supply and inspection rows remain fenced:
`PopulationPlanner.plan_from_world_inputs()` returns
`civilization_capability_consumer_not_admitted` before source admission, plan
creation or writes. Dedicated capability-gated methods are admitted only for
the two contract tables above. Each acceptance or rejection capability is
asserted independently by the INF-4Y Harness; this does not authorize a broad
consumer interface.

Non-goals: civilization progression, six-axis propagation, institution owner,
creator control plane, direct semantic tag assignment, all consumer bindings
other than the named supply and inspection edges, P6, and P7.

## INF-4Y-A evidence

The owner-admission implementation is
`backend/app/gameplay/civilization_capability_runtime.py`; focused behavior is
locked by `backend/tests/test_infra_civilization_capability_read.py`. Independent
capability assertions and their command logs are recorded by
`infra-civilization-capability-read` at
`.harness/verification/infra-civilization-capability-read-report.json`. This
evidence admits only the owner/read surface described above.
