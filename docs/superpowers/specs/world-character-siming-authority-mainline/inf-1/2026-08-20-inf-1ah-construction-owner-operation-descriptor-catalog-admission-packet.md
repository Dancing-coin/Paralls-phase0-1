# INF-1AH Construction Owner-Operation Descriptor And Catalog Admission Packet

Status: `historical admission prerequisite; lifecycle vertical implemented and verified on 2026-08-21`

## Purpose And Scope

This packet was the approval surface for exactly one frozen INF-1AH operation;
the approved immutable rows are now installed in the existing read-only catalog
and verified through the existing Registry binding path:

```text
active mill_reinforced facility -> facility_decommissioned@1
```

At this packet's admission stage, it installed no lifecycle runtime behavior.
The later separately approved runtime gate is now closed by the
[lifecycle runtime closure](2026-08-21-inf-1ah-mill-decommission-lifecycle-runtime-closure.md).
This packet remains read-only admission evidence and does not independently
authorize a verifier, projector, reducer, or business-event append.

## Frozen Package And Source Pins

The future binding must resolve only this frozen v3 record:

```text
package_id         = package:industrial-facilities
package_revision   = package:industrial-facilities:v3
content_digest     = sha256:bde53b49ee207d90c2d2bfd7e7ff95ef03638a41719883a21c2b83a3e15930ca
declaration_ref    = declaration:industrial-facilities-mill-reinforced-decommission@1
declaration_digest = sha256:ad800530f5e9a85baad29c5825a0e7edfc7e6cfa664a20208f5d2566819a7c3c
binding_ref        = binding:industrial-facilities-mill-reinforced-decommission@1
```

Frozen v2 is source evidence, not content for this admission:

```text
package_revision   = package:industrial-facilities:v2
content_digest     = sha256:8deea88c5e49c2aa06f30bbf1bd78ed103e26d8fb31769fe5564dbb7cc279896
declaration_ref    = declaration:industrial-facilities-mill-to-mill-reinforced@1
declaration_digest = sha256:73d3313283bf584254281a2ca1b60d888585f6ba89e6370a30d622e4529b1bc8
descriptor_ref     = descriptor:construction-facility-mill-reinforcement@1
descriptor_revision= descriptor:construction-facility-mill-reinforcement@1
```

Neither package is caller-writable, and neither package is allowed to select
owner, stream, event family, privacy, receipt, replay reader, compensation, or
settlement fragment.

## Proposed Immutable Descriptor

The following identifiers are mechanically derived from the approved exact
row, its frozen v3 package, and the existing catalog naming pattern. They are
proposal literals for this approval only, not installed catalog content.

```text
descriptor_ref       = descriptor:construction-facility-mill-decommission@1
descriptor_revision  = descriptor:construction-facility-mill-decommission@1
capability_ref       = capability:construction-facility-mill-decommission@1
outcome_family_ref   = outcome:construction-facility-mill-decommission@1
allowed_predicates   = [predicate:construction-facility-mill-reinforced@1]
allowed_effects      = [effect:construction-facility-mill-decommission@1]
```

The descriptor admits only the exact binding request whose typed requirement
is, in this order:

```text
requirement_ref      = requirement:construction-facility-mill-reinforced@1
predicate_family_ref = predicate:construction-facility-mill-reinforced@1
subject_slot_ref     = slot:facility-project@1
```

`slot:facility-project@1` binds both `facility_ref` and `project_ref`; it does
not accept a caller-provided proof or substitute project. `proposal_effect_types`
must equal the one allowed effect above. The descriptor does not admit a
generic transform, a generic decommission action, another predicate family, a
different effect, or arbitrary content-defined authority coordinates.

## Proposed Governed Contract Row

```text
contract_ref        = inf:construction-facility-mill-decommission@1
contract_kind       = lifecycle
owner_ref           = actor_gameplay.construction_production_domain
owner               = ConstructionProductionAuthority
stream_patterns     = [gameplay:construction_production:{facility_ref}]
event_types         = [gameplay.construction_production.facility_decommissioned]
projection_scope    = project
receipt_reader_ref  = GameplayEventStore.append_batch
replay_reader_ref   = ConstructionProductionAuthority.projector
```

`contract_kind=lifecycle` classifies the already-approved Construction-owned
`active -> decommissioned` transition; it does not create a lifecycle owner or
generic lifecycle framework. The one catalog event type is fixed to its `@1`
family by the row contract and future runtime validator. All other fields are
fixed existing boundaries, rather than package or caller input.

## Exact-One Activation And Retained Pins

Only the existing `GameplayPatchRegistry.compose_active_set()/activate()` path
may evaluate this packet after separate admission approval. It must:

1. select the one v3 manifest by exact package id, revision, and content digest;
2. select exactly one declaration by exact ref and declaration digest;
3. select exactly one request by exact binding ref and source package revision;
4. select exactly one immutable descriptor whose capability, outcome family,
   predicate vector, and effect vector all equal the values above; and
5. retain the existing activation snapshot pins: package revision, content
   digest, declaration ref/digest, descriptor ref/revision, and active-set
   revision.

The later Construction append envelope must additionally carry and validate the
committed v2 acquisition/reinforcement source-event ids, revisions,
facility/project binding, project visibility, projected facility revision, and
facility-stream head. Those are runtime proof pins, not activation-selected
coordinates.

Zero/multiple/unadmitted descriptor matches, absent/multiple declaration or
binding records, package/declaration digest mismatch, wrong request vectors, or
conflicting retained pins must fail closed before candidate or active-set
mutation. No priority, load order, fallback descriptor, caller choice, or
silent normalization is permitted.

## Later Runtime Boundary And Rejections

Admission alone cannot produce a decommission event. A separately approved
owner-bound verifier may later accept only project-visible committed
`facility_acquired(mill)` plus exact frozen v2 `mill -> mill_reinforced`
evidence for the same facility/project and current `mill_reinforced`, `active`
projection. It must also reject a committed started `ProductionRun` for that
facility before append.

The later fixed event is the sole vector:

```text
gameplay.construction_production.facility_decommissioned@1
stream   = gameplay:construction_production:{facility_ref}
privacy  = project
result   = facility_kind remains mill_reinforced;
           lifecycle_status active -> decommissioned;
           facility revision advances once
```

Unknown/inactive packages, digest mismatch, zero/multiple/unadmitted bindings,
missing/private/stale/ambiguous evidence, facility/project conflicts, source or
facility/stream revision conflicts, active runs, duplicate/change-duplicate,
and caller-selected authority coordinates are zero-write. Full and checkpoint-
tail replay must use the existing Construction projector and reconstruct equal
lifecycle status, retained kind, project binding, facility revision, and source
revision vector. V1 is terminal: no reactivation, downgrade, retry-as-new,
compensation, fanout, payment, material, inventory, production output,
weather, maintenance, social, or cross-domain event exists.

## Explicit Non-Admission

This packet does not add a generic owner, generic transform/decommission,
router, registry, coordinator, writer, settlement authority, second
runtime/store/bus/clock/scheduler, or caller-selected authority coordinate.
`GovernedAuthorityContractCatalog` remains immutable/read-only and
`SettlementPlan` remains composition-only over fixed owner-authorized
fragments. INF-1AH is one implemented narrow vertical; August INF A-D remain
not complete.

## Admission Evidence

The exact descriptor and contract row above are present in the immutable
`GovernedAuthorityContractCatalog`. The existing Registry resolves exactly one
read-only binding for frozen v3 and persists package/content/declaration/
descriptor/active-set pins. Focused tests and the independent
`infra-construction-mill-decommission-descriptor-admission` Harness cover
success, snapshot replay, and unknown/multiple/mismatch zero-write. No
Construction lifecycle event is emitted by this admission evidence.

## Required Disposition (Satisfied)

The exact descriptor and contract row were approved together with the existing
Registry exact-one read-only binding/pin-retention boundary. A change to any
literal requires a new immutable package revision and a revised packet; it may
not amend frozen v3.
