from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATHS = (
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "closed-generic"
    / "recipe-production"
    / "package-recipe-production-demo-v1.manifest.json",
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "closed-generic"
    / "recipe-production"
    / "package-recipe-production-kiln-v1.manifest.json",
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "closed-generic"
    / "facility-identity-upgrade"
    / "package-facility-identity-upgrade-demo-v1.manifest.json",
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "closed-generic"
    / "facility-identity-upgrade"
    / "package-facility-identity-upgrade-mill-demo-v1.manifest.json",
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "closed-generic"
    / "production-output-certification"
    / "package-production-output-certification-demo-v1.manifest.json",
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "closed-generic"
    / "production-output-certification"
    / "package-production-output-certification-mill-demo-v1.manifest.json",
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "closed-generic"
    / "owner-bound-environment-consumer"
    / "package-owner-bound-environment-consumer-rain-v1.manifest.json",
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "closed-generic"
    / "owner-bound-environment-consumer"
    / "package-owner-bound-environment-consumer-drought-v1.manifest.json",
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "closed-generic"
    / "owner-bound-environment-consumer"
    / "package-owner-bound-environment-consumer-frost-v1.manifest.json",
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "closed-generic"
    / "harvest-to-custody"
    / "package-harvest-wheat-family.manifest.json",
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "closed-generic"
    / "harvest-to-custody"
    / "package-harvest-barley-family.manifest.json",
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "closed-generic"
    / "facility-lifecycle-transition"
    / "package-facility-lifecycle-transition-mill-v1.manifest.json",
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "closed-generic"
    / "facility-lifecycle-transition"
    / "package-facility-lifecycle-transition-bakery-v1.manifest.json",
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "closed-generic"
    / "declared-exchange"
    / "package-declared-exchange-item-v7.manifest.json",
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "closed-generic"
    / "declared-exchange"
    / "package-declared-exchange-service-v5.manifest.json",
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "closed-generic"
    / "private-follow-on"
    / "package-private-follow-on-public-milling-v1.manifest.json",
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "closed-generic"
    / "private-follow-on"
    / "package-private-follow-on-public-workshop-v1.manifest.json",
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "closed-generic"
    / "domain-acceptance-marker"
    / "package-domain-acceptance-marker-wheat-v1.manifest.json",
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "closed-generic"
    / "domain-acceptance-marker"
    / "package-domain-acceptance-marker-barley-v1.manifest.json",
)


def test_closed_generic_manifests_are_committed_files() -> None:
    for path in MANIFEST_PATHS:
        assert path.is_file(), path
