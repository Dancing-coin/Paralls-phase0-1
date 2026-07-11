# Layered Character Mind Factor Plan Series

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this series plan-by-plan. Each linked plan uses checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the remaining implementation phases of `docs/superpowers/specs/2026-07-11-layered-character-mind-factor-architecture-design.md` after the Phase 1/2 shadow foundation.

**Architecture:** Keep `CharacterMindFrame` as a read model assembled from owned source stores. Projection services, affordance adapters, delta-ledger builders, writeback policy routing, and graph projection ports live under `backend/app/character_agent/mind/`; existing `L1/L2/L3/L4`, ESM, System L6, memory stores, profile truth, and social-memory ownership remain authoritative in their current boundaries.

**Tech Stack:** Python 3.13, Pydantic v2, pytest, existing `backend/app/character_agent` runtime models, no new dependencies.

---

## Coverage Answer

Status: all linked implementation plans completed and verified.

This series covers the spec's unfinished implementation phases:

- Phase 3: projection services.
- Phase 4: skill/action affordance summaries.
- Phase 5: delta ledger and writeback policy routing.
- Phase 6: optional graph-backed memory projections.

This is complete for the spec's intended implementation phases except for explicit non-goals and distant integrations:

- No graph database implementation.
- No full Character Skill System implementation.
- No final action library.
- No L2/L3 prompt-path replacement without a later explicit migration plan and parity approval.
- No ESM/System L6/Godot/Kimodo/settlement authority changes.

## Plan Order

Run these plans in order. Do not skip ahead; each plan assumes the previous plan's tests and commit are complete.

1. `docs/superpowers/plans/2026-07-11-layered-character-mind-factor-phase3-projection-services-plan.md`
2. `docs/superpowers/plans/2026-07-11-layered-character-mind-factor-phase4-affordances-plan.md`
3. `docs/superpowers/plans/2026-07-11-layered-character-mind-factor-phase5-delta-ledger-writeback-plan.md`
4. `docs/superpowers/plans/2026-07-11-layered-character-mind-factor-phase6-graph-projections-plan.md`
5. `docs/superpowers/plans/2026-07-11-layered-character-mind-factor-completion-verification-plan.md`

## Standing Constraints

- Keep `L1RuntimePerceptionBridge` as the perception bridge.
- Keep System L6 as the public authority event bridge.
- ESM does not own character cognition.
- Keep authored profile truth, runtime state, memory evidence, and long-term drift separate.
- Keep social relationship network owned by social memory; graph projection may enrich cards but must not become an external truth source.
- Do not directly wire `CharacterMindFrame` into existing L2/L3 prompt main paths in this series.
