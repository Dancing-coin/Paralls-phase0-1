# SGC-4 PresentationView Projection Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task after an owner event family and asset manifest are approved.

**Goal:** Produce a deterministic scoped semantic view for existing local presentation.

**Spec:** `docs/superpowers/specs/world-character-siming-authority-mainline/siming-group-world-formalization/04-sgc-4-presentation-view-contract.md`

**Prerequisite:** One owner event family, scoped projection and published asset manifest.

### Task 0: Presentation source gate

**Files:** `backend/app/world_runtime/projection.py`, `backend/app/gameplay/godot_mirror_projection.py`, published manifest record, `.harness/verification/`

- [ ] Record the single owner event family, source scope, manifest revision and mapping revision.
- [ ] Confirm renderer feedback enters an existing evidence/candidate path only; otherwise stop with `owner-contract blocked`.
- [ ] Record the semantic layer privacy policy and aggregation threshold before changing a model.

### Task 1: Freeze view schema and RED tests

**Files:** `backend/app/models/presentation_view.py` (Create), `backend/app/contracts/l1/presentation_command.py` (only if an existing command must carry a view ref), `backend/tests/test_sgc_presentation_view_contract.py`

- [ ] Define a frozen `PresentationView` model in `backend/app/models/presentation_view.py` with basis vector, scope digest, manifest/mapping revisions, layer metadata and fallbacks; do not make `PresentationCommand` a truth model.
- [ ] Write RED tests for private source, identity leakage, aggregation threshold, revision mismatch and renderer feedback.
- [ ] Run the focused test file and retain RED evidence.

### Task 2: Implement one pure projection

**Files:** `backend/app/models/presentation_view.py`, `backend/app/world_runtime/projection.py`, `backend/app/gameplay/godot_mirror_projection.py`

- [ ] Map the admitted owner projection to one semantic layer set with deterministic digest.
- [ ] Separate manifest-bound semantic output from device-local LOD and asset fallback.
- [ ] Route Godot observations only through existing evidence/candidate ingress; do not append from renderer.

### Task 3: Replay/privacy Harness closure

**Files:** `backend/tests/test_sgc_presentation_view_contract.py`, `scripts/verification/harness.py`, `scripts/verification/registry.py`, `.harness/profiles/sgc-4-presentation-view.json`, `.harness/rules/sgc-4-presentation-view.json`, `docs/harness.md`

- [ ] Prove privacy, fallback, zero-write feedback, receipt visibility and full/tail replay equivalence.
- [ ] Register and run the selector named `sgc-4-presentation-view` after focused pytest.
- [ ] Save semantic digests, redaction, fallback and full/tail replay evidence under `.harness/verification/sgc-4/`.
- [ ] Update the matching August/spec/plan/checkpoint records.
