# INF-1AG Construction Candidate Owner-Admission Design

Status: `package content frozen and digest verified; immutable descriptor/binding admission remains the next independent gate`

## Purpose And Boundary

This is the approved INF-1AG design stage after the terminal existing-owner
audits. It reads only committed Construction facts already owned by
`ConstructionProductionAuthority`; it is not a fourth discovery audit and it
creates no catalog row, runtime command, test, Harness, or runtime surface.

The required candidate shape is:

```text
one committed source event or state -> one exact Construction outcome
```

The result now defines one fixed outcome family whose concrete source and target
are resolved only from an active immutable gameplay-package declaration. A
package declaration is data admitted with the package revision and content
digest; it is not a runtime registry, caller-selected transform, or writer.
No default source kind, target kind, eligibility, policy, event, scope, receipt,
fragment, or compensation rule is inferred below.

## Existing Construction Fact Boundary

`ConstructionProductionAuthority` already owns the canonical
`gameplay:construction_production:{facility_ref}` stream and projects only:

- `facility_acquired` into immutable facility identity, plot binding, kind,
  condition, and facility revision;
- `run_started` / `run_finished` into a production run and its committed recipe
  snapshot;
- maintenance state and obligation lifecycle facts; and
- the fixed `facility_repaired` / compensation and
  `facility_transformed(bakery -> bakery_reinforced)` outcomes.

It does not own plot title, permits, blueprints, materials, payments, inventory
output, work compensation, package policy registration, a clock, or a generic
facility-action vocabulary. The existing authority is the only possible owner
for a future owner-local facility or run outcome; none of the reviewed paths
requires a new owner. That fact does not make a new outcome admissible.

## Concrete Facility Transform Candidate List

These are the only three source kinds found in committed
`facility_acquired@1` fixtures and the corresponding facility projection.
Their acquisition event ids are instance-specific and must be read from the
store; no caller-supplied id is a candidate fact. Every row reuses the existing
Construction owner, stream pattern
`gameplay:construction_production:{facility_ref}`, and project-scoped facility
projection boundary. Those reusable boundaries do not admit a write.

| Candidate | Existing source kind | Target kind | Committed source/projection | Eligibility or policy evidence | Reusable owner / stream / privacy | Existing-row overlap | Terminal/reversal/compensation choice | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C-1 | `bakery` | `bakery_reinforced` | `gameplay.construction_production.facility_acquired@1` plus `ConstructionProductionProjection.facilities` | immutable `inf:construction-facility-bakery-reinforcement@1` and `policy:construction_bakery_reinforcement` | `ConstructionProductionAuthority`; `gameplay:construction_production:{facility_ref}`; project-scoped facility projection | exactly INF-1AF; must not be a new row | already terminal; no reversal, compensation, retry, or fanout | `duplicate/closed` |
| C-2 | `oven` | `kiln` | committed `facility_acquired@1` plus `ConstructionProductionProjection.facilities`; source kind and plot binding are read from the committed event/projection | approved row-specific `construction:facility-acquired@1` proof owned by `ConstructionProductionAuthority`; package policy `policy:industrial-facilities:oven-to-kiln@1` says committed `oven` acquisition is sufficient for this row only | `ConstructionProductionAuthority`; `gameplay:construction_production:{facility_ref}`; project-scoped facility projection | not INF-1AE, INF-1AF, due-finish, or work-completion evidence; no generic transform | target/policy/package/eligibility values are fixed by the approved row; canonical `content_digest` remains a manifest-freeze gate; v1 terminal/no-compensation is fixed | `design approved; implementation gated` |
| C-3 | `mill` | declared by active package revision; otherwise `needs gameplay decision` | committed `facility_acquired@1` in existing weather/maintenance fixtures plus the same facility projection; no transform event is admitted for this source until a declaration resolves | package must provide immutable eligibility references and policy revision; none is currently committed for `mill` | `ConstructionProductionAuthority`; `gameplay:construction_production:{facility_ref}`; project-scoped facility projection | not INF-1AE, INF-1AF, due-finish, or work-completion evidence; existing weather-to-maintenance rows are not transforms | package author must declare one target literal, eligibility refs, policy revision, package revision, and digest; v1 terminal/no-compensation is fixed by this design | `design pending` |

The `mill` row remains a candidate-only observation, not a contract. The
`oven -> kiln` row is now a separately approved design contract below;
`facility_kind` remains a free string on the acquisition model, and the
projector's executable transform admission is still limited until the
industrial manifest digest gate is closed. Naming any other target by analogy
would create gameplay semantics not present in an approved package.

### Minimum User Decisions

For C-1, no further decision is requested: it is already closed by INF-1AF and
must not be reopened as INF-1AG. C-2 is now approved as the exact
`package:industrial-facilities:v1` `oven -> kiln` design row; its only open
gate is derivation and reconfirmation of the complete manifest's canonical
`content_digest`. C-3 still requires a separate package declaration and
row-specific approval. For C-3 only, the minimum fields remain:

1. one declaration inside an active immutable package revision containing the
   literal `source_kind`, literal `target_kind`, and `eligibility_refs`;
2. the package `policy_revision`, `package_revision`, and canonical
   `content_digest`, with eligibility references resolving to committed facts;
3. confirmation that the source is `facility_acquired@1` plus the current
   facility projection/revision fence, unless a separately approved source
   projection is named; and
4. no caller-selected owner/stream/event/privacy/receipt/fragment and no
   compensation override; v1 terminal/no-compensation semantics are fixed.

Until the C-3 package declaration and eligibility references exist, C-3 remains
design-pending. For C-2, the remaining digest gate likewise prevents any
package-specific catalog entry, RED test, Harness, or runtime write from being
authorized.

## Package-Declared Facility Transform Contract (Design Only)

This design is subordinate to the foundation
[Package Content And Cross-Domain Binding Matrix](../../character-gameplay-foundation/2026-08-17-package-content-and-cross-domain-binding-matrix-design.md).
The manifest record shapes and legacy-model boundary are further closed by
[Package Contract Closure And Manifest Adapter](../../character-gameplay-foundation/2026-08-17-package-contract-closure-and-manifest-adapter-design.md).
The matrix defines which declaration data may come from a package and which
owner/replay/privacy fields remain fixed by Construction. INF-1AG does not
create a second package schema or a generic package binding registry.

The design-only author workflow is captured in the separate
[Facility-Transform Content-Authoring Packet](2026-08-18-inf-1ag-facility-transform-content-authoring-packet-design.md).
It may prepare an auditable candidate, but it cannot admit a package row or
replace the later row-specific approval gate.

The fixed capability/outcome family is
`capability:construction-facility-package-declared-transform@1` /
`construction_facility_package_declared_transform@1`. It is one owner-local
outcome family, not a generic `facility_kind -> facility_kind` API. The active
immutable package revision supplies the finite declaration below; the caller
cannot supply or alter any of these values:

```text
FacilityTransformDeclaration
  source_kind
  target_kind
  eligibility_refs[]
  policy_revision
  package_revision
  content_digest
```

The declaration is validated as part of the immutable package/active-revision
boundary. It is not runtime-writable, does not select an owner or stream, and
does not contain executable code, a router, a registry, a settlement fragment,
or compensation instructions.

The declaration schema must reject `owner_ref`, `stream_id`, `event_type`,
`privacy_scope`, `receipt_reader_ref`, `compensation_policy`,
`settlement_fragment`, and router/coordinator fields. Those values are fixed by
this owner contract or derived from the existing authority; they are never
package or caller inputs.

### Canonical declaration schema and digest (design closure)

The six package-declared fields are the complete declaration payload. The
package does not add a caller-visible declaration id or digest field:

```text
FacilityTransformDeclarationPayload
  source_kind: non-empty UTF-8 string
  target_kind: non-empty UTF-8 string
  eligibility_refs: sorted, unique non-empty reference strings
  policy_revision: immutable policy reference
  package_revision: exact active GameplayPatchManifest.patch_revision_id
  content_digest: exact active GameplayPatchManifest.content_digest
```

The `eligibility_refs` order is canonicalized lexicographically and duplicate
references are invalid. `source_kind == target_kind` is invalid, and the
already closed `bakery -> bakery_reinforced` pair cannot be admitted again by
INF-1AG.

The authority derives, rather than accepts, the declaration digest:

```text
declaration_digest = sha256:<hex>
canonical input = {
  "content_digest": content_digest,
  "eligibility_refs": sorted(eligibility_refs),
  "package_revision": package_revision,
  "policy_revision": policy_revision,
  "source_kind": source_kind,
  "target_kind": target_kind
}
```

The canonical encoding is the existing Patch convention: JSON with
`ensure_ascii=false`, sorted keys, no insignificant whitespace, encoded as
UTF-8, and prefixed with `sha256:`. `declaration_digest` may be retained in a
typed proposal, receipt, and authority event as derived evidence, but it is
never caller-selected or independently package-authored.

An active patch-set may contain at most one declaration for a given
`(source_kind, target_kind)` pair. Two declarations with that pair but
different eligibility or policy payloads are an activation conflict, not a
load-order choice. A declaration duplicated with the same canonical payload
is rejected as a duplicate. Across active packages there is likewise no
last-write-wins rule; an ambiguous match is zero-write.

The direct Construction intent contains only the facility identity and normal
causation/correlation context. It does not contain a target kind, package
revision, content digest, declaration digest, owner, stream, event, privacy,
receipt, or policy. A package-originated typed proposal may carry the derived
`declaration_digest`; Construction must re-derive it from the active manifest
before accepting the proposal.

### Row-specific eligibility proof contract (design closure)

`eligibility_refs[]` remain opaque until a separately admitted Construction row
names the accepted reference families and their existing owners. The
row-specific verifier returns this proof shape; it is not a generic registry
or cross-domain resolver:

```text
FacilityTransformEligibilityProof
  eligibility_ref
  facility_ref
  project_ref
  evidence_owner_ref
  evidence_kind
  evidence_event_id_or_digest
  evidence_revision
  privacy_scope
  source_policy_revision
  source_package_revision
  proof_digest
```

`proof_digest` is derived from the other fields with the same canonical digest
algorithm. The verifier must enforce that the owner and accepted event kind
are fixed by the row-specific contract; that the proof is about the requested
facility and project; that the evidence revision is the expected committed
revision; that the package and policy revisions match the declaration; and
that the returned privacy scope is project-visible and authorized for this
command. The caller supplies none of those authority coordinates.

The verifier rejects an unknown reference family, missing or revoked evidence,
owner/event mismatch, subject mismatch, stale revision, policy/package digest
mismatch, private-scope conflict, duplicate reference, or forged digest before
`append_batch()`. Construction consumes the proof but does not become the
owner of the referenced fact. Until a concrete package chooses an accepted
reference family and its existing owner/event revision, this proof contract is
specified but not implementable.

`eligibility_refs[]` are opaque references, not caller or package-selected
authority coordinates. A later approved resolver must map each reference to an
existing owner's committed evidence and return its owner-derived event kind,
event/projection revision, privacy scope and evidence digest. Missing,
ambiguous, stale, revoked or scope-incompatible resolution is zero-write;
Construction only consumes the resolved proof and never becomes its owner.

| Contract field | Fixed design rule |
| --- | --- |
| owned facts | Construction owns facility kind, facility revision, acquisition binding, and the terminal transform event on the facility stream |
| non-owned facts | package activation/digest, permits, blueprints, materials, payment, inventory output, plot title, clocks, and compensation truth remain outside Construction; opaque eligibility refs must resolve to already committed owner facts with owner-derived event/revision/privacy/digest pins |
| command surface | typed facility transform intent identifies only the facility and correlation/idempotency context; active package revision is resolved by authority context, never selected by caller |
| source | committed `gameplay.construction_production.facility_acquired@1` and current `ConstructionProductionProjection.facilities` entry; acquisition event id/revision is read from the store |
| source revision fence | acquisition event revision, current facility revision, and current facility-stream head must all match the pre-append projection; source kind must equal the package declaration |
| target stream | `gameplay:construction_production:{facility_ref}` fixed by Construction owner |
| event family | `gameplay.construction_production.facility_transformed@1` fixed; payload carries resolved prior/next kinds, source event id/revision, facility revisions, policy/package revision and content digest |
| write revision | one atomic append at expected stream head; facility revision advances by exactly one |
| privacy | source, event, authority receipt and project projection are `project`; no broader or caller-selected scope is admitted |
| idempotency | `construction:facility-transform:{package_revision}:{content_digest}:{facility_ref}:{acquisition_event_id}:{prior_facility_revision}`; all components are authority-derived |
| receipt | append-derived `GameplayEventStore.append_batch()` receipt containing committed event ids and revisions; outbox exposes only the fixed project-safe facility fields |
| replay | full replay rebuilds the facility projection from all committed events; checkpoint-tail replay starts from an authority-created checkpoint and applies only the remaining committed tail, with package/digest and event payload pins revalidated |
| terminal semantics | one successful declaration is terminal for v1; no retry-as-new-transform, downgrade, reopen, reversal, compensation, fanout, or combined receipt |
| zero-write | unknown/inactive package revision, digest mismatch, unknown source or target kind, missing/unresolvable eligibility ref, stale source/facility/stream revision, privacy conflict, malformed declaration, caller-selected owner/stream/event/policy, or duplicate intent rejects before `append_batch()` |

The exact package source/target pair is therefore not pre-fixed by the
Construction base. It is fixed per active immutable declaration and becomes
admissible only when all references resolve to committed facts and the
authority's source/revision/privacy fences pass. A package with no declaration
for a facility kind remains zero-write; no default kind or implicit policy is
allowed.

### Current design blockers

1. The runtime `GameplayPatchManifest` currently has no
   `facility_transform_declarations` field or declaration digest validator;
   this document now fixes the design shape and canonical digest, but the
   runtime schema remains absent.
2. No existing immutable eligibility-reference verifier is defined for the
   Construction owner; this document now fixes the accepted
   `construction:facility-acquired@1` family, owner, committed event and
   revision/binding pins for C-2, but no verifier exists and implementation is
   gated on the manifest digest freeze.
3. The Construction projector currently accepts only the committed bakery
   pair, so package-resolved non-bakery kinds have no admitted reducer rule.
4. No package-specific immutable catalog admission row exists for this family;
   this design stage intentionally does not create one.
5. The row-specific `package:industrial-facilities:v1` design is now approved,
   but its complete immutable manifest and canonical `content_digest` are not
   yet frozen or user-reconfirmed. The only executable package manifest
   currently present is `package:frost-farm` at `package:frost-farm:v1` with
   digest `sha256:frost-farm-v1`, and it declares no facility transform. The
   former foundation `oven -> kiln` example is superseded by the exact row
   contract below, but it is not executable content until the industrial
   manifest digest gate is closed.

These are formal blockers, not permission to add a generic registry, writer,
router, or runtime owner. They must be closed in the later approved plan before
RED tests or implementation.

## Reviewed Paths

### 1. Package-Declared Facility Transform

The event relationship is fixed as a design family; literal kind values remain
package data and are intentionally not hard-coded by the Construction base:

```text
committed facility_acquired(facility_kind)
  -> facility_transformed(prior_kind, next_kind)
```

The current projector rejects every transform other than committed
`bakery -> bakery_reinforced`. A future implementation must add a declaration-
validated reducer branch, not loosen that check into a generic transform. The
package supplies the pair, while the base still fixes owner, stream, event
family, privacy, receipt, replay and terminal boundaries.

| Required contract field | Current fact | Missing, non-inferable decision |
| --- | --- | --- |
| capability id and owned fact | Construction owns facility kind/revision | package declaration schema and declaration digest |
| non-owned facts | plot title, permits, blueprint, materials, payment, and production output are outside Construction | whether any of those facts are a required committed eligibility source, and their existing owner/event pins |
| committed source and source revision | `facility_acquired` records a generic string kind on the facility stream | active package declaration, source event id/revision and current facility revision fence |
| target stream and write revision | the facility stream and its head/revision are known | fixed facility stream, one append at expected head, facility revision +1 |
| fixed event vector and privacy | project scope and one `facility_transformed` event exist for bakery reinforcement | package-resolved payload under fixed `facility_transformed@1` and project scope |
| idempotency | bakery reinforcement has a pair-specific key | authority-derived package/content/source digest key |
| receipt and replay | current receipt/projector reconstruct only the bakery pair | append-derived receipt plus declaration-pinned full/checkpoint-tail replay |
| terminal/reversal/compensation | bakery reinforcement is terminal; repair compensation affects only condition | v1 terminal/no-compensation is fixed; no caller override |

Minimum package admission choice: declare one literal source/target pair,
eligibility references, policy revision, package revision and content digest in
an active immutable package, then provide the owner/revision-pinned resolver
for each eligibility reference. The base contract fields above do not vary by
package and cannot be caller-selected.

### 2. Due Production Completion

Potential shape:

```text
committed run_started(finish_tick, recipe snapshot)
  -> gameplay.construction_production.run_finished
```

This is not a new candidate. `ConstructionDueCompletionPolicy` and the
existing due-finish fragments already own the fixed completed-run outcome; the
frost consumer contracts reuse that owner-local result without changing it.
The direct helper accepts run, recipe, and tick inputs, so treating it as a new
agent-facing capability would require a canonical time trigger and fixed
selection rule. No clock or scheduler may be introduced, and an unpinned
caller-supplied tick, run, or recipe is not admissible.

The source, target stream, `run_finished` event family, project privacy,
idempotency, append receipt, full replay, checkpoint-tail replay, and terminal
completed-run semantics are already owned by the existing fixed row. A new
contract would duplicate that row rather than discharge an INF-1 blocker.

### 3. Completed Worker Evidence

Potential shape:

```text
committed run_finished + committed worker contribution from run_started
  -> gameplay.construction_production.work_completion_evidence_recorded
```

This is not a new candidate. The existing INF-4Z source contract already pins
the finished event, contribution digest, same production stream revision, and
actor-only projection. It has the fixed append-derived receipt and full/
checkpoint-tail replay reader consumed by the approved INF-4T wage vertical.
Re-designing it under INF-1 would duplicate an implemented Construction outcome
and would not produce a new facility action.

## Required Zero-Write Boundary

Until the declaration schema, eligibility resolver and reducer admission are
approved and implemented, all of the following
remain zero-write before `GameplayEventStore.append_batch()`:

- a caller-selected facility source/target kind, stream, event family,
  revision, privacy scope, receipt, fragment, policy, retry, reversal, or
  compensation rule;
- a non-bakery use of `facility_transformed` without a validated active package
  declaration and admitted reducer;
- a `run_started` completion request that supplies a tick, run, or recipe as a
  replacement for an admitted due-completion trigger; and
- a second work-evidence contract or an attempt to use work evidence as a
  generic action/transform source.

This preserves the isolation from generic Construction actions and transforms:
`SettlementPlan` remains composition-only, and neither the catalog nor any
new helper may become a writer, router, registry, coordinator, or settlement
authority.

## Next Admission Condition

The row-specific contract is approved for design only. No RED tests, Harness
profile, catalog entry, manifest schema, verifier, reducer, or runtime code is
authorized yet. The next gate is to freeze the complete immutable
`package:industrial-facilities:v1` manifest, derive its canonical
`content_digest` using the existing Patch convention, record that digest in
formal evidence, and obtain explicit reconfirmation. Only after that gate may
the separately ordered implementation plan be opened.

## Approved INF-1AG Row-Specific Contract (Design Only)

The following exact row is now approved as a design contract. This approval
does not admit a manifest schema, catalog row, verifier, reducer, RED test,
Harness profile, or runtime write path.

### Fixed row identity and owned fact

```text
outcome_family  = construction_facility_package_declared_transform@1
capability_ref  = capability:construction-facility-package-declared-transform@1
package_id      = package:industrial-facilities
package_revision= package:industrial-facilities:v1
source_kind     = oven
target_kind     = kiln
policy_ref      = policy:industrial-facilities:oven-to-kiln
policy_revision = policy:industrial-facilities:oven-to-kiln@1
```

The target semantic is a one-time high-temperature production-facility
identity upgrade from `oven` to `kiln`. Construction owns only the facility
kind transition and its committed facility revision. This row creates no
material, inventory, payment, production output, permit, technology, license,
or other-domain fact. The package policy says that a committed acquisition of
the declared `oven` is sufficient for this row; it is not a permit,
technology, material, payment, or generic eligibility assertion.

### Package declaration and digest gate

The active immutable `GameplayPatchManifest` must contain the exact declaration
for the six package fields already fixed by this design:

```text
source_kind      = oven
target_kind      = kiln
eligibility_refs = [construction:facility-acquired@1]
policy_revision  = policy:industrial-facilities:oven-to-kiln@1
package_revision= package:industrial-facilities:v1
content_digest   = <derived from the complete immutable manifest canonical JSON>
```

`content_digest` is intentionally not filled by this document. It must be
derived by the existing `GameplayPatchManifest` canonical JSON rules after the
complete immutable `package:industrial-facilities:v1` manifest is frozen. A
caller, package author, agent, or this design may not invent or select it.
The resulting digest must be recorded in the row-specific implementation
evidence and reconfirmed by the user before any runtime implementation gate
opens. A digest mismatch, missing digest, inactive revision, or declaration
canonicalization conflict is zero-write.

### Existing-owner eligibility and project binding

```text
eligibility_ref_family = construction:facility-acquired@1
eligibility_refs       = [construction:facility-acquired@1]
existing_owner         = ConstructionProductionAuthority
evidence_kind          = gameplay.construction_production.facility_acquired@1
project_binding_rule   = construction_plot_as_project@1
project_ref            = committed facility_acquired.plot_ref
facility_ref           = committed facility_acquired.facility_ref
privacy                = project-scoped
```

The owner-derived proof must bind the same `facility_ref` and `project_ref`,
with source `facility_kind=oven`. Its revision vector must exactly pin the
committed acquisition-event stream revision, current facility revision, and
facility stream head. The facility reference, plot/project binding, and source
kind must all agree with the current Construction projection. This row-specific
plot binding is not a global project model and cannot be selected by caller,
package, or agent.

### Fixed write and evidence contract

The existing Construction owner fixes every authority coordinate:

```text
owner          = ConstructionProductionAuthority
target_stream  = gameplay:construction_production:{facility_ref}
event_family   = gameplay.construction_production.facility_transformed@1
privacy_scope  = project-scoped
write_revision = one append at the expected facility-stream head; facility revision +1
```

The event vector contains one `facility_transformed@1` event whose prior kind
is `oven`, next kind is `kiln`, and whose payload carries only authority-
derived source event/revision, facility revision, package/policy revision,
content digest, declaration digest, and the bound facility/project identity.
The idempotency key remains authority-derived:

```text
construction:facility-transform:
  package_revision:content_digest:facility_ref:
  acquisition_event_id:prior_facility_revision
```

The receipt is the append-derived `GameplayEventStore.append_batch()` receipt.
The project-scoped outbox exposes only the fixed safe facility fields. Full
replay rebuilds the facility projection from committed events. Checkpoint-tail
replay starts from an authority-created checkpoint and applies the committed
tail only after package/digest, source, proof, and revision pins are
revalidated.

### Terminal and zero-write semantics

V1 is terminal and has no reversal, downgrade, retry-as-new-transform,
reopen, compensation, fanout, combined receipt, payment, material, or
production-output vector. `bakery -> bakery_reinforced` remains the closed
INF-1AF row and cannot be admitted through this capability.

Before `GameplayEventStore.append_batch()`, the operation must perform zero
writes for unknown or inactive package/revision, missing or mismatched
canonical digest, unknown kind, missing/ambiguous/stale/private or forged
`facility_acquired` evidence, facility/project binding conflict, source or
stream revision conflict, duplicate or ambiguous declaration, a non-`oven`
source, a prior transform, caller-selected authority coordinates, or any
request that supplies payment, material, permit, technology, output,
compensation, reversal, or target-selection semantics. No default target,
implicit project, implicit policy, or caller-selected digest is permitted.

### Implementation gate

The row-specific design is approved. The complete immutable manifest is now
frozen with separately approved equal outer/inner version values, and its
declaration/content digest evidence is recorded in the
[2026-08-19 freeze record](2026-08-19-inf-1ag-industrial-facilities-v1-freeze-record.md).
The exact immutable descriptor/catalog row and read-only binding admission were
subsequently approved. The owner-bound verifier, declaration-validated reducer,
focused RED-to-green tests, independent Harness, and one append-only vertical
were then implemented for this row only. Evidence is `11 passed` in
`backend/tests/test_infra_construction_facility_package_transform.py` and a
green `infra-construction-facility-package-transform` Harness. This closes only
the frozen `oven -> kiln` row; it does not authorize a generic transform,
additional package declaration, or broader August INF completion claim.
