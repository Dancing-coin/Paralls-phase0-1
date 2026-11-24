# M6-5 Information report source evidence

## Scope and exact code

- Code tip: `3fe50ca561eb36e97ebccfb3b298c96be9a99780` on `thread-a/ownership-bond-followup-20261121`. Information delivery was selectively integrated from B through `abba3c3c`, `6741ab61`, and `63f41c8b`. No B branch merge or integration update was performed.
- Python `3.12.2`; SQLite `3.43.1`. `PYTHONPATH` was set to this A worktree's `backend`, and `app.__file__` resolved to `F:\codex-temp\paralls-v2-thread-a-bond-20261121\backend\app\__init__.py`.
- Implementation commits: `0fd74b4c` (Information-owned recipient report source, schema and pack declaration), `f442c1f9` (dedicated signer configuration, production HTTP Gateway, delivery dispatch and exact Owner-bound L5 source recognition), and `3fe50ca5` (preserve the hidden signer map in child-process settings tests).

## Behavior verified

- The production EventSchema factory registers `gameplay.information.siege_report_published@1`. The Information pack declares its recipient-private report FactType and publication command.
- `POST /api/v2/siege/information/report-publication-input` accepts the authenticated report publication input. The Information Owner commits a recipient-scoped report event with its source event, stream and revision reference, then records SocialDelivery. The existing L5 dispatcher recognizes the committed report only when its EventSchema, FactType and transaction Owner match, and writes the recipient-private knowledge fact.
- Invalid signatures, unknown authorities, missing or stale source revisions, changed-receipt retries and requests missing production signing configuration are covered by zero-write or rejection tests. Exact retry returns the original receipts, including after the publication window closes.
- Existing B Information delivery and reaction paths are used. This evidence covers the trusted report publication input through recipient knowledge projection. It does not establish a fully configured siege playthrough or close the separate `impact_gate` obligation gap.

## Focused verification

At exact code SHA `3fe50ca561eb36e97ebccfb3b298c96be9a99780`, nine Information, Gateway, EventSchema, L5 and runtime test files completed with `199 passed, 6 warnings` (`12.63s`). Raw output: `F:\paralls-verification\thread-a\information-report-exact-3fe50ca5-20261124-01\pytest.log`.

The 25-node Information report selection completed with `selected=25 problems=0 improvements=0`. Raw output: `F:\paralls-verification\thread-a\information-report-selection-3fe50ca5-20261124-02\console.log` and its `selection` subdirectory. The five frozen selections were previously run at this exact SHA: ownership 24, modifier 12, equipment 87 and inventory 56 had zero problems and improvements. Shared-replay 990 had two Port 8000 failures and zero improvements. Those two failures were reproduced at parent `f442c1f9` as external-process health failures. Raw output is in `F:\paralls-verification\thread-a\information-report-frozen-3fe50ca5-20261124-01` and `F:\paralls-verification\thread-a\information-parent-port8000-f442c1f9-20261124-01`.

## Merged-worktree full suite

The full backend suite ran on the uncommitted documentation workspace at code tip `3fe50ca561eb36e97ebccfb3b298c96be9a99780`, using the same Python and A-worktree import path. It completed with exit code 1: `10603 passed, 21 failed, 2 skipped, 2 xfailed, 227 warnings in 1635.50s`.

The 21 failures were `test_all_22_repaired_budgets_equal_fixed_official_usage`; the Godot CharacterTask45 probe; two repeated-run embodied interaction cases; the population cold-ready gate; 16 population harness-evidence parameter cases; the population recovery measurement; and the Task8 role-presentation registry probe. The detailed failures include a missing `tokenizers` module, Port 8000 occupied by an external process, and Godot parse/type-resolution errors. These failures do not touch the Information report tests or changed source files. They were not rerun on the parent SHA in this run, so they are recorded without a baseline attribution. Full-suite output: `F:\paralls-verification\thread-a\information-report-full-3fe50ca5-20261124-03\full.log`.

## Static checks and limitations

- `git diff --check 8227e94c..3fe50ca561eb36e97ebccfb3b298c96be9a99780` passed.
- The production writer now provides a real Information-owned report source and removes the need to configure an arbitrary source-event allowlist. The signed input authority is configured through the dedicated `SIEGE_INFORMATION_REPORT_AUTHORITY_SECRETS_JSON` setting.
- No Godot runtime or fully configured siege playthrough was run. M6-5 remains in progress. Formal `impact_gate` execution and production gate profile values remain outstanding. This unit does not establish Architecture v2 completion.
