from __future__ import annotations

import hashlib
import json
from secrets import token_urlsafe
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.embodied_interaction import ControllerBinding, ControllerExecutionGrant, EmbodiedActionRequest


CredentialKind = Literal["trusted_local_launch", "authenticated_session"]


class EmbodiedControllerEnrollment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    credential_kind: CredentialKind
    credential: str = Field(min_length=1)
    actor_id: str = Field(min_length=1)
    controller_instance_id: str = Field(min_length=1)
    protocol_version: int = Field(ge=1)


class ControllerBindResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    binding: ControllerBinding | None = None
    error_code: str = ""


class GrantValidationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    grant: ControllerExecutionGrant | None = None
    idempotent: bool = False
    error_code: str = ""


class _TrustedLocalCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actor_id: str
    controller_instance_id: str
    issued_at: int
    expires_at: int
    used: bool = False


class EmbodiedControllerAuthService:
    def __init__(self, *, authenticated_session_adapter_configured: bool = False) -> None:
        self.authenticated_session_adapter_configured = authenticated_session_adapter_configured
        self._trusted_credentials: dict[str, _TrustedLocalCredential] = {}
        self._bindings: dict[str, ControllerBinding] = {}
        self._controller_epochs: dict[str, int] = {}
        self._grants: dict[str, ControllerExecutionGrant] = {}
        self._grant_results: dict[str, dict[str, object]] = {}

    def create_trusted_local_launch_credential(
        self,
        *,
        actor_id: str,
        controller_instance_id: str,
        issued_at: int,
        expires_at: int,
    ) -> str:
        secret = f"trusted_local_launch:{token_urlsafe(24)}"
        self._trusted_credentials[secret] = _TrustedLocalCredential(
            actor_id=actor_id,
            controller_instance_id=controller_instance_id,
            issued_at=issued_at,
            expires_at=expires_at,
        )
        return secret

    def bind_controller(
        self,
        enrollment: EmbodiedControllerEnrollment,
        *,
        remote_host: str,
        now: int,
    ) -> ControllerBindResult:
        if enrollment.credential_kind == "authenticated_session":
            if not self.authenticated_session_adapter_configured:
                return ControllerBindResult(accepted=False, error_code="authenticated_session_adapter_unavailable")
            return ControllerBindResult(accepted=False, error_code="authenticated_session_adapter_not_implemented")
        if remote_host not in {"127.0.0.1", "::1", "localhost"}:
            return ControllerBindResult(accepted=False, error_code="trusted_local_launch_requires_loopback")
        credential = self._trusted_credentials.get(enrollment.credential)
        if credential is None:
            return ControllerBindResult(accepted=False, error_code="trusted_local_launch_unknown")
        if credential.used:
            return ControllerBindResult(accepted=False, error_code="trusted_local_launch_already_used")
        if now > credential.expires_at:
            return ControllerBindResult(accepted=False, error_code="trusted_local_launch_expired")
        if credential.actor_id != enrollment.actor_id or credential.controller_instance_id != enrollment.controller_instance_id:
            return ControllerBindResult(accepted=False, error_code="trusted_local_launch_subject_mismatch")
        credential.used = True
        epoch = self._controller_epochs.get(enrollment.controller_instance_id, 0) + 1
        self._controller_epochs[enrollment.controller_instance_id] = epoch
        binding = ControllerBinding(
            binding_id=f"controller_binding:{enrollment.controller_instance_id}:{epoch}",
            authenticated_principal_ref=f"principal:trusted_local:{enrollment.actor_id}",
            actor_id=enrollment.actor_id,
            controller_instance_id=enrollment.controller_instance_id,
            connection_epoch=epoch,
        )
        self._bindings[binding.binding_id] = binding
        return ControllerBindResult(accepted=True, binding=binding)

    def issue_execution_grant(
        self,
        *,
        binding: ControllerBinding,
        request: EmbodiedActionRequest,
        issued_at: int,
        ttl: int,
    ) -> ControllerExecutionGrant:
        request_digest = self.request_digest(request)
        grant = ControllerExecutionGrant(
            grant_id=f"grant:{request.interaction_attempt_id}:{binding.connection_epoch}",
            authenticated_principal_ref=binding.authenticated_principal_ref,
            controller_instance_id=binding.controller_instance_id,
            connection_epoch=binding.connection_epoch,
            interaction_attempt_id=request.interaction_attempt_id,
            session_id=request.session_id,
            actor_id=request.actor_id,
            target_ref=request.target_ref,
            affordance_id=request.affordance_id,
            request_digest=request_digest,
            scene_revision=request.scene_revision,
            binding_revision=request.binding_revision,
            policy_revision=request.policy_revision,
            issued_at=issued_at,
            expires_at=issued_at + ttl,
            one_time_outcome_nonce=f"nonce:{token_urlsafe(24)}",
        )
        self._grants[grant.grant_id] = grant
        return grant

    def validate_grant_for_phase(self, *, grant_id: str, connection_epoch: int) -> GrantValidationResult:
        grant = self._grants.get(grant_id)
        if grant is None:
            return GrantValidationResult(accepted=False, error_code="grant_unknown")
        if grant.state == "revoked":
            return GrantValidationResult(accepted=False, error_code="grant_revoked")
        if grant.state == "consumed":
            return GrantValidationResult(accepted=False, error_code="grant_consumed")
        if grant.connection_epoch != connection_epoch:
            return GrantValidationResult(accepted=False, error_code="stale_connection_epoch")
        return GrantValidationResult(accepted=True, grant=grant)

    def consume_grant_for_outcome(
        self,
        *,
        grant_id: str,
        connection_epoch: int,
        outcome_nonce: str,
        payload_digest: str,
        now: int,
    ) -> GrantValidationResult:
        grant = self._grants.get(grant_id)
        if grant is None:
            return GrantValidationResult(accepted=False, error_code="grant_unknown")
        stored = self._grant_results.get(grant_id)
        if stored is not None:
            if stored.get("payload_digest") == payload_digest and stored.get("outcome_nonce") == outcome_nonce:
                return GrantValidationResult(accepted=True, grant=grant, idempotent=True)
            return GrantValidationResult(accepted=False, error_code="grant_consumed")
        if grant.state == "revoked":
            return GrantValidationResult(accepted=False, error_code="grant_revoked")
        if grant.connection_epoch != connection_epoch:
            return GrantValidationResult(accepted=False, error_code="stale_connection_epoch")
        if now > grant.expires_at:
            grant.state = "expired"
            return GrantValidationResult(accepted=False, error_code="grant_expired")
        if grant.one_time_outcome_nonce != outcome_nonce:
            return GrantValidationResult(accepted=False, error_code="nonce_mismatch")
        grant.state = "consumed"
        self._grant_results[grant_id] = {
            "payload_digest": payload_digest,
            "outcome_nonce": outcome_nonce,
        }
        return GrantValidationResult(accepted=True, grant=grant)

    def revoke_controller_epoch(self, *, controller_instance_id: str, connection_epoch: int) -> None:
        for grant in self._grants.values():
            if grant.controller_instance_id == controller_instance_id and grant.connection_epoch == connection_epoch:
                grant.state = "revoked"

    @staticmethod
    def request_digest(request: EmbodiedActionRequest) -> str:
        payload = json.dumps(request.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()
