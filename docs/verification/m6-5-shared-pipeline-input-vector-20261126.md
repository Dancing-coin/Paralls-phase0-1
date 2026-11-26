# M6-5 Shared Pipeline Input Vector

## Scope

- Parent: `58b57f76534b114e32c10bda483f33318f69b1da`.
- Implementation: `4cf77e5d3f59ff1c1203808dac1bbb8a93a7ee0c`.
- The obligation projection reconstructs a four-stream input revision vector from events preceding the signed Gate input's `global_sequence`. The vector contains door durability, latch durability, integrity, and Place passability revisions, then remains stable when later Facility and Presence commits are replayed.
- The vector is derived projection data. It does not change persisted event schemas or replace either Owner's CAS/read set.

## Verification

- Python `3.12.2`, SQLite `3.43.1`, `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`; `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- Red test before implementation: `test_impact_gate_rebuild_pins_the_shared_input_revision_vector` failed with the expected missing `input_revision_vector` attribute.
- Command: `python -m pytest -q -p no:cacheprovider --basetemp=F:\paralls-verification\thread-a\m6-5-vector-final-20261126-01\pytest-tmp backend\tests\test_facility_gate_layered_runtime.py backend\tests\test_m6_5_siege_runtime.py`.
- Result: `52 passed, 6 warnings in 1.88s`, exit 0. The new test closes and reopens SQLite before rebuilding the vector.
- M6-5 impact-gate selection: `selected=22 problems=0 improvements=0`.
- Frozen ownership selection: `selected=24 problems=0 improvements=0`.
- Frozen shared-replay selection: `selected=990 problems=0 improvements=0`.
- Raw outputs: `F:\paralls-verification\thread-a\m6-5-vector-final-20261126-01\`; `F:\paralls-verification\thread-a\m6-5-vector-selections-20261126-01\`.

## Status

This increment verifies historical vector reconstruction and durable replay. The county siege pack still has no `impact_gate` Pipeline declaration, and production does not consume a compiled `Pipeline`. Resolver handler registration and shared `main.py` coordination remain open. The backend full suite, production deployment, authoritative Gate values, UE transport, and a complete siege run were not verified. M6-5 remains in progress and no U1-U10 completion is claimed.
