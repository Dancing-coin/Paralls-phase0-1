# M0 inventory

- Code scan SHA: `0e67fe812280e7e518c84c27653153f5a69f2330`. Latest coordination-document baseline fetched during this continuation: `9b09084c5adccc2367f2d5da9f438af9d80393b4`; the task instructions and handoff were read from that commit without merging or rebasing it into this worktree.
- Scan time: 2026-11-22 19:18 Asia/Shanghai. Scope is static source and documentation inspection. No tests, test collection, runtime service, or code mutation was performed.
- Conclusion level: Python environment and registry query verified; all code relationships below are static-only; no migration acceptance is claimed.
- Python command: `$env:PYTHONPATH = Join-Path (Get-Location).Path 'backend'; & 'D:\Temp\paralls-g0-py312\Scripts\python.exe' -c "import sys, app; print(sys.version); print(app.__file__)"`
- Raw output:

  ```text
  3.12.2 (tags/v3.12.2:6abddd9, Feb  6 2024, 21:26:36) [MSC v.1937 64 bit (AMD64)]
  F:\codex-temp\paralls-v2-thread-b-debt-contract-20261121\backend\app\__init__.py
  ```

- Registry query 1: `& 'D:\Temp\paralls-g0-py312\Scripts\python.exe' -c "import sys; sys.path.insert(0,'backend'); from app.models.fact_type import FACT_TYPE_REGISTRY as R; e=sorted(set(R.event_types())); print(len(e)); print('\\n'.join(e[:20]))"`
- Raw output:

  ```text
  139
  character_behavior_event
  constraint_state_event
  conversation_resolution_event
  daily_rhythm.activity_phase_state
  daily_rhythm.fatigue_state
  daily_rhythm.need_pressure_state
  daily_rhythm.starvation_credit_state
  esm_result_event
  gameplay.character.life_state_changed
  gameplay.construction_production.construction_job_completed@1
  gameplay.construction_production.construction_job_failed@1
  gameplay.construction_production.construction_job_started@1
  gameplay.construction_production.facility_acquired
  gameplay.construction_production.facility_decommissioned
  gameplay.construction_production.facility_repair_compensated
  gameplay.construction_production.facility_repaired
  gameplay.construction_production.facility_transformed
  gameplay.construction_production.maintenance_obligation_created
  gameplay.construction_production.maintenance_state_applied
  gameplay.construction_production.maintenance_state_dispelled
  ```
- Registry query 2: `& 'D:\Temp\paralls-g0-py312\Scripts\python.exe' -c "import sys; sys.path.insert(0,'backend'); from app.models.fact_type import FACT_TYPE_REGISTRY as R; e=set(R.event_types()); xs=['gameplay.debt.claim_issued','gameplay.debt.payment_applied','gameplay.contract.record_created','gameplay.contract.service_completion_recorded','gameplay.commerce.debt_issued_settled']; print({x:x in e for x in xs})"`
- Raw output: `{'gameplay.debt.claim_issued': False, 'gameplay.debt.payment_applied': False, 'gameplay.contract.record_created': False, 'gameplay.contract.service_completion_recorded': False, 'gameplay.commerce.debt_issued_settled': False}`. This is registry membership only, not evidence of runtime projection behavior.
- Worktree check: branch `thread-b/debt-contract-20261121`, HEAD `0e67fe812280e7e518c84c27653153f5a69f2330`, clean before M0 documentation edits. The two named untracked source files were absent from the worktree. Copies already existed under `F:\paralls-verification\thread-b\m0-inputs-20261122\`; they were left in place. S-9's requested D: move was not repeated because the source paths are absent and the archived copies are already on F:.
- Read-only inventory commands and outputs are summarized in the task files below. No file was written to D:. The Python executable itself remains at the user-specified D: path.

## Files

| File | Coverage |
|---|---|
| [m0-1-runtime-owner-map.md](m0-1-runtime-owner-map.md) | Runtime/event/stream candidates, Combat fact locations, Contract fact families |
| [m0-2-mechanism-adoption.md](m0-2-mechanism-adoption.md) | Shared helpers, replay adoption, digest variants, store/checkpoint symbols, visibility literals |
| [m0-3-second-truth.md](m0-3-second-truth.md) | B0 fields, Siming subscriptions/copies, prefix routing, cross-runtime private imports |
| [m0-4-readers.md](m0-4-readers.md) | AST import/read counts and G2 inventory comparison |
| [m0-5-command-envelope.md](m0-5-command-envelope.md) | Sampled command paths against the v2 envelope document |
| [m0-6-waves.md](m0-6-waves.md) | Static wave inputs and tentative ordering table |
| [design-life-state.md](design-life-state.md) | Read-only LifeState candidate design and U6 readers |
| [design-action-consequence.md](design-action-consequence.md) | Read-only action-consequence boundary and candidate fact split |
| [design-reference-data.md](design-reference-data.md) | Read-only dataset fact and consumer design |

The M0-1 debt/contract registry spot check was corrected to use runtime event declarations in `DebtSettlementPlan._EVENT_STREAMS`, `ContractProjector._EVENT_TYPES`, and the additional Contract event emitted at `contract_runtime.py:1357`. The full query and raw output are in M0-1. This establishes registry membership only, not graph-projector delivery or application.

## Decision inputs

- S-1 Combat remains for the project lead. Multiple combat event writers exist across service and gameplay modules.
- S-2 B0 Owner mapping remains for the project lead. The six fields are represented in a hot-state store and in event-backed FactTypes, but this scan did not establish an Owner mapping or a complete write-authority path.
- S-3 Siming graph and its three local projections remain for the project lead. Main subscribes by registered FactType, while the projector still stores a current payload and the three consumers retain local state.
- S-4 Whether to validate `pinned_revisions` in Store remains for the project lead. Model shape checks exist, while no equality check against current Store heads was located in the Store append paths.
- Contract S-8 is decided to split by fact domain, without adding an Owner, in the specification (`docs/superpowers/specs/2026-11-22-architecture-v2-migration-spec.md:105`), the migration plan (`docs/superpowers/plans/2026-11-22-architecture-v2-migration.md:87`), and coordination handoff (`docs/v2-coordination/handoff.md`, project decision S-8). The plan says the concrete split list is still pending; M0-1 records the observed contract purposes and candidate fact domains as its input.
- Under AUTONOMY §5, B has no first-domain candidate that meets all three conditions: only `Credential`, `Ownership`, and `Economy / Market` are registered at `fact_type_registry.py:11`; Credential and Ownership are A-owned in `BOUNDARIES.md`; Economy / Market is a hub and debt is scheduled for wave 3. This continues M0 supplementary inventory; it does not start a domain migration.
- No stop condition requiring code changes or tests was triggered. The Owner count discrepancy remains a document finding. S-8's decision is settled, while the future implementation split remains pending its concrete list and Owner registration prerequisites.
- H-A-003 supplementary candidate designs are read-only inputs. `life_state` is the preferred next candidate only after A completes M0.5; no domain migration has started.
