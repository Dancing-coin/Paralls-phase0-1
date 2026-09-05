from __future__ import annotations

from app.gameplay.p5.scripted_mystery_content import CaseContentAdmissionResult, stormnight_case_content
from app.gameplay.p5.scripted_mystery_case_package import build_stormnight_case_package


def test_second_content_variant_uses_same_case_adapter() -> None:
    first = stormnight_case_content()
    second = first.model_copy(update={"case_ref": "case:stormnight-copper-annex@1", "case_revision": "case:stormnight-copper-annex@1", "package_ref": "package:stormnight-copper-annex@1", "package_revision": "package:stormnight-copper-annex:v1@1", "location_ref": "location:stormnight-copper-annex@1", "provenance_note": "Original second content variant; no source text copied."}, deep=True)
    assert second.case_ref != first.case_ref
    assert CaseContentAdmissionResult.admit(second, admitted_action_graph_refs=second.action_graph_refs, admitted_predicate_refs=("predicate:stormnight:inspect@1", "predicate:stormnight:phase-transition@1")).accepted
    package = build_stormnight_case_package(second)
    assert package.manifest.patch_revision_id == second.package_revision
