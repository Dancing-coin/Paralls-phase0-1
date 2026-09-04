# Gameplay Creator Skill and Siming Director Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn natural-language game briefs into governed gameplay drafts and let Siming select admitted variants without bypassing world owners.

**Architecture:** Build on Manifest v3/platform 2.0, existing package admission, action graph, owner adapters, projections and replay. Keep authoring/preview state separate from production events and keep Siming proposal-only.

**Tech Stack:** Python/Pydantic, existing patch/package runtime, replay/Harness, Godot projection and TTS paths.

**Spec:** `docs/superpowers/specs/world-character-siming-authority-mainline/2026-09-04-gameplay-creator-siming-director-extension-design.md`

---

### Task 1: Typed authoring brief and compilation result

**Files:**
- Create: `backend/app/gameplay/creator_authoring_contract.py`
- Test: `backend/tests/test_creator_authoring_contract.py`

- [ ] Add strict `GameBrief`, `GameplayAuthoringBundle`, `ExtensionPacket` and `AuthoringValidationResult` models.
- [ ] Compile only references to existing families and return explicit missing-contract entries for new facts/owners/events.
- [ ] Test existing-family compilation, unknown family, missing owner contract, duplicate refs, privacy mismatch and no production-store writes.

### Task 2: Creator Skill workflow and draft artifacts

**Files:**
- Create: `skills/paralls-gameplay-creator/SKILL.md`
- Create: `skills/paralls-gameplay-creator/references/family-map.md`
- Create: `skills/paralls-gameplay-creator/references/authoring-boundaries.md`
- Test: `backend/tests/test_creator_skill_artifacts.py`

- [ ] Document the brief-to-bundle workflow, family selection, owner boundaries, action graph authoring and required verification outputs.
- [ ] Ensure the skill never claims freeze/admission from a draft and points to exact repository validators.
- [ ] Test that generated artifact manifests contain no placeholders, arbitrary code hooks or caller-selected authority coordinates.

### Task 3: Siming Director proposal and safe-boundary selection

**Files:**
- Create: `backend/app/gameplay/siming_director_runtime.py`
- Test: `backend/tests/test_siming_director_runtime.py`

- [ ] Add strict `SimingDirectorProposal` and a proposal validator consuming only scope-filtered committed signals.
- [ ] Revalidate candidate package/content, adjustment bounds, policy, expiry and revision before returning an owner intent; do not append director facts directly.
- [ ] Test admitted variant selection, repeated-failure assist, private/stale/unadmitted rejection, duplicate/changed duplicate and deterministic seed reuse.

### Task 4: UI/voice transition projection

**Files:**
- Modify: `backend/app/gameplay/bakery_mirror_source.py` or the shared projection surface only through an additive generic transition view
- Modify: `scripts/interaction/GameplayMirrorBridge.gd`
- Test: `backend/tests/test_director_transition_projection.py`

- [ ] Project preparing/loading/ready/active/suspending/returned/rejected from committed transition facts.
- [ ] Route revisioned voice templates through the existing TTS path; UI and voice must not create facts.
- [ ] Test privacy, rejection cleanup, replay equality and fallback on unavailable package.

### Task 5: Preview, admission and marketplace handoff boundaries

**Files:**
- Create: `scripts/verification/verify_creator_director_extension.py`
- Create: `.harness/profiles/gameplay-creator-siming-director-extension.json`
- Test: `backend/tests/test_creator_director_replay.py`

- [ ] Verify draft preview is isolated from production append and that only explicit package admission can create an active binding.
- [ ] Verify director proposals replay identically and do not create accounts, inventory, scores, relationships or world facts without target-owner acceptance.
- [ ] Add marketplace demand/delivery records as non-gameplay artifacts; defer pricing/revenue settlement to a separately governed platform service.
- [ ] Run focused tests, replay, Harness, docs checks and `git diff --check`.

## Rollback and future seams

- Discard draft bundles without touching production events.
- Revoke a director proposal before activation; retain the proposal audit.
- Retire a package for new sessions while preserving readers for existing pins.
- Future higher-frequency director or creator automation must consume the same
  proposal/admission contracts and cannot add a second world runtime.
