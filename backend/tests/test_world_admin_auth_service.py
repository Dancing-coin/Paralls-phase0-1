"""Deployment-provisioned admin identity is separate from local launch credentials."""

import pytest
from pydantic import ValidationError

from app.config import WorldAdminCredentialSettings
from app.services.world_admin_auth_service import WorldAdminCredentialVerifier


def _credential(**updates):
    values = dict(
        credential_ref="credential:bakery-admin:v1",
        principal_ref="principal:bakery-admin",
        world_refs=("world:bakery",),
        secret="a" * 40,
        expires_at=200,
    )
    values.update(updates)
    return WorldAdminCredentialSettings(**values)


def test_configured_admin_credential_authenticates_named_world_scope() -> None:
    credential = _credential()
    verifier = WorldAdminCredentialVerifier((credential,))
    identity = verifier.authenticate("a" * 40, world_ref="world:bakery", now=200)
    assert identity is not None
    assert identity.credential_ref == "credential:bakery-admin:v1"
    assert identity.principal_ref == "principal:bakery-admin"
    assert identity.world_ref == "world:bakery"
    assert "a" * 40 not in credential.model_dump_json()
    assert "a" * 40 not in repr(credential)
    assert "a" * 40 not in repr(verifier)


@pytest.mark.parametrize("token,world,now", [
    (None, "world:bakery", 100),
    ("wrong", "world:bakery", 100),
    ("a" * 40, "world:other", 100),
    ("a" * 40, "world:bakery", 201),
])
def test_missing_invalid_cross_world_or_expired_credential_is_denied(token, world, now) -> None:
    verifier = WorldAdminCredentialVerifier((_credential(),))
    assert verifier.authenticate(token, world_ref=world, now=now) is None
    assert WorldAdminCredentialVerifier(()).authenticate(token, world_ref=world, now=now) is None


@pytest.mark.parametrize("updates", [
    {"secret": "too-short"},
    {"world_refs": ()},
    {"principal_ref": ""},
    {"credential_ref": ""},
])
def test_admin_credential_requires_explicit_strong_identity_and_scope(updates) -> None:
    with pytest.raises(ValidationError):
        _credential(**updates)


def test_duplicate_admin_credential_references_or_secrets_are_rejected() -> None:
    with pytest.raises(ValueError, match="world_admin_credential_duplicate"):
        WorldAdminCredentialVerifier((_credential(), _credential(principal_ref="principal:other")))


def test_admin_credentials_load_from_deployment_environment_without_public_secret(monkeypatch):
    import json
    from pathlib import Path
    import subprocess
    import sys

    monkeypatch.setenv("WORLD_ADMIN_CREDENTIALS_JSON", json.dumps([dict(
        credential_ref="credential:env-admin:v1", principal_ref="principal:env-admin",
        world_refs=["world:bakery-district"], secret="c" * 40, expires_at=200,
    )]))
    script = """
from app.config import settings
from app.services.world_admin_auth_service import WorldAdminCredentialVerifier
credential, = settings.world_admin_credentials
identity = WorldAdminCredentialVerifier((credential,)).authenticate(
    credential.secret, world_ref='world:bakery-district', now=100)
assert identity.principal_ref == 'principal:env-admin'
assert identity.credential_ref == 'credential:env-admin:v1'
assert credential.secret not in settings.model_dump_json() + repr(settings) + repr(credential)
print('deployment-configured')
"""
    result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True, timeout=15)
    assert "c" * 40 not in result.stdout + result.stderr
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "deployment-configured"


@pytest.mark.parametrize("source", ["environment", "bootstrap"])
@pytest.mark.parametrize("invalid", ["missing_identity", "short_secret"])
def test_invalid_admin_configuration_never_logs_secret(monkeypatch, source, invalid):
    import json
    from pathlib import Path
    import subprocess
    import sys

    secret = "invalid-admin-secret" if invalid == "short_secret" else "ADMIN_SECRET_CANARY" + "x" * 16
    credential = dict(secret=secret)
    if invalid == "short_secret":
        credential.update(credential_ref="credential:test", principal_ref="principal:test",
                          world_refs=["world:test"], expires_at=200)
    monkeypatch.delenv("WORLD_ADMIN_CREDENTIALS_JSON", raising=False)
    if source == "environment":
        monkeypatch.setenv("WORLD_ADMIN_CREDENTIALS_JSON", json.dumps([credential]))
        script = "from app.config import settings"
    else:
        # Same nested validation used when the child accepts trusted bootstrap settings.
        script = ("from app.config import Settings\n"
                  "import sys\nSettings.model_validate_json(sys.stdin.read())")
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[1],
        input=json.dumps(dict(world_admin_credentials=[credential])),
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode != 0
    assert "ValidationError" in result.stderr
    assert secret not in result.stdout + result.stderr
    assert "ADMIN_SECRET_CANARY" not in result.stdout + result.stderr
