"""Verify deployment-provisioned world-admin service credentials."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from hmac import compare_digest

from app.config import WorldAdminCredentialSettings


@dataclass(frozen=True)
class WorldAdminIdentity:
    credential_ref: str
    principal_ref: str
    world_ref: str


class WorldAdminCredentialVerifier:
    def __init__(self, credentials: tuple[WorldAdminCredentialSettings, ...]) -> None:
        refs = [item.credential_ref for item in credentials]
        digests = [sha256(item.secret.encode("utf-8")).digest() for item in credentials]
        if len(refs) != len(set(refs)) or len(digests) != len(set(digests)):
            raise ValueError("world_admin_credential_duplicate")
        self._credentials = tuple(
            (item.credential_ref, item.principal_ref, item.world_refs, item.expires_at, digest)
            for item, digest in zip(credentials, digests)
        )

    @property
    def enabled(self) -> bool:
        return bool(self._credentials)

    def authenticate(self, token: str | None, *, world_ref: str, now: int) -> WorldAdminIdentity | None:
        if not isinstance(token, str) or not token or not isinstance(world_ref, str) or not world_ref:
            return None
        if type(now) is not int or now < 0:
            return None
        candidate = sha256(token.encode("utf-8")).digest()
        matched = None
        for credential_ref, principal_ref, worlds, expires_at, digest in self._credentials:
            if compare_digest(candidate, digest) and world_ref in worlds and now <= expires_at:
                matched = WorldAdminIdentity(
                    credential_ref=credential_ref, principal_ref=principal_ref, world_ref=world_ref)
        return matched
