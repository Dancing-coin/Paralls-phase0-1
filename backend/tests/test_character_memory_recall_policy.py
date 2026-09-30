import json
from app.character_agent.gateway.memory_recall import CharacterMemoryRecallPolicy
from app.character_agent.gateway.model_gateway import CharacterModelGateway
from app.character_agent.gateway.model_provider import CharacterModelProvider
from app.character_agent.planning.l3_planner import CharacterAgentL3Service
from app.character_agent.planning.l3_planner import MissingRequiredMemoryEvidence
from app.character_agent.storage.memory_store import CharacterAgentMemoryStore
from app.models.character_agent_runtime import CharacterInterpretation
import pytest
from copy import deepcopy


@pytest.mark.parametrize("pool", ["event_memories", "relational_memories"])
def test_recall_only_copies_payloads_returned_within_the_budget(pool) -> None:
    copied = []

    class TrackedPayload(dict):
        def __deepcopy__(self, memo):
            copied.append(self["marker"])
            return TrackedPayload(deepcopy(dict(self), memo))

    entries = [
        {"memory_id": f"memory:{index}", "world_ts": index,
         "entity_id": f"actor_{index}", "belief_type": "trust", "value": "neutral",
         "summary": "unrelated weather", "payload": TrackedPayload(marker=index, values=[1])}
        for index in range(32)
    ]
    entries[-1]["summary"] = "letter " + "x" * 2000
    policy = CharacterMemoryRecallPolicy(pool_limit=2, token_budget=120)

    result = policy.select({pool: entries}, context={"attention_targets": ["letter"]})

    output_pool = "knowledge_memories" if pool == "relational_memories" else pool
    assert [entry["memory_id"] for entry in result.memory[output_pool]] == ["memory:30"]
    assert copied == [30]
    assert result.metadata["truncated"] is True
    result.memory[output_pool][0]["payload"]["values"].append(2)
    assert entries[30]["payload"]["values"] == [1]


def test_recall_preserves_equal_rank_duplicate_ids_and_independent_aliases() -> None:
    memory = {
        "event_memories": [
            {"memory_id": "b", "world_ts": 10, "summary": "weather", "payload": {"marker": [0]}},
            {"memory_id": "a", "world_ts": 10, "summary": "weather", "payload": {"marker": [1]}},
            {"memory_id": "a", "world_ts": 10, "summary": "weather", "payload": {"marker": [2]}},
        ],
        "episodic_memories": [],
        "relational_memories": [
            {"entity_id": "actor_b", "belief_type": "trust", "value": "neutral", "payload": {"marker": [3]}}
        ],
    }
    original = deepcopy(memory)

    result = CharacterMemoryRecallPolicy(pool_limit=2, token_budget=1000).select(memory, context={})

    assert [entry["payload"]["marker"] for entry in result.memory["event_memories"]] == [[1], [2]]
    assert result.metadata["selected_memory_refs"] == ["event:a", "event:a", "knowledge:relation:actor_b:trust"]
    result.memory["event_memories"][0]["payload"]["marker"].append(9)
    assert result.memory["episodic_memories"][0]["payload"]["marker"] == [1]
    assert result.memory["event_memories"][1]["payload"]["marker"] == [2]
    result.memory["relational_memories"][0]["value"] = "changed"
    assert result.memory["knowledge_memories"][0]["value"] == "neutral"
    assert memory == original


def test_recall_preserves_duplicate_id_token_selection_and_row_isolation() -> None:
    memory = {"event_memories": [
        {"memory_id": "same", "world_ts": 1, "summary": "short", "payload": {"marker": [1]}},
        {"memory_id": "same", "world_ts": 1, "summary": "x" * 2000, "payload": {"marker": [2]}},
    ]}
    result = CharacterMemoryRecallPolicy(pool_limit=2, token_budget=30).select(memory, context={})

    # 既有按 ID 保留语义会保留同 ID 的两行，不能在排序优化中改成逐行去重。
    assert [entry["payload"]["marker"] for entry in result.memory["event_memories"]] == [[1], [2]]
    assert result.metadata["selected_memory_refs"] == ["event:same", "event:same"]
    assert result.metadata["estimated_tokens"] == 19
    assert result.metadata["truncated"] is True
    result.memory["event_memories"][1]["payload"]["marker"].append(9)
    assert memory["event_memories"][1]["payload"]["marker"] == [2]


def test_recall_preserves_stable_cutoff_when_one_entry_occurs_twice() -> None:
    repeated = {"memory_id": "a", "world_ts": 1, "payload": {"marker": [1]}}
    entries = [repeated, repeated, {"memory_id": "a", "world_ts": 1, "payload": {"marker": [2]}}]
    result = CharacterMemoryRecallPolicy(pool_limit=2, token_budget=1000).select(
        {"event_memories": entries}, context={},
    )

    assert [entry["payload"]["marker"] for entry in result.memory["event_memories"]] == [[1], [1]]
    result.memory["event_memories"][0]["payload"]["marker"].append(9)
    assert result.memory["event_memories"][1]["payload"]["marker"] == [1]
    assert repeated["payload"]["marker"] == [1]


def test_strong_recall_preserves_required_ref_order_across_pool_and_token_truncation() -> None:
    memory = {
        "knowledge_memories": [
            {"memory_id": "k_a", "source_event_id": "e_a", "world_ts": 1,
             "claim": {"subject_ref": "obj_letter", "predicate": "a", "source_ref": "e_a"}},
            {"memory_id": "k_b", "source_event_id": "e_b", "world_ts": 2,
             "claim": {"subject_ref": "obj_letter", "predicate": "b", "source_ref": "e_b"}},
            {"memory_id": "k_c", "source_event_id": "e_c", "world_ts": 3,
             "claim": {"subject_ref": "obj_letter", "predicate": "c", "source_ref": "e_c"}},
        ],
        "event_memories": [
            {"memory_id": f"e_{name}", "world_ts": index, "summary": "x" * 1000}
            for index, name in enumerate(("a", "b", "c"), 1)
        ],
    }
    result = CharacterMemoryRecallPolicy(pool_limit=1, token_budget=1).select(memory, context={
        "attention_targets": ["obj_letter"],
        "profile": {"capability_constraint_layer": {"memory_retention": "strong"}},
    })

    assert result.metadata["missing_required_refs"] == [
        "event:e_b", "event:e_a", "knowledge:k_b", "knowledge:k_a", "knowledge:k_c", "event:e_c",
    ]
    assert result.metadata["selected_memory_refs"] == []
    assert result.metadata["estimated_tokens"] == 0


@pytest.mark.parametrize("history_size", [128, 1024])
def test_recall_timestamp_work_is_linear_in_retained_history(history_size, monkeypatch):
    policy = CharacterMemoryRecallPolicy(pool_limit=2, token_budget=1200)
    memory = {pool: [
        {"memory_id": f"{pool}:{index:04d}", "world_ts": index,
         "producer_ts": index + 10, "summary": "unrelated weather"}
        for index in range(history_size)
    ] for pool in ("event_memories", "observation_memories")}
    for entries in memory.values():
        entries[0]["summary"] = "sealed letter"
    original_memory = deepcopy(memory)
    timestamp_reads = 0
    original_timestamp = policy._timestamp

    def counted_timestamp(entry):
        nonlocal timestamp_reads
        timestamp_reads += 1
        return original_timestamp(entry)

    monkeypatch.setattr(policy, "_timestamp", counted_timestamp)
    result = policy.select(memory, context={"attention_targets": ["letter"]})

    # 历史增长只增加线性扫描；不能为每个候选再次扫描整个池。
    assert timestamp_reads <= 4 * history_size * 2 + 32
    for pool in memory:
        assert [entry["memory_id"] for entry in result.memory[pool]] == [
            f"{pool}:0000", f"{pool}:{history_size - 1:04d}"]
    assert result.metadata["truncated"] is True
    assert result.metadata["estimated_tokens"] <= 1200
    assert memory == original_memory
    result.memory["event_memories"][0]["summary"] = "changed selected copy"
    assert memory == original_memory


def test_recall_prefers_attention_and_goal_relevance_over_newest_irrelevant_memory() -> None:
    policy = CharacterMemoryRecallPolicy()
    memory = {
        "event_memories": [
            {
                "memory_id": "event:letter",
                "world_ts": 10,
                "summary": "the sealed letter was destroyed",
                "certainty_score": 0.9,
                "clarity_score": 0.9,
            },
            {
                "memory_id": "event:weather",
                "world_ts": 99,
                "summary": "the northern rain became heavier",
                "certainty_score": 1.0,
                "clarity_score": 1.0,
            },
        ],
        "knowledge_memories": [],
        "observation_memories": [],
        "social_memories": [],
        "higher_order_memories": [],
        "working_memory": [],
    }

    result = policy.select(
        memory,
        context={
            "snapshot": {"current_focus_target": "obj_letter"},
            "event": {"perceived_summary": "the letter is gone", "target_object_id": "obj_letter"},
            "current_goal_state": {"primary_goal": "understand what happened to the letter"},
        },
    )

    assert result.memory["event_memories"][0]["memory_id"] == "event:letter"
    assert result.metadata["selected_memory_refs"] == ["event:event:letter", "event:event:weather"]


def test_recall_enforces_pool_and_token_budgets_with_deterministic_metadata() -> None:
    policy = CharacterMemoryRecallPolicy(pool_limit=2, token_budget=80)
    memory = {
        "event_memories": [
            {"memory_id": f"event:{index}", "world_ts": index, "summary": "letter " + ("x" * 80)}
            for index in range(5)
        ],
        "observation_memories": [],
        "knowledge_memories": [],
        "social_memories": [],
        "higher_order_memories": [],
        "working_memory": [],
    }

    result = policy.select(memory, context={"snapshot": {}, "event": {}})

    assert len(result.memory["event_memories"]) == 2
    assert result.metadata["token_budget"] == 80
    assert result.metadata["estimated_tokens"] <= 80
    assert result.metadata["truncated"] is True
    assert result.metadata["context_hash"] == policy.select(memory, context={"snapshot": {}, "event": {}}).metadata["context_hash"]


def test_model_gateway_exposes_recall_metadata_alongside_selected_memory() -> None:
    gateway = CharacterModelGateway()
    request = gateway.prepare_run_request(
        task_kind="l2_reasoning",
        route_override="local_only",
        context={
            "actor_id": "char_b",
            "control_mode": "agent_full_auto",
            "snapshot": {"current_focus_target": "obj_letter"},
            "event": {"perceived_summary": "letter removed", "target_object_id": "obj_letter"},
            "current_goal_state": {"primary_goal": "understand the letter"},
            "memory": {
                "working_memory": [],
                "event_memories": [{"memory_id": "event:letter", "world_ts": 1, "summary": "letter removed"}],
                "observation_memories": [],
                "knowledge_memories": [],
                "social_memories": [],
                "higher_order_memories": [],
            },
        },
    )

    recall = request["context"]["memory_recall"]
    assert recall["selected_memory_refs"] == ["event:event:letter"]
    assert recall["context_hash"]
    assert request["context"]["memory"]["event_memories"][0]["memory_id"] == "event:letter"


def test_strong_recall_keeps_old_subject_evidence_in_final_gateway_request() -> None:
    memory = {"knowledge_memories": [
        {"memory_id": "knowledge:letter", "state": "believed", "source_event_id": "event:letter_destroyed",
         "claim": {"scope_ref": "world:main", "subject_ref": "obj_letter", "predicate": "state",
                   "value": "destroyed", "valid_at": 1, "source_ref": "event:letter_destroyed"}},
    ], "event_memories": [
        {"memory_id": "event:letter_destroyed", "world_ts": 1, "source_event_id": "observation:letter"},
        *({"memory_id": f"event:noise:{i}", "world_ts": i + 2, "summary": "unrelated conversation"}
          for i in range(30)),
    ]}
    request = CharacterModelGateway().prepare_run_request(task_kind="l2_reasoning", route_override="local_only", context={
        "actor_id": "char_a", "snapshot": {"current_attention_targets": ["obj_letter"]}, "memory": memory,
        "profile": {"capability_constraint_layer": {"memory_retention": "strong"}},
    })
    refs = request["context"]["memory_recall"]
    assert "event:letter_destroyed" in {item["memory_id"] for item in request["context"]["memory"]["event_memories"]}
    assert "knowledge:letter" in {item["memory_id"] for item in request["context"]["memory"]["knowledge_memories"]}
    assert refs["pool_limit"] == 16 and refs["token_budget"] == 2400
    assert refs["estimated_tokens"] <= refs["token_budget"]
    assert memory["event_memories"][0]["source_event_id"] == "observation:letter"


def test_strong_recall_reports_oversized_current_claim_without_flagging_normal_history() -> None:
    memory = {"knowledge_memories": [{"memory_id": "knowledge:letter", "claim": {
        "subject_ref": "obj_letter", "source_ref": "event:letter_destroyed"},
        "source_event_id": "event:letter_destroyed", "proposition": "destroyed " + "x" * 10000}],
        "event_memories": [{"memory_id": "event:letter_destroyed", "summary": "seen"}]}
    context = {"snapshot": {"current_attention_targets": ["obj_letter"]},
               "profile": {"capability_constraint_layer": {"memory_retention": "strong"}}}
    strong = CharacterMemoryRecallPolicy().select(memory, context=context)
    normal = CharacterMemoryRecallPolicy().select(memory, context={**context, "profile": {}})
    assert strong.metadata["missing_required_refs"] == ["knowledge:knowledge:letter"]
    assert normal.metadata["missing_required_refs"] == []


def test_prepared_recall_is_used_without_second_selection() -> None:
    policy = CharacterMemoryRecallPolicy(pool_limit=16, token_budget=2400)
    recall = policy.select({"event_memories": [
        {"memory_id": "event:letter_destroyed", "subject_ref": "obj_letter", "source_event_id": "observation:1",
         "world_ts": 1, "summary": "destroyed letter " + "e" * 5000},
    ]}, context={"snapshot": {"current_focus_target": "obj_letter"}})
    request = CharacterModelGateway().prepare_run_request(task_kind="l3_planning", route_override="local_only", context={
        "actor_id": "char_a", "snapshot": {"current_focus_target": "obj_letter"}, "memory": recall.memory,
    }, prepared_recall=recall)
    assert request["context"]["memory"]["event_memories"] == recall.memory["event_memories"]
    assert request["context"]["memory_recall"] == recall.metadata
    assert recall.metadata["estimated_tokens"] > 1200


def test_l3_final_model_request_retains_selected_strong_memory() -> None:
    class CapturingProvider(CharacterModelProvider):
        def complete(self, request):
            self.request = request
            return self._offline_complete(request)

    provider = CapturingProvider(provider_kind="local")
    planner = CharacterAgentL3Service(gateway=CharacterModelGateway(provider=provider))
    plan = planner.build_intent_plan(
        interpretation=CharacterInterpretation(
            actor_id="char_a", interpreted_summary="look at letter", interpretation_type="world_signal",
            salience_score=0.8, ambiguity_level="low", risk_level="low", opportunity_level="medium",
            attention_target="obj_letter", inner_prompt_candidate="inspect",
        ), control_mode="agent_full_auto", snapshot={"current_attention_targets": ["obj_letter"]},
        profile={"capability_constraint_layer": {"memory_retention": "strong"}},
        memory_bundle={"event_memories": [{
            "memory_id": "event:letter_destroyed", "actor_id": "char_a", "event_id": "letter_destroyed",
            "source_event_id": "observation:letter", "world_ts": 1, "event_type": "observation",
            "summary": "the letter was destroyed " + "x" * 5000, "clarity_score": 1.0, "certainty_score": 1.0,
        }]},
    )
    selected = provider.request["context"]["memory"]["event_memories"]
    assert selected[0]["memory_id"] == "event:letter_destroyed"
    assert plan["memory_recall"] == provider.request["context"]["memory_recall"]
    assert plan["memory_recall"]["estimated_tokens"] > 1200


def test_strong_recall_links_actual_perceived_claim_event_and_observation_sources() -> None:
    store = CharacterAgentMemoryStore()
    store.write_event({"event_id": "percept:letter_destroyed", "actor_id": "char_a", "producer_ts": 10,
                       "event_type": "character_perceived_event", "payload": {
                           "summary": "letter destroyed", "target_object_id": "obj_letter", "percept_channel": "visual",
                           "fact_claim": {"scope_ref": "world:main", "subject_ref": "obj_letter", "predicate": "state",
                                          "value": "destroyed", "valid_at": 10, "source_ref": "percept:letter_destroyed"}}})
    for i in range(30):
        store.write_event({"event_id": f"percept:other:{i}", "actor_id": "char_a", "producer_ts": i + 11,
                           "event_type": "character_perceived_event", "payload": {
                               "summary": "unrelated conversation", "target_object_id": "obj_other"}})
    bundle = store.retrieval_bundle("char_a")
    selected = CharacterMemoryRecallPolicy().select(bundle, context={
        "snapshot": {"current_attention_targets": ["obj_letter"]},
        "profile": {"capability_constraint_layer": {"memory_retention": "strong"}},
    })
    assert bundle["event_memories"][0]["memory_id"] == "event:char_a:percept:letter_destroyed:1"
    assert bundle["observation_memories"][0]["source_event_id"] == "percept:letter_destroyed"
    assert {item["source_event_id"] for item in selected.memory["event_memories"]} >= {"percept:letter_destroyed"}
    assert {item["source_event_id"] for item in selected.memory["observation_memories"]} >= {"percept:letter_destroyed"}
    claim = selected.memory["knowledge_memories"][0]["claim"]
    assert (claim["value"], claim["valid_at"], claim["source_ref"]) == (
        "destroyed", 10, "percept:letter_destroyed")
    assert next(item for item in selected.memory["event_memories"]
                if item["source_event_id"] == "percept:letter_destroyed")["world_ts"] == 10
    assert selected.metadata["missing_required_refs"] == []


def test_l3_refuses_model_call_when_required_known_claim_was_truncated() -> None:
    class RejectProvider(CharacterModelProvider):
        def complete(self, request):
            pytest.fail("model saw a decision without required evidence")

    planner = CharacterAgentL3Service(gateway=CharacterModelGateway(provider=RejectProvider(provider_kind="local")))
    interpretation = CharacterInterpretation(actor_id="char_a", interpreted_summary="inspect letter",
        interpretation_type="world_signal", salience_score=.8, ambiguity_level="low", risk_level="low",
        opportunity_level="medium", attention_target="obj_letter", inner_prompt_candidate="inspect")
    memory = {"knowledge_memories": [{"memory_id": "knowledge:letter", "actor_id": "char_a",
        "proposition_key": "letter", "proposition": "destroyed " + "x" * 10000,
        "state": "believed", "confidence": .9, "source_event_id": "event:letter", "producer_ts": 1,
        "claim": {"scope_ref": "world:main", "subject_ref": "obj_letter", "predicate": "state",
                  "value": "destroyed", "valid_at": 1, "source_ref": "event:letter"}}]}
    with pytest.raises(MissingRequiredMemoryEvidence) as error:
        planner.build_intent_plan(interpretation=interpretation, control_mode="agent_full_auto",
            snapshot={"current_attention_targets": ["obj_letter"]},
            profile={"capability_constraint_layer": {"memory_retention": "strong"}}, memory_bundle=memory)
    assert error.value.missing_required_refs == ["knowledge:knowledge:letter"]


@pytest.mark.parametrize("task_kind", ["l2_reasoning", "dialogue_generation"])
def test_every_gateway_rejects_missing_required_claim_before_model(task_kind: str) -> None:
    class RejectProvider(CharacterModelProvider):
        def complete(self, request):
            pytest.fail("provider called without required evidence")

    gateway = CharacterModelGateway(provider=RejectProvider(provider_kind="local"))
    context = {"actor_id": "char_a", "snapshot": {"current_attention_targets": ["obj_letter"]},
               "profile": {"capability_constraint_layer": {"memory_retention": "strong"}},
               "memory": {"knowledge_memories": [{"memory_id": "knowledge:letter", "state": "believed",
                   "source_event_id": "percept:letter", "proposition": "destroyed " + "x" * 10000,
                   "claim": {"subject_ref": "obj_letter", "predicate": "state", "value": "destroyed",
                             "valid_at": 10, "source_ref": "percept:letter"}}]}}
    with pytest.raises(MissingRequiredMemoryEvidence) as error:
        gateway.prepare_run_request(task_kind=task_kind, route_override="local_only", context=context)
    assert error.value.missing_required_refs == ["knowledge:knowledge:letter"]
    if task_kind == "dialogue_generation":
        with pytest.raises(MissingRequiredMemoryEvidence):
            list(gateway.stream_dialogue_task(context=context, route_override="local_only", cancelled=lambda: False))


def test_l3_exposes_own_dispute_and_personality_verification_bias_without_forcing_choice() -> None:
    class CapturingGateway:
        def run_task(self, *, context, **kwargs):
            self.context = context
            return {"candidate_intents": ["observe", "defer"], "selected_intent": "defer"}

        def complete_prepared_request(self, request_json):
            request = json.loads(request_json)
            return self.run_task(task_kind=request["task_kind"], context=request["context"], route_override=request.get("route_override"))

        def prepare_run_request(self, *, task_kind, context, route_override=None, prepared_recall=None):
            return {"task_kind": task_kind, "context": context, "route_override": route_override}

    gateway = CapturingGateway()
    planner = CharacterAgentL3Service(gateway=gateway)
    interpretation = CharacterInterpretation(actor_id="a", interpreted_summary="letter uncertain",
        interpretation_type="world_signal", salience_score=.8, ambiguity_level="high", risk_level="low",
        opportunity_level="medium", attention_target="obj_letter", inner_prompt_candidate="observe")
    plan = planner.build_intent_plan(interpretation=interpretation, control_mode="agent_full_auto",
        snapshot={"current_attention_targets": ["obj_letter"]},
        profile={"trait_vector_layer": {"rationality": .95}}, memory_bundle={"knowledge_memories": [{
            "memory_id": "knowledge:letter", "actor_id": "a", "proposition_key": "letter",
            "proposition": "letter may be gone", "state": "disputed", "confidence": .5,
            "source_event_id": "event:letter", "producer_ts": 1,
            "claim": {"scope_ref": "world:main", "subject_ref": "obj_letter", "predicate": "state",
                      "value": "intact", "valid_at": 1, "source_ref": "event:letter"}}]})
    assert gateway.context["verification"]["subject_ref"] == "obj_letter"
    assert gateway.context["verification"]["reason"] == "disputed"
    assert gateway.context["verification"]["recommended_intents"] == ["observe", "inspect_object"]
    scores = {item["candidate"]: item["gain_loss_score"] for item in plan["filter_results"]}
    assert scores["observe"] > scores["defer"]
    assert plan["model_output"]["selected_intent"] == "defer"


def test_l3_recommends_probe_only_for_available_actor_and_no_unseen_target() -> None:
    planner = CharacterAgentL3Service()
    interpretation = CharacterInterpretation(actor_id="a", interpreted_summary="ask about letter",
        interpretation_type="world_signal", salience_score=.8, ambiguity_level="high", risk_level="low",
        opportunity_level="medium", attention_target="char_b", inner_prompt_candidate="ask_probe")
    memory = {"knowledge_memories": [{"memory_id": "k", "state": "disputed",
        "claim": {"subject_ref": "char_b", "source_ref": "event:said"}}]}
    available = planner._verification_context(interpretation, {"current_attention_targets": ["char_b"]}, memory, {})
    assert available["recommended_intents"] == ["ask_probe"]
    assert planner._verification_context(interpretation, {"current_attention_targets": []}, memory, {}) == {}


def test_l3_uses_accessible_failed_interaction_for_verification_reason() -> None:
    planner = CharacterAgentL3Service()
    interpretation = CharacterInterpretation(actor_id="a", interpreted_summary="box failed",
        interpretation_type="world_signal", salience_score=.8, ambiguity_level="high", risk_level="low",
        opportunity_level="medium", attention_target="obj_box", inner_prompt_candidate="observe")
    context = planner._verification_context(interpretation, {"current_attention_targets": ["obj_box"]}, {}, {},
        [{"category": "constraint_result", "target_ref": "obj_box", "source_event_id": "result:denied"}])
    assert context["reason"] == "failed_interaction"
    assert context["source_ref"] == "result:denied"
