# M2-2 Compiled FactType Identity

## Scope

- Code commit: `57d8f4f4b21f985282f472633e6e193a8641e6a8`, based on `8ee7a25e27136e508e304da660217fc99dfb2fc2`.
- The validated FactType `identity` declaration is now retained in the compiled runtime `FactType` object.
- This supplies metadata for a future read resolver. It does not implement event-to-instance FactType attribution, principal qualification, visibility evaluation, or generic `read_as`.
- No persisted event, storage-core, Owner, authorization, or reader behavior changed.

## Verification

Environment: Python `3.12.2`, SQLite `3.43.1`, and `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.

| Check | Result |
|---|---|
| TDD red | New assertion failed with `AttributeError: 'FactType' object has no attribute 'identity'` |
| Full RulePack validator test module | `132 passed, 2 warnings` |
| New registered selection | `selected=1 problems=0 improvements=0` |
| Frozen ownership / modifier / equipment / inventory / shared-replay | `24/0/0`, `12/0/0`, `87/0/0`, `56/0/0`, `990/0/0` |
| Full backend suite | `10,790 passed, 20 failed, 2 skipped, 2 xfailed, 227 warnings`, exit 1 |
| Corrected rerun of affected environment-sensitive tests | `42 passed, 2 warnings` |

The full-suite command used a deeply nested F-drive `TEMP`; 14 nested-evidence cases failed to create paths under that root. The recovery measurement also inherited an empty `GIT_CONFIG_VALUE_0`. The 14 nested-evidence cases, recovery measurement, and one runtime-process concurrency node passed when rerun with a short F-drive `TEMP` and process-local removal of malformed `GIT_CONFIG_*` values. The corrected rerun output is `F:\paralls-verification\thread-a\m2-2-facttype-identity-20261127-03\adjusted-failures.log`.

The four remaining full-suite failures were the optional `tokenizers` dependency, two existing Godot parser probes (`task45` and `task8`), and `test_cold_ready` failing its `resource_bounds` check. The unmodified parent was not rerun for this increment. Full-suite pass is not claimed. Full raw output is `F:\paralls-verification\thread-a\m2-2-facttype-identity-20261127-02\full-backend\pytest.log`.

The new selection and five frozen selection outputs are under `F:\paralls-verification\thread-a\m2-2-facttype-identity-20261127-02\`. TDD red/green output is under `F:\paralls-verification\thread-a\m2-2-facttype-identity-20261127-01\`.

## Remaining M2-2 Gaps

- Runtime mapping from committed events to FactType instances, including ambiguous shared-schema events.
- Historical principal qualification and evaluation for the registered selectors.
- Runtime enforcement of FactType visibility and generic `read_as` semantics.
- M2-2 remains blocked and U7 remains incomplete.
