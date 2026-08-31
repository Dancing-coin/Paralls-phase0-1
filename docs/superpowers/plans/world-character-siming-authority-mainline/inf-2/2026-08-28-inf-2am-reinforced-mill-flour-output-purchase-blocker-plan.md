# INF-2AM Reinforced-Mill Flour Output Purchase Blocker Plan

> **Historical note:** The blocker gate was closed by the autonomous row-resolution mandate. The implemented INF-2AM plan is recorded in `2026-08-28-inf-2am-reinforced-mill-flour-output-purchase-plan.md`.

**Goal:** Convert the reinforced-mill output-purchase direction into an admissible INF-2 Slot-C row only after its Inventory custody source and Economy terms are real, committed, and uniquely pinned.

**Architecture:** Keep Construction as the source of committed production completion, Inventory as the sole custody owner, and Economy as the sole ledger owner. Reuse the existing `GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch()` spine and existing package-exchange substrate only for the fixed row; do not introduce a generic output adapter or market route.

**Tech Stack:** Existing Python/Pydantic gameplay authorities, immutable GameplayPatchManifest v2, GovernedAuthorityContractCatalog, GameplayEventStore replay, focused pytest, and independent Harness verification.

---

### Task 1: Close the business-literal gate

**Files:**
- Read: `docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/2026-08-28-inf-2am-reinforced-mill-flour-output-purchase-blocker-design.md`
- Update: `docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/2026-08-20-inf-2-remaining-rows-blocker-design-packet.md`
- Update: `docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/2026-08-20-inf-2-owner-admission-candidate-register.md`

- [ ] Record approved exact recipe, item definition/schema/content, quantity, custody holder/container derivation, provider/receiver, currency, price policy, Economy root outcome, lifecycle, and new package revision.
- [ ] Reject the task before any mutation if any literal is missing, caller-selected, fixture-derived, or conflicts with frozen package revisions v1-v6.

### Task 2: Author the row-specific Inventory source contract

**Files:**
- Modify: `backend/app/gameplay/inventory_runtime.py`
- Modify: `backend/app/gameplay/construction_production_runtime.py` only if a dedicated committed source view is required
- Create: `backend/tests/test_inf2am_reinforced_mill_flour_output.py`

- [ ] Write RED tests first for exact mill/facility/recipe/reinforcement provenance, owner-derived custody coordinates, fixed quantity, project/actor privacy, revision fences, changed-key rejection, duplicate replay, and pre-append zero-write.
- [ ] Add one Inventory-owner method whose arguments identify only the committed source event and expected revisions; derive item, holder, container, quantity, stream, privacy, and idempotency internally.
- [ ] Keep generic `record_output_receipt()` unchanged and reject its use as INF-2AM source proof.
- [ ] Add full and checkpoint-tail Inventory replay assertions for the exact custody event.

### Task 3: Freeze the new immutable package

**Files:**
- Create: `docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/package-industrial-facilities-v7-reinforced-mill-flour-output-purchase.manifest.json`
- Create: row-specific contract and freeze record under `docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/`
- Modify: existing package admission tests only to register the new immutable file

- [ ] Validate a complete manifest v2 with no placeholder or default values.
- [ ] Require the author declaration digest claim, derive the expected declaration digest from the canonical declaration payload with the claim excluded, compare exactly, and save only the derived value.
- [ ] Derive content digest only after declarations are normalized, excluding only `content_digest`; missing, malformed, mismatched, or conflicting claims are zero-write.
- [ ] Install the candidate only after digest validation and activate only through the existing exact-one binding path.

### Task 4: Admit the exact descriptor and Economy binding

**Files:**
- Modify: `backend/app/gameplay/governed_contract_catalog.py`
- Modify: `backend/app/gameplay/economy_runtime.py`
- Create: `backend/tests/test_inf2am_descriptor_binding.py`

- [ ] Add one immutable descriptor/catalog row for the exact package, declaration, binding, policy, source mode, parties, currency, event vector, privacy, receipt, replay, and lifecycle.
- [ ] Resolve exactly one read-only binding at activation and persist package/content/declaration/descriptor/active-set pins.
- [ ] Write RED tests for unknown/inactive package, digest mismatch, multiple/unadmitted binding, stale/private/mismatched custody, account conflict, insufficient balance, duplicate, and revision conflict.
- [ ] Keep provider/receiver and accounts owner-derived; no caller-selected authority coordinates.

### Task 5: Implement and verify the Economy outcome

**Files:**
- Modify: `backend/app/gameplay/economy_runtime.py`
- Create: `scripts/verification/verify_inf2am_reinforced_mill_flour_output.py`
- Create: `.harness/profiles/inf2am-reinforced-mill-flour-output.json`

- [ ] Append the fixed Economy vector through `GameplayCommandEnvelope -> SettlementPlan -> append_batch()` after revalidating the Inventory source.
- [ ] Return only an append-derived Economy receipt; keep the Inventory receipt separate.
- [ ] Verify full/checkpoint-tail Economy replay, privacy, revision pins, idempotency, zero-write rejection, terminal/reversal/compensation semantics, and no generic payment or market behavior.

### Task 6: Synchronize evidence and close the row

**Files:**
- Update: INF-2 README, mainline completion audit, remaining-scope matrix, blocker taxonomy, and continuation checkpoint

- [ ] Record the decision trace, rejected shortcuts, exact source/owner/outcome tuple, tests, Harness report, and replay evidence.
- [ ] Mark only INF-2AM as `implemented narrow vertical` after all evidence is green.
- [ ] Preserve Slot C's blocker if any gate fails; never mark August INF A-D complete from this row alone.

## Current Gate

Tasks 2-6 are intentionally blocked. The current repository lacks the exact
business literals listed in Task 1; no runtime, package, catalog, tests, or
Harness changes are authorized by this plan until that gate is closed.
