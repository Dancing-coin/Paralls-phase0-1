# M6-5 Production Assembly Static Audit

## Scope

Read-only audit at A branch commit `195c2795d` of the M6-5 runtime assembly, trusted command outputs, reaction handlers, package loading, dispatch callers, and physical-input recovery. No source code or runtime behavior was changed by this audit, and no tests were run for it.

## Production Call Graph

| Concern | Evidence | Finding |
|---|---|---|
| Runtime construction | `backend/app/main.py:2002` | `build_m6_5_siege_runtime` is called during runtime assembly. |
| Trusted outputs | `backend/app/main.py:1994-1998` | Main registers outputs for `morale.refold`, `presence.reevaluate`, and `information.update_knowledge`. |
| Transaction dispatch | `backend/app/main.py:2230` | Committed transactions are sent to `m6_5_siege_runtime.after_transaction_dispatched`. |
| Morale handler | `backend/app/gameplay/m6_5_siege_runtime.py:347-349` | `morale.refold` is handled by `MoraleRefoldAuthority.refold_after_casualty`. |
| Presence handler | `backend/app/gameplay/m6_5_siege_runtime.py:350-355` | `presence.reevaluate` is handled by `PlacePassabilityAuthority.commit_assessment`. |
| Information handler | `backend/app/gameplay/m6_5_siege_runtime.py:357-364` | `information.update_knowledge` consumes committed delivery and authoritative world tick. |
| Conditions and packs | `backend/app/gameplay/m6_5_siege_runtime.py:320-341`, `367-371` | M6-5 and Information packs are loaded or resolved, and `facility_breach@1` is bound to `_is_breach_entry`. |
| Physical-input recovery | `backend/app/gameplay/m6_5_siege_runtime.py:213-269` | Startup scans durable signed Gate and Presence inputs and reconciles Facility/Place owner writes. |
| Obligation projection | `backend/app/gameplay/m6_5_siege_runtime.py:168-170` | `impact_gate_obligations()` rebuilds obligation state from stored evidence. |

## Remaining Runtime Gap

`impact_gate_obligations()` exposes a rebuilt projection, but no production caller dispatches or settles the formal durable obligation lifecycle. The existing recovery method reconciles signed physical inputs and Owner writes only. Therefore M6-5 production assembly for Gateway/L5, Morale/Presence/Information handlers, trusted outputs, package conditions, and physical-input recovery exists; formal `impact_gate` obligation execution and its restart recovery remain unimplemented. This audit does not establish production deployment, authoritative Gate values, live UE transport, or a complete siege run.

## Conclusion

Static-only. No test or runtime result is claimed.

## Current-tip correction at `38f88408`

The prior gap statement overstated the missing recovery path. `backend/app/main.py:2396` invokes `m6_5_siege_runtime.recover_physical_input_obligations()` during startup. `backend/app/gameplay/m6_5_siege_runtime.py:222-260` replays durable signed Gate and Presence inputs through the existing Owner authorities and dispatches the layered Gate transaction. `backend/tests/test_facility_gate_layered_runtime.py` includes a durable-store restart case that verifies receipt replay and no repeated damage, documented in `docs/verification/m6-5-obligation-recovery-20261124.md`.

The remaining gap is the formal obligation contract, not absence of restart recovery. `backend/app/gameplay/impact_gate_obligation.py:16-23` currently exposes `obligation_id`, `gate_ref`, `status`, and step receipt IDs. It does not expose `pipeline_ref`, completed/pending step sets, pending reason, responsible Owner refs, recovery action, or a deadline tick. The existing event-derived projection and startup reconciliation avoid a separate workflow ledger, but they do not yet provide those required lifecycle fields or classify unresolved work. The M6-5 runtime also does not consume a compiled `Pipeline` for this flow.

This correction is static-only at A tip `38f88408`. No code or tests changed in this correction. A prior exact-slice test result remains in the linked recovery evidence and is not presented as a rerun at this tip.

## Exact-tip recovery verification at `9b77738d`

- Python `3.12.2`; SQLite `3.43.1`; `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`; `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- Command: Python 3.12.2 `pytest.main` with `-q -p no:cacheprovider --basetemp F:\paralls-verification\thread-a\m6-5-obligation-current-tip-20261126-03\pytest-tmp backend/tests/test_m6_5_siege_runtime.py backend/tests/test_facility_gate_layered_runtime.py`.
- Result: `51 passed, 6 warnings in 1.59s`, exit 0. This includes the durable layered-impact restart recovery test.
- Raw output: `F:\paralls-verification\thread-a\m6-5-obligation-current-tip-20261126-03\pytest.log`. Temporary files are under the same F-drive run directory.
- Frozen selections and the full backend suite were not run. Production server startup, Gate values, UE transport, and a complete siege session remain unverified.

## Exact-tip documentation follow-up at `f9ed782d`

- The documentation-only follow-up did not change runtime source files. At exact tip `f9ed782d690f4796dbc1ae517bbc105fa8fddbbe`, `test_m6_5_siege_runtime.py` plus `test_facility_gate_layered_runtime.py` returned `51 passed, 6 warnings in 1.96s`, exit 0.
- Python `3.12.2`, SQLite `3.43.1`, and `app.__file__` under the A worktree were verified. Raw output is `F:/paralls-verification/thread-a/m6-5-current-tip-20261126-04/pytest.log`.
- This verifies the focused recovery/runtime tests at the current documentation tip. It does not verify the missing formal obligation metadata, production deployment, Gate values, UE transport, frozen selections, or the full backend suite.

## Formal obligation shape cross-check

The external Architecture v2 settlement contract (`docs/architecture-v2/06-模型与结算/02-跨域结算.md`, lines 131-161) defines the required obligation shape as `obligation_id`, `pipeline_ref`, `completed_steps`, `pending_steps`, `pending_reason` with values `rejected | unknown | timeout | host_unavailable`, `owner_refs`, `recovery_action` with values `retry | reconcile | manual | compensate`, and `deadline_world_tick`. It also requires unknown outcomes to be checked by the original idempotency key before retry, timeout to remain unknown without automatic rollback, and compensation to append events.

This narrows the implementation gap. `impact_gate_obligation.py` still lacks all fields beyond `obligation_id`, `gate_ref`, `status`, and receipt IDs. The formal source does not specify the M6-5 pipeline reference, responsible Owner mapping, or deadline source. Those inputs remain required before adding the projection fields. No placeholder deadline or inferred pipeline was added.

## Exact-tip obligation metadata implementation at `HEAD`

- `ImpactGateObligation` now exposes the formal metadata as a rebuildable projection. `pipeline_ref` is the explicitly documented `impact_gate` pipeline. `completed_steps` and `pending_steps` derive from the existing four receipt groups. Pending `facility` work maps to `Production`; pending `presence_input` or `passability` maps to `Presence`. Open obligations use `pending_reason="unknown"` and `recovery_action="reconcile"`. Settled obligations have no pending reason, Owner refs, or recovery action.
- `deadline_world_tick` remains `None` because the formal sources do not define a M6-5 deadline policy or authoritative tick source. No deadline was inferred from physics ticks, event sequence, or the demo profile.
- Regression assertions were added to `backend/tests/test_facility_gate_layered_runtime.py`. Exact-tip focused command returned `51 passed, 6 warnings in 1.74s` at commit before this documentation update. Raw output: `F:/paralls-verification/thread-a/m6-5-obligation-metadata-full-20261126-01/pytest.log`.
- The implementation adds no persisted event or second workflow ledger. It reconstructs the metadata from existing durable receipts and preserves the existing startup recovery path. Production deployment, Gate values, UE transport, frozen selections, and full backend regression remain unverified.
- Frozen registered selections at exact tip `20c67b18` returned `selected=21 problems=0 improvements=0` for `m6-5-impact-gate-layered-execution.json` and `selected=6 problems=0 improvements=0` for `m6-5-production-wiring.json`. Raw outputs: `F:/paralls-verification/thread-a/m6-5-obligation-selection-20261126-01/impact-gate.log` and `F:/paralls-verification/thread-a/m6-5-obligation-selection-20261126-01/production-wiring.log`.
- The remaining M6-5 registered selections at exact tip returned zero differences: facility-integrity `5/0/0`, gate-profile-contract `19/0/0`, information-report-source `25/0/0`, organization-roster `3/0/0`, place-output-types `3/0/0`, and presence-passability `6/0/0`. Together with the two obligation selections, M6-5 registered coverage is `81 selected, 0 problems, 0 improvements`. Raw outputs are under `F:/paralls-verification/thread-a/m6-5-all-selections-20261126-01/`.
