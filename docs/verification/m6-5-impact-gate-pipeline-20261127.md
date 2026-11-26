# M6-5 Impact Gate Pipeline Production Wiring

## Scope

- Base: `b70308aa628ca12a6f2b3b70f70e2746f4074862`.
- Adds the four-step `impact_gate` declaration to `county_siege_morale_presence@1.0.1`, layered on `county_siege_facility@1.0.0`. The existing `county_siege_morale_presence@1.0.0` remains available for historical pins and keeps the legacy path without a compiled Pipeline.
- The production runtime binds the Pipeline to the original four-stream revision snapshot reconstructed from the durable signed-input event sequence. Facility and Presence Owners keep their current CAS read sets. Resolver outputs are checked against the signed input before Owner facts commit; disagreement rejects without writing Facility or Place facts.
- Startup and package archive loading register the code Resolver handlers required by the versioned package.

## Verification

- Environment: Python `3.12.2`, SQLite `3.43.1`, `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`; `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`. `TEMP`, `TMP`, `PYTHONPYCACHEPREFIX`, and pytest `--basetemp` point to this run directory on F:.
- Focused command: `python -m pytest -q -p no:cacheprovider --basetemp=F:\paralls-verification\thread-a\m6-5-impact-pipeline-20261127-01\pytest-tmp backend\tests\test_facility_gate_layered_runtime.py backend\tests\test_m6_5_siege_runtime.py backend\tests\test_gameplay_event_schema_registry.py backend\tests\test_rule_pack_validator.py`.
- Focused result: `197 passed, 6 warnings in 7.83s`, exit 0.
- M6-5 registered selection: `selected=26 problems=0 improvements=0`.
- Frozen Ownership selection: `selected=24 problems=0 improvements=0`.
- Frozen shared-replay selection: `selected=990 problems=0 improvements=0`.
- Raw outputs: `F:\paralls-verification\thread-a\m6-5-impact-pipeline-20261127-01\`.

## Remaining

- M6-5 remains in progress. No authoritative production Gate values or deployment target are present in the repository. `.env.example` remains a demonstration profile. No production deployment, UE transport, complete siege run, or full backend suite was verified.
- `deadline_world_tick` remains unknown because no deadline policy/source is defined.
- This increment does not claim U1-U11 or Architecture v2 completion.
