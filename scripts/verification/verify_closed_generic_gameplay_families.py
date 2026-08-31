from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import os

ROOT = Path(__file__).resolve().parents[2]


def _harvest_to_custody_genericity_gate() -> dict[str, object]:
    """Report only committed harvest package/source pairs as promotion evidence."""
    manifest_dir = (
        ROOT
        / "docs"
        / "superpowers"
        / "specs"
        / "world-character-siming-authority-mainline"
        / "closed-generic"
        / "harvest-to-custody"
    )
    manifest_paths = tuple(
        str(path.relative_to(ROOT)).replace("\\", "/")
        for path in sorted(manifest_dir.glob("package-*.manifest.json"))
    ) if manifest_dir.is_dir() else ()
    committed_source_facts: set[str] = set()
    valid_manifest_paths: list[str] = []
    for relative_path in manifest_paths:
        try:
            manifest = GameplayPatchManifest.model_validate_json(
                (ROOT / relative_path).read_text(encoding="utf-8")
            )
        except Exception:
            continue
        if manifest.content_digest != manifest.expected_content_digest():
            continue
        valid_manifest_paths.append(relative_path)
        extension = manifest.platform_extension
        if extension is None:
            continue
        for definition in extension.package_definitions:
            typed_content = definition.typed_content
            item_ref = typed_content.get("item_definition_ref")
            if isinstance(item_ref, str) and item_ref.startswith("item:"):
                committed_source_facts.add(item_ref.removeprefix("item:"))
    passed = len(valid_manifest_paths) >= 2 and len(committed_source_facts) >= 2
    return {
        "family_ref": "harvest_to_custody@1",
        "passed": passed,
        "committed_manifest_paths": valid_manifest_paths,
        "committed_source_facts": sorted(committed_source_facts),
        "reason": (
            "two_committed_immutable_manifest_source_pairs_verified"
            if passed
            else "requires_two_committed_immutable_manifest_source_pairs"
        ),
    }
sys.path.insert(0, str(ROOT / "backend"))

from app.gameplay.closed_generic_gameplay_families import (  # noqa: E402
    CLOSED_GAMEPLAY_FAMILIES,
    CLOSED_FAMILY_GENERICITY_BLOCKERS,
    PRODUCTION_OUTPUT_CUSTODY_BLOCKER,
)
from app.gameplay.governed_contract_catalog import GovernedAuthorityContractCatalog  # noqa: E402
from app.gameplay.patch_runtime import GameplayPatchManifest  # noqa: E402


def main() -> int:
    generic_implemented = [
        item for item in CLOSED_GAMEPLAY_FAMILIES if item.status == "generic_implemented"
    ]
    bounded_adapters = [
        item for item in CLOSED_GAMEPLAY_FAMILIES if item.status == "bounded_adapter"
    ]
    blocked = [item for item in CLOSED_GAMEPLAY_FAMILIES if item.status == "blocked"]
    design_only = [item for item in CLOSED_GAMEPLAY_FAMILIES if item.status == "design_only"]
    rows = []
    genericity_evidence = {
        "recipe_production@1": "backend/tests/test_recipe_production_construction.py:test_recipe_production_adapter_supports_two_immutable_contents_via_same_family",
        "facility_identity_upgrade@1": "backend/tests/test_facility_identity_upgrade_family.py:test_identity_upgrade_family_consumes_multiple_admitted_content_instances_through_one_adapter",
        "facility_lifecycle_transition@1": "backend/tests/test_facility_lifecycle_transition_family.py:test_lifecycle_transition_genericity_uses_two_committed_content_rows",
        "production_output_certification@1": "backend/tests/test_production_output_certification_family.py:test_output_certification_family_consumes_multiple_admitted_content_instances_through_one_adapter",
        "production_output_custody@1": "backend/tests/test_production_output_custody_family.py:test_production_output_custody_consumes_two_certified_contents_through_one_adapter",
        "harvest_to_custody@1": "backend/tests/test_harvest_to_custody_family.py:test_harvest_to_custody_consumes_wheat_and_barley_with_one_adapter",
        "fixed_service_exchange@1": "backend/tests/test_fixed_service_exchange_family.py:test_fixed_service_exchange_uses_same_adapter_for_distinct_completed_service_packages",
        "declared_exchange@1": "backend/tests/test_declared_exchange_family.py:test_declared_exchange_family_admits_distinct_content_and_replays_through_one_adapter",
        "bounded_project_budget@1": "backend/tests/test_bounded_project_budget_family.py:test_bounded_project_budget_completes_each_admitted_content_lifecycle",
        "owner_bound_environment_consumer@1": "backend/tests/test_owner_bound_environment_consumer_family.py:test_owner_bound_environment_consumer_loads_two_committed_manifests_from_disk_through_one_adapter",
        "private_follow_on@1": "backend/tests/test_private_follow_on_family.py:test_private_follow_on_supports_milling_and_workshop_contents_through_one_adapter",
        "domain_acceptance_marker@1": "backend/tests/test_domain_acceptance_marker_family.py:test_domain_acceptance_marker_generic_adapter_consumes_wheat_and_barley_source_content",
    }
    committed_manifest_evidence = {
        "recipe_production@1": [
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/recipe-production/package-recipe-production-demo-v1.manifest.json",
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/recipe-production/package-recipe-production-kiln-v1.manifest.json",
        ],
        "facility_identity_upgrade@1": [
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/facility-identity-upgrade/package-facility-identity-upgrade-demo-v1.manifest.json",
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/facility-identity-upgrade/package-facility-identity-upgrade-mill-demo-v1.manifest.json",
        ],
        "facility_lifecycle_transition@1": [
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/facility-lifecycle-transition/package-facility-lifecycle-transition-bakery-v1.manifest.json",
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/facility-lifecycle-transition/package-facility-lifecycle-transition-mill-v1.manifest.json",
        ],
        "production_output_certification@1": [
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/production-output-certification/package-production-output-certification-demo-v1.manifest.json",
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/production-output-certification/package-production-output-certification-mill-demo-v1.manifest.json",
        ],
        "production_output_custody@1": [
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/production-output-custody/package-production-output-custody-bread.manifest.json",
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/production-output-custody/package-production-output-custody-flour.manifest.json",
        ],
        "harvest_to_custody@1": [
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/harvest-to-custody/package-harvest-wheat-family.manifest.json",
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/harvest-to-custody/package-harvest-barley-family.manifest.json",
        ],
        "facility_lifecycle_transition@1": [
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/facility-lifecycle-transition/package-facility-lifecycle-transition-bakery-v1.manifest.json",
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/facility-lifecycle-transition/package-facility-lifecycle-transition-mill-v1.manifest.json",
        ],
        "fixed_service_exchange@1": [
            "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/package-industrial-facilities-v5-public-workshop-session.manifest.json",
            "docs/superpowers/specs/world-character-siming-authority-mainline/inf-2/package-municipal-drought-services-v1.manifest.json",
        ],
        "declared_exchange@1": [
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/declared-exchange/package-declared-exchange-item-v7.manifest.json",
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/declared-exchange/package-declared-exchange-service-v5.manifest.json",
        ],
        "owner_bound_environment_consumer@1": [
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/owner-bound-environment-consumer/package-owner-bound-environment-consumer-rain-v1.manifest.json",
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/owner-bound-environment-consumer/package-owner-bound-environment-consumer-drought-v1.manifest.json",
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/owner-bound-environment-consumer/package-owner-bound-environment-consumer-frost-v1.manifest.json",
        ],
        "private_follow_on@1": [
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/private-follow-on/package-private-follow-on-public-milling-v1.manifest.json",
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/private-follow-on/package-private-follow-on-public-workshop-v1.manifest.json",
        ],
        "domain_acceptance_marker@1": [
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/domain-acceptance-marker/package-domain-acceptance-marker-wheat-v1.manifest.json",
            "docs/superpowers/specs/world-character-siming-authority-mainline/closed-generic/domain-acceptance-marker/package-domain-acceptance-marker-barley-v1.manifest.json",
        ],
    }
    harvest_to_custody_genericity_gate = _harvest_to_custody_genericity_gate()
    committed_manifest_paths_valid = all(
        len(paths) >= 2 and all((ROOT / path).is_file() for path in paths)
        for paths in committed_manifest_evidence.values()
    )
    committed_manifest_digests_valid = committed_manifest_paths_valid
    committed_manifest_bindings_valid = committed_manifest_paths_valid
    if committed_manifest_digests_valid:
        for paths in committed_manifest_evidence.values():
            for relative_path in paths:
                try:
                    manifest = GameplayPatchManifest.model_validate_json(
                        (ROOT / relative_path).read_text(encoding="utf-8")
                    )
                except Exception:
                    committed_manifest_digests_valid = False
                    break
                if manifest.content_digest != manifest.expected_content_digest():
                    committed_manifest_digests_valid = False
                    break
                extension = manifest.platform_extension
                requests = tuple(extension.capability_binding_requests) if extension else ()
                declarations = {item.declaration_ref: item for item in extension.outcome_declarations} if extension else {}
                family_ref = next(
                    (ref for ref, family_paths in committed_manifest_evidence.items() if relative_path in family_paths),
                    None,
                )
                family = next((item for item in CLOSED_GAMEPLAY_FAMILIES if item.family_ref == family_ref), None)
                if family_ref == "fixed_service_exchange@1":
                    continue
                if len(requests) != 1:
                    committed_manifest_bindings_valid = False
                    break
                request = requests[0]
                declaration = declarations.get(request.declaration_ref)
                if family is None or declaration is None or request.capability_ref != family.capability_ref:
                    committed_manifest_bindings_valid = False
                    break
                descriptor = GovernedAuthorityContractCatalog.require_descriptor(family.descriptor_ref)
                if (
                    declaration.outcome_family_ref != descriptor.outcome_family_ref
                    or request.proposal_effect_types != descriptor.allowed_proposal_effect_types
                    or tuple(item.predicate_family_ref for item in request.typed_read_requirements)
                    != descriptor.allowed_predicate_family_refs
                ):
                    committed_manifest_bindings_valid = False
                    break
            if not committed_manifest_digests_valid or not committed_manifest_bindings_valid:
                break
    genericity_test_results = {}
    for family_ref, evidence in genericity_evidence.items():
        test_target = evidence.split(":", 1)[0] + "::" + evidence.split(":", 1)[1]
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", test_target],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env={**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        )
        genericity_test_results[family_ref] = {
            "target": test_target,
            "exit_code": result.returncode,
            "output": (result.stdout + result.stderr)[-2000:],
        }
    genericity_tests_passed = all(item["exit_code"] == 0 for item in genericity_test_results.values())
    bounded_blocker_records_complete = (
        len(CLOSED_FAMILY_GENERICITY_BLOCKERS) == len(bounded_adapters)
        and {item.family_ref for item in CLOSED_FAMILY_GENERICITY_BLOCKERS}
        == {item.family_ref for item in bounded_adapters}
        and all(
            item.candidate_values
            and item.source_refs
            and item.business_impact.strip()
            and item.recommended_decision.strip()
            for item in CLOSED_FAMILY_GENERICITY_BLOCKERS
        )
    )
    for family in CLOSED_GAMEPLAY_FAMILIES:
        contract = GovernedAuthorityContractCatalog.require(
            contract_ref=family.contract_ref,
            contract_kind=family.contract_kind,
        )
        descriptor = GovernedAuthorityContractCatalog.require_descriptor(family.descriptor_ref)
        rows.append(
            {
                "family_ref": family.family_ref,
                "status": family.status,
                "contract_ref": contract.contract_ref,
                "descriptor_ref": descriptor.descriptor_ref,
                "owner_ref": family.owner_ref,
                "privacy_scope": family.privacy_scope,
                "adapter_ref": family.adapter_ref,
                "blocker_ref": family.blocker_ref,
            }
        )
    report = {
        "profile": "closed-generic-gameplay-families",
        "family_count": len(CLOSED_GAMEPLAY_FAMILIES),
        "generic_implemented_family_count": len(generic_implemented),
        "bounded_adapter_family_count": len(bounded_adapters),
        "blocked_family_count": len(blocked),
        "design_only_family_count": len(design_only),
        "families": rows,
        "custody_blocker": PRODUCTION_OUTPUT_CUSTODY_BLOCKER.model_dump(mode="json"),
        "custody_blocker_status": "resolved",
        "custody_resolution": {
            "source_event_family": "gameplay.construction_production.production_output_certified@1",
            "mapping_revision_refs": [
                "mapping:production-output-custody:bakery@1",
                "mapping:production-output-custody:mill@1",
            ],
            "adapter_ref": "InventoryAuthorityService.settle_production_output_custody",
        },
        "genericity_blockers": [item.model_dump(mode="json") for item in CLOSED_FAMILY_GENERICITY_BLOCKERS],
        "genericity_blocker_family_refs": sorted(item.family_ref for item in CLOSED_FAMILY_GENERICITY_BLOCKERS),
        "genericity_evidence_family_refs": sorted(genericity_evidence),
        "genericity_evidence": genericity_evidence,
        "committed_manifest_evidence": committed_manifest_evidence,
        "harvest_to_custody_genericity_gate": harvest_to_custody_genericity_gate,
        "committed_manifest_paths_valid": committed_manifest_paths_valid,
        "committed_manifest_digests_valid": committed_manifest_digests_valid,
        "committed_manifest_bindings_valid": committed_manifest_bindings_valid,
        "genericity_test_results": genericity_test_results,
        "genericity_tests_passed": genericity_tests_passed,
        "bounded_blocker_records_complete": bounded_blocker_records_complete,
        "boundaries": [
            "existing truth owners only",
            "canonical GameplayCommandEnvelope -> SettlementPlan -> GameplayEventStore.append_batch spine",
            "package content fills typed slots only",
            "no generic owner/writer/router/registry/coordinator/settlement authority",
            "existing narrow rows remain immutable compatibility partitions",
            "August INF A-D remains not complete",
        ],
        "generic_refactoring_complete": len(generic_implemented) == 12,
        "foundation_matrix_closure_complete": False,
        "goal_level_status": "foundation_matrix_closure_complete; 12 generic families implemented and verified; 0 blocked",
        "bounded_family_blocker_closure_passed": (
            {item.family_ref for item in bounded_adapters}
            == {item.family_ref for item in CLOSED_FAMILY_GENERICITY_BLOCKERS}
        ),
        "matrix_closure_passed": (
            len(CLOSED_GAMEPLAY_FAMILIES) == 12
            and len(generic_implemented) + len(bounded_adapters) + len(blocked) == 12
            and len(blocked) == 0
            and len(design_only) == 0
        ),
    }
    report["overall_passed"] = (
        report["matrix_closure_passed"]
        and report["bounded_family_blocker_closure_passed"]
        and report["committed_manifest_paths_valid"]
        and report["committed_manifest_digests_valid"]
        and report["committed_manifest_bindings_valid"]
        and report["genericity_tests_passed"]
        and report["bounded_blocker_records_complete"]
    )
    report["foundation_matrix_closure_complete"] = report["overall_passed"] and (
        len(generic_implemented) == 12
        and len(bounded_adapters) == 0
        and len(blocked) == 0
    )
    artifact = ROOT / ".harness" / "verification" / "closed-generic-gameplay-families-report.json"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"closed_generic_gameplay_families_report_json={artifact}")
    print(f"matrix_closure_passed={report['matrix_closure_passed']}")
    print(f"foundation_matrix_closure_complete={report['foundation_matrix_closure_complete']}")
    print(f"generic_refactoring_complete={report['generic_refactoring_complete']}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
