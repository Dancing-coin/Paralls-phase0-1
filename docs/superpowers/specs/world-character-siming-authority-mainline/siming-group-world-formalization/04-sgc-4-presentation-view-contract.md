# SGC-4 PresentationView Projection Contract

Status: `proposed; owner event family and manifest revision required`

## Scope

This package translates scoped committed events into deterministic scene
semantics consumed by existing Godot/local presentation paths. It does not
own visual truth and does not accept renderer feedback as settlement.

## Contract

`PresentationView` contains `basis_event_vector`, `scope_digest`,
`asset_manifest_revision`, `mapping_revision`, semantic layers and explicit
fallbacks. Each layer carries `source_ref`, visibility, redaction disposition
and identity policy. Crowd output is an approved aggregate band; actor seeds
may reference only already-visible `CharacterRecord` data and may not encode
private relations, hidden positions or unsettled outcomes.

The semantic digest is deterministic for the same basis vector, scope,
manifest and mapping revision. Device capability, local asset availability,
frame rate and LOD are renderer-local and can select only declared fallbacks.
They cannot change the digest, widen scope or append a world event.

## Evidence contract

Focused tests and Harness must prove authorized projection, privacy layer
redaction, aggregation threshold, manifest/mapping revision conflict,
asset-missing fallback, renderer-feedback zero-write, full replay and
checkpoint-tail replay.

## Dependencies and non-goals

Depends on one existing owner event family, scoped projection and published
asset manifest. It does not create an asset registry, presentation truth
owner, visual event store or renderer-to-authority shortcut.
