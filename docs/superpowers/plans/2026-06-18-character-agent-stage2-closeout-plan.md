# CharacterAgent Stage 2 Closeout Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the current CharacterAgent Stage 2 convergence gaps without broadening provider scope, request surface, or actor-runtime contracts.

**Architecture:** Keep the existing single-provider `CharacterModelGateway` as the only live dialogue-generation path, promote current timeline/memory JSON seams into the existing durability layer without changing retrieval bundle shape, thin compatibility bridges around `CharacterGoalCommand` and actor ingress rather than adding new contracts, and explicitly quarantine or repair `verify_l1_runtime_edges.py` based on current runtime truth.

**Tech Stack:** Python 3.11+, pytest, existing FastAPI backend runtime, current Godot shared actor contract, harness verification scripts.

---

## Scope

- Merge dialogue generation into the existing `CharacterModelGateway` main endpoint.
- Preserve the current local fallback path.
- Do not add providers, provider registry entries, API keys, env vars, or request classes.
- Promote CharacterAgent timeline and memory persistence to the current durability path.
- Preserve retrieval bundle output shape.
- Reduce `L4Adapter` compatibility churn without reverting from the `character_agent_output(command_type)` path.
- Continue actor Stage 2 seam tightening only through `CharacterIntentFrame` and `CharacterPresentationInput`.
- Repair `verify_l1_runtime_edges.py` or isolate it with explicit truth if runtime verification cannot support the stronger claim.

## Task 1: Baseline Mapping

**Files:**
- Read: `backend/app/**/character*`
- Read: `backend/tests/test_character_agent_*`
- Read: `scripts/verification/verify_l1_runtime_edges.py`
- Read: `scripts/character/CharacterPresentationInput.gd`
- Read: `scripts/character/CharacterRuntimeState.gd`
- Read: `scripts/character/CharacterReplica.gd`

- [ ] Map the current gateway, fallback, persistence, and L4 adapter paths.
- [ ] Identify touched focused test files before implementation.
- [ ] Record whether `verify_l1_runtime_edges.py` currently fails because of product drift or verifier drift.

## Task 2: Dialogue Path Unification

**Files:**
- Modify: `backend/app/...CharacterModelGateway...`
- Modify: `backend/app/...character agent runtime / dialogue orchestration...`
- Test: `backend/tests/test_character_agent_*`

- [ ] Write or update a failing focused test proving dialogue generation routes through `CharacterModelGateway`.
- [ ] Verify the test fails for the expected reason.
- [ ] Implement the minimal routing change.
- [ ] Keep local fallback behavior intact.
- [ ] Run focused tests for the gateway/dialogue area.

## Task 3: Durability Path Promotion

**Files:**
- Modify: `backend/app/character_agent/storage/**`
- Modify: `backend/app/character_agent/runtime/**`
- Test: `backend/tests/test_character_agent_memory_writeback.py`

- [ ] Write or update a failing test proving timeline and memory persistence use the formal durability path.
- [ ] Verify retrieval bundle shape does not change.
- [ ] Implement the minimal persistence move.
- [ ] Run focused persistence tests.

## Task 4: L4 Compatibility Thinning

**Files:**
- Modify: `backend/app/character_agent/execution/l4_adapter.py`
- Modify: related runtime execution files
- Test: `backend/tests/test_character_agent_l4_execution.py`

- [ ] Write or update a failing test proving redundant `CharacterGoalCommand -> character_agent_execution` reconstruction is reduced.
- [ ] Preserve the current `character_agent_output(command_type)` main path.
- [ ] Keep the bridge surface thin and compatibility-only.
- [ ] Run focused L4 execution tests.

## Task 5: Actor Ingress Tightening

**Files:**
- Modify: `scripts/character/CharacterPresentationInput.gd`
- Modify: `scripts/character/CharacterRuntimeState.gd`
- Modify: `scripts/character/CharacterReplica.gd`
- Test: existing actor seam static/runtime tests

- [ ] Write or update a failing focused test for the shared ingress seams if coverage is missing.
- [ ] Tighten only `CharacterIntentFrame` and `CharacterPresentationInput` seams.
- [ ] Avoid introducing parallel actor ingress contracts.
- [ ] Run focused actor seam tests.

## Task 6: `verify_l1_runtime_edges.py` Resolution

**Files:**
- Modify if needed: `scripts/verification/verify_l1_runtime_edges.py`
- Modify if needed: adjacent verification helpers/tests

- [ ] Reproduce the verifier failure or mismatch.
- [ ] Decide whether the script should be repaired to current runtime truth or explicitly isolated from unsupported claims.
- [ ] Add or update focused tests around the verifier behavior when practical.
- [ ] Run `python scripts/verification/verify_l1_runtime_edges.py`.

## Verification Order

1. Focused pytest for each touched slice.
2. `python -m pytest -q`
3. `python scripts/verification/harness.py --profile docs`
4. `python scripts/verification/harness.py --profile character-agent-execution`
5. `python scripts/verification/harness.py --profile phase0`
6. `python scripts/verification/harness.py --profile phase1-slice`
7. `python scripts/verification/verify_l1_runtime_edges.py`

## Constraints

- No new provider integrations.
- No provider registry expansion.
- No new API key or env wiring.
- No new request classes.
- Use `apply_patch` for file edits only.
- Do not claim Stage B or full single-path `L4 -> CharacterActor` completion ahead of evidence.
