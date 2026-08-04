"""Backend-owned trusted-local embodied-controller enrollment issuance and Godot child handoff."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from app.services.embodied_controller_auth_service import EmbodiedControllerAuthService, EmbodiedControllerEnrollment


@dataclass(frozen=True)
class TrustedLocalEmbodiedControllerLaunchProfile:
    """Server configuration that owns one local launch actor/controller subject pair."""

    profile_ref: str
    actor_id: str
    controller_instance_id: str
    credential_ttl_seconds: int

    def __post_init__(self) -> None:
        if not self.profile_ref or not self.actor_id or not self.controller_instance_id:
            raise ValueError("trusted_local_embodied_controller_launch_profile_subject_required")
        if self.credential_ttl_seconds < 1:
            raise ValueError("trusted_local_embodied_controller_launch_profile_ttl_invalid")


class TrustedLocalEmbodiedControllerEnrollmentIssuer:
    """Issues opaque enrollments from configured profiles, never client subject claims."""

    def __init__(
        self,
        *,
        auth_service: EmbodiedControllerAuthService,
        launch_profiles: tuple[TrustedLocalEmbodiedControllerLaunchProfile, ...],
    ) -> None:
        profiles_by_ref = {profile.profile_ref: profile for profile in launch_profiles}
        if len(profiles_by_ref) != len(launch_profiles):
            raise ValueError("trusted_local_embodied_controller_launch_profile_duplicate")
        self.auth_service = auth_service
        self._profiles_by_ref: Mapping[str, TrustedLocalEmbodiedControllerLaunchProfile] = profiles_by_ref

    def issue_for_launch_profile(self, launch_profile_ref: str, now: int) -> EmbodiedControllerEnrollment:
        profile = self._profiles_by_ref.get(launch_profile_ref)
        if profile is None:
            raise ValueError("trusted_local_embodied_controller_launch_profile_unknown")
        credential = self.auth_service.create_trusted_local_launch_credential(
            actor_id=profile.actor_id,
            controller_instance_id=profile.controller_instance_id,
            issued_at=now,
            expires_at=now + profile.credential_ttl_seconds,
        )
        return EmbodiedControllerEnrollment(
            credential_kind="trusted_local_launch",
            credential=credential,
            actor_id=profile.actor_id,
            controller_instance_id=profile.controller_instance_id,
            protocol_version=1,
        )


@dataclass(frozen=True)
class EmbodiedControllerGodotLaunchHandoff:
    """Prepares the sole opaque enrollment value inherited by the Godot child."""

    enrollment: EmbodiedControllerEnrollment

    def child_environment(self) -> dict[str, str]:
        return {"PARALLS_EMBODIED_CONTROLLER_ENROLLMENT_JSON": self.enrollment.model_dump_json(exclude_none=True)}


__all__ = [
    "EmbodiedControllerGodotLaunchHandoff",
    "TrustedLocalEmbodiedControllerEnrollmentIssuer",
    "TrustedLocalEmbodiedControllerLaunchProfile",
]
