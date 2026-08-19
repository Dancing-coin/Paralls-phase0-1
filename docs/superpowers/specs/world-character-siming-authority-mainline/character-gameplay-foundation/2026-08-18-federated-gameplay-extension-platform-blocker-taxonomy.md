# Federated Gameplay Extension Platform Blocker Taxonomy

Status: `design-only; classification aid`

Date: `2026-08-18`

This taxonomy keeps platform, package, owner, implementation, and environment
blockers distinct. A blocker never authorizes a generic owner or a default
value.

| Status | Meaning | What may proceed | What remains prohibited |
| --- | --- | --- | --- |
| `platform-design pending` | Platform-level design still has unresolved contract fields or approval questions | documentation, design review, plan and taxonomy refinement | schema, digest freeze, catalog, verifier, tests, Harness, runtime |
| `platform-contract pending` | Platform schema, canonicalization, or immutable admission boundary is awaiting approval | formal design, plan, taxonomy, audit and checkpoint updates | manifest schema, digest freeze, catalog, verifier, reducer, tests, Harness, runtime |
| `platform-contract approved` | Four platform gates and scope constraints are explicitly approved; downstream schema/package decisions remain separate | schema-decision design and approval planning | schema implementation, package freeze, digest calculation, catalog, compiler, verifier, reducer, tests, Harness, runtime |
| `platform mechanics implemented and verified` | The approved v2 manifest, canonical digest, immutable candidate/active snapshot path, and P1 candidate-time structural / activation-time exact-one read-only binding boundary have focused and independent Harness evidence | separately approve and freeze one real package, then approve one row binding | treating INF-P as an INF-1/2/3/4 row, adding a business descriptor/catalog row implicitly, or executing a business vertical |
| `candidate-binding sequencing pending` | Historical pre-P1 blocker: a complete package required a non-empty binding but the platform rejected it before candidate installation | retained only as audit evidence | empty-binding placeholder packages, same-revision mutation, descriptor inference, a second registry, router, coordinator, or generic authority |
| `design approved and complete` | Platform contract, schema mapping/migration, and schema closure are explicitly approved as documentation-only design | maintain the approved record; a separately authorized schema-v2 implementation plan may be proposed later | manifest schema, package freeze/digest, row binding, catalog/compiler/verifier, tests, Harness, runtime, and INF execution |
| `schema-decision pending` | Approved platform semantics still need exact manifest paths/types, canonical array rules, legacy preservation, pin locations, or migration/rollout correction | documentation-only mapping, migration, audit, plan and taxonomy work | manifest schema edits, package freeze, digest calculation, compiler/catalog/runtime work |
| `schema implementation approval pending` | Exact schema mapping and migration design are accepted, but actual schema implementation has not been separately approved | review and approval of the schema implementation plan | manifest schema edits, package freeze, digest calculation, compiler/catalog/runtime work |
| `package-content pending` | Platform contract is approved, but a complete immutable package revision/content digest is not frozen | content-authoring packet and package review | implementation or caller-supplied digest |
| `package content frozen; descriptor/binding admission pending` | Exact canonical bytes and untrusted digest claims have been validated and frozen, but no exact-one immutable descriptor has been admitted | separately approve the descriptor/catalog row and its read-only activation boundary | same-revision edits, caller-selected descriptor data, candidate/active mutation without exact-one resolution, or any business vertical |
| `package frozen and digest-verified; exact Construction OwnerOperationDescriptor/catalog admission pending` | INF-1AG has an exact documentation-only packet for a frozen package, but its fixed existing-Construction descriptor/catalog row is not approved or present | approve or reject that exact row | treating the packet as catalog data, binding activation, verifier/reducer/append work, RED tests, Harness, or a generic transform |
| `package frozen/digest-verified and exact descriptor/catalog admission implemented; Construction vertical pending` | The one approved static descriptor/catalog row is present and the frozen package resolves exactly it | separately approve the owner-bound verifier/reducer and narrow append vertical | generic transforms, caller-selected authority coordinates, compensation, fanout, payment, material, router, registry, writer, or second runtime |
| `implemented and verified: exact frozen package-declared oven-to-kiln narrow vertical` | INF-1AG consumes the frozen package and exact read-only descriptor binding through the existing Construction owner only | process the next independently approved row or its formal blocker disposition | treating this one row as generic transform admission, a new owner, or August INF A-D completion |
| `existing-owner-discovery exhausted` | The bounded existing-owner audit has reached its terminal evidence without finding a second complete legal owner contract | row-specific admission design or platform-level contract work | a fourth equivalent search, generic owner invention, or treating exhaustion as implementation approval |
| `admission-evidence pending` | An owner/descriptor family is named, but required committed evidence, subject binding, privacy scope, revision pin, or proof provenance is incomplete | formal evidence contract and blocker documentation | defaults, caller-supplied proof, implicit jurisdiction/project/account, or append/write work |
| `owner-admission design pending` | Exact row needs a complete owner contract or approved admission design | row-specific contract and plan drafting | runtime owner, generic resolver, write path |
| `owner-contract blocked` | Existing owner and an approved row-specific admission contract are both absent or incomplete | blocker evidence and independent rows | inventing a truth owner or generic settlement surface |
| `implementation approval pending` | Contract, package, and evidence fields are complete but implementation authorization is absent | RED test/design preparation only when explicitly allowed | runtime/catalog/write path |
| `implemented narrow vertical` | One exact approved row has code and required focused/Harness/replay/privacy evidence | maintenance and audit synchronization | generalizing the row into a generic API |
| `fully implemented and verified` | All row and mainline acceptance evidence is complete and environment constraints are accounted for | completion reporting | claiming broader scope than evidence proves |
| `unimplemented` | Scope is recognized but no implementation lane has been admitted | preserve zero-write and document next gate | treating proposal or package content as committed truth |
| `environment-limited verification` | Verification was blocked by host/workspace restrictions unrelated to the code claim | rerun in a writable environment | calling the suite green |

## Current Application

INF-P platform mechanics, including P1 candidate-binding sequencing, are
implemented and verified. The mapping/migration errata and schema-closure
addendum remain the governing design evidence. Package-content freeze/digest,
row binding, and INF runtime remain separate. For INF-1AG specifically, P1
permits a complete binding-bearing candidate but activation requires an
independently admitted exact-one immutable descriptor. INF-1AG has its
approved static descriptor/catalog admission implemented and focused verified;
its exact Construction runtime is implemented and verified. No other business descriptor or
INF row has been resumed.

The first attempt to write the descriptor/catalog admission packet was blocked
by environment review error `MODEL_PRICE_NOT_CONFIGURED`. That is a tooling
condition only, not a code failure or test result; it does not alter the
packet's independent approval requirement.

The already implemented rows retain `implemented narrow vertical` and their
existing evidence. August INF A-D remains `not complete`. No row becomes
unblocked merely because this taxonomy or the platform design exists.

## Goal-Level Blocked Definition

`Goal-level blocked` is reserved for an actual impasse where no approved
platform, contract, content, admission, or documentation work remains that can
make progress without a new external decision or state change. Three exhausted
existing-owner discovery audits are not, by themselves, a global blocked
condition. If platform-contract, design, package-content, admission-evidence,
or other bounded work is explicitly approved, the Goal remains active and is
classified by the narrowest applicable blocker status above.

The independent platform-level design lane is complete. August INF row
execution remains paused, but that pause is not a Goal-level blocked
disposition.

The platform approval packet, mapping/migration errata, and schema-closure
addendum are complete design evidence. The platform schema-v2 implementation
and P1 sequencing amendment are verified. The real
`package:industrial-facilities:v1` is now frozen with verified canonical
digests, but no candidate, descriptor, or INF runtime row is admitted; its
status is `package content frozen; descriptor/binding admission pending`.
