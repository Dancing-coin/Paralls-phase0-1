# M5-5 Formal Validator Rule Catalog Coverage

## Scope and method

Static cross-check of every rule code in the formal Architecture v2 `05-规则包/03-校验器规则.md` against the A tip `ce0e1fde2d5d654360505cf8146c7e97f0bcc5af` implementation, tests, and the supported package format. The code catalog is a read-only source in the documentation repository. This audit makes no runtime or pytest claim.

The supported package sections in `rule_pack_validator.py` are FactTypes, machines, models, Pools, entity types, impact profiles, aggregation models, bindings, command catalog, pipelines, workflows, reactions, and play patterns. Owner declarations and executable invariant definitions are not package sections. The package compiler creates FactType `resolution_order` from a deterministic topological sort starting at 10.

## Catalog results

| Rule | Status | Evidence or applicability |
|---|---|---|
| `primitive_count_exceeded` | Structurally prevented | Exactly six primitives are registered in code. Packages cannot declare primitives and unknown values are rejected. A package cannot add a seventh primitive. |
| `primitive_unknown` | Implemented and tested | Package FactType schema rejects values outside the six registered primitive IDs. |
| `primitive_missing` | Implemented and tested | FactType registry rejects an omitted primitive. |
| `facttype_visibility_missing` | Implemented and tested | FactType registry rejects missing or empty visibility. |
| `facttype_resolution_order_missing` | Implemented and tested | Every FactType must occur in a `before` edge or the explicit `unrelated` list. |
| `facttype_resolution_order_duplicate` | Structurally prevented, regression assertion absent | The compiler assigns one integer to each topologically ordered FactType. Tests do not currently assert uniqueness of the emitted values. |
| `facttype_resolution_order_gap` | Structurally prevented, regression assertion absent | The compiler enumerates the topological order consecutively from 10. Tests do not currently assert density of the emitted values. |
| `facttype_owner_unknown` | Implemented and tested | Package Owner references must resolve to the code-registered Owner ID list. |
| `facttype_schema_unknown` | Implemented and tested | Event-schema and primitive-specific references are resolved during compilation. |
| `facttype_refold_missing` | Implemented and tested | Distribution requires a registered refold model. |
| `facttype_naming_invalid` | Implemented and tested | FactType IDs are checked against the registered name, domain, and length constraints. |
| `facttype_scope_missing` | Implemented and tested | Missing scope receives a dedicated rejection code. |
| `resolver_writes_undeclared` | Implemented and tested | Model outputs must name registered FactTypes. |
| `resolver_owner_mismatch` | Implemented and tested | Resolver output Owners must match the target FactType Owner. |
| `resolver_input_undeclared` | Implemented and tested | Restricted inputs reject undeclared reads. |
| `resolver_missing_determinism` | Implemented and tested | Model declarations require a supported determinism policy. |
| `resolver_not_pure` | Not established by package validation | Package format references registered code and declares inputs, outputs, and determinism, but has no code-capability or side-effect attestation contract. This catalog item requires a Resolver registration contract before it can be meaningfully enforced. |
| `impact_layer_facttype_unknown` | Implemented and tested | Impact layers resolve FactTypes from the compiled registry. |
| `impact_layer_owner_mismatch` | Implemented and tested | Layer Resolver Owner and declared write set are compared with FactType ownership. |
| `impact_profile_cycle` | Not representable in the current package format | Impact profiles are an ordered list of layers and contain no profile-to-profile or recursive routing reference. |
| `impact_atomic_cross_host` | Implemented and tested | Host sets and declared atomicity are checked. |
| `impact_layer_conflicts_order` | Implemented and tested | Layer order must be unique and ascending by FactType resolution order. |
| `pipeline_revision_vector_mismatch` | Implemented and tested | Compiled pipeline validation requires consistent revision vectors. |
| `pipeline_cross_scope_atomic` | Implemented and tested | Atomic pipelines cannot span scopes. |
| `pattern_declares_writes` | Implemented and tested | Play patterns and reaction/workflow declarations reject direct writes. |
| `pattern_command_unknown` | Implemented and tested | Reaction and workflow commands resolve through the registered command catalog. |
| `pattern_workflow_cycle` | Implemented and tested | Workflow graph compilation detects cycles. |
| `pack_contains_logic` | Implemented and tested | YAML executable keys, environment substitutions, and forbidden YAML features are rejected at parse time. |
| `pack_invariant_executable` | Not representable in the current package format | Packages reference registered models and FactType schemas but provide no invariant-expression section. This rule needs a formal invariant representation before an expression validator can be added. |
| `pack_overrides_visibility_requirement` | Implemented and tested | Parent-pack override checks preserve or narrow inherited visibility. |
| `pack_defines_primitive` | Implemented and tested | Primitive declarations in the manifest or contents are rejected. |
| `pack_cycle_in_parents` | Implemented and tested | Parent-pack resolution rejects repeated pinned identities. |
| `pack_content_hash_mismatch` | Implemented and tested | Saved expected hashes are compared with the resolved package hash. |
| `owner_overlaps_owner` | Not applicable to package loading | The package format only lists registered Owner IDs. Owner write-set declarations are not package content. |
| `owner_writes_denied` | Not applicable to package loading | The package format does not declare Owner write or deny sets. |
| `owner_native_without_resolvers` | Not applicable to package loading | Owner kind and resolver ownership are not declared in package files. |
| `owner_stewarded_with_resolvers` | Not applicable to package loading | Owner kind and resolver ownership are not declared in package files. |
| `owner_no_invariants` | Not applicable to package loading | Owner invariant registries are not package content. |

## Follow-up boundary

The catalog items marked structurally prevented have explicit source-level guarantees but lack direct regression assertions. Resolver purity and executable invariant checks need formal registration/schema contracts. Owner checks belong to an Owner declaration registry, which this package loader does not currently consume. Impact-profile cycles cannot occur with the current list-only layer format. No unsupported fields, Owner model, or package semantics were invented in this audit.

The audit does not establish complete M5-5 acceptance. It identifies where package validation is implemented, where structure makes a condition impossible, and where the formal rule catalog lacks a representation consumed by the current loader.

## Current-tip correction (2026-11-26)

The initial audit above predates commits `7690df59` and `38a1ccd0`. At A tip `27c2aaa0`, the credential registry tests now assert stable topological ordering, unique and dense `resolution_order` values starting at 10, cycle rejection, and positive coverage for all four registered identity values. The resolution-order duplicate/gap entries are covered by regression assertions; their prior status as assertion gaps is superseded.

At the same tip, validator and registry tests returned `136 passed, 2 warnings in 3.32s` with Python 3.12.2, SQLite 3.43.1, and `app.__file__` resolving under the A worktree. Raw pytest output is `F:/paralls-verification/thread-a/m5-5-rule-catalog-current-tip-20261126-01/focused.log`; pytest temporary data is under the same F-drive run directory.

Remaining M5-5 catalog limits are unchanged: Owner write-set and invariant rules need an Owner declaration contract; Resolver purity needs a registration/capability contract; impact-profile cycles are not expressible in the current flat layer format; executable invariant validation has no invariant-expression section. `temporal_effects` remains blocked separately on its entry schema, reference namespace, validation/rejection contract, consumer, and effect-instance persistence boundary. No package fields or runtime semantics were inferred from the directory name or examples.
