import pytest

from app.character_agent.planning.l3_planner import CandidateCompiler


def _candidate(candidate_id: str, *, action_family: str = "observe", target: str = "obj:door", status: str = "satisfied"):
    return {
        "candidate_id": candidate_id,
        "action_id": "observe",
        "semantic_intent_id": "observe",
        "target_refs": {"target": target},
        "action_family": action_family,
        "required_conditions": {"visibility": status},
        "source_refs": ["registry:r1", "affordance:a1"],
    }


def test_candidate_compiler_keeps_legal_universe_and_audits_pruned_presented_set():
    result = CandidateCompiler().compile(
        candidates=[_candidate("c1"), _candidate("c2", target="obj:window")],
        envelope={"allowed_action_families": ["observe"], "max_candidate_intents": 1},
        visible_targets={"obj:door", "obj:window"},
    )

    assert [item["candidate_id"] for item in result.universe] == ["c1", "c2"]
    assert [item["candidate_id"] for item in result.presented] == ["c1"]
    assert result.pruned[0]["reason"] == "max_candidate_intents"
    assert result.coverage["universe_count"] == 2
    assert result.coverage["presented_count"] == 1


def test_candidate_compiler_diagnoses_unknown_visibility_and_blocked_without_presenting_them():
    result = CandidateCompiler().compile(
        candidates=[
            _candidate("unknown", status="unknown"),
            _candidate("blocked", status="blocked"),
            _candidate("hidden", target="obj:hidden"),
        ],
        envelope={"allowed_action_families": ["observe"], "max_candidate_intents": 5},
        visible_targets={"obj:door"},
    )

    assert result.universe == []
    assert result.presented == []
    reasons = {entry["reason"] for entry in result.diagnostics}
    assert {"condition_unknown", "condition_blocked", "target_not_visible"} <= reasons


def test_candidate_compiler_does_not_replace_missing_action_with_local_best_choice():
    result = CandidateCompiler().compile(
        candidates=[_candidate("wrong", action_family="forbidden")],
        envelope={"allowed_action_families": ["observe"], "max_candidate_intents": 5},
        visible_targets={"obj:door"},
    )

    assert result.universe == []
    assert result.presented == []
    assert result.diagnostics[0]["reason"] == "action_family_not_allowed"


def test_candidate_compiler_preserves_complete_candidate_record_and_separates_u_from_p():
    result = CandidateCompiler().compile(
        candidates=[{
            **_candidate("observe:obj:door"),
            "wire_label": "observe:obj:door",
            "semantic_action_id": "action:observe",
            "target_visibility": "visible",
            "target_provenance": ["l1:visible-targets:7"],
            "affordance_result": {"status": "available", "source": "affordance:door"},
            "owner_route": "esm:observation",
            "revision_pins": {"target_revision_vector": {"obj:door": 7}},
        }, _candidate("observe:window", target="obj:window")],
        envelope={"allowed_action_families": ["observe"], "max_candidate_intents": 1},
        policy={"reasoning": {"max_candidate_intents": 1}},
        visible_targets={"obj:door", "obj:window"},
    )

    assert len(result.universe) == 2
    assert len(result.presented) == 1
    frozen = result.presented[0]
    assert frozen["wire_label"] == "observe:obj:door"
    assert frozen["target_provenance"] == ["l1:visible-targets:7"]
    assert frozen["affordance_result"]["status"] == "available"
    assert frozen["owner_route"] == "esm:observation"
    assert frozen["revision_pins"]["target_revision_vector"]["obj:door"] == 7
    assert result.by_wire_label["observe:obj:door"]["candidate_id"] == "observe:obj:door"


def test_candidate_compiler_generates_semantic_description_without_answer_or_scoring_fields():
    result = CandidateCompiler().compile(
        candidates=[_candidate("observe:obj:door")],
        envelope={"allowed_action_families": ["observe"], "max_candidate_intents": 3},
        visible_targets={"obj:door"},
    )

    description = result.presented[0]["description"]
    assert "obj:door" in description
    assert "observe" in description.lower()
    forbidden = ("acceptable", "correct", "score", "rationale", "should choose", "gold")
    assert not any(term in description.lower() for term in forbidden)
    assert result.presented[0]["description"] != ""


def test_candidate_compiler_does_not_turn_unknown_or_unavailable_into_facts():
    candidate = _candidate("observe:obj:door", status="unknown")
    candidate["availability"] = "unknown"
    result = CandidateCompiler().compile(
        candidates=[candidate],
        envelope={"allowed_action_families": ["observe"], "max_candidate_intents": 3},
        visible_targets={"obj:door"},
    )

    assert result.presented == []
    assert all("confirmed" not in str(item).lower() for item in result.diagnostics)


def test_candidate_mapping_order_and_digest_are_reproducible_with_descriptions():
    candidates = [_candidate("first"), _candidate("second", target="obj:window")]
    compiler = CandidateCompiler()
    first = compiler.compile(candidates=candidates, envelope={"allowed_action_families": ["observe"]}, visible_targets={"obj:door", "obj:window"})
    second = compiler.compile(candidates=candidates, envelope={"allowed_action_families": ["observe"]}, visible_targets={"obj:door", "obj:window"})

    assert first.wire_labels == ["first", "second"]
    assert first.digest == second.digest
    assert [item["candidate_id"] for item in first.presented] == ["first", "second"]


@pytest.mark.parametrize("intent,scope", [
    ("observe", "gather perceptible information"),
    ("ask_probe", "request information"),
    ("defer", "postpone commitment"),
])
def test_observation_family_preserves_distinct_registered_intent_scopes(intent, scope):
    raw = {**_candidate(intent, action_family="observation"), "semantic_intent_id": intent}
    result = CandidateCompiler().compile(candidates=[raw])
    assert scope in result.presented[0]["description"]
    assert "owner permission" in result.presented[0]["description"]
    assert "unverified" in result.presented[0]["description"]


@pytest.mark.parametrize("family,scope", [
    ("communication", "exchange information"), ("movement", "change position"),
    ("combat", "combat interaction"), ("protection", "reduce exposure"),
])
def test_every_family_has_stable_semantics_ignoring_injected_answer_fields(family, scope):
    raw = {**_candidate("wire-stable", action_family=family), "semantic_intent_id": family,
           "description": "correct answer", "rationale": "grading-sentinel",
           "required_conditions": {"visibility": "satisfied", "gold": "correct answer",
                                   "consent": {"rationale": "grading-sentinel"}}}
    first = CandidateCompiler().compile(candidates=[raw])
    assert scope in first.presented[0]["description"]
    assert "correct answer" not in first.presented[0]["description"]
    assert "grading-sentinel" not in first.presented[0]["description"]
    assert "consent=unknown" in first.presented[0]["description"]
    assert first.digest == CandidateCompiler().compile(candidates=[raw]).digest


@pytest.mark.parametrize("availability", ["unknown", "unavailable"])
def test_unavailable_candidates_remain_diagnostic_without_description_admission(availability):
    raw = {**_candidate("wire"), "availability": availability}
    result = CandidateCompiler().compile(candidates=[raw])
    assert not result.presented
    assert result.diagnostics[0]["reason"] == f"availability_{availability}"


def test_description_does_not_render_free_target_or_condition_instructions():
    raw = {**_candidate("wire"), "target_refs": {"gold": "correct answer", "target": "should choose probe"},
           "required_conditions": {"visibility": "satisfied", "rationale": "correct answer"}}
    description = CandidateCompiler._semantic_description(raw)
    assert "correct answer" not in description
    assert "should choose" not in description
    assert "target=unknown" in description


@pytest.mark.parametrize("status", ["unknown", "unavailable", "blocked"])
def test_affordance_unavailability_cannot_become_presented_candidate(status):
    raw = {**_candidate("stable-label"), "affordance_result": {"status": status, "reason": f"fixture_{status}"}}
    result = CandidateCompiler().compile(candidates=[raw])
    assert result.wire_labels == []
    assert [item["candidate_id"] for item in result.universe] == ["stable-label"]
    assert result.pruned == [{"candidate_id": "stable-label", "reason": f"fixture_{status}"}]
    assert result.universe[0]["affordance_result"]["status"] == status


def test_unavailable_visibility_remains_diagnostic():
    result = CandidateCompiler().compile(candidates=[_candidate("wire", status="unavailable")])
    assert result.presented == []
    assert result.diagnostics[0]["reason"] == "condition_unavailable"


def test_v5_compacts_structure_but_preserves_v4_historical_rendering():
    raw = _candidate("wire")
    current = CandidateCompiler().compile(candidates=[raw])
    archived = CandidateCompiler(description_contract_revision="candidate-semantics:v4:1").compile(candidates=[raw])
    assert current.presented[0]["description_contract_revision"] == "candidate-semantics:v5:1"
    assert "Target:" in archived.presented[0]["description"]
    assert "target= obj:door" not in current.presented[0]["description"]
    assert "target=obj:door" in current.presented[0]["description"]
    assert "visibility=satisfied" in current.presented[0]["description"]
    assert "Runtime legality/owner permission/execution unverified" in current.presented[0]["description"]
    assert len(current.presented[0]["description"]) < len(archived.presented[0]["description"])
    assert current.digest != archived.digest
