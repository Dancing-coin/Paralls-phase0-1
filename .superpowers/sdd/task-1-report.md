## Task 1 Report: Narrative Models and Core

### Scope

Implemented the Task 1 self-contained narrative-core surface:

- `backend/app/models/siming_narrative.py`
- `backend/app/services/siming_narrative_core.py`
- `backend/tests/test_siming_narrative_core.py`

No unrelated files were modified.

### TDD Evidence

#### Red

Ran:

```powershell
python -m pytest backend/tests/test_siming_narrative_core.py -v
```

Observed expected failure:

```text
ModuleNotFoundError: No module named 'app.services.siming_narrative_core'
```

This matched the brief's required failing-first condition.

#### Green Attempt 1

Added the narrative models and deterministic narrative core implementation, then reran:

```powershell
python -m pytest backend/tests/test_siming_narrative_core.py -v
```

Observed one failing assertion:

```text
assert result.seeds[0].seed_type == "fact_reveal"
E AssertionError: assert 'unresolved_reveal' == 'fact_reveal'
```

### Minimal Fix Applied

Adjusted `SimingNarrativeCore._seed_for(...)` so `InterventionSeed.seed_type` follows the seed contract asserted by the brief's tests:

- unresolved reveal obligation -> `seed_type="fact_reveal"`
- constraint recovery obligation -> `seed_type="opportunity"`

This was the smallest code change needed to satisfy the test-owned contract while keeping the implementation deterministic and LLM-isolated.

### Final Verification

Ran:

```powershell
python -m pytest backend/tests/test_siming_narrative_core.py -v
```

Result:

```text
3 passed in 0.16s
```

### Behavioral Outcome

The implemented core now deterministically:

- turns `visual_fact_event` observations with established facts into an `unresolved_reveal` obligation
- turns `constraint_state_event` observations into a `constraint_recovery` obligation
- raises room-local pressure from `normal` to `elevated` when unresolved obligations accumulate
- emits narrative-core-owned intervention seeds without any LLM dependency or state mutation from LLM output

### Constraints Check

Confirmed within Task 1 scope:

- no PlotPilot code imported or executed
- no external service/process added
- no UI/workbench added
- no persistence/checkpoint recovery added
- no event-chain search added
- no daemon/queue/lifecycle manager added
- no LLM output used to mutate deterministic narrative state
- `ObservedSimingEvent` was consumed directly as required

### Commit

Planned commit message:

```text
Add deterministic Siming narrative core
```
