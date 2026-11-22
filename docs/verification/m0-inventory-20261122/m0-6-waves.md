# M0-6 Candidate waves

- Code scan SHA: `0e67fe812280e7e518c84c27653153f5a69f2330`; latest coordination baseline checked was `0ecf65aae1698fabba06f06491f7800abdc1728a` and differs only in coordination docs.
- Inputs: M0-1 runtime/importer candidates, M0-2 helper adoption, M0-4 app importer AST scan; read-only comparison with migration plan lines 73-90.
- Scan time: 2026-11-22 Asia/Shanghai.
- Conclusion level: static-only, proposed inputs for project-lead review. No wave is validated or accepted.
- Regression node counts: not collected. Test collection/selection is disallowed by this task.

The importer counts below use distinct importer files under `backend/app`, excluding tests. Repeated mechanism count is the number of `replay_duplicate` / `rejected_result` helpers adopted by the domain runtime, not an estimate of every duplicated rule. “Hubs” are delayed according to the supplied protocol's common-boundary list and the formal Owner map. Event importers and runtime callers still need human review.

| Wave | Domain | Importers | Repeated mechanism adoption | Regression surface (directed test nodes) | Hub | Mechanism dependencies |
|---|---|---:|---:|---|---|---|
| 1 | frost_farm, economy_platform, soul_effect, reference_data, government_treasury, gift, land_right, life_state, action_consequence, ecology_platform, inventory_platform, civilization_capability, bakery_reference, ecology, soul_fact, daily_rhythm, soul, action_window | 0-3 each | generally 0-1; debt/contract excluded | not counted | no, candidate | Bond for `land_right`; Pool for resource facts; Process for multi-event workflows; read_as remains a later requirement |
| 2 | survival, ability, modifier, organization_government_social_platform | 4-5 each | 0-1 each; helper use is per runtime in M0-2 | not counted | no, candidate | Pool, Process; read_as for subject-facing reads; L5 only where authored workflow is required |
| 3 | debt, construction_production, econ1_economy, ownership | 5-9 each | debt/ownership adopt replay; construction/econ1 vary | not counted | debt is Owner-linked to Economy / Market; ownership has Bond work assigned to A | Bond, Process, Pool; debt waits for Economy hub prerequisites; S-8 contract facts are not included |
| 4 | patch_runtime, resource_body_runtime, organization_government_runtime, economy_runtime, inventory_runtime | 15-21 for these targets in current AST; plan's old counts differ | economy adopts rejection helper; resource/other local variation | not counted | yes | Pool, Holdings, Place, Process, read_as, L5 as required; enter after earlier wave evidence |
| unassigned | contract | 7 | `replay_duplicate` + `rejected_result` | not counted | cross-domain fan-out | S-8 sets a fact-domain split; concrete split list remains pending. The candidate Owners are not all in `REGISTERED_OWNER_IDS`, so no implementation wave or rule package is assigned here |
| unassigned | ownership | 9 | `replay_duplicate` + `rejected_result` | not counted | no by current import count, but Bond is mechanism-owned by A | Bond is in progress on mechanism line; domain wave placement requires A's delivery state |

The supplied plan's draft groups some domains differently and uses G3 branch `imported_by` counts. Current AST numbers must be used when revising that plan. `debt` is retained in wave 3 per the explicit task correction because its formal Owner candidate is `Economy / Market`, and that Owner's runtime is a shared hub. `contract` remains unassigned because S-8's concrete fact split remains pending and the candidate Owners are not all registered. Sorting of the non-hub groups is tentative because importer counts do not measure command/event cross-domain fan-out or regression node counts.
