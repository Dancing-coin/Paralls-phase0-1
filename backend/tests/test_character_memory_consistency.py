from app.character_agent.memory.knowledge_memory import CharacterKnowledgeMemory
from app.character_agent.models.memory_consistency import MemoryFactClaim, compare_memory_claims
from app.character_agent.reasoning.actor_scene_knowledge import ActorSceneKnowledgeEntry, ActorSceneKnowledgeStore


def _claim(**changes):
    fields = dict(scope_ref="world:main", subject_ref="obj_letter", predicate="location", value="desk", valid_at=9, source_ref="observation:9")
    fields.update(changes)
    return MemoryFactClaim(**fields)


def test_comparison_requires_same_scope_subject_predicate_and_valid_time():
    original = _claim()
    assert compare_memory_claims(original, _claim(value="drawer", source_ref="observation:other")) == "conflicted"
    assert compare_memory_claims(original, _claim(source_ref="observation:other")) == "consistent"
    for changes in (dict(valid_at=10, value="drawer"), dict(scope_ref="world:branch", value="drawer"),
                    dict(subject_ref="obj_book", value="drawer"), dict(predicate="condition", value="destroyed")):
        assert compare_memory_claims(original, _claim(**changes)) == "not_comparable"
    assert compare_memory_claims(original, None) == "not_comparable"


def test_knowledge_memory_keeps_optional_claim_and_old_records_load():
    memory = CharacterKnowledgeMemory()
    memory.upsert_proposition("a", "letter_location", "on desk", "BELIEVED", .8, "event:9", 12, claim=_claim())
    record = memory.recall_records("a")[0]
    assert record.claim.valid_at == 9
    assert record.model_validate(record.model_dump()).claim.source_ref == "observation:9"
    assert record.model_validate({key: value for key, value in record.model_dump().items() if key != "claim"}).claim is None


def test_ask_only_disputes_structured_claims_at_the_same_valid_time():
    store = ActorSceneKnowledgeStore()
    original = ActorSceneKnowledgeEntry(entry_id="letter", actor_id="a", session_id="s", scene_id="scene",
                                        subject_ref="obj_letter", knowledge_type="target", summary="on desk",
                                        source_kind="canonical_percept_bundle", source_refs=["observation:9"], claim=_claim())
    assert store.upsert(original, producer_ts=12).operation == "add"
    later = original.model_copy(update={"summary": "in drawer", "claim": _claim(value="drawer", valid_at=10, source_ref="observation:10")})
    assert store.upsert(later, producer_ts=13).operation != "conflict"
    assert store.get(actor_id="a", session_id="s", scene_id="scene", subject_ref="obj_letter", knowledge_type="target").claim.valid_at == 10
    same_time = later.model_copy(update={"summary": "destroyed", "claim": _claim(value="destroyed", valid_at=10, source_ref="observation:other")})
    assert store.upsert(same_time, producer_ts=14).operation == "conflict"
