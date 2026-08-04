import pytest
from pydantic import ValidationError
from pydantic import TypeAdapter

from app.models.siming_heavenly_graph import HeavenlyGraphScope
from app.models.siming_heavenly_memory import (
    ActorCognitionMemoryEntry,
    CausalTimelineMemoryEntry,
    ConvergenceStrategyMemoryEntry,
    InterventionOutcomeMemoryEntry,
    SimingCompiledContext,
    SimingContextRequest,
    SimingHeavenlyMemoryEntry,
    StorylineObligationMemoryEntry,
    WorldFactMemoryEntry,
)


def test_world_fact_requires_authority_result_ref() -> None:
    with pytest.raises(ValidationError, match="authority_result_ref"):
        WorldFactMemoryEntry(
            entry_id="fact:letter:removed",
            world_anchor_id="obj_letter",
            state_key="surface_state",
            state_value="removed_from_surface",
            evidence_refs=["visual:letter:gone"],
        )


def test_context_request_rejects_actor_private_scope() -> None:
    with pytest.raises(ValidationError, match="siming_heavenly"):
        SimingContextRequest(
            scope=HeavenlyGraphScope(
                world_id="world:demo", session_id="session:demo", story_branch_id="branch:main",
                graph_namespace="actor_private", owner_actor_id="char_b",
            ),
            valid_at=10, recorded_at=10, seed_node_ids=["fact:letter:removed"],
            relevant_actor_ids=["char_b"],
        )


@pytest.mark.parametrize(
    "entry",
    [
        WorldFactMemoryEntry(
            entry_id="fact:letter:removed",
            world_anchor_id="obj_letter",
            state_key="surface_state",
            state_value="removed_from_surface",
            authority_result_ref="authority:letter:removed",
            evidence_refs=["visual:letter:gone"],
        ),
        CausalTimelineMemoryEntry(
            entry_id="cause:letter",
            cause_ref="fact:letter:removed",
            effect_ref="story:N3",
            relation_type="CAUSED_BY",
        ),
        ActorCognitionMemoryEntry(
            entry_id="cognition:char_b",
            actor_id="char_b",
            revision_vector={"event": "1"},
            completeness="complete",
            supporting_memory_refs=["actor_memory_surface:char_b:event:1"],
        ),
        StorylineObligationMemoryEntry(
            entry_id="obligation:O6",
            record_type="obligation",
            lifecycle="open",
        ),
        InterventionOutcomeMemoryEntry(
            entry_id="outcome:dispatch",
            stage="dispatch",
            correlation_id="corr:letter",
        ),
        ConvergenceStrategyMemoryEntry(entry_id="strategy:letter"),
    ],
)
def test_union_discriminates_all_six_domains(entry: SimingHeavenlyMemoryEntry) -> None:
    restored = TypeAdapter(SimingHeavenlyMemoryEntry).validate_python(
        entry.model_dump(mode="json")
    )

    assert restored == entry


@pytest.mark.parametrize(
    "ref",
    [
        "data:image/png;base64,AAAA",
        "file:///private/letter.png",
        "actor_private:char_b:event:secret",
    ],
)
def test_memory_refs_reject_raw_or_private_artifacts(ref: str) -> None:
    with pytest.raises(ValidationError, match="normalized public reference"):
        WorldFactMemoryEntry(
            entry_id="fact:letter:removed",
            world_anchor_id="obj_letter",
            state_key="surface_state",
            state_value="removed_from_surface",
            authority_result_ref="authority:letter:removed",
            evidence_refs=[ref],
        )


def test_actor_cognition_rejects_private_memory_reference() -> None:
    with pytest.raises(ValidationError, match="normalized public reference"):
        ActorCognitionMemoryEntry(
            entry_id="cognition:char_b",
            actor_id="char_b",
            revision_vector={"event": "1"},
            completeness="complete",
            supporting_memory_refs=["actor_private:char_b:event:secret"],
        )


def test_union_rejects_unknown_domain_tag() -> None:
    with pytest.raises(ValidationError, match="union_tag_invalid"):
        TypeAdapter(SimingHeavenlyMemoryEntry).validate_python(
            {"domain": "unknown", "entry_id": "memory:unknown"}
        )


def test_memory_models_forbid_extra_fields_and_are_frozen() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        WorldFactMemoryEntry(
            entry_id="fact:letter:removed",
            world_anchor_id="obj_letter",
            state_key="surface_state",
            state_value="removed_from_surface",
            authority_result_ref="authority:letter:removed",
            unexpected=True,
        )

    entry = WorldFactMemoryEntry(
        entry_id="fact:letter:removed",
        world_anchor_id="obj_letter",
        state_key="surface_state",
        state_value="removed_from_surface",
        authority_result_ref="authority:letter:removed",
    )
    with pytest.raises(ValidationError, match="frozen_instance"):
        entry.entry_id = "fact:other"


def test_ownerless_heavenly_scope_and_compiled_context_are_typed() -> None:
    request = SimingContextRequest(
        scope=HeavenlyGraphScope(
            world_id="world:demo",
            session_id="session:demo",
            story_branch_id="branch:main",
        ),
        valid_at=10,
        seed_node_ids=["fact:letter:removed"],
    )
    context = SimingCompiledContext(
        request=request,
        world_facts=[
            WorldFactMemoryEntry(
                entry_id="fact:letter:removed",
                world_anchor_id="obj_letter",
                state_key="surface_state",
                state_value="removed_from_surface",
                authority_result_ref="authority:letter:removed",
            )
        ],
        truncated=False,
        context_hash="a" * 64,
    )

    assert request.scope.graph_namespace == "siming_heavenly"
    assert context.world_facts[0].entry_id == "fact:letter:removed"
