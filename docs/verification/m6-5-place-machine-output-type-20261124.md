# M6-5 trusted Place machine output type

- Implementation commit: `4023c182158a7d90185b72e17acfeedf1c7d3c0f`.
- Worktree: `F:\codex-temp\paralls-v2-thread-a-bond-20261121`, branch `thread-a/ownership-bond-followup-20261121`.
- Python: `D:\Temp\paralls-g0-py312\Scripts\python.exe`, version `3.12.2`.
- `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`; `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- `TEMP`, `TMP`, pytest basetemp and raw output were directed to unique directories under `F:\paralls-verification\thread-a\`.

## Contract

The formal siege play pattern emits `reevaluate_passability` after a Facility integrity breach. The official Place identifier is `place:gate-03:passability`. L5's trusted-output validators previously accepted only `fact:` identifiers, so the formal Place machine could not be declared as a trusted command output.

The gateway and reaction compiler now accept exact `place:` identifiers alongside `fact:` identifiers. Wildcards and whitespace remain rejected. This change enables output declaration and committed breach dispatch. It does not implement a Presence resolver or derive passability from the breach.

## Verification

| Check | Result |
|---|---|
| TDD red run before implementation | 2 new Place-output tests failed with `l5_command_outputs_invalid` and `reaction_command_outputs_invalid`; 17 existing tests passed. Raw output: `F:\paralls-verification\thread-a\m6-5-place-output-types-red-20261124-01\pytest.txt`. |
| Exact commit focused tests | `python -m pytest -q -p no:cacheprovider backend/tests/test_l5_dispatch_runtime.py backend/tests/test_l5_reaction.py` — 20 passed, 2 deprecation warnings. Raw output: `F:\paralls-verification\thread-a\m6-5-place-output-types-commit-4023c182-20261124-01\pytest.txt`. |
| Permanent unit selection | `selected=3 problems=0 improvements=0`. Raw output: `F:\paralls-verification\thread-a\m6-5-place-output-types-selections-20261124-01\unit\batch-0000.log`. |
| Frozen ownership | `selected=24 problems=0 improvements=0`. |
| Frozen shared-replay | `selected=990 problems=2 improvements=0`. The two failures are `test_profile_repeated_in_one_run_receives_fresh_events[isolated-storage]` and `[wall-clock]`, both reporting an unhealthy external listener on Port 8000. Raw logs: `F:\paralls-verification\thread-a\m6-5-place-output-types-selections-20261124-01\shared-replay\`. |
| Full suite | Not run for this component. |

The frozen-selection summary is in `F:\paralls-verification\thread-a\m6-5-place-output-types-selections-20261124-01\selections.log`. The two Port 8000 failures were not terminated or modified by this run. Previous A evidence records the same test failures at a parent revision. This unit does not claim a full-suite pass.

## Migration status

- Verified: exact Place machine output declarations compile and a committed Facility breach transaction dispatches the registered reevaluation command.
- Not covered: production `main.py` registration, rule-pack loading, trusted Presence resolver registration, Facility gate-impact input, Morale handler registration, FactType visibility/read scope, end-to-end replay, and full suite.
- M6-5 remains in progress. A breach still cannot determine passability by itself. Missing trusted decision evidence remains `unknown` with zero Place writes.

## Reader inventory and DoD

- Formal output identifier: `place:gate-03:passability`; the formal play pattern routes `gate_breach_to_presence_reeval` to `reevaluate_passability`.
- Existing writer: `PlacePassabilityAuthority.commit_assessment` in `backend/app/gameplay/place_passability_runtime.py`.
- Existing stream reader: `PlacePassabilityAuthority.state` replays and validates `place:<gate>:passability` transitions.
- Existing event schema registration: `backend/app/gameplay/place_event_schema.py`.
- Dispatch component: `L5ReactionDispatcher.after_transaction_dispatched` submits the committed threshold event through `TrustedGameplayCommandGateway`; production `main.py` registration and the Presence command handler are not present.
- No event type or payload changed in this unit, so no new P-3 assertion is required.

| DoD | Status |
|---|---|
| U1 Owner declaration and classification | Not changed by this unit. |
| U2 FactType declaration | Not done; no complete v2 Place schema is added here. |
| U3 Event schema and P-3 | Existing event unchanged; no new event type introduced. |
| U4 Shared mechanism | Partially verified; committed transaction dispatch is tested, but production callback wiring is absent. |
| U5 R1/R2/R3 | Not verified; this unit writes no Owner facts. |
| U6 Reader inventory and tests | Static inventory recorded above; exact Place output and committed breach dispatch tests pass. |
| U7 Read classification and visibility | Not done; this unit does not declare `read_as` or visibility. |
| U8 Rule-pack settings and Resolver registration | Not done; production rule package and trusted Presence resolver remain unregistered. |
| U9 Probe and frozen baseline | Partially verified; own selection and ownership are zero-difference; shared-replay has two Port 8000 failures; full suite not run. |
| U10 Changed files and verification levels | Recorded in the implementation commit and this file. |
| U11 Permanent unit selection | Verified; `docs/verification/selection/m6-5-place-output-types.json`, `selected=3 problems=0 improvements=0`. |
