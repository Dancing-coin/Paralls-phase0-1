"""Backend-owned WebSocket session identity and actor read-scope grants."""

from __future__ import annotations

from dataclasses import dataclass
from secrets import token_urlsafe
from time import time
from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field
from app.ws_protocol import GameplayMirrorCapabilityOffer, GameplayMirrorCapabilityProfile


CredentialKind = Literal["trusted_local_launch", "authenticated_session"]
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


class WebSocketSessionEnrollment(BaseModel):
    """Untrusted enrollment request; authority subjects live in the credential."""

    model_config = ConfigDict(extra="forbid")

    credential_kind: CredentialKind
    credential: str = Field(min_length=1)
    protocol_version: int = Field(ge=1)
    capability_offer: GameplayMirrorCapabilityOffer | None = None


class WebSocketSessionBinding(BaseModel):
    """Opaque backend-issued session identity with fixed actor and advisory read scopes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    session_ref: str
    principal_ref: str
    allowed_actor_refs: tuple[str, ...]
    allowed_government_drought_advisory_jurisdiction_refs: tuple[str, ...] = ()
    binding_state: Literal["bound_active", "renewal_due", "revoked", "expired", "disconnected"] = "bound_active"
    connection_epoch: int = Field(ge=0, default=0)
    lease_expires_at: int = Field(ge=0, default=0)


class WebSocketSessionBindResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    binding: WebSocketSessionBinding | None = None
    error_code: str = ""


class WebSocketSessionLifecycleRecord(BaseModel):
    """Redacted terminal binding facts retained only for bounded diagnostics."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    session_ref: str
    binding_state: Literal["renewal_due", "revoked", "expired", "disconnected"]
    reason_code: str
    occurred_at: int


class _TrustedLocalSessionCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")

    principal_ref: str
    allowed_actor_refs: tuple[str, ...]
    allowed_government_drought_advisory_jurisdiction_refs: tuple[str, ...] = ()
    issued_at: int
    expires_at: int
    used: bool = False
    revoked: bool = False


@dataclass
class WebSocketConnectionContext:
    """Connection-local transport facts; it is never a world-authority context."""

    remote_host: str
    observed_at: int
    connection_ref: str = ""
    binding: WebSocketSessionBinding | None = None
    capability_profile: GameplayMirrorCapabilityProfile | None = None

    @classmethod
    def direct_handler_compatibility(cls) -> "WebSocketConnectionContext":
        """Keeps direct handler tests separate from a real network connection."""

        return cls(remote_host="127.0.0.1", observed_at=int(time()), connection_ref="direct_handler")


class WebSocketSessionAuthService:
    """Issues opaque connection bindings without importing controller execution policy."""

    def __init__(
        self,
        *,
        authenticated_session_adapter_configured: bool = False,
        renewal_scope_selector: Callable[[WebSocketSessionBinding], tuple[str, ...]] | None = None,
    ) -> None:
        self.authenticated_session_adapter_configured = authenticated_session_adapter_configured
        self._renewal_scope_selector = renewal_scope_selector or (lambda binding: binding.allowed_actor_refs)
        self._trusted_credentials: dict[str, _TrustedLocalSessionCredential] = {}
        self._bindings: dict[str, WebSocketSessionBinding] = {}
        self._closed_bindings: dict[str, WebSocketSessionLifecycleRecord] = {}
        self._next_connection_epoch = 1

    def create_trusted_local_launch_credential(
        self,
        *,
        principal_ref: str,
        allowed_actor_refs: tuple[str, ...],
        allowed_government_drought_advisory_jurisdiction_refs: tuple[str, ...] = (),
        issued_at: int,
        expires_at: int,
    ) -> str:
        if not principal_ref or not allowed_actor_refs or any(not actor_ref for actor_ref in allowed_actor_refs):
            raise ValueError("trusted_local_session_subject_required")
        if any(not jurisdiction_ref for jurisdiction_ref in allowed_government_drought_advisory_jurisdiction_refs):
            raise ValueError("trusted_local_government_drought_advisory_scope_invalid")
        if expires_at < issued_at:
            raise ValueError("trusted_local_session_expiry_invalid")
        credential = f"trusted_local_launch:{token_urlsafe(24)}"
        self._trusted_credentials[credential] = _TrustedLocalSessionCredential(
            principal_ref=principal_ref,
            allowed_actor_refs=tuple(dict.fromkeys(allowed_actor_refs)),
            allowed_government_drought_advisory_jurisdiction_refs=tuple(
                dict.fromkeys(allowed_government_drought_advisory_jurisdiction_refs)
            ),
            issued_at=issued_at,
            expires_at=expires_at,
        )
        return credential

    def bind_session(
        self,
        enrollment: WebSocketSessionEnrollment,
        *,
        remote_host: str,
        now: int,
    ) -> WebSocketSessionBindResult:
        if enrollment.credential_kind == "authenticated_session":
            if not self.authenticated_session_adapter_configured:
                return WebSocketSessionBindResult(accepted=False, error_code="authenticated_session_adapter_unavailable")
            return WebSocketSessionBindResult(accepted=False, error_code="authenticated_session_adapter_not_implemented")
        if remote_host not in _LOOPBACK_HOSTS:
            return WebSocketSessionBindResult(accepted=False, error_code="trusted_local_launch_requires_loopback")
        credential = self._trusted_credentials.get(enrollment.credential)
        if credential is None:
            return WebSocketSessionBindResult(accepted=False, error_code="trusted_local_launch_unknown")
        if credential.revoked:
            return WebSocketSessionBindResult(accepted=False, error_code="trusted_local_launch_revoked")
        if credential.used:
            return WebSocketSessionBindResult(accepted=False, error_code="trusted_local_launch_already_used")
        if now > credential.expires_at:
            return WebSocketSessionBindResult(accepted=False, error_code="trusted_local_launch_expired")
        credential.used = True
        binding = WebSocketSessionBinding(
            session_ref=f"ws_session:{token_urlsafe(24)}",
            principal_ref=credential.principal_ref,
            allowed_actor_refs=credential.allowed_actor_refs,
            allowed_government_drought_advisory_jurisdiction_refs=(
                credential.allowed_government_drought_advisory_jurisdiction_refs
            ),
            connection_epoch=self._next_connection_epoch,
            lease_expires_at=credential.expires_at,
        )
        self._next_connection_epoch += 1
        self._bindings[binding.session_ref] = binding
        return WebSocketSessionBindResult(accepted=True, binding=binding)

    def resolve_binding(self, session_ref: str) -> WebSocketSessionBinding | None:
        return self._bindings.get(session_ref)

    def lifecycle_record(self, session_ref: str) -> WebSocketSessionLifecycleRecord | None:
        return self._closed_bindings.get(session_ref)

    def revoke_enrollment(self, credential: str) -> bool:
        """Server-only invalidation for an unconsumed opaque enrollment."""

        record = self._trusted_credentials.get(credential)
        if record is None or record.used:
            return False
        record.revoked = True
        return True

    def issue_replacement_enrollment(self, session_ref: str, now: int) -> WebSocketSessionEnrollment:
        """Replace an active binding with a fresh opaque enrollment chosen from backend state."""

        binding = self._bindings.get(session_ref)
        if binding is None:
            raise ValueError("websocket_session_renewal_required")
        if binding.lease_expires_at < now:
            self._close_binding(binding, state="expired", reason_code="session_expired", now=now)
            raise ValueError("websocket_session_renewal_required")
        self._close_binding(binding, state="renewal_due", reason_code="renewal_enrollment_issued", now=now)
        credential = self.create_trusted_local_launch_credential(
            principal_ref=binding.principal_ref,
            allowed_actor_refs=self._renewal_scope_selector(binding),
            allowed_government_drought_advisory_jurisdiction_refs=(
                binding.allowed_government_drought_advisory_jurisdiction_refs
            ),
            issued_at=now,
            expires_at=binding.lease_expires_at,
        )
        return WebSocketSessionEnrollment(
            credential_kind="trusted_local_launch",
            credential=credential,
            protocol_version=1,
        )

    def revoke_session(self, session_ref: str, *, reason_code: str, now: int) -> bool:
        binding = self._bindings.get(session_ref)
        if binding is None:
            return False
        self._close_binding(binding, state="revoked", reason_code=reason_code, now=now)
        return True

    def disconnect_session(self, session_ref: str, *, now: int) -> bool:
        binding = self._bindings.get(session_ref)
        if binding is None:
            return False
        self._close_binding(binding, state="disconnected", reason_code="websocket_disconnected", now=now)
        return True

    def _close_binding(
        self,
        binding: WebSocketSessionBinding,
        *,
        state: Literal["renewal_due", "revoked", "expired", "disconnected"],
        reason_code: str,
        now: int,
    ) -> None:
        self._bindings.pop(binding.session_ref, None)
        self._closed_bindings[binding.session_ref] = WebSocketSessionLifecycleRecord(
            session_ref=binding.session_ref,
            binding_state=state,
            reason_code=reason_code,
            occurred_at=now,
        )
