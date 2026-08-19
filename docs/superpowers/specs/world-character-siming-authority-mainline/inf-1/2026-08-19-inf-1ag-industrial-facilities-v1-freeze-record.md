# INF-1AG Industrial Facilities V1 Freeze Record

Status: `package content frozen and canonical digests verified; exact descriptor/binding admission and Construction narrow vertical implemented and verified`

Date: `2026-08-19`

## Frozen Bytes

The exact canonical UTF-8 bytes are stored in
[package-industrial-facilities-v1.manifest.json](package-industrial-facilities-v1.manifest.json).
It contains no placeholder or trailing newline and is the only immutable
content for `package:industrial-facilities:v1`. It must not be edited in place;
a content change requires a new package revision and separate approval.

```text
manifest pair      = (2, "1.0")
patch version      = 1.0.0
package version    = 1.0.0
declaration digest = sha256:04869873a57a24b834cc123a14440444717bdd482910eb9d8ae1d50cc3bc2ed8
content digest     = sha256:41e1b40bcd1fd13e1692f2f51aed7dea6dceee0b1605bf215fe6c673fcd11f88
```

The outer and inner version values are distinct fields and are exactly equal
by explicit approval. The manifest fixes only the approved `oven -> kiln`
declaration, binding, predicate family, subject slot, and effect type. Owner,
stream, event, privacy, receipt, replay, and compensation remain excluded from
package-controlled fields.

## Adapter Verification

The author-supplied declaration digest claim was accepted only after the
adapter derived the expected value from the canonical declaration payload with
only `declaration_digest` excluded. The normalized immutable declaration
stores that derived value. After declaration normalization, the outer content
digest was derived from the complete v2 record with only `content_digest`
excluded, then compared exactly with the author claim.

```text
declaration_claim_verified=True
content_claim_verified=True
candidate_validation_nonmutating=True
canonical_file_bytes=True
```

Missing, malformed, mismatched, or conflicting digest claims remain zero-write
and are never silently repaired or overwritten.

## Boundary After Freeze

No `GameplayPatchRegistry` candidate was installed, no active set was
composed, and no Construction descriptor/catalog row was added. The current
read-only catalog resolves zero descriptors for
`capability:construction-facility-package-declared-transform@1`; an activation
attempt would fail closed with `patch_capability_binding_unknown` before active
set mutation.

The next minimum approval is the exact immutable INF-1AG
`OwnerOperationDescriptor` catalog row and its read-only binding admission.
Construction verifier/reducer/append work, RED tests, and Harness remain
separate later approvals. This freeze does not implement INF-1AG or advance
August INF A-D completion.
