# INF-1X General Semantic Rule Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a closed, replayable semantic rule vocabulary only for rows with a named domain owner.

**Admission status (2026-08-12):** The only documented
row was the INF-1R one-shot production-finish mapping. INF-1J later admitted
one separately closed Economy wage-obligation row, not a generic RuleSet
handler. No generic durable lifecycle,
retry, cancellation, transformation, or compensation row has a named owner
event and INF-2X registration. Do not add general RuleSet/lifecycle behavior
that implies an unregistered target owner. Resume only after an owner matrix
with stream, event family, revision, scoped reader, and zero-write condition is
approved for each claimed row. The one-shot production row is now admitted and
verified; no durable row is admitted.

**Architecture:** Extend `backend/app/gameplay/semantic_registry.py` and `semantic_authority.py` as pure, revision-pinned evaluation; route accepted results through the existing owner fragment and event-store spine. No semantic module writes target truth.

**Tech Stack:** Python, Pydantic models, `GameplayEventStore`, existing replay/projectors, pytest, Harness.

---

### Task 1: Lock the rule and owner-matrix contract

**Files:** Modify `backend/app/gameplay/semantic_registry.py`; create `backend/tests/test_infra_general_semantic_rule.py`; update INF-1 design.

- [ ] Write failing tests that reject unknown phase/conflict/handler/target rows, ambiguous owners, altered idempotency reuse and an unregistered state lifecycle before the event store is called.
- [ ] Add frozen `RuleSetRevision`, `EffectDefinition`, `ResistanceProfile`, `StateLifecyclePolicy` and `OwnerMapping` models with digest, revision and declared owner/stream/event fields.
- [ ] Register only the existing production-finish mapping to `ConstructionProductionAuthority.build_due_finish_fragment`; assert an economy/survival/ecology target cannot be registered without an exact builder map. INF-1J subsequently adds one exact Economy builder map with separate focused evidence; all other targets remain rejected.
- [ ] Run `python -m pytest backend/tests/test_infra_general_semantic_rule.py -q` and confirm the contract tests pass.

### Task 2: Implement deterministic pure evaluation

**Files:** Modify `backend/app/gameplay/semantic_registry.py`; modify focused test.

- [ ] Add phase execution in the fixed order, stable same-phase ordering, fixed-precision numeric conversion, closed conflict resolution, visited tuple tracking and depth/per-target/per-chain budgets.
- [ ] Test each conflict policy, resistance attenuation, suppression, cycle detection and budget truncation without an authority/event store dependency.
- [ ] Emit a redaction-ready trace and proposal only; assert evaluator errors contain no events or append side effect.

### Task 3: Bind state lifecycle to named owners

**Files:** Modify `backend/app/gameplay/semantic_authority.py`; modify `backend/app/gameplay/construction_production_runtime.py`; modify focused test.

- [ ] Convert the only registered typed proposal into `build_due_finish_fragment` and assemble it using the existing `SettlementPlan`/`append_batch` path.
- [ ] Add tests for target revision conflict, owner decline and fragment overlap with unchanged stream heads/event count.
- [ ] For durable/expiry policies, reject unless an INF-2X registered obligation and owner lifecycle event exist; test that projection reads never refresh/expire state.

### Task 4: Projection, replay and evidence

**Files:** Modify the existing causal/scoped projection and replay reader only as needed; create `.harness/profiles/infra-general-semantic-rule.json`; create its verifier/report.

- [ ] Add explicit versioned reader/upcaster coverage for correlation payload fields and prove full versus checkpoint-tail event/projection/trace equality.
- [ ] Test authority, actor, public and creator trace filtering independently from settlement input.
- [ ] Add one Harness assertion per item named in the design, then run focused tests, the profile, full pytest, and `git diff --check`.
- [ ] Update the August status, formal spec, plan and evidence report with each enabled owner row and all still-rejected rows.

## Delivered scope

- [x] Added immutable closed RuleSet/effect/owner/lifecycle contracts and
  admitted the production-finish mapping. INF-1J separately adds the exact
  Economy wage-obligation row without widening RuleSet handling.
- [x] Added deterministic phase/priority/specificity conflict decisions,
  fixed-point resistance attenuation, and trace redaction without a store
  dependency.
- [x] Bound only the registered row to the existing production fragment and
  rejected altered idempotency reuse before append.
- [x] Rejected every scheduled lifecycle registration except the separately
  documented Survival `state:cold@1` owner/event/fragment row; retry and
  compensation remain rejected.
- [x] Added `infra-general-semantic-rule`, with independent evidence for each
  claimed capability, and synchronized status documents.
