# Closed Generic Gameplay Families Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the refactoring of all identified specific gameplay rows into the closed, owner-bound family set defined by the companion design, with immutable package content, existing-owner truth, deterministic admission, replay compatibility, focused tests and Harness evidence.

**Architecture:** Keep existing row-specific methods and event vectors as historical compatibility paths. Add family behavior only behind an immutable descriptor and package admission; package slots carry content, while Construction, Inventory and Economy retain their existing facts and separate receipts. `SettlementPlan` remains composition-only and `GameplayEventStore.append_batch()` remains the sole append path.

**Tech Stack:** Python, Pydantic strict models, existing GameplayPatchManifest v2 and GameplayPatchRegistry, GovernedAuthorityContractCatalog, `GameplayCommandEnvelope`, `SettlementPlan`, `GameplayEventStore`, pytest, verification Harness.

---

## Current Progress

The full objective is active. `recipe_production@1` content, descriptor,
binding and Construction start adapter are implemented and verified. The
closed-family matrix now defines all twelve required family records with
immutable content-model, owner, contract, descriptor, stream, event, privacy,
predicate, effect and package-slot pins. All eleven writable families meet the
multi-content genericity gate through one owner-bound adapter. The
`production_output_custody@1` family is formally blocked by missing committed
output quantity, source-to-holder mapping and unique destination-container
evidence; that does not reduce the scope of the overall program.

## Program Completion Definition

The program is complete only when all twelve family workstreams in the companion
design are either `generic_implemented and verified` with schema,
descriptor/binding, owner adapter, at least two distinct immutable content
instances through that same adapter, family-specific source proof/digest/
lifecycle/replay tests, Harness, privacy/revision/idempotency/receipt and
full/tail replay evidence, or `formally blocked` with the exact missing fact or
business decision recorded and zero-write behavior proven. No family may be
counted as generic because its first narrow example is implemented.

## Genericization Recovery Gate

The current matrix is `11 generic_implemented` and `1 blocked`. A bounded
adapter may reuse an existing owner append path, but it is not evidence that
package content changes the execution semantics. Before any family can become
`generic_implemented`,
the owner must prove all of the following with two semantically distinct,
immutable package contents through the same family adapter:

- each instance is selected only from active immutable package/declaration/
  descriptor bindings, and its content and declaration digests are recomputed
  and verified during actual activation;
- fixed owner, stream, event, privacy, revision, receipt and lifecycle pins
  remain descriptor-owned while content changes only approved typed slots;
- source proof and replay reader are family-specific, not inferred from the
  matrix owner category;
- full and checkpoint-tail replay cover both contents and reject a cross-
  instance source, digest, lifecycle or idempotency substitution;
- historical rows retain their original behavior and do not become the second
  instance by alias or renamed fixture.

The promoted adapters derive their execution coordinates from committed source
evidence and selected immutable content; historical row constants remain only
in compatibility paths. Removing a constant alone is insufficient without the
evidence above.

The family contract matrix and boundary Harness are now implemented at the
read-only admission boundary. The immutable
Construction descriptor/catalog row fixes source, stream, event, privacy,
revision, idempotency, receipt, replay and lifecycle pins, while activation
validates typed recipe content and retains package/content/declaration/
descriptor/active-set pins. Distinct recipe bindings remain content-extensible;
duplicate binding refs and all unknown, ambiguous, mismatched or malformed
bindings fail before active-set mutation. The Construction adapter remains the
next family slice and is now implemented as a narrow start-run adapter with owner-
derived idempotency, committed source/privacy/revision checks, and append
provenance pins.

`production_output_certification@1` is now implemented as a separate
Construction-owned `production_output_certified@1` event/reducer. It derives
recipe, output, and quantity from one committed `run_finished` source plus an
admitted package declaration, uses owner-derived idempotency and append
provenance, and does not write Inventory custody. Existing mill-flour
certification remains a historical compatibility row.

`fixed_service_exchange@1` is now implemented as an Economy wrapper over the
committed fulfilled-service Contract and the existing v5 package-exchange
settlement. It derives both parties and the fixed 12-unit local-currency price,
retains the existing append/replay receipt path, and rejects caller-selected
party, account, price, currency, event, and idempotency coordinates.

`harvest_to_custody@1`, `domain_acceptance_marker@1`, and
`private_follow_on@1` are now promoted with
owner-bound wrappers over exact committed Ecology/Population,
Inventory/Organization, and Social evidence. Their fixed receipts and
full/checkpoint-tail readers remain separate from production output custody.

The current continuation has promoted all eleven writable families to
independently verified family adapters. Their source, content, and lifecycle
semantics are closed to typed package content; all historical oven, bakery,
mill, exchange, harvest, weather, organization, social and budget rows remain
unchanged compatibility partitions.

The declarative matrix/Harness checkpoint classifies all eleven writable
entries as `generic_implemented` and `production_output_custody@1` as
`blocked` by missing committed facts. The program remains active until the
custody blocker is resolved or formally retained with required zero-write
evidence.

The family verifier emits `genericity_evidence` for each writable family and a
single formal custody blocker. The Harness fails if evidence or blocker state
drifts from the matrix status.

The activation path now invokes the same immutable family binding helper used
by focused admission tests. It recomputes typed-content and declaration
payload digests before an active-set mutation and records committed-manifest
evidence for each generic family in the aggregate report. This closes the
previous helper-only verification gap.
The current verified distribution is `11 generic_implemented / 0
bounded_adapter / 1 blocked`, with repository pytest at `4260 passed`.

Registry activation now uses the additive family descriptor set for family
capabilities. It validates each selected family content model before mutation,
rejects duplicate binding refs within a package, and rejects blocked custody
family bindings with `patch_capability_binding_family_blocked`. Historical
recipe and INF descriptor monkeypatch/regression semantics remain unchanged.

## 2026-08-30 Task 7 Lifecycle Promotion

- [x] Add committed immutable lifecycle manifests for `mill_reinforced` and
  `bakery_reinforced`.
- [x] Bind both manifests exactly once to the lifecycle family descriptor and
  recompute manifest/content/declaration digests during activation.
- [x] Prove both content instances through the same Construction adapter with
  fixed source, owner, stream, event, project privacy, terminal lifecycle,
  append-derived receipt, zero-write rejection, and full/checkpoint-tail replay.
- [x] Preserve the frozen v3 mill decommission and INF-1AF bakery reinforcement
  rows as compatibility partitions.

## Task 1: Freeze the family matrix and compatibility baseline

**Files:**
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-29-specific-gameplay-to-closed-generic-families-design.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-29-owner-operation-conflict-matrix-design.md`
- Modify: `docs/superpowers/plans/world-character-siming-authority-mainline/README.md`
- Test: `backend/tests/test_owner_operation_conflict_matrix.py`

- [ ] Record the exact family vocabulary, owner boundaries, and historical-row rule in the conflict matrix.
- [ ] Add regression assertions that bakery, oven, mill reinforcement, mill decommission, flour purchase, grain custody and weather rows keep their original operation keys and are not aliases for a generic family.
- [ ] Run `python -m pytest -q backend/tests/test_owner_operation_conflict_matrix.py` and confirm the historical partitions remain unchanged.

## Task 2: Define strict recipe content records

**Files:**
- Create: `backend/app/gameplay/recipe_production_family.py`
- Test: `backend/tests/test_recipe_production_content_schema.py`

- [x] Add strict, frozen models for `RecipeProductionContent`, `RecipeInputSlot`, and `RecipeOutputSlot` using `extra="forbid"`.
- [x] Require namespace-qualified definition and schema references, positive quantities, explicit units, positive duration, and non-empty output definitions.
- [x] Reject owner, stream, event, account, currency, receipt, privacy, compensation, executable-code and arbitrary lookup fields as schema errors.
- [x] Preserve author array order for canonical input; reject non-canonical order and duplicate semantic slots instead of sorting or silently deduplicating.
- [x] Run `python -m pytest -q backend/tests/test_recipe_production_content_schema.py` and confirm invalid content fails before candidate mutation (`6 passed`).

## Task 3: Add the immutable recipe descriptor and read-only binding contract

**Files:**
- Modify: `backend/app/gameplay/governed_contract_catalog.py`
- Modify: `backend/app/gameplay/patch_runtime.py`
- Test: `backend/tests/test_recipe_production_descriptor_binding.py`

- [x] Define one immutable descriptor revision for `recipe_production@1` with fixed Construction source/event/stream/privacy/revision/idempotency/receipt/replay/lifecycle fields.
- [x] Define the allowed predicate families and package-fillable slots; keep descriptor and catalog read-only.
- [x] Require exact-one binding at activation and persist package, content, declaration, descriptor and active-set pins in the existing snapshot/lifecycle record.
- [x] Reject unknown, inactive, unadmitted, duplicate, multiple, stale and digest-mismatched bindings before any mutation.
- [x] Run `python -m pytest -q backend/tests/test_recipe_production_descriptor_binding.py` and verify full and checkpoint-tail binding replay (`7 passed`).

## Task 4: Refactor the Construction production path behind the fixed descriptor

**Files:**
- Modify: `backend/app/gameplay/construction_production_runtime.py`
- Test: `backend/tests/test_recipe_production_construction.py`

- [x] Add a row-specific adapter that reads the admitted recipe declaration and constructs the existing `ProductionRun` with owner-derived facility stream and idempotency.
- [x] Validate committed facility evidence, recipe revision, source privacy, current facility revision and target stream head before building a fragment.
- [x] Keep run-start and run-finish event families fixed; do not accept caller-selected event types, streams, revisions, privacy or receipt values.
- [x] Preserve the existing bakery and mill methods as compatibility paths with unchanged outputs.
- [x] Write RED tests for success, unknown recipe, stale facility, private evidence, duplicate and changed duplicate; run them and confirm failure before implementation.
- [x] Implement the minimum adapter and run `python -m pytest -q backend/tests/test_recipe_production_construction.py` (`7 passed`).

## Task 5: Add the separate Inventory output-custody family gate

**Files:**
- Modify: `backend/app/gameplay/inventory_runtime.py`
- Modify: `backend/app/gameplay/governed_contract_catalog.py`
- Test: `backend/tests/test_production_output_custody_family.py`

- [x] Define a separate owner-bound custody descriptor requiring one committed Construction completion source, an admitted item definition, and an owner-derived holder/container.
- [x] Keep Inventory receipt and replay separate from Construction receipt and replay.
- [x] Reject caller-selected holder, container, item, quantity, stream and event coordinates through the explicit blocker gate.
- [x] Add RED-to-green blocker tests and independent Harness evidence for missing source provenance.
- [x] Do not migrate the existing mill flour custody row automatically; prove it remains a distinct historical partition.

**Current blocker (2026-08-29):** The existing committed Construction
`run_finished` event exposes `output_item` but no committed output quantity.
`facility_acquired.owner_ref` is not an admitted Inventory holder mapping, and
the Inventory projection has no guaranteed unique open destination container.
Therefore an owner-bound `production_output_custody@1` write cannot yet derive
its item quantity, holder or container without caller input or a default. The
task remains pending; the minimum unblock is a committed source-to-holder
mapping, a quantity-bearing source/recipe provenance pin, and an exact unique
container rule, each with its own revision/privacy contract. No runtime or
generic custody writer is added while this blocker stands.

## Task 6: Add the fixed exchange family gate

**Files:**
- Modify: `backend/app/gameplay/economy_runtime.py`
- Modify: `backend/app/gameplay/governed_contract_catalog.py`
- Test: `backend/tests/test_declared_exchange_family.py`

- [x] Define package slots for a typed item/service exchange while keeping provider, receiver, accounts, currency, price policy, lifecycle and compensation fixed by descriptor or owner-derived evidence.
- [x] Require existing Inventory, Ownership or Contract source evidence and keep Economy as the sole ledger owner.
- [x] Reject generic payment, transfer, market pricing, caller-selected account/currency/amount and arbitrary multi-owner vectors.
- [x] Add RED-to-green tests for exact source, price-bound, account, privacy, duplicate, stale custody and separate receipts/replay.
- [x] Preserve INF-2AM, INF-2AL and other fixed exchanges as historical rows without aliasing them to the family.

## Task 7: Verify family-level boundaries and compatibility

**Files:**
- Create: `.harness/profiles/closed-generic-gameplay-families.json`
- Create: `scripts/verification/verify_closed_generic_gameplay_families.py`
- Test: `backend/tests/test_closed_generic_gameplay_families_harness.py`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-29-inf-goal-completion-readiness-audit.md`
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/2026-08-29-inf-residual-blocker-register.md`

- [x] Verify the family adapter cannot create a new owner, event family, stream, router, registry writer, coordinator, settlement authority or second runtime.
- [x] Verify same input/revision produces identical full and checkpoint-tail projection digests.
- [x] Verify all failed admissions are zero-write and all successful writes use append-derived receipts.
- [x] Run `python scripts/verification/verify_closed_generic_gameplay_families.py`.
- [x] Run `python scripts/verification/harness.py --profile closed-generic-gameplay-families`.
- [x] Run `python -m pytest -q` and `git diff --check`; report the external heavenly-runtime preflight separately if unavailable.

### Task 7 Checkpoint: Matrix and custody blocker

- [x] Define and verify the twelve-family immutable matrix in
  `backend/app/gameplay/closed_generic_gameplay_families.py`.
- [x] Expose additive read-only catalog/descriptor lookup through
  `GovernedAuthorityContractCatalog` without changing historical descriptor
  enumeration semantics.
- [x] Add deterministic exact-one selection and typed binding validation.
- [x] Record the `production_output_custody@1` blocker with candidate values,
  sources, impact, recommendation, and zero-write status.
- [x] Run `python scripts/verification/verify_closed_generic_gameplay_families.py`
  and `python scripts/verification/harness.py --profile closed-generic-gameplay-families`.
- [x] Verify focused and full repository tests (`4133 passed` at the latest
  full run before this checkpoint; focused rerun remains green).

The two formerly design-only promotions now have separate TDD adapters,
focused tests and Harness evidence. The program remains active solely because
the production-output custody family is formally blocked by missing committed
facts; no silent migration or generic fallback is permitted.

## Task 8: Gate later family additions

**Files:**
- Modify: `docs/superpowers/specs/world-character-siming-authority-mainline/README.md`
- Modify: `docs/superpowers/plans/world-character-siming-authority-mainline/README.md`
- Modify: `docs/8月分析/12-实现收口与证据映射.md`

- [x] Record that new facility, weather, project, social and exchange families require a separate descriptor/catalog admission when they change fact ownership, event meaning, privacy, lifecycle or cross-domain recipe shape.
- [x] Record that package content can expand indefinitely only inside an approved family and cannot auto-admit new truth.
- [x] Keep August INF A-D `not complete` until its own finite business matrix is closed; do not count the family framework as business-row completion.
- [x] Re-run documentation checks and the continuation gate.
