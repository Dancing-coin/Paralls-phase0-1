# INF-1 Remaining Construction Candidate Design Inventory

Status: `historical inventory; INF-1AH implemented and verified; remaining slots formally blocked or duplicate/closed`

## Current Disposition

This inventory records the candidate boundary as it stood before the separate
INF-1AH runtime approval. The exact `mill_reinforced -> decommissioned`
vertical is now implemented and verified under the existing
`ConstructionProductionAuthority`; its current evidence is the
[lifecycle runtime closure](2026-08-21-inf-1ah-mill-decommission-lifecycle-runtime-closure.md).
The historical candidate text below does not authorize another lifecycle
writer, and it does not form INF-1-SLOT-B or INF-1-SLOT-C.

This is a Construction-only candidate inventory, not an INF-1 progress
denominator. Its three slots exclude the already verified INF-1 semantic,
Survival, Ecology, Economy, weather-front, maintenance, repair, and earlier
facility-transform rows.

## Scope And Method

This inventory reads only the existing `ConstructionProductionAuthority`, its
committed event/projection boundary, frozen and admitted Construction package
contracts, and the current INF-1 formal record. It is not a fourth
existing-owner discovery and it creates neither a runtime path nor a package,
catalog, descriptor, test, Harness, or write authorization.

The inventory allows at most three independent candidates. Only one meets the
minimum shape of a committed Construction source/state leading to one exact
Construction outcome. The remaining apparent shapes are recorded as blocked
non-candidates so that an existing narrow row, fixture, or identifier cannot
be promoted into a new business fact.

## Historical Candidate INF-1AH: Mill Reinforced Decommission

### Exact Source To Exact Outcome

```text
committed project-visible facility_acquired(mill)
  + committed project-visible frozen-v2 facility_transformed(mill -> mill_reinforced)
  + current Construction facility projection
-> gameplay.construction_production.facility_decommissioned@1
```

At the time of this historical inventory, this was one row-specific,
design-only candidate. Its proposed identifiers were
`capability:construction-facility-mill-decommission@1` and
`outcome:construction-facility-mill-decommission@1`; no generic Construction
action or decommission capability is implied.

| Contract dimension | Fixed candidate boundary |
| --- | --- |
| Owned facts | `ConstructionProductionAuthority` alone owns the facility lifecycle transition, one facility revision increment, source-proof validation, target stream/event family, privacy, idempotency, receipt, and replay interpretation. |
| Non-owned facts | The row does not own or alter facility kind, condition, plot/project identity, production output, recipe, reservation, maintenance, material, inventory, payment, permit, technology, weather, social, or any other-domain fact. Package content may describe only its approved typed definitions and row-local policy/dependency declarations. |
| Committed source/evidence | One `gameplay.construction_production.facility_acquired@1` event with `facility_kind=mill`, plus one same-stream `gameplay.construction_production.facility_transformed@1` event with `prior_kind=mill`, `next_kind=mill_reinforced`. The reinforcement evidence must retain the frozen v2 package, content digest, declaration/digest, descriptor/revision, and policy-revision pins. |
| Subject and privacy fence | Both source events and the only target event are `project` visible. The same committed `facility_ref` must occur in acquisition, reinforcement, current projection, and target stream; `project_ref` is derived as `facility_acquired.plot_ref`, never supplied as a substitute. |
| Revision fence | Pin acquisition event id/revision, reinforcement event id/revision, the source-event revisions carried by reinforcement, current projected facility revision, and current `gameplay:construction_production:{facility_ref}` head. The future owner also pins the exact new-package declaration/content and descriptor/active-set revisions. |
| Target stream and event | `gameplay:construction_production:{facility_ref}` and exactly `gameplay.construction_production.facility_decommissioned@1`. The event retains `facility_kind=mill_reinforced` and changes only lifecycle `active -> decommissioned`. |
| Eligibility | The row-local proof family is `construction:facility-mill-reinforced@1`, with proposed mechanical names `requirement:construction-facility-mill-reinforced@1`, `predicate:construction-facility-mill-reinforced@1`, and fixed `slot:facility-project@1`. No caller or agent selects proof, source coordinates, or eligibility. |
| Idempotency and receipt | The authority derives a key from the exact new-package/declaration/descriptor pins, facility, acquisition/reinforcement identities and revisions, and prior facility revision. An exact duplicate may replay only the original `GameplayEventStore.append_batch()` receipt; changed-key semantics are zero-write. |
| Full/tail replay | The existing Construction projector/replay boundary is the designated reader. The later row-specific branch makes full and checkpoint-tail replay agree on lifecycle status, facility revision, unchanged kind, facility/project binding, and source revision vector; see the lifecycle runtime closure. The absence described here was a historical implementation gate, not current runtime status. |
| Terminal/reversal/compensation | Version one is terminal: no reactivation, downgrade, reversal, retry-as-new, compensation, cancellation, refund, payment, material, inventory, output, maintenance, fanout, combined receipt, or cross-domain effect. A same-facility committed `ProductionRun(status=started)` rejects before append, without cancelling the run, releasing reservations, disposing output, refunding, compensating, or emitting a substitute event. |

### Fixed Event Vector

The future append is exactly one project-scoped vector, after its separate
package and descriptor gates:

```text
facility_decommissioned@1 {
  facility_ref,
  project_ref,
  prior_kind = mill_reinforced,
  next_kind = mill_reinforced,
  prior_lifecycle_status = active,
  next_lifecycle_status = decommissioned,
  acquisition_event_id, acquisition_event_revision,
  reinforcement_event_id, reinforcement_event_revision,
  expected_stream_revision,
  prior_facility_revision,
  facility_revision = prior_facility_revision + 1,
  decommission package/declaration/policy/descriptor/active-set pins
}
```

Package, caller, and agent cannot choose the authority coordinates, privacy,
receipt, compensation, settlement fragment, event vector, or source proof.
Frozen `package:industrial-facilities:v2` remains source evidence only: it is
not modified, recalculated, copied, overwritten, or reused as the new row.

### Zero-Write Boundary

All of the following reject before append: unknown, inactive, ambiguous, or
multiple future bindings; unadmitted/missing/malformed/mismatched/conflicting
new-package declaration or content digests; wrong package, source/target kind,
event family, stream, privacy, facility/project binding, or frozen-v2 pin;
missing, private, stale, ambiguous, or forged source evidence; absent or
non-`active` lifecycle, already-decommissioned facility, wrong current kind,
started run, descriptor/active-set/facility/stream-head/source revision
conflict; caller-provided authority coordinates or receipt; and duplicate or
changed-duplicate mismatch.

### Historical Missing Business Decisions And Exact Blocker

The candidate had a defined target semantic and terminal boundary, but was
blocked pending the minimum new immutable package literals: package identity
and version, author, trust policy, source and target definition/schema/typed
content records, lifecycle-only policy identity, and explicit dependency and
conflict arrays. `declaration_ref`, `binding_ref`, capability, outcome,
requirement, predicate, and derived revision names follow mechanically after
those decisions and are not separate business approvals.

Those gates subsequently closed through independent manifest authoring and
validation, immutable freeze, exact descriptor/catalog admission, replayable
lifecycle projection work, and separate runtime authorization. This historical
document does not authorize another row or broaden the completed one.

### Relation To Existing Construction Rows

| Existing narrow row | Relation and non-overlap |
| --- | --- |
| `bakery -> bakery_reinforced` | Existing fixed transform vertical. It neither supplies decommission source evidence nor permits another transform/lifecycle row. |
| `oven -> kiln` | Existing frozen v1 package-declared transform. Its package/digest/descriptor pins cannot be reused for this candidate. |
| `mill -> mill_reinforced` | Existing frozen v2 transform and the sole reinforcement source evidence. It remains read-only and does not authorize decommission package content or a generic next action. |
| facility repair and repair compensation | Existing paired repair boundary with its own condition and compensation semantics. It cannot be recast as lifecycle decommission. |
| run start/finish and maintenance-state lifecycle | Existing owner outcomes with their own completion, expiry, dispel, cancellation, or obligation semantics. They cannot be duplicated as new INF-1 rows. |

## No Second Or Third Candidate Is Formed

The current audit yields no independent second or third row. These shapes are
not candidates because their exact missing business decision cannot be safely
inferred:

| Observed Construction fact or shape | Why it cannot form a row | Missing business decision |
| --- | --- | --- |
| committed `run_started -> run_finished` | It is already an existing fixed Construction outcome, not a new candidate. Re-declaring it would duplicate an owner path. | No new target may be inferred; a different source and exact target semantic would have to be named. |
| committed maintenance state -> dispel/expiry/settlement | These are existing fixed lifecycle vectors, including their named cancellation/obligation behavior. | A distinct source, target event family, policy, eligibility, terminal/reversal/compensation semantics, and package/descriptor admission would need explicit business selection. |
| committed facility repair -> repair compensation | This existing pair already has compensation semantics and cannot become a new terminal lifecycle outcome. | An independent target semantic, policy, eligibility, and terminal or compensation boundary would need explicit selection. |
| committed production-completed work evidence | Current committed evidence has a defined evidence projection but no unclaimed exact Construction target semantic. It must not be converted into payment, promotion, facility mutation, or another-domain consequence. | Exact Construction outcome/capability/event family, owner policy, eligibility, privacy, revision fence, terminal/reversal/compensation semantics, and admission pins. |

Accordingly, all unformed shapes remain zero-write. A new row may start only
after a business decision names one independent committed Construction source
and one exact Construction-owned outcome with all missing fields above; the
existing-owner discovery result must not be repeated.

## Evidence Consulted

- `backend/app/gameplay/construction_production_runtime.py`
- `2026-08-15-inf-mainline-completion-audit.md`
- `2026-08-12-inf-remaining-scope-dependency-design.md`
- `2026-08-17-inf-mainline-continuation-checkpoint.md`
- `inf-1/README.md` and `plans/.../inf-1/README.md`
- INF-1AH Owner-Admission, projection/replay, package decision, and plan
  records
- `docs/harness.md` for the distinction between documentation and later
  verification evidence
