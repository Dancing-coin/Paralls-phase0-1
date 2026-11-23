"""Compile workflow steps and recovery policy against a command catalog."""

from collections.abc import Mapping, Set
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter


_ACTIONS = ("abort", "abort_with_compensation", "record_obligation")
_RECOVERIES = ("reconcile_then_retry", "retry", "reconcile", "manual", "compensate")


@dataclass(frozen=True, slots=True)
class WorkflowStep:
    step_id: str
    command: str
    depends_on: tuple[str, ...]
    on_reject: str | None
    on_fail: str | None
    on_timeout: str | None
    recovery: str | None


@dataclass(frozen=True, slots=True)
class Workflow:
    workflow_id: str
    steps: tuple[WorkflowStep, ...]


def compile_workflow(declaration: object, *, command_types: Set[str]) -> Workflow:
    if not isinstance(declaration, Mapping):
        raise ValueError("workflow_schema_invalid")
    if "writes" in declaration:
        raise ValueError("pattern_declares_writes")
    if declaration.keys() - {"workflow_id", "steps", "open_obligations", "timeout_policy"}:
        raise ValueError("workflow_schema_invalid")
    workflow_id = declaration.get("workflow_id")
    steps = declaration.get("steps")
    if not isinstance(workflow_id, str) or not workflow_id or not isinstance(steps, list) or not steps:
        raise ValueError("workflow_schema_invalid")

    timeout = declaration.get("timeout_policy", {})
    if not isinstance(timeout, Mapping) or timeout.keys() - {"default", "per_step"}:
        raise ValueError("workflow_timeout_invalid")
    default_timeout = timeout.get("default")
    per_step = timeout.get("per_step", {})
    if (("default" in timeout and default_timeout not in _ACTIONS)
            or not isinstance(per_step, Mapping)
            or any(action not in _ACTIONS for action in per_step.values())):
        raise ValueError("workflow_timeout_invalid")

    recovery_by_step = {}
    obligations = declaration.get("open_obligations", [])
    if not isinstance(obligations, list):
        raise ValueError("workflow_recovery_invalid")
    for obligation in obligations:
        if not isinstance(obligation, Mapping) or obligation.keys() != {"step_id", "recovery"}:
            raise ValueError("workflow_recovery_invalid")
        step_id, recovery = obligation["step_id"], obligation["recovery"]
        if (not isinstance(step_id, str) or not step_id or step_id in recovery_by_step
                or recovery not in _RECOVERIES):
            raise ValueError("workflow_recovery_invalid")
        recovery_by_step[step_id] = recovery

    compiled = {}
    for step in steps:
        if not isinstance(step, Mapping):
            raise ValueError("workflow_step_invalid")
        if "writes" in step:
            raise ValueError("pattern_declares_writes")
        if step.keys() - {"id", "command", "depends_on", "on_reject", "on_fail"}:
            raise ValueError("workflow_step_invalid")
        step_id, command = step.get("id"), step.get("command")
        if not isinstance(step_id, str) or not step_id or step_id in compiled:
            raise ValueError("workflow_step_invalid")
        if not isinstance(command, str) or command not in command_types:
            raise ValueError("pattern_command_unknown")
        dependencies = step.get("depends_on", [])
        if (not isinstance(dependencies, list)
                or any(not isinstance(item, str) or not item for item in dependencies)
                or len(set(dependencies)) != len(dependencies)):
            raise ValueError("workflow_dependency_invalid")
        if any(field in step and step[field] not in _ACTIONS for field in ("on_reject", "on_fail")):
            raise ValueError("workflow_step_policy_invalid")
        on_reject, on_fail = step.get("on_reject"), step.get("on_fail")
        on_timeout = per_step.get(step_id, default_timeout)
        recovery = recovery_by_step.get(step_id)
        if "record_obligation" in (on_reject, on_fail, on_timeout) and recovery is None:
            raise ValueError("workflow_recovery_required")
        compiled[step_id] = WorkflowStep(
            step_id, command, tuple(dependencies), on_reject, on_fail, on_timeout, recovery,
        )

    if (per_step.keys() | recovery_by_step.keys()) - compiled.keys():
        raise ValueError("workflow_step_unknown")
    graph = {step_id: step.depends_on for step_id, step in compiled.items()}
    if any(set(dependencies) - graph.keys() for dependencies in graph.values()):
        raise ValueError("workflow_dependency_unknown")
    try:
        TopologicalSorter(graph).prepare()
    except CycleError as error:
        raise ValueError("pattern_workflow_cycle") from error
    return Workflow(workflow_id, tuple(compiled.values()))
