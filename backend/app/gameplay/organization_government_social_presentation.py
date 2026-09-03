"""Read-only OGS mirror payloads for clients and Godot presentation."""
from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from app.gameplay.organization_government_social_platform_runtime import OGSPlatformProjection


class OGSPresentationError(ValueError):
    pass


def build_ogs_read_model(projection: OGSPlatformProjection) -> Mapping[str, object]:
    if not projection.projection_hash.startswith("sha256:"):
        raise OGSPresentationError("ogs_presentation_projection_invalid")
    return MappingProxyType({
        "projection_hash": projection.projection_hash,
        "organization_lifecycles": dict(projection.organization_lifecycles),
        "organization_memberships": {
            ref: value.model_dump(mode="json")
            for ref, value in projection.organization_memberships.items()
        },
        "organization_operating_periods": {
            ref: value.model_dump(mode="json")
            for ref, value in projection.organization_operating_periods.items()
        },
        "organization_commitments": {
            ref: value.model_dump(mode="json")
            for ref, value in projection.organization_commitments.items()
        },
        "government_policies": {
            ref: value.model_dump(mode="json")
            for ref, value in projection.government_policies.items()
        },
        "government_cases": {
            ref: value.model_dump(mode="json")
            for ref, value in projection.government_cases.items()
        },
        "government_tax_projects": {
            ref: value.model_dump(mode="json")
            for ref, value in projection.government_tax_projects.items()
        },
        "government_notices": {
            ref: value.model_dump(mode="json")
            for ref, value in projection.government_notices.items()
        },
        "social_relationships": {
            ref: value.model_dump(mode="json")
            for ref, value in projection.social_relationships.items()
        },
        "social_groups": {
            ref: value.model_dump(mode="json")
            for ref, value in projection.social_groups.items()
        },
        "social_conflicts": {
            ref: value.model_dump(mode="json")
            for ref, value in projection.social_conflicts.items()
        },
        "social_private_projections": {
            ref: value.model_dump(mode="json")
            for ref, value in projection.social_private_projections.items()
        },
        "population_signals": {
            ref: value.model_dump(mode="json")
            for ref, value in projection.population_signals.items()
        },
        "source_revision_vector": dict(projection.source_revision_vector),
        "speculative_truth": False,
    })


def reject_speculative_ogs_state(candidate: object) -> None:
    if candidate is not None:
        raise OGSPresentationError("ogs_presentation_speculative_truth_denied")
