# M5-5 principal selector registration increment

- Base A commit: `49402972c41720869a5cf90c5911c117a122defb`.
- Scope: validate the declared `learnable_by` selector syntax while compiling FactTypes. This does not evaluate principal qualifications or implement `read_as`.
- Formal basis: Architecture v2 FactType schema selector forms recorded in the prior M2-2 contract audit. The Information package's existing `recipient_of(subject)` selector is also retained because its production report FactTypes use it.
- Compatibility: declarations without `learnable_by` keep their existing behavior. The accepted registered grammar is `world`, `self`, `faction:<ref>`, `role:<ref>`, `owner_of(<ref>)`, `holder_of(<ref>)`, `group_of(<selector>)` with one wrapper level, and existing `recipient_of(subject)` use. Malformed values reject with `facttype_selector_invalid`; nested group selectors reject with `facttype_selector_nesting_invalid`.
- Python: `D:\Temp\paralls-g0-py312\Scripts\python.exe`, Python 3.12.2. `PYTHONPATH=F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend`; `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.

## Verification

- TDD red: the new registry test cases returned `9 failed, 17 passed, 2 warnings`; all nine failures were the expected missing rejection paths.
- Focused integration suite, rerun with pytest basetemp, TEMP/TMP, and Python cache prefix on F: `218 passed, 6 warnings in 11.03s`. The output and temporary files are under `F:\paralls-verification\thread-a\m5-5-selector-registration-20261127-06\`.
- Existing M5-5 registered selection: `selected=38 problems=0 improvements=0`.
- All 30 pre-existing registered selections: zero problems and zero improvements. Raw output is under `F:\paralls-verification\thread-a\m5-5-selector-registration-20261127-07\`.
- Frozen selections: Ownership `24/0/0`, Modifier `12/0/0`, Equipment `87/0/0`, Inventory `56/0/0`, shared-replay `990/0/0`. Raw output is under `F:\paralls-verification\thread-a\m5-5-selector-registration-20261127-08\`.
- New selector U11 selection: `selected=6 problems=0 improvements=0`, raw output under `F:\paralls-verification\thread-a\m5-5-selector-registration-20261127-06\selection\`.
- No full backend suite was run for this increment.

## Remaining M2-2 work

This is registration syntax validation only. Principal qualification sources, runtime selector evaluation, event-type to FactType/visibility mapping, and a subject-facing `read_as` path remain unimplemented. M2-2 remains blocked and M5-5 remains in progress.
