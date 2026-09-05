from __future__ import annotations

import pytest

from app.gameplay.p5.scripted_mystery_case_package import (
    build_stormnight_case_package,
    load_stormnight_case_package,
    resolve_exact_one_binding,
    install_stormnight_case_package,
)
from app.gameplay.patch_runtime import GameplayPatchRegistry


def test_stormnight_package_is_v3_platform_2_and_digest_verified() -> None:
    package = load_stormnight_case_package()
    assert package.manifest.manifest_schema_version == 3
    assert package.manifest.platform_extension is not None
    assert package.manifest.platform_extension.platform_schema_version == "2.0"
    assert package.manifest.content_digest == package.manifest.expected_content_digest()
    assert package.binding.descriptor_ref == "descriptor:scripted-mystery-case@1"
    assert package.binding.privacy_scope == "project"


def test_untrusted_digest_claims_are_rejected() -> None:
    with pytest.raises(ValueError, match="content_digest_claim_mismatch"):
        build_stormnight_case_package(untrusted_content_digest_claim="sha256:" + "f" * 64)
    with pytest.raises(ValueError, match="declaration_digest_claim_mismatch"):
        build_stormnight_case_package(untrusted_declaration_digest_claim="sha256:" + "f" * 64)


def test_binding_resolution_is_exactly_one() -> None:
    package = load_stormnight_case_package()
    assert resolve_exact_one_binding((package.binding,), package.binding.binding_ref) == package.binding
    with pytest.raises(ValueError, match="exact_one"):
        resolve_exact_one_binding((), package.binding.binding_ref)
    with pytest.raises(ValueError, match="exact_one"):
        resolve_exact_one_binding((package.binding, package.binding), package.binding.binding_ref)


def test_package_content_is_immutable_and_package_revision_pinned() -> None:
    package = load_stormnight_case_package()
    with pytest.raises((TypeError, ValueError)):
        package.content.case_ref = "case:changed@1"  # type: ignore[misc]
    assert package.binding.package_revision == package.manifest.patch_revision_id


def test_package_installs_as_exact_one_active_binding() -> None:
    registry = GameplayPatchRegistry(trusted_authors=frozenset({"author:repo"}))
    package = install_stormnight_case_package(registry)
    assert registry.active_patch_set is not None
    matches = tuple(binding for binding in registry.active_patch_set.capability_bindings if binding.binding_ref == package.binding.binding_ref)
    assert len(matches) == 1
    assert matches[0].descriptor_ref == package.binding.descriptor_ref
