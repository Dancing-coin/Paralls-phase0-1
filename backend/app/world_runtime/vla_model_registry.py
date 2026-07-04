from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class VLAModelCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str
    family: str
    license_summary: str
    deployment_modes: list[str]
    structured_output_schema: str
    runtime_boundary: str
    allowed_runtime_roles: list[str] = Field(default_factory=lambda: ["advisory_visual_spatial_findings"])
    forbidden_runtime_roles: list[str] = Field(
        default_factory=lambda: [
            "world_truth_write",
            "esm_authority_write",
            "actor_control",
            "robotics_action_head_runtime_control",
        ]
    )


def default_vla_model_registry() -> dict[str, VLAModelCandidate]:
    candidates = [
        VLAModelCandidate(
            model_id="qwen3-vl-plus",
            family="Qwen3-VL",
            license_summary="Provider/license must be checked at deployment time; runtime use remains advisory only.",
            deployment_modes=["http", "local"],
            structured_output_schema="VLAProviderResult advisory visual_spatial findings",
            runtime_boundary="Consumes PQF artifact refs and structured fact refs only; does not read Godot scene directly.",
        ),
        VLAModelCandidate(
            model_id="qwen3-vl-local",
            family="Qwen3-VL",
            license_summary="Open/local deployment candidate; validate weights license before use.",
            deployment_modes=["local"],
            structured_output_schema="VLAProviderResult advisory visual_spatial findings",
            runtime_boundary="Local slow path adapter; no current-tick blocking and no authority writes.",
        ),
        VLAModelCandidate(
            model_id="seed-vl-advisor",
            family="Seed",
            license_summary="Seed-series candidate; validate provider terms and deployment rights before use.",
            deployment_modes=["http"],
            structured_output_schema="VLAProviderResult advisory visual_spatial findings",
            runtime_boundary="HTTP slow path adapter; timeout/degrade required before runtime consumption.",
        ),
        VLAModelCandidate(
            model_id="openvla-action-head-research-only",
            family="OpenVLA-style robotics",
            license_summary="Research-only candidate in this game runtime.",
            deployment_modes=["non_runtime_research"],
            structured_output_schema="Not allowed for runtime actor/world control.",
            runtime_boundary="Forbidden for runtime control; may not control actor, world, or ESM.",
            allowed_runtime_roles=[],
        ),
    ]
    return {candidate.model_id: candidate for candidate in candidates}
