# INF-1AG Facility-Transform Content-Authoring Packet

Status: `design-only authoring packet; no concrete package row admitted`

## Purpose And Boundary

This packet is an authoring worksheet for a future gameplay package that may
propose one facility transform under the already designed
`construction_facility_package_declared_transform@1` outcome family. It is
content guidance and audit evidence, not a runtime manifest schema, verifier,
registry, catalog entry, reducer, command, test, Harness profile, or owner.

The packet does not approve a facility pair. A real package row must be
submitted separately with all fields filled from an actual immutable package
revision and then receive its own Owner-Admission Contract approval.

The package may declare only content values. `ConstructionProductionAuthority`
continues to fix the owner, stream, event family, project privacy, receipt,
replay, idempotency and v1 terminal/no-compensation rules.

## Authoring Rules

### Package identity, revision and digest

| Field | Authoring rule | Audit rejection |
| --- | --- | --- |
| `package_id` | Stable, namespaced identity owned by the package author; never reuse an identity for materially different content | missing, malformed, or identity reuse with changed history |
| `package_revision` | New immutable revision for every content or policy change; the row must reference the exact active immutable revision | inactive, unknown, floating, or superseded revision |
| `content_digest` | Derived from the canonical executable package manifest JSON using the existing Patch convention; authoring tools may calculate it but an author/caller may not choose it | absent, non-canonical, or digest mismatch |
| `active_patch_set_revision` | Runtime context pin used when the row is proposed; it is resolved by the active patch set and is not package content | absent, stale, or caller-selected active set |

The packet records the package identity and digest as audit inputs. It does not
add fields to `GameplayPatchManifest`; the existing manifest/active-patch
admission path remains the only executable package boundary.

### Facility transform declaration template

The author fills this logical content declaration from package definitions:

```text
FacilityTransformContent
  package_id: <actual immutable package identity>
  package_revision: <exact active immutable revision>
  content_digest: <derived canonical manifest digest>
  source_kind: <non-empty kind defined by this package>
  target_kind: <different non-empty kind defined by this package>
  policy_revision: <fixed package policy revision>
  eligibility_refs:
    - <one or more non-empty opaque eligibility references>
```

`source_kind` and `target_kind` must be exact package definition literals. No
wildcard, prefix, default target, inferred reinforcement suffix, or caller
replacement is valid. Both definitions must be present in the same immutable
package revision and their semantic revisions must be digest-pinned by the
package content.

The package declaration cannot contain `owner_ref`, `stream_id`, `event_type`,
`privacy_scope`, `receipt_reader_ref`, `replay_reader_ref`,
`compensation_policy`, `settlement_fragment`, router, coordinator, or registry
fields.

### Policy revision template

```text
TransformPolicyDeclaration
  policy_ref: <namespaced fixed policy identity>
  policy_revision: <immutable revision>
  allowed_source_kind: <must equal declaration.source_kind>
  allowed_target_kind: <must equal declaration.target_kind>
  eligibility_rule_refs: <references named in eligibility_refs>
  terminal_mode: terminal_no_compensation_v1
```

The policy revision is a package content reference, not executable authority
code. It must state the exact pair and the eligibility rule references. It may
not redefine Construction ownership or introduce reversal, compensation,
retry, fanout, payment, material, inventory, or settlement behavior. A missing,
ambiguous, or policy/digest-mismatched policy is zero-write.

## Eligibility Reference And Existing-Owner Mapping

The package carries opaque references only. The mapping below is an authoring
review template for the separately approved row-specific contract; it is not a
generic resolver and is not package-controlled:

```text
EligibilityReferenceMapping
  eligibility_ref_family: <specific namespaced family@version>
  eligibility_ref: <real non-empty opaque reference>
  existing_owner: <approved existing owner>
  evidence_kind: <committed event or projection kind>
  evidence_event_or_projection_ref: <real committed evidence identity>
  evidence_revision_pin: <exact revision rule>
  privacy: project
  subject_binding:
    facility_ref: <same facility under consideration>
    project_ref: <same project scope>
  evidence_digest: <owner-derived canonical digest>
```

The package author cannot choose `existing_owner`, event kind, revision rule,
privacy, receipt, replay, or compensation. Those fields are filled during
row-specific owner review from existing committed evidence. The proof is valid
only when the existing owner returns an owner-derived result bound to both
`facility_ref` and `project_ref`.

The row-specific verifier must reject unknown, missing, ambiguous, revoked,
stale, private, subject-mismatched, forged, or digest-mismatched evidence, and
must reject duplicate eligibility references before any append. No default
eligibility or implicit jurisdiction/project may be substituted.

## Fixed Construction Binding

After a real row is separately approved, the only allowed binding is:

```text
typed facility intent
  -> active package declaration read
  -> owner-bound eligibility proof
  -> ConstructionProductionAuthority
  -> gameplay:construction_production:{facility_ref}
  -> gameplay.construction_production.facility_transformed@1
  -> project-scoped projection/outbox
```

The source is the committed `facility_acquired@1` event and current
`ConstructionProductionProjection.facilities` entry. The source acquisition
event revision, current facility revision and stream head are authority-derived
revision fences. One append advances the facility revision by one.

Construction derives the idempotency key from the active package revision,
content digest, facility reference, source acquisition event identity and prior
facility revision. The receipt is the `GameplayEventStore.append_batch()`
receipt; no package or caller supplies a receipt shape. Full replay rebuilds the
facility projection from committed events, and checkpoint-tail replay applies a
committed tail to an authority-created checkpoint with package/digest and proof
pins revalidated.

V1 is terminal and has no reversal, reopen, downgrade, retry-as-new-transform,
compensation, fanout or combined receipt. Unknown package content, unknown
kind, missing/ambiguous eligibility, stale revision, privacy conflict, digest
mismatch and duplicate intent are all zero-write before `append_batch()`.

## Conflict And Selection Rules

1. Only declarations from the active immutable patch set are eligible for new
   proposals.
2. A declaration is selected by the fixed outcome family plus the
   authority-derived source facility kind; callers cannot select a package,
   target, owner, stream, event, revision, privacy scope or fragment.
3. At most one active declaration may match a `(source_kind, target_kind)` pair.
   Different policy, eligibility or digest payloads are an activation conflict,
   not a load-order choice.
4. An exact canonical duplicate is rejected as duplicate and performs no write.
5. Unknown package, inactive revision, digest mismatch, unknown kind, missing
   policy, missing eligibility or ambiguous match is zero-write.
6. The already implemented `bakery -> bakery_reinforced` row is closed under
   INF-1AF and cannot be re-admitted through this packet.

## Disable, Upgrade And Replay Impact

- Disabling a package prevents new proposals from using its declaration; it
  does not delete historical Construction events or their receipts.
- An upgrade creates a new package revision and content digest. It cannot mutate
  or reinterpret an earlier declaration, and it cannot silently replace an
  active conflicting pair.
- Full replay of historical events uses the declaration revision/digest and
  proof pins recorded with the committed event. Replay does not rerun changed
  package rules to reinterpret history.
- Checkpoint-tail replay requires the checkpoint's active package-set revision
  and declaration/proof pins to be compatible with the committed tail. If the
  required immutable declaration is unavailable, replay returns an auditable
  replay-readiness failure rather than guessing.

## Illustrative Example: Non-Admitted

The following is deliberately synthetic content for authoring review only. It
is not a real package, not an active revision, not a catalog row, and must not
be copied into runtime fixtures or tests:

```text
package_id       = package:kiln-demo-illustrative
package_revision = package:kiln-demo-illustrative:v1
content_digest   = <not a real manifest digest>
source_kind      = oven
target_kind      = kiln
policy_revision  = building-policy:v3
eligibility_refs = [blueprint:kiln@1, capability:ceramic-firing@1]
```

The example intentionally lacks a real active manifest, canonical digest,
existing-owner evidence mapping and approved catalog row. It remains
`non-admitted` and zero-write.

## Approval Gate

This packet is complete as authoring guidance only. Before implementation, the
user must separately approve one real package row with actual identity,
revision, canonical digest, source/target definitions, policy revision,
eligibility family, existing owner, committed evidence kind and revision pin.
That approval must then produce a row-specific contract, RED tests, Harness,
immutable catalog entry and Construction implementation in the existing append
spine. Nothing in this packet authorizes those steps now.
