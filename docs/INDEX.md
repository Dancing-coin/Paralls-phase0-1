# Paralls Phase 0 Repository Index

This is the agent-readable map for the runnable Paralls Phase 0 validation demo.

## Start Here

- `AGENTS.md`: operating contract, mission, boundaries, verification rules, and non-goals.
- `docs/ai-engineering-workflow.md`: OpenSpec, Superpowers, Harness, Goal, and native subagent workflow.
- `PHASE0_README.md`: short workspace summary and verification entry points.
- `docs/harness.md`: Harness Engineering command surface for repeatable verification.
- `docs/demo-script.md`: expected demo beats and observable proof path.

## Active Design And Plans

- `docs/superpowers/specs/2026-06-15-character-actor-architecture-optimization-design.md`
- `docs/superpowers/plans/2026-06-15-character-actor-architecture-optimization-implementation-plan.md`
- `docs/superpowers/plans/2026-06-15-character-actor-near-term-cleanup-implementation-plan.md`
- `docs/superpowers/plans/2026-06-15-character-actor-final-convergence-implementation-plan.md`
- `docs/superpowers/specs/2026-06-15-full-character-agent-runtime-with-llm-design.md`
- `docs/superpowers/plans/2026-06-15-full-character-agent-runtime-with-llm-implementation-plan.md`
- `docs/superpowers/specs/2026-06-16-character-model-router-openai-compatible-multiprovider-design.md`
- `docs/superpowers/plans/2026-06-16-character-model-router-openai-compatible-multiprovider-implementation-plan.md`
- `docs/superpowers/specs/2026-06-12-character-actor-unification-design.md`
- `docs/superpowers/specs/2026-06-12-character-actor-runtime-boundary-design.md`
- `docs/superpowers/specs/2026-06-12-character-actor-control-and-locomotion-design.md`
- `docs/superpowers/plans/2026-06-12-character-actor-unification-implementation-plan.md`
- `docs/superpowers/plans/2026-06-12-character-actor-runtime-boundary-implementation-plan.md`
- `docs/superpowers/plans/2026-06-12-character-actor-control-and-locomotion-implementation-plan.md`
- `docs/superpowers/specs/2026-06-11-character-agent-minimal-runtime-slice-design.md`
- `docs/superpowers/plans/2026-06-11-character-agent-minimal-runtime-slice-implementation-plan.md`
- `docs/superpowers/specs/2026-06-03-harness-engineering-design.md`
- `docs/superpowers/plans/2026-06-03-harness-engineering-implementation-plan.md`
- `docs/superpowers/specs/2026-06-10-ai-engineering-workflow-integration-design.md`
- `docs/superpowers/plans/2026-06-10-ai-engineering-workflow-integration-implementation-plan.md`
- `docs/superpowers/plans/2026-06-10-siming-event-bus-final-merge-retrospective.md`
- `docs/superpowers/specs/2026-06-02-phase05-runtime-alignment-design.md`
- `docs/superpowers/plans/2026-06-02-phase05-runtime-alignment-implementation-plan.md`

## Runtime Areas

- `backend/`: FastAPI authority backend, Pydantic models, services, and pytest coverage.
- `docs/character/`: character architecture, control chain, asset integration, and future action asset interface docs.
- `scripts/autoload/`: Godot backend bridge and local presentation bus.
- `scripts/phase0/`: Phase 0 demo orchestration.
- `scripts/player/`: player intent and embodiment path.
- `scripts/visual/`: visual fact emission path.
- `scripts/verification/`: local verification and harness scripts.
- `scenes/phase0/`: Phase 0 Godot scenes.
- `.harness/profiles/`: versioned harness profile manifests.
- `.harness/rules/`: versioned rule-to-evidence manifests.
- `.harness/references/`: adapted external Harness Engineering reference taxonomies.
- `.harness/templates/`: starter manifests for future formal module profiles.
- `.harness/ci/`: release gate metadata.
- `.harness/features.json`: harness feature ledger with evidence.
- `.harness/retention-policy.json`: generated evidence retention and diff policy.
- `.github/workflows/harness.yml`: CI entry point for full harness execution.

## Verification Profiles

Use `python scripts/verification/harness.py --profile <name>`.

- `docs`: documentation freshness and index checks.
- `boundaries`: static Harness Engineering boundary checks.
- `drift`: cleanup and local artifact drift checks.
- `backend-contract`: backend protocol model and WebSocket contract checks.
- `godot-project`: Godot main scene, autoload, and `res://` static integrity checks.
- `release-gate`: CI workflow and release gate metadata checks.
- `harness-lifecycle`: lifecycle ledger, local CI, retention, templates, quality, and handoff checks.
- `change-lifecycle`: OpenSpec, Superpowers, Harness, Goal, and native subagent workflow checks.
- `harness-reference`: adapted external Harness Engineering taxonomy, template, and reference coverage checks.
- `phase0`: strict Phase 0 backend plus Godot runtime validation.
- `phase1-slice`: current Phase1-shaped runtime slice validation.
- `all`: runs all profiles in order.

Reports are written under `.harness/verification/`.

Harness profile and rule manifests are project inputs:

- `.harness/profiles/`: profile order, script dispatch, and Godot requirements.
- `.harness/rules/`: mechanical invariant manifests for docs, boundaries, and drift checks.
- `.harness/references/`: reference taxonomies mapped to current project artifacts.

Run-id evidence archives are written under `.harness/verification/runs/`.
Latest run manifest, baseline, and diff artifacts are written under `.harness/verification/`.

## Harness Lifecycle Docs

- `docs/harness-architecture.md`
- `docs/ai-engineering-workflow.md`
- `docs/harness-reliability.md`
- `.harness/clean-state-checklist.md`
- `.harness/session-handoff.md`
- `.harness/evaluator-rubric.md`
- `.harness/quality-document.md`
- `.harness/templates/PLAN.md`
- `.harness/templates/IMPLEMENT.md`
- `.harness/templates/HARNESS_CHECKLIST.md`
- `.harness/templates/AGENTS.md`

## Reference Material

- `docs/phase1/`
- `docs/reference/phase1-event-bus/`
- `docs/reference/phase1-character-agent/`
- `docs/reference/phase1-siming/`

## Character Docs

- `docs/character/character-actor-architecture.md`
- `docs/character/character-control-chain.md`
- `docs/character/character-asset-integration.md`
- `docs/character/character-action-asset-interface.md`
- `docs/character/character-actor-migration-status.md`
- `docs/character/character-actor-final-convergence-target.md`
- `docs/character/character-actor-final-convergence-gap-report.md`
- `docs/character/character-debug-and-verification.md`

Reference docs are supporting context. Current task truth still follows `AGENTS.md` and active specs/plans.
