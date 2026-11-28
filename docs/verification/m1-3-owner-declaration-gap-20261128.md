# M1-3 Morale Owner declaration gap

Date: 2026-11-28

## Scope and basis

Static review at A branch `thread-a/ownership-bond-followup-20261121`, HEAD `69f64bb2e76dc49005c102000c515b426a56721e`. The formal sources are the read-only Architecture v2 Owner definition, Resolver contract, migration specification and migration plan in the Paralls-docs repository. No source or tests were changed for this audit.

## Formal contract

- `04-Owner/01-Owner定义.md` lists Morale / Formation as `stewarded`. It defines an Owner declaration with `owner_id`, `kind`, `domain`, `writes`, `denies`, `invariants`, `commands`, `resolvers`, `reads`, `default_scope`, and `host`.
- The migration specification's success criterion 1 requires these L3 fields, classification decided under D5, writes mapped to registered FactTypes, and an `owner_overlaps_owner` validator result. Unit DoD U1 requires an Owner declaration and adjudicated classification.
- `06-模型与结算/01-Resolver合同.md` states code and data models share one registry. The migration specification records D3 as approved and says code FactTypes and Resolvers enter the same registry.
- The formal Owner document describes a stewarded Owner as having no Owner runtime. This statement conflicts with the current Morale implementation shape below and needs an explicit classification/implementation ruling before a complete declaration can be claimed.

## A-code evidence

- `backend/app/gameplay/fact_type_registry.py:12-36` defines `REGISTERED_OWNER_IDS`, an ID allowlist. It contains no Owner declaration fields or declaration compiler.
- `packs/county_siege_morale_presence_1_0_2/fact_types/morale.yaml:1-16` declares one Morale-owned Pool FactType, `fact:unit:garrison-east:morale`, with the `MORALE_D8_NARROW@1` invariant reference.
- `packs/county_siege_morale_presence_1_0_2/models/morale_resolvers.yaml:1-16` registers `morale_refold@1` as a code implementation owned by Morale, reading `living_count` and `member_count` and writing the Morale FactType.
- `packs/county_siege_morale_presence_1_0_2/command_catalog/commands.yaml:1-7` declares `morale.refold` handled by Morale.
- `backend/app/gameplay/morale_refold_runtime.py:25-75` implements the calculation and `MoraleRefoldAuthority`, which commits the Pool write. Lines 94 onward read committed casualty, Organization roster, and LifeState history.
- These FactType, Resolver, and command declarations do not provide the full Owner declaration. No code-consumable Morale `writes` pattern set, explicit `denies`, cross-FactType invariant declaration set, Owner reads/default scope/host declaration, or Owner declaration validation was found. This agrees with the existing M5-5 catalog audit.

## Result

U1 is partial. The formal Owner table names Morale as stewarded, while the implementation uses an Owner-specific runtime and a code Resolver. The code has no complete L3 Morale declaration or validator to establish the declaration contract. This audit does not infer missing write/deny patterns or invariant grammar from the package and runtime.

Static-only. No pytest command ran. The B Information replay branch needs no cherry-pick: A already has equivalent event-time, checkpoint-tail test, and selection changes at `07db5404`, `400d4ff9`, and `0c3173f2`; A also contains the separate Information receipt-validation commit `33a1c38a`. `integration` was not modified.

## Required decision/input

The project owner needs to decide how the Morale implementation fits the formal classification: keep Morale stewarded and identify the runtime as an allowed adapter around a registered code Resolver, or adjudicate a native classification under D5. The declaration schema/validator must also consume the formal fields and the existing `MORALE_D8_NARROW@1` reference without inventing an invariant expression grammar. Until this is resolved and implemented, U1 stays partial.
