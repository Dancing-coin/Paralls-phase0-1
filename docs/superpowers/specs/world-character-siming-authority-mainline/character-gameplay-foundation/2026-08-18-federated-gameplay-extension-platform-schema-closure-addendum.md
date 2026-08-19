# Federated Gameplay Extension Platform Schema-Closure Addendum

Status: `design approved; INF-P schema mechanics implemented and verified; package and row gates remain separate`

Date: `2026-08-18`

This addendum closes the remaining schema-contract ambiguities. It does not
modify `GameplayPatchManifest`, add Pydantic models, change snapshot code,
freeze a package, calculate a digest, add tests/Harness, or resume INF work.

## Strict v2 Extension Schema

The v2 object at `/platform_extension` is equivalent to the following strict
Pydantic shape. The notation is a schema contract, not executable code.

```python
class StrictExtensionModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
    )

class PackageIdentity(StrictExtensionModel):
    package_id: str                     # exact equality with /patch_id
    package_version: str                # exact equality with /patch_version
    package_revision: str               # exact equality with /patch_revision_id

class PackageDefinition(StrictExtensionModel):
    definition_ref: DefinitionRef
    definition_schema_ref: SchemaRef
    source_package_revision: str        # exact equality with /patch_revision_id
    typed_content: JsonObject           # validated by definition_schema_ref

class OutcomeDeclarationAuthorInput(StrictExtensionModel):
    declaration_ref: DeclarationRef
    outcome_family_ref: OutcomeRef
    definition_refs: tuple[DefinitionRef, ...]
    eligibility_refs: tuple[EligibilityRef, ...]
    policy_revision_ref: PolicyRevisionRef
    source_package_revision: str        # exact equality with /patch_revision_id
    declaration_digest: Digest          # required untrusted claim; never authoritative

class NormalizedOutcomeDeclaration(StrictExtensionModel):
    declaration_ref: DeclarationRef
    outcome_family_ref: OutcomeRef
    definition_refs: tuple[DefinitionRef, ...]
    eligibility_refs: tuple[EligibilityRef, ...]
    policy_revision_ref: PolicyRevisionRef
    source_package_revision: str
    declaration_digest: Digest          # adapter-derived immutable value

class TypedReadRequirement(StrictExtensionModel):
    requirement_ref: RequirementRef
    predicate_family_ref: PredicateFamilyRef
    subject_slot_ref: SlotRef

class CapabilityBindingRequest(StrictExtensionModel):
    binding_ref: BindingRef
    capability_ref: CapabilityRef
    source_package_revision: str        # exact equality with /patch_revision_id
    declaration_ref: DeclarationRef
    typed_read_requirements: tuple[TypedReadRequirement, ...]
    proposal_effect_types: tuple[EffectRef, ...]

class DependencyConflictRef(StrictExtensionModel):
    relation: Literal["requires", "conflicts"]
    ref: PackageOrCapabilityOrSchemaRef
    revision: RevisionToken

class ReplayReaderRef(StrictExtensionModel):
    reader_ref: ReaderRef
    reader_revision: RevisionToken
    replay_mode: Literal["full", "checkpoint-tail"]

class PlatformExtension(StrictExtensionModel):
    platform_schema_version: Literal["1.0"]
    package_identity: PackageIdentity
    package_definitions: tuple[PackageDefinition, ...]
    outcome_declarations: tuple[OutcomeDeclarationAuthorInput, ...]
    capability_binding_requests: tuple[CapabilityBindingRequest, ...]
    dependency_and_conflict_refs: tuple[DependencyConflictRef, ...]
    replay_reader_refs: tuple[ReplayReaderRef, ...]
    verification_profile_refs: tuple[VerificationProfileRef, ...]
```

All fields in `PlatformExtension` and all fields in its nested objects are
required. The six collection fields may be empty tuples; `null`, omitted
fields, unknown fields, and duplicate identities are invalid. The only
optional values in this contract are optionality already present in the
legacy outer manifest; no v2 extension field is optional.

`JsonObject` means a JSON object whose keys and value types are validated by
the referenced immutable `definition_schema_ref`. It is not executable code,
an expression language, or an authority lookup. A definition schema that is
missing, unknown, or not admitted by the descriptor is zero-write.

## Declaration Digest Derivation Boundary

`declaration_digest` is required in `OutcomeDeclarationAuthorInput`, but it
is an untrusted comparison claim, never an admitted value. The adapter must:

1. validate the author input shape and its pre-canonical array order;
2. remove only `declaration_digest` from that one declaration object;
3. serialize the remaining declaration payload with the approved canonical
   JSON bytes: UTF-8, `ensure_ascii=false`, sorted object keys, compact
   separators, and no array sorting or rewriting;
4. derive `expected_declaration_digest = sha256:<hex>` from those bytes;
5. compare `expected_declaration_digest` exactly to the required author
   claim; and
6. emit a `NormalizedOutcomeDeclaration` containing only the derived value
   when, and only when, the values match exactly.

The author input is not retained as an immutable admission record. The
normalized declaration replaces its digest claim with the derived value. The
following are fixed zero-write outcomes, with no overwrite or repair:

| Input condition | Fixed disposition |
| --- | --- |
| digest absent, `null`, malformed, or wrong type | `platform_declaration_digest_missing` |
| canonical derivation differs from the author claim | `platform_declaration_digest_mismatch` |
| two declarations have one canonical identity but different claimed or derived digests | `platform_declaration_digest_conflict` |
| a normalized declaration is supplied with a missing, wrong, or conflicting derived digest | `platform_declaration_digest_conflict` |

After every declaration is normalized, the adapter constructs the complete v2
manifest record with normalized declarations in
`/platform_extension/outcome_declarations`. It then computes the outer
`content_digest` from that complete canonical v2 record, excluding only
`/content_digest` itself. The derived declaration digests are included in this
outer digest input. This is a contract for a future adapter, not permission to
calculate any package digest now.

## Reference Types And Namespaces

The lexical namespaces are closed by field type. A reference must use the
listed prefix and a version suffix where shown:

| Type | Allowed namespace/form | Canonical identity |
| --- | --- | --- |
| `DefinitionRef` | `definition:<name>@<revision>` | exact string |
| `SchemaRef` | `schema:<name>@<revision>` | exact string |
| `DeclarationRef` | `declaration:<name>@<revision>` | exact string |
| `OutcomeRef` | `outcome:<name>@<revision>` | exact string |
| `EligibilityRef` | `<approved-domain>:<name>@<revision>` | exact string; descriptor must admit the domain family |
| `PolicyRevisionRef` | `policy:<name>@<revision>` | exact string |
| `RequirementRef` | `requirement:<name>@<revision>` | exact string |
| `PredicateFamilyRef` | `predicate:<name>@<revision>` | exact string; descriptor allow-list required |
| `SlotRef` | `slot:<name>` | exact string |
| `BindingRef` | `binding:<name>@<revision>` | exact string |
| `CapabilityRef` | `capability:<name>@<revision>` | exact string; read-only catalog lookup only |
| `EffectRef` | `effect:<name>@<revision>` | exact string; proposal type only |
| `PackageOrCapabilityOrSchemaRef` | `package:`/`patch:`/`capability:`/`schema:` | exact string plus `revision` |
| `ReaderRef` | `reader:<name>` | `(reader_ref, reader_revision, replay_mode)` |
| `VerificationProfileRef` | `verification:<name>@<revision>` | exact string |
| `Digest` | `sha256:` followed by 64 lowercase hex characters | exact bytes |

`package_id`, `package_version`, `package_revision`, and
`source_package_revision` are identity strings cross-checked against the
existing outer manifest. They are not caller-selected authority coordinates.
An eligibility namespace is usable only when the fixed owner descriptor
already lists that exact family; lexical validity never creates admission.

The canonical identity of `PackageIdentity` is the pair
`(package_id, package_revision)`; `package_version` is an equality-checked
metadata field and cannot create a second identity. Every nested reference
uses its exact canonical string (or the tuple stated in the table); no
case-folding, whitespace trimming, or implicit revision insertion is allowed.

## Authority-Shaped Payload Prohibition

`extra="forbid"` applies recursively to every declared extension object.
For `typed_content`, the referenced immutable definition schema must also
reject these key families at every depth:

```text
owner, owner_ref, stream, stream_ref, event, event_family, event_ref,
privacy, privacy_scope, receipt, receipt_rule, compensation,
settlement, fragment, router, registry, coordinator, writer,
authority, authority_coordinate, target_owner, target_stream,
proof, caller_proof, lookup, arbitrary_code, script, executable
```

The extension may carry only content slots and opaque references. It may not
carry an owner name, stream id, event family, revision fence, privacy scope,
receipt rule, replay rule, idempotency rule, compensation rule, settlement
fragment, arbitrary predicate code, arbitrary owner lookup, or caller proof.
Those values are fixed by the immutable owner descriptor and read-only
catalog/binding boundary. A forbidden key, unknown nested key, or authority-
shaped value is zero-write even when its lexical type is otherwise valid.

## Canonical Input Is Author-Ordered

For v2, canonical array order is an admission precondition, not a
normalization step. The author must submit every array in the exact order
defined by its field's canonical key. An array that is valid as a set but not
already in canonical order is zero-write. Admission must not sort, deduplicate,
rewrite, or round-trip the author's content before digest validation.

The required keys are:

```text
package_definitions       -> definition_ref
outcome_declarations      -> declaration_ref
capability_binding_requests -> binding_ref
dependency_and_conflict_refs -> (relation, ref, revision)
replay_reader_refs        -> (replay_mode, reader_ref, reader_revision)
verification_profile_refs -> verification_profile_ref
definition_refs           -> definition_ref
eligibility_refs          -> eligibility_ref
typed_read_requirements   -> requirement_ref
proposal_effect_types     -> effect_ref
```

For existing outer arrays in a v2 manifest, the canonical keys remain the
keys recorded in the mapping errata: dependency tuple identity, state-group
id, migration group id, event-schema identity, rule id, capability identity,
effect type, verification profile, and the legacy economic-outcome identity.
The same direct-rejection rule applies to their nested arrays. Duplicate
semantic identities are zero-write; empty is encoded as `[]`; `null` is
zero-write. v1 arrays retain their historical order and serializer behavior.

## Replay Pairing

The only valid outer/inner schema pairings are:

```text
(manifest_schema_version=1, inner platform_schema_version absent)
(manifest_schema_version=2, platform_schema_version="1.0")
```

The following are zero-write:

```text
(1, "1.0")
(2, absent)
(2, unknown major/minor)
```

The first pair uses the legacy manifest reader and legacy digest bytes. The
second pair uses the v2 extension reader and exact platform schema `1.0`.
There is no compatibility fallback between the two readers.

## Existing Candidate Snapshot And Replay Preconditions

The extension reuses the current `GameplayPatchRegistry` persistence and
lifecycle replay boundary. No new store or registry is introduced.

| Requirement | Existing contract |
| --- | --- |
| save responsibility | the patch control-plane/lifecycle host invokes `GameplayPatchRegistry.save_snapshot(path)` after a validated candidate or active-set transition; package content and domain owners never save or mutate the registry |
| snapshot contents | `export_snapshot()` stores `snapshot_schema_version=1`, every immutable candidate manifest sorted by `patch_revision_id`, and the active set with `registry_revision`, `active_patch_set_revision`, and `patch_revision_ids` |
| atomic persistence | existing save path writes a temporary file, flushes/fsyncs it, and atomically replaces the target; no second persistence mechanism is permitted |
| retention | retain the latest valid snapshot and every candidate revision referenced by retained lifecycle or historical replay evidence; a candidate cannot be garbage-collected while its install/activation/replay evidence is retained |
| rebuild loading | startup/recovery calls existing `GameplayPatchRegistry.load_snapshot()`; `from_snapshot()` validates snapshot schema, re-validates every manifest, reinstalls candidates, recomposes the active set, and checks both active-set revisions |
| missing snapshot | load failure is fixed `patch_registry_snapshot_load_failed`; recovery fails closed and does not select a package or write an event |
| unsupported snapshot schema | fixed `patch_registry_snapshot_schema_unsupported` |
| malformed candidate/active data | fixed `patch_registry_snapshot_invalid` |
| active-set mismatch | fixed `patch_registry_snapshot_active_set_mismatch` |
| lifecycle replay precondition | `GameplayPatchLifecycleProjector.rebuild()` requires the candidate snapshot to be loaded first; missing candidate is `patch_lifecycle_candidate_missing`, digest mismatch is `patch_lifecycle_candidate_digest_mismatch`, and an uninstalled referenced candidate is `patch_lifecycle_candidate_not_installed` |

Replay cannot reconstruct an active set from lifecycle events alone when the
candidate snapshot is absent. It must fail closed with the fixed error rather
than infer a manifest, use a newer package, or create a replacement registry.

## Approved Design Completion

The platform contract, schema mapping/migration errata, and this schema-
closure addendum are explicitly approved and complete as design-only work.
The next artifact, only when separately authorized, is a file-by-file
`schema-v2 implementation plan` naming exact edits, focused RED tests,
Harness selectors, and rollout gates. That plan requires independent approval
before any schema/runtime change. Package-content freeze/digest, row binding,
and INF runtime recovery are separate, unapproved future tasks.

```text
platform design: approved and complete
schema implementation: approval pending
package content freeze/digest: independent and not approved
row binding and INF runtime: independent and not approved
August INF A-D: paused; not complete
```
