# INF-1AH Mill Reinforced Decommission Owner-Admission Contract Design

Status: `implemented narrow vertical: exact frozen mill_reinforced -> facility_decommissioned row verified`

## Scope

This design proposes one Construction-owned terminal lifecycle transition:

```text
committed facility_acquired(mill) + committed exact mill -> mill_reinforced
  -> facility_decommissioned@1
```

It uses only `ConstructionProductionAuthority`. It changes exactly the
Construction facility lifecycle status from `active` to `decommissioned` and
advances that facility revision once. It does not change `facility_kind`,
condition, project identity, or any payment, material, inventory,
production-output, recipe, permit, technology, weather, maintenance, social,
or other-domain fact.

This is not an approval to create a projector branch, verifier, event append
path, or lifecycle business event. The frozen
`package:industrial-facilities:v2` is source evidence only and must never be
modified, reused as the decommission package, or re-digested.

## Candidate Identity And Owner Boundary

The following are the exact admitted contract literals. They are installed
immutable catalog metadata, not caller-selectable coordinates; lifecycle
runtime still remains separately gated.

```text
capability_ref candidate     = capability:construction-facility-mill-decommission@1
outcome_family candidate     = construction_facility_mill_decommission@1
outcome_family_ref candidate = outcome:construction-facility-mill-decommission@1
event family                 = gameplay.construction_production.facility_decommissioned@1
stream                       = gameplay:construction_production:{facility_ref}
owner                        = ConstructionProductionAuthority
privacy                      = project
receipt                      = GameplayEventStore.append_batch() append-derived receipt
replay reader                = ConstructionProductionAuthority.projector
lifecycle                    = v1 terminal / no reactivation / no compensation
```

Construction owns the facility lifecycle fact on its existing facility stream.
It does not thereby own a generic facility action vocabulary, a generic
decommission process, or any external consequence of decommissioning.

## Source And Eligibility Contract

The one non-empty eligibility family is:

```text
eligibility_ref       = construction:facility-mill-reinforced@1
requirement candidate = requirement:construction-facility-mill-reinforced@1
predicate candidate   = predicate:construction-facility-mill-reinforced@1
subject slot          = slot:facility-project@1
```

The future owner-bound proof must derive, never accept from the caller, all of
the following from committed project-visible Construction facts:

1. One exact `gameplay.construction_production.facility_acquired@1` event with
   `facility_kind=mill`, its event id, stream revision, `facility_ref`, and
   `plot_ref`.
2. One exact `gameplay.construction_production.facility_transformed@1` event
   on the same facility stream with `prior_kind=mill`,
   `next_kind=mill_reinforced`, project visibility, and these frozen source
   pins:

   ```text
   package_revision  = package:industrial-facilities:v2
   content_digest    = sha256:8deea88c5e49c2aa06f30bbf1bd78ed103e26d8fb31769fe5564dbb7cc279896
   declaration_ref   = declaration:industrial-facilities-mill-to-mill-reinforced@1
   declaration_digest= sha256:73d3313283bf584254281a2ca1b60d888585f6ba89e6370a30d622e4529b1bc8
   descriptor_ref    = descriptor:construction-facility-mill-reinforcement@1
   descriptor_revision = descriptor:construction-facility-mill-reinforcement@1
   policy_revision   = policy:industrial-facilities:mill-to-mill-reinforced@1
   ```

3. Equality of both source `facility_ref` values, the current projected
   facility reference, and the target stream reference.
4. Equality of both source project values with
   `project_ref=facility_acquired.plot_ref`; no caller project reference may
   substitute.
5. Project visibility on both source events and the target event.
6. The exact acquisition event revision, exact reinforcement event revision,
   current facility revision, facility stream head, and the source event
   revision values contained in the reinforced event. All must be pinned in
   the proposed append envelope.
7. Current facility kind `mill_reinforced` and current lifecycle status
   `active`.

The existing projection has no `lifecycle_status` field. The approved
row-specific projection contract permits only `active` and `decommissioned`:
`active` is derived only from the complete pinned acquisition/reinforcement
source vector while no fixed decommission event exists; `decommissioned` is
derived only from the fixed decommission event. It is not a default inferred
from facility kind, a missing field, or an unrelated package. No runtime
change is authorized by this design.

## Fixed Event And Idempotency Shape

After the new package and exact descriptor are separately approved, the only
permitted event vector is one project-scoped event:

```text
gameplay.construction_production.facility_decommissioned@1 {
  facility_ref,
  project_ref,
  prior_kind = mill_reinforced,
  next_kind = mill_reinforced,
  prior_lifecycle_status = active,
  next_lifecycle_status = decommissioned,
  acquisition_event_id,
  acquisition_event_revision,
  reinforcement_event_id,
  reinforcement_event_revision,
  expected_stream_revision,
  prior_facility_revision,
  facility_revision = prior_facility_revision + 1,
  decommission_package_revision,
  decommission_content_digest,
  decommission_declaration_ref,
  decommission_declaration_digest,
  decommission_policy_ref,
  decommission_policy_revision,
  descriptor_ref,
  descriptor_revision,
  active_set_revision
}
```

`next_kind` is a fixed equality assertion, not a transform input. Package and
descriptor pin values are owner-derived from a future active immutable package
and read-only exact-one binding. They must not be copied from v2 or supplied by
the caller.

The authority-derived idempotency key shape is:

```text
construction:facility-mill-decommission:
  decommission_package_revision:decommission_content_digest:
  decommission_declaration_digest:descriptor_revision:facility_ref:
  acquisition_event_id:acquisition_event_revision:
  reinforcement_event_id:reinforcement_event_revision:
  prior_facility_revision
```

An exact duplicate replays the append-derived receipt. A changed duplicate is
zero-write and cannot create a new decommission transition.

## Replay, Terminal, And Rejection Rules

Full replay and checkpoint-tail replay use the existing Construction projector.
The future row-specific branch must accept only the complete vector above,
preserve `facility_kind=mill_reinforced`, set lifecycle status to
`decommissioned`, and advance the facility revision once. It must reject every
other `facility_decommissioned` shape.

V1 is terminal: no reactivation, compensation, reversal, retry-as-new-event,
fanout, combined receipt, payment, material, output, maintenance, or
cross-domain vector exists.

Before any append, these conditions are zero-write:

- unknown, inactive, ambiguous, unadmitted, or multiple decommission package
  bindings;
- missing, malformed, mismatched, or conflicting new-package declaration or
  content digest;
- wrong source event family, source kind, target kind, frozen v2 source pin,
  stream, event visibility, facility/project binding, or source revision;
- missing, private, stale, ambiguous, or forged acquisition/reinforcement
  evidence;
- absent lifecycle status, non-`active` lifecycle status, already
  `decommissioned` facility, wrong current kind, facility revision conflict,
  stream-head conflict, or active-set/descriptor revision conflict;
- any committed `ProductionRun` with the same `facility_ref` and
  `status=started`; the row must reject before append and must not cancel the
  run, release a reservation, discard output, or append a replacement event;
- caller-supplied owner, stream, event family, privacy, receipt, fragment,
  package pin, proof, policy, or idempotency coordinate; and
- exact-key semantic mismatch or changed duplicate.

## Approval Gates

The future decommission package must be a new immutable revision. Its
`package_id`, `package_revision`, declaration/binding/policy refs, author and
trust identity, definition content, canonical bytes, digest claims, derived
digests, descriptor ref/revision, and catalog contract ref are not determined
by the frozen source package and remain unapproved.

The new package content is frozen and digest-verified in the
[v3 freeze record](2026-08-20-inf-1ah-industrial-facilities-v3-decommission-freeze-record.md).
Until exact descriptor/catalog admission, row-specific lifecycle projection
implementation, and exact runtime gate are separately approved, this row
remains design-only and all requests are zero-write.

The package-admission and projection/replay details are recorded in the
[package admission packet](2026-08-20-inf-1ah-decommission-package-admission-packet.md)
and [projection/replay contract](2026-08-20-inf-1ah-decommission-projection-replay-contract.md).
The complete literal approval surface is isolated in the
[minimum business decision and admission closure packet](2026-08-20-inf-1ah-minimum-business-decision-admission-closure-packet.md).

## Explicit Exclusions

This contract does not add a generic transform/action, new owner, router,
registry, coordinator, writer, settlement authority, compensation path,
second runtime/store/bus/clock/scheduler, or any external domain fact.

## Implementation Closure

The separately approved v3 package and exact immutable Construction descriptor /
catalog binding are frozen and digest-verified. The row-specific
`ConstructionProductionAuthority` verifier, fixed projector/reducer branch, and
one-event append path are implemented through
`GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()`.
Focused tests and independent Harness evidence prove privacy, revision fences,
idempotency, append-derived receipt, full replay, checkpoint-tail replay, and
zero-write rejection for unknown, inactive, ambiguous, mismatched, private,
stale, duplicate, conflicting, or active-run inputs. August INF A-D remains
not complete; this record does not admit a generic lifecycle capability.
