"""Backend-owned WebSocket session identity and actor read-scope grants."""

from __future__ import annotations

from dataclasses import dataclass
from secrets import token_urlsafe
from time import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


CredentialKind = Literal["trusted_local_launch", "authenticated_session"]
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


class WebSocketSessionEnrollment(BaseModel):
    """Untrusted enrollment request; authority subjects live in the credential."""

    model_config = ConfigDict(extra="forbid")

    credential_kind: CredentialKind
    credential: str = Field(min_length=1)
    protocol_version: int = Field(ge=1)


class WebSocketSessionBinding(BaseModel):
    """Opaque backend-issued session identity with a fixed multi-actor read scope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    session_ref: str
    principal_ref: str
    allowed_actor_refs: tuple[str, ...]


class WebSocketSessionBindResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    binding: WebSocketSessionBinding | None = None
    error_code: str = ""


class _TrustedLocalSessionCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")

    principal_ref: str
    allowed_actor_refs: tuple[str, ...]
    issued_at: int
    expires_at: int
    used: bool = False


@dataclass
class WebSocketConnectionContext:
    """Connection-local transport facts; it is never a world-authority context."""

    remote_host: str
    observed_at: int
    connection_ref: str = ""
    binding: WebSocketSessionBinding | None = None

    @classmethod
    def direct_handler_compatibility(cls) -> "WebSocketConnectionContext":
        """Keeps direct handler tests separate from a real network connection."""

        return cls(remote_host="127.0.0.1", observed_at=int(time()), connection_ref="direct_handler")


class WebSocketSessionAuthService:
    """Issues opaque connection bindings without importing controller execution policy."""

    def __init__(self, *, authenticated_session_adapter_configured: bool = False) -> None:
        self.authenticated_session_adapter_configured = authenticated_session_adapter_configured
        self._trusted_credentials: dict[str, _TrustedLocalSessionCredential] = {}
        self._bindings: dict[str, WebSocketSessionBinding] = {}

    def create_trusted_local_launch_credential(
        self,
        *,
        principal_ref: str,
        allowed_actor_refs: tuple[str, ...],
        issued_at: int,
        expires_at: int,
    ) -> str:
        if not principal_ref or not allowed_actor_refs or any(not actor_ref for actor_ref in allowed_actor_refs):
            raise ValueError("trusted_local_session_subject_required")
        if expires_at < issued_at:
            raise ValueError("trusted_local_session_expiry_invalid")
        credential = f"trusted_local_launch:{token_urlsafe(24)}"
        self._trusted_credentials[credential] = _TrustedLocalSessionCredential(
            principal_ref=principal_ref,
            allowed_actor_refs=tuple(dict.fromkeys(allowed_actor_refs)),
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
        if credential.used:
            return WebSocketSessionBindResult(accepted=False, error_code="trusted_local_launch_already_used")
        if now > credential.expires_at:
            return WebSocketSessionBindResult(accepted=False, error_code="trusted_local_launch_expired")
        credential.used = True
        binding = WebSocketSessionBinding(
            session_ref=f"ws_session:{token_urlsafe(24)}",
            principal_ref=credential.principal_ref,
            allowed_actor_refs=credential.allowed_actor_refs,
        )
        self._bindings[binding.session_ref] = binding
        return WebSocketSessionBindResult(accepted=True, binding=binding)

    def resolve_binding(self, session_ref: str) -> WebSocketSessionBinding | None:
        return self._bindings.get(session_ref)
