# Stormnight Copper Sanatorium Package Admission Record

Status: `candidate content verified; global descriptor/catalog admission is a later gate`

Package identity is fixed to the original case content:

```text
package_id       = package:stormnight-copper-sanatorium@1
package_revision = package:stormnight-copper-sanatorium:v1@1
package_version  = 1.0.0
manifest         = GameplayPatchManifest v3 / platform_schema_version 2.0
```

The adapter derives declaration and content digests from canonical normalized
bytes. Any author-supplied or caller-supplied digest is untrusted and must
match the derived value exactly. The package wrapper currently proves
cardinality, pin retention and exact-one local binding without modifying the
global frozen package set.

The descriptor identity is `descriptor:scripted-mystery-case@1`, with one
project-scoped case binding and explicit full/checkpoint-tail reader refs. A
global catalog admission requires a separate additive registration once the
case event schema and runtime owner are implemented; this record must not be
read as authorization for a generic case writer.
