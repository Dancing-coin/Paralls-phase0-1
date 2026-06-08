# System L1 Full Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the full `Phase 1` `System L1` domain in the current repository without collapsing it back into a monolith, while preserving the already-verified `raw_fact_event` spine and current verification harnesses.

**Architecture:** Treat `System L1` as a multi-subsystem domain: client interaction execution, spatial audio and auditory fact emission, `ESM`, visual fact system, the remaining raw sensory/state emitter classes, the `System L1 -> System L2` fact boundary, and the debug/replay/verification surface. Execute these as separate implementation plans so boundaries stay explicit and reviewable.

**Tech Stack:** Godot 4.x GDScript, Python 3.13, FastAPI backend, Pydantic models, pytest, current Godot runtime verification harnesses, main-project Phase 1 architecture docs.

---

## Status Snapshot

- Date: `2026-06-09`
- Plan status: partially executed
- Verification baseline:
  - backend full suite: green on the latest verified run
  - `verify_phase1_slice.py`: green on the latest verified run
  - `verify_phase0.py`: green on the latest verified run
  - `verify_l1_runtime_edges.py`: green on the latest verified run

## Child Plan Execution Register

| Child plan | Status | Notes |
| --- | --- | --- |
| `system-l1-client-interaction` | 已做（部分/已验证） | `focus_target_change`、`interact`、`action_request` 等真实链路已落地 |
| `system-l1-spatial-audio-auditory-facts` | 已做（已验证） | first auditory path、expanded taxonomy、explicit `L1-only` policy 已验证 |
| `system-l1-esm` | 已做（部分/已验证） | 已从最小 helper 扩到多结果/状态机/环境场 slice |
| `system-l1-visual-fact-system` | 已做（部分/已验证） | 五类 visual emitters 已显式落位 |
| `system-l1-remaining-emitter` | 已做（已验证） | shell plan 与 runtime-wired follow-on plan 都已落地并通过验证 |
| `system-l1-to-l2-interface` | 已做（最小/已验证） | 当前仍以最小桥接为主，未扩成多感官全域 |
| `system-l1-debug-replay-verification` | 已做（部分/已验证） | verification triad 与 audit 明显增强，但不是最终形态 |

## Plan Structure

This scope is too broad for one execution plan. It is intentionally decomposed into child plans:

1. `docs/superpowers/plans/2026-06-08-system-l1-client-interaction-implementation-plan.md`
2. `docs/superpowers/plans/2026-06-08-system-l1-spatial-audio-auditory-facts-implementation-plan.md`
3. `docs/superpowers/plans/2026-06-08-system-l1-esm-implementation-plan.md`
4. `docs/superpowers/plans/2026-06-08-system-l1-visual-fact-system-implementation-plan.md`
5. `docs/superpowers/plans/2026-06-08-system-l1-remaining-emitter-implementation-plan.md`
6. `docs/superpowers/plans/2026-06-08-system-l1-to-l2-interface-implementation-plan.md`
7. `docs/superpowers/plans/2026-06-08-system-l1-debug-replay-verification-implementation-plan.md`

This parent plan is the sequencing and control document.

## Domain File Map

### Existing stable base that must be preserved

- `scripts/l1/facts/FactEnvelopeBuilder.gd`
- `scripts/l1/facts/RawFactEmitter.gd`
- `scripts/l1/facts/FactDeduper.gd`
- `backend/app/models/raw_fact.py`
- `backend/app/services/fact_handlers/spatial_access_fact_handler.py`
- `scripts/phase0/MainDemoController.gd`
- `scripts/verification/verify_phase0.py`
- `scripts/verification/verify_phase1_slice.py`
- `scripts/verification/verify_l1_runtime_edges.py`

### Child plans add or expand the following families

- visual source-domain emitters
- auditory raw facts
- additional raw sensory/state emitter families
- `ESM` environment field and settlement
- `System L1 -> System L2` message seams
- replay/debug proof surfaces

## Execution Order

### Phase A: Preserve and extend the proven base

- [ ] **Step 1: Re-run the current foundation verification before any new child plan executes**

Run:

```bash
python -m pytest -v
python scripts/verification/verify_phase1_slice.py
python scripts/verification/verify_phase0.py
python scripts/verification/verify_l1_runtime_edges.py
```

Expected:

- all tests and verification reports pass before further implementation begins

- [ ] **Step 2: Execute child plans in this order**

Recommended execution order:

1. `visual-fact-system`
2. `esm`
3. `l1-to-l2-interface`
4. `spatial-audio-auditory-facts`
5. `client-interaction`
6. `remaining-emitter`
7. `debug-replay-verification`

Reason:

- visual facts and `ESM` are the two strongest existing anchors in this repo
- the `L1 -> L2` interface must stay aligned as those expand
- auditory and interaction systems should then hook into the same stable seam
- the remaining emitter classes should share the settled contract
- verification should close the loop last

### Phase B: Cross-plan verification gate

- [ ] **Step 3: After each child plan, re-run the plan’s focused tests plus the full backend suite**

Baseline backend command:

```bash
python -m pytest -v
```

- [ ] **Step 4: After every two child plans, re-run the Godot verification trio**

Run:

```bash
python scripts/verification/verify_phase1_slice.py
python scripts/verification/verify_phase0.py
python scripts/verification/verify_l1_runtime_edges.py
```

Expected:

- no regression in the current playable verification flows

## Integration Requirements Across Child Plans

- [ ] **Step 5: Preserve the shared `raw_fact_event` surface**

All child plans must keep using:

- `FactEnvelopeBuilder.gd`
- `RawFactEmitter.gd`
- backend `RawFactEvent`

No new ad hoc Godot -> backend fact send surface may be introduced.

- [ ] **Step 6: Keep `System L1` distinct from `System L2`**

Child plans may add:

- raw facts
- execution results
- local runtime state

They may not:

- push candidate compilation back into Godot
- emit role-private perceived events from Godot
- bypass `System L2` with direct character-private conclusions

- [ ] **Step 7: Keep `System L1` distinct from `Character Agent L1-L4`**

Child plans may expose better low-level facts.

They may not:

- smuggle character cognition into `System L1`
- let `ESM` or emitters produce belief, motive, or social-meaning outputs

## Final Completion Criteria For This Parent Plan

- [ ] **Step 8: Confirm every child plan has either been executed or explicitly deferred with rationale**

Produce a final matrix:

- executed
- deferred
- blocked

for each child plan.

Current register:

- executed partially:
  - `visual-fact-system`
  - `esm`
  - `l1-to-l2-interface`
  - `spatial-audio-auditory-facts`
  - `client-interaction`
  - `debug-replay-verification`
- executed:
  - `remaining-emitter`
- blocked:
  - none at the document level right now

- [ ] **Step 9: Confirm the repository still satisfies existing runtime baselines**

Required proof:

- backend full suite green
- `verify_phase0.py` green
- `verify_phase1_slice.py` green
- `verify_l1_runtime_edges.py` green

- [ ] **Step 10: Commit this parent plan only if sequencing notes changed during execution**

```bash
git add docs/superpowers/plans/2026-06-08-system-l1-full-phase1-implementation-plan.md
git commit -m "docs: sync system-l1 full phase1 execution index"
```
