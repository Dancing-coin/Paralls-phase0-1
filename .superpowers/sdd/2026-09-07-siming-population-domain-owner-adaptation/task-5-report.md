# Task 5 Report: Public Social Population Signal Vertical

## Changed files

- `backend/app/population_continuity/domain_projection_sources.py`
  - Added a pure projection for one public, revision-pinned `social_population_signal` candidate.
  - Rejects non-public scope, private/relationship-shaped fields, missing source pins, and non-proposed materialization.
- `backend/app/population_continuity/social_owner_adapter.py`
  - Added `SocialPopulationSignalOwnerExecutor`.
  - Derives the Social stream, event family, binding, public visibility, and idempotency key; caller payload cannot override them.
  - Routes settlement only through `SocialFactAuthority.record_admitted_population_signal_materialization_proposal(...)` and replays an existing matching receipt without appending.
- `backend/app/population_continuity/decision_surface.py`
  - Registered `population:social-population-signal:v1` against `authority:p5:social` and `inf:population-signal-materialization@1`.
- `backend/app/population_continuity/__init__.py`
  - Exported the adapter.
- `backend/tests/test_siming_population_social_signal_vertical.py`
  - Added public selection/settlement, private projection exclusion, and duplicate replay coverage.
- `backend/tests/test_siming_population_decision_planner.py`
  - Updated the closed default-capability expectation for the admitted Social behavior.

## Verification

Required focused command:

`python -m pytest -q backend/tests/test_siming_population_social_signal_vertical.py backend/tests/test_organization_government_social_family_success_matrix.py`

```text
14 passed, 2 warnings in 1.73s
```

Decision-surface regression:

`python -m pytest -q backend/tests/test_siming_population_decision_planner.py backend/tests/test_siming_population_decision_routing.py backend/tests/test_siming_population_decision_contracts.py backend/tests/test_siming_population_contracts.py`

```text
25 passed, 2 warnings in 2.54s
```

`git diff --check`

```text
passed (no output)
```

## Commit

`769b8e8` (`接入司命公开社会信号 Owner 纵切`)

## Concerns

- This vertical admits only `materialization_state="proposed"`; identity allocation and target-owner creation remain separate Owner operations.
- The existing untracked implementation-plan file was intentionally left outside this Task 5 commit.
