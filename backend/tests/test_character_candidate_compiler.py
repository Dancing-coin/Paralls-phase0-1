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
    # Rendering stays answer-agnostic; malformed consent cannot enter U/P.
    description = CandidateCompiler._semantic_description(raw)
    assert scope in description
    assert "correct answer" not in description
    assert "grading-sentinel" not in description
    assert "consent=unknown" in description
    assert first.presented == []
    assert first.diagnostics[0]["condition"] == "consent"
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


def test_action_specific_target_projection_keeps_worktable_state_digest_on_choice():
    from app.character_agent.planning.l3_planner import CharacterAgentL3Service
    from app.models.character_agent_runtime import CharacterPrivateWorldSnapshot, CharacterInterpretation
    from app.services.esm_service import ESMService

    owner = ESMService()
    snapshot = CharacterPrivateWorldSnapshot(actor_id="char_a", room_id="r", scene_id="s", zone_id="z",
        producer_ts=1, updated_at=1, visible_target_refs=["obj_worktable"])
    snapshot.target_catalog = owner.project_character_targets(snapshot)
    planner = CharacterAgentL3Service()
    interpretation = CharacterInterpretation(actor_id="char_a", interpreted_summary="visible worktable",
        interpretation_type="object", salience_score=0.5, ambiguity_level="low", risk_level="low",
        opportunity_level="medium", attention_target="obj_worktable")
    envelope, policy = planner._compile_capability_contracts(interpretation=interpretation,
        actor_id="char_a", turn_context=None, profile={}, effective_profile={},
        snapshot=snapshot.model_dump(mode="json"), dynamic_state={}, skill_affordance_summary={})
    records = planner._candidate_records(intents=["use_object", "finish_use"],
        interpretation=interpretation, snapshot=snapshot.model_dump(mode="json"), envelope=envelope,
        policy=policy, frame=None, skill_affordance_summary={})
    records = CandidateCompiler().compile(candidates=records,
        visible_targets={"obj_worktable"}).presented

    assert len(records) == 1
    record = records[0]
    assert record["semantic_intent_id"] == "use_object"
    assert record["semantic_action_id"] == "action:use"
    assert record["target_refs"] == {"object": "obj_worktable"}
    assert record["revision_pins"]["target_admission_digest"] == snapshot.target_catalog[0]["target_admission_digest"]
    prepared = planner.prepare_intent_plan(interpretation=interpretation,
        control_mode="autonomous", snapshot=snapshot.model_dump(mode="json"))
    selected = prepared.candidate_mapping["use_object:obj_worktable"]
    assert selected["revision_pins"]["target_admission_digest"] == record["revision_pins"]["target_admission_digest"]
    assert "use registered object" in selected["description"]
    assert "finish_use:obj_worktable" not in prepared.candidate_mapping
    ids = [item["candidate_id"] for item in prepared.frozen_candidates]
    assert len(ids) == len(set(ids))


def test_domain_candidate_expansion_accepts_only_registered_worktable_interactions():
    from app.character_agent.planning.l3_planner import CharacterAgentL3Service

    snapshot = {"target_catalog": [
        {"supported_intents": ["use_object", "finish_use", "injected_action"]},
        {"supported_intents": ["finish_use"]},
    ]}

    intents = CharacterAgentL3Service._expand_domain_candidates(["observe"], snapshot)

    assert intents == ["observe", "use_object", "finish_use"]


@pytest.mark.parametrize("condition", ["consent", "privacy", "contact", "range", "permission", "availability"])
@pytest.mark.parametrize("status", ["blocked", "unknown", "unavailable", None, {"status": "satisfied"}])
def test_nonvisual_required_condition_cannot_admit_an_executable_candidate(condition, status):
    denied = {**_candidate("denied"),
              "required_conditions": {"visibility": "satisfied", condition: status}}
    result = CandidateCompiler().compile(candidates=[denied, _candidate("observe")])

    assert result.wire_labels == ["observe"]
    assert [item["candidate_id"] for item in result.universe] == ["observe"]
    diagnostic, = result.diagnostics
    assert diagnostic["candidate_id"] == "denied"
    assert diagnostic["condition"] == condition


def test_deferred_range_check_is_not_a_known_denial_or_a_satisfied_condition():
    raw = {**_candidate("inspect"),
           "required_conditions": {"visibility": "satisfied", "range": "required"}}
    result = CandidateCompiler().compile(candidates=[raw])
    assert result.wire_labels == ["inspect"]
    assert result.presented[0]["required_conditions"]["range"] == "required"
    assert "range=required" in result.presented[0]["description"]


def test_l3_preparation_preserves_permission_denial_in_the_frozen_provider_input():
    import json

    from app.character_agent.planning.l3_planner import CharacterAgentL3Service
    from app.models.character_agent_runtime import CharacterInterpretation, CharacterPrivateWorldSnapshot
    from app.services.esm_service import ESMService

    snapshot = CharacterPrivateWorldSnapshot(actor_id="char_a", room_id="r", scene_id="s", zone_id="z",
        producer_ts=1, updated_at=1, visible_target_refs=["obj_worktable"])
    snapshot.target_catalog = ESMService().project_character_targets(snapshot)
    for descriptor in snapshot.target_catalog:
        descriptor["required_conditions"]["permission"] = "blocked"
    restored = CharacterPrivateWorldSnapshot.model_validate_json(snapshot.model_dump_json())
    prepared = CharacterAgentL3Service().prepare_intent_plan(
        interpretation=CharacterInterpretation(actor_id="char_a", interpreted_summary="visible worktable",
            interpretation_type="object", salience_score=0.5, ambiguity_level="low", risk_level="low",
            opportunity_level="medium", attention_target="obj_worktable"),
        control_mode="agent_full_auto", snapshot=restored.model_dump(mode="json"))
    context = json.loads(prepared.request_json)["context"]
    assert all("obj_worktable" not in label for label in context["candidate_intents"])
    assert "observe" in context["candidate_intents"]
    assert any(item["candidate_id"] == "use_object:obj_worktable" and item["condition"] == "permission"
               for item in context["candidate_diagnostics"])
