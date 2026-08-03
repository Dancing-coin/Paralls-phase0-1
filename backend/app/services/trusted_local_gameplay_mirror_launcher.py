"""Backend-owned trusted-local enrollment issuance and Godot child handoff."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from app.services.websocket_session_auth_service import WebSocketSessionAuthService, WebSocketSessionEnrollment


@dataclass(frozen=True)
class TrustedLocalGameplayMirrorLaunchProfile:
    """Server configuration that owns one local launch subject and read scope."""

    profile_ref: str
    principal_ref: str
    allowed_actor_refs: tuple[str, ...]
    credential_ttl_seconds: int

    def __post_init__(self) -> None:
        if not self.profile_ref or not self.principal_ref or not self.allowed_actor_refs:
            raise ValueError("trusted_local_gameplay_mirror_launch_profile_subject_required")
        if any(not actor_ref for actor_ref in self.allowed_actor_refs):
            raise ValueError("trusted_local_gameplay_mirror_launch_profile_subject_required")
        if self.credential_ttl_seconds < 1:
            raise ValueError("trusted_local_gameplay_mirror_launch_profile_ttl_invalid")


class TrustedLocalGameplayMirrorEnrollmentIssuer:
    """Issues opaque enrollments from configured profiles, never client scope claims."""

    def __init__(
        self,
        *,
        auth_service: WebSocketSessionAuthService,
        launch_profiles: tuple[TrustedLocalGameplayMirrorLaunchProfile, ...],
    ) -> None:
        profiles_by_ref = {profile.profile_ref: profile for profile in launch_profiles}
        if len(profiles_by_ref) != len(launch_profiles):
            raise ValueError("trusted_local_gameplay_mirror_launch_profile_duplicate")
        self.auth_service = auth_service
        self._profiles_by_ref: Mapping[str, TrustedLocalGameplayMirrorLaunchProfile] = profiles_by_ref

    def issue_for_launch_profile(self, launch_profile_ref: str, now: int) -> WebSocketSessionEnrollment:
        profile = self._profiles_by_ref.get(launch_profile_ref)
        if profile is None:
            raise ValueError("trusted_local_gameplay_mirror_launch_profile_unknown")
        credential = self.auth_service.create_trusted_local_launch_credential(
            principal_ref=profile.principal_ref,
            allowed_actor_refs=profile.allowed_actor_refs,
            issued_at=now,
            expires_at=now + profile.credential_ttl_seconds,
        )
        return WebSocketSessionEnrollment(
            credential_kind="trusted_local_launch",
            credential=credential,
            protocol_version=1,
        )


@dataclass(frozen=True)
class GameplayMirrorGodotLaunchHandoff:
    """Prepares the sole opaque enrollment value inherited by the Godot child."""

    enrollment: WebSocketSessionEnrollment

    def child_environment(self) -> dict[str, str]:
        return {"PARALLS_GAMEPLAY_MIRROR_ENROLLMENT_JSON": self.enrollment.model_dump_json(exclude_none=True)}


__all__ = [
    "GameplayMirrorGodotLaunchHandoff",
    "TrustedLocalGameplayMirrorEnrollmentIssuer",
    "TrustedLocalGameplayMirrorLaunchProfile",
]
