"""Compile L5 pipelines from validated impact profiles."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class PipelineStep:
    fact_type_pattern: str
    resolver: str


@dataclass(frozen=True, slots=True)
class Pipeline:
    pipeline_id: str
    profile_ref: str
    atomic: bool
    steps: tuple[PipelineStep, ...]
    recovery_action: str | None

    def bind_inputs(
        self, *, scopes: Sequence[str], revision_vectors: Sequence[Mapping[str, int]],
    ) -> Mapping[str, int]:
        """Bind the per-step scope and read evidence before planning settlement."""
        if len(scopes) != len(self.steps) or any(not scope for scope in scopes):
            raise ValueError("pipeline_scope_invalid")
        if self.atomic and len(set(scopes)) != 1:
            raise ValueError("pipeline_cross_scope_atomic")
        if len(revision_vectors) != len(self.steps):
            raise ValueError("pipeline_revision_vector_mismatch")
        shared = revision_vectors[0]
        if any(
            not isinstance(stream, str) or not stream or type(revision) is not int or revision < 0
            for vector in revision_vectors for stream, revision in vector.items()
        ):
            raise ValueError("pipeline_revision_vector_invalid")
        if any(vector != shared for vector in revision_vectors[1:]):
            raise ValueError("pipeline_revision_vector_mismatch")
        return MappingProxyType(dict(shared))


def compile_pipeline(
    pipeline_id: str, declaration: Mapping[str, object], *,
    impact_profiles: Mapping[str, Mapping], fact_specs: Mapping[str, Mapping],
) -> Pipeline:
    if not pipeline_id or declaration.keys() - {
        "pipeline_id", "profile_ref", "atomic", "host_requirement", "steps", "recovery_action",
    } or declaration.get("pipeline_id", pipeline_id) != pipeline_id:
        raise ValueError("pipeline_schema_invalid")
    profile_ref = declaration.get("profile_ref")
    prefix = "impact_profile/"
    if not isinstance(profile_ref, str) or not re.fullmatch(r"impact_profile/[^@/\s]+@[^@/\s]+", profile_ref):
        raise ValueError("pipeline_profile_ref_invalid")
    profile = impact_profiles.get(profile_ref.removeprefix(prefix))
    if profile is None:
        raise ValueError("pipeline_profile_unknown")

    atomic = declaration.get("atomic")
    if type(atomic) is not bool:
        raise ValueError("pipeline_atomicity_invalid")
    host_requirement = declaration.get("host_requirement")
    recovery_action = declaration.get("recovery_action")
    if atomic:
        if host_requirement != "single" or "recovery_action" in declaration:
            raise ValueError("pipeline_schema_invalid")
    elif "host_requirement" in declaration or recovery_action not in ("retry", "reconcile", "manual", "compensate"):
        raise ValueError("pipeline_recovery_action_invalid")

    steps = tuple(PipelineStep(layer["fact_type"], layer["resolver"]) for layer in profile["layers"])
    declared_steps = [
        {"fact_type_pattern": step.fact_type_pattern, "resolver": step.resolver} for step in steps
    ]
    if declaration.get("steps") != declared_steps:
        raise ValueError("pipeline_profile_steps_mismatch")
    if atomic:
        hosts = {fact_specs[step.fact_type_pattern]["host"] for step in steps}
        if impact_layers_cross_hosts(hosts, len(steps)):
            raise ValueError("impact_atomic_cross_host")
        scopes = {step.fact_type_pattern.split(":")[2] for step in steps}
        scopes.discard("*")
        if len(scopes) > 1:
            raise ValueError("pipeline_cross_scope_atomic")
    return Pipeline(pipeline_id, profile_ref, atomic, steps, recovery_action)


def impact_layers_cross_hosts(hosts: set[str], layer_count: int) -> bool:
    return layer_count > 1 and (len(hosts) > 1 or "either" in hosts)
