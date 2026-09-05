from __future__ import annotations

from app.gameplay.p5.stormnight_scenario import StormnightScenarioRunner


def test_scenario_runner_rejects_unknown_terminal_outcome_without_extra_write() -> None:
    runner = StormnightScenarioRunner()
    try:
        runner.run(outcome_kind="not-admitted")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown outcome must fail closed")
