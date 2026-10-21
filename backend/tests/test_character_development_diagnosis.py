from __future__ import annotations

import copy
import hashlib
import json

import pytest

from scripts.verification.diagnose_character_development import (
    build_variants,
    ordered_digest,
    validate_variant,
)


def row():
    return {
        "scenario_id": "archive-scratches", "actor_id": "char_a", "split": "development",
        "provider_request": {"context": {"candidate_intents": ["a", "b"], "candidate_mapping": {
            "a": {"candidate_id": "a", "wire_label": "a", "action_family": "observe", "target_refs": {"target": "door"}},
            "b": {"candidate_id": "b", "wire_label": "b", "action_family": "defer", "target_refs": {"target": "door"}}},
            "effective_profile_summary": "character_id=char_a; canonical_name=Lin Yue; occupation_role=archive attendant",
            "provider_revision": "p"}},
        "wire_request": {"questions": {"choice": {"criteria": {"a": "a", "b": "b"}}}},
    }


def test_ordered_digest_distinguishes_mapping_order():
    assert ordered_digest({"a": 1, "b": 2}) != ordered_digest({"b": 2, "a": 1})
    assert ordered_digest({"a": 1}) == hashlib.sha256(b'{"a":1}').hexdigest()


def test_unknown_variant_rejected_and_single_variable_validated():
    with pytest.raises(ValueError, match="unknown_variant"):
        validate_variant(row(), "wat")
    variants = build_variants([row()])
    assert {v["variant"] for v in variants} == {"baseline-repeat", "descriptions", "anonymous-summary"}
    for item in variants:
        validate_variant(item["row"], item["variant"])


def test_variants_preserve_mapping_and_only_expected_fields_change():
    base = row()
    variants = {v["variant"]: v["row"] for v in build_variants([base])}
    assert variants["descriptions"]["provider_request"]["context"]["candidate_mapping"] == base["provider_request"]["context"]["candidate_mapping"]
    assert "character_id=" not in variants["anonymous-summary"]["provider_request"]["context"]["effective_profile_summary"]
    assert "canonical_name=" not in variants["anonymous-summary"]["provider_request"]["context"]["effective_profile_summary"]
