# Layered Character Mind Factor Completion Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Document completed spec coverage and run final verification for the layered character mind factor plan series.

**Architecture:** Update status/runtime docs with the Phase 3-6 flow and run focused, runtime, docs, backend-contract, and diff/worktree checks. This plan does not introduce new runtime behavior.

**Tech Stack:** Markdown, pytest, repository harness scripts, git.

---

## Status Snapshot

Status: `implemented-and-verified-documentation-closure`.

The documentation updates described below are present in
`docs/character/character-mind-core-status.md`,
`docs/架构/运行时/模块/角色智能体.md`, and the plan series status. Current
verification evidence is summarized in
`docs/superpowers/plans/2026-07-completion-matrix.md`.

## Scope Boundary

Included:

- Documentation updates for completed Phase 3-6 coverage.
- Final focused mind-factor tests.
- Related runtime regression tests.
- Docs and backend-contract harnesses.
- `git diff --check` and clean worktree check.

Excluded:

- Source behavior changes.
- Additional architecture beyond the approved spec and plan series.

## File Structure

- `docs/character/character-mind-core-status.md`
  - Status update for projection, affordance, ledger, writeback, and graph-projection phases.
- `docs/架构/运行时/模块/角色智能体.md`
  - Runtime module flow update.
- `docs/superpowers/plans/2026-07-11-layered-character-mind-factor-plan-series.md`
  - Series coverage status if needed.

---

### Task 1: Document Completed Spec Coverage And Run Final Verification

**Files:**
- Modify: `docs/character/character-mind-core-status.md`
- Modify: `docs/架构/运行时/模块/角色智能体.md`
- Modify: `docs/superpowers/plans/2026-07-11-layered-character-mind-factor-plan-series.md`

- [ ] **Step 1: Update character mind-core status with Phase 3-6 coverage**

In `docs/character/character-mind-core-status.md`, update the `分层心智因子投影` section to include these bullets after the existing boundary list:

```markdown
后续补全阶段：

- projection services 将 profile、memory、relationship、need、dynamic state、goal、tension 和 supervision 转成只读 cards。
- affordance adapter 只暴露 skill/action/environment/equipment/physical feasibility summaries，不暴露 skill registry。
- `MindDeltaLedger` 统一包裹 L2/L3/L4/settlement/writeback 候选，但 persistence 仍由 writeback policy 和原 store 边界决定。
- graph-backed memory 只作为 memory-evidence projection，可增强 knowledge/social/higher-order reads，不成为 cognition owner。
```

- [ ] **Step 2: Update runtime module doc with completed flow**

In `docs/架构/运行时/模块/角色智能体.md`, extend the `Layered mind factor frame` section with:

````markdown
Completed flow after Phase 3-6:

```text
owned source stores
-> projection services
-> CharacterMindFrame
-> bounded L2/L3/L4/writeback views
-> MindDeltaLedger
-> writeback policy router
-> existing memory/state/goal/skill-evidence/drift boundaries
```

Graph-backed memory is optional and enters only through memory-evidence cards.
It must not replace event memory, social memory ownership, or L2/L3 cognition.
````

- [ ] **Step 3: Mark plan series completion language**

In `docs/superpowers/plans/2026-07-11-layered-character-mind-factor-plan-series.md`, add this after `## Coverage Answer` once all linked plans are complete:

```markdown
Status: all linked implementation plans completed and verified.
```

- [ ] **Step 4: Run full mind-factor tests**

Run:

```bash
pytest backend/tests/test_character_mind_frame_models.py backend/tests/test_character_mind_frame_builder.py backend/tests/test_character_mind_context_views.py backend/tests/test_character_runtime_shadow_mind_frame.py backend/tests/test_character_mind_projectors.py backend/tests/test_character_mind_affordances.py backend/tests/test_character_mind_delta_ledger.py backend/tests/test_character_mind_writeback_policy.py backend/tests/test_character_mind_graph_projection.py -v
```

Expected: PASS.

- [ ] **Step 5: Run related runtime regression tests**

Run:

```bash
pytest backend/tests/test_character_agent_runtime.py backend/tests/test_character_agent_l2_reasoning.py backend/tests/test_character_agent_l3_planning.py backend/tests/test_character_runtime_needs_affect_flow.py backend/tests/test_character_agent_cognition_writeback.py -v
```

Expected: PASS.

- [ ] **Step 6: Run docs and backend-contract harnesses**

Run:

```bash
python scripts/verification/harness.py --profile docs
python scripts/verification/harness.py --profile backend-contract
```

Expected: PASS.

- [ ] **Step 7: Run diff and worktree checks**

Run:

```bash
git diff --check
git status --short
```

Expected:

- `git diff --check` exits 0.
- `git status --short` is clean after all task commits.

- [ ] **Step 8: Commit Task 1**

```bash
git add docs/character/character-mind-core-status.md docs/架构/运行时/模块/角色智能体.md docs/superpowers/plans/2026-07-11-layered-character-mind-factor-plan-series.md
git commit -m "Document full layered mind factor coverage" -m "The plan and architecture docs now distinguish the completed shadow foundation from the added projection, affordance, ledger, writeback, and graph-projection phases needed to cover the approved spec." -m "Constraint: Documentation must preserve L1/L2/L3/L4, ESM, System L6, memory, profile, and social-memory ownership boundaries" -m "Confidence: high" -m "Scope-risk: narrow" -m "Tested: full mind-factor tests; related runtime regression tests; docs harness; backend-contract harness; git diff --check"
```
