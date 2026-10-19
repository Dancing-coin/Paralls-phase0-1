# Character Owner Target Projection Implementation Plan

**Goal:** Fill R05's missing production target input using received private visibility and existing ESM policy.

**Architecture:** L1 freezes explicit visibility, the existing ESM instance projects only registered action eligibility, and the existing L3 compiler expands only supported action+target pairs. No new authority or planner.

**Tech Stack:** Existing Python, Pydantic, ESM, pytest and Harness.

**Spec:** `docs/superpowers/specs/2026-10-20-character-owner-target-projection-design.md`.

## Task 1: Private production target input

Files: `backend/app/models/character_agent_runtime.py`, `backend/app/character_agent/reasoning/l1_perception.py`, `backend/app/character_agent/runtime/runtime_loop.py`, `backend/app/services/esm_service.py`, `backend/app/character_agent/planning/l3_planner.py`, `backend/app/main.py`; tests `backend/tests/test_character_owner_target_projection.py`.

- [ ] Write RED for private received target→ESM projection→typed roundtrip→actual `_candidate_records` and `CandidateCompiler`; block unsupported actions, unknown targets and explicit empty visibility.
- [ ] Add latest visual identity/source fields and optional trusted resolver to L1/runtime. Clear visibility on scope change; filter resolver output to private visible refs; refresh on frozen Siming snapshot copy.
- [ ] Add ESM read-only `project_character_targets(snapshot)` for registered inspect policies, state/owner eligibility and explicit source digest; wire production reset immediately after the current ESM instance is created. Verify two real lifecycle starts bind distinct owners and each observes its own state changes.
- [ ] Restrict L3 records by `supported_intents`, preserve digest pins, and distinguish empty visibility from unspecified visibility.
- [ ] Run focused target/L1/candidate/L4 contract tests and the smallest applicable existing Harness; production composition evidence must use the real backend fixture, not only direct constructor tests.
- [ ] Review, update unified matrix precisely, and commit this bounded implementation. R05 overall remains partial until remaining domain actions and current owner revalidation are integrated.

## Constraints and review focus

No inferred target from attention/current player; no client-provided owner route or success; no cross-actor/scene catalog leak; no silent empty-visible bypass. The digest must change when target state/owner/policy changes. Candidate eligibility is not domain execution; range and owner submission remain independently checked. Preserve unrelated dirty changes and historical fixtures. Godot and models are not launched in this task.
