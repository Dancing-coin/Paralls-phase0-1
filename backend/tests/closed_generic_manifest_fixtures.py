from __future__ import annotations

import json
from pathlib import Path

from app.gameplay.patch_runtime import GameplayPatchManifest


ROOT = Path(__file__).resolve().parents[2]
BASE_DIR = (
    ROOT
    / "docs"
    / "superpowers"
    / "specs"
    / "world-character-siming-authority-mainline"
    / "closed-generic"
)

MANIFEST_PATHS = {
    "recipe-production-demo-v1": BASE_DIR / "recipe-production" / "package-recipe-production-demo-v1.manifest.json",
    "recipe-production-kiln-v1": BASE_DIR / "recipe-production" / "package-recipe-production-kiln-v1.manifest.json",
    "facility-identity-upgrade-demo-v1": BASE_DIR
    / "facility-identity-upgrade"
    / "package-facility-identity-upgrade-demo-v1.manifest.json",
    "facility-identity-upgrade-mill-demo-v1": BASE_DIR
    / "facility-identity-upgrade"
    / "package-facility-identity-upgrade-mill-demo-v1.manifest.json",
    "production-output-certification-demo-v1": BASE_DIR
    / "production-output-certification"
    / "package-production-output-certification-demo-v1.manifest.json",
    "production-output-certification-mill-demo-v1": BASE_DIR
    / "production-output-certification"
    / "package-production-output-certification-mill-demo-v1.manifest.json",
    "facility-lifecycle-transition-mill-v1": BASE_DIR
    / "facility-lifecycle-transition"
    / "package-facility-lifecycle-transition-mill-v1.manifest.json",
    "facility-lifecycle-transition-bakery-v1": BASE_DIR
    / "facility-lifecycle-transition"
    / "package-facility-lifecycle-transition-bakery-v1.manifest.json",
    "owner-bound-environment-consumer-rain-v1": BASE_DIR / "owner-bound-environment-consumer" / "package-owner-bound-environment-consumer-rain-v1.manifest.json",
    "owner-bound-environment-consumer-drought-v1": BASE_DIR / "owner-bound-environment-consumer" / "package-owner-bound-environment-consumer-drought-v1.manifest.json",
    "owner-bound-environment-consumer-frost-v1": BASE_DIR / "owner-bound-environment-consumer" / "package-owner-bound-environment-consumer-frost-v1.manifest.json",
    "declared-exchange-item-v7": BASE_DIR / "declared-exchange" / "package-declared-exchange-item-v7.manifest.json",
    "declared-exchange-service-v5": BASE_DIR / "declared-exchange" / "package-declared-exchange-service-v5.manifest.json",
    "bounded-project-budget-workshop-v1": BASE_DIR
    / "bounded-project-budget"
    / "package-bounded-project-budget-workshop-v1.manifest.json",
    "bounded-project-budget-maintenance-v1": BASE_DIR
    / "bounded-project-budget"
    / "package-bounded-project-budget-maintenance-v1.manifest.json",
}


def manifest_path(key: str) -> Path:
    return MANIFEST_PATHS[key]


def load_manifest_payload(key: str) -> dict[str, object]:
    return json.loads(manifest_path(key).read_text(encoding="utf-8"))


def load_manifest(key: str) -> GameplayPatchManifest:
    return GameplayPatchManifest.model_validate(load_manifest_payload(key))
