from __future__ import annotations

import json
import pytest

from app.models.social_model import FactCard, FrozenModelInput
from app.population_continuity.simulation_contracts import simulation_digest
from test_social_model_execution_contract import standard_inputs


def test_frozen_input_copies_nested_content_and_serialization():
    inputs=standard_inputs()
    with pytest.raises(TypeError):
        inputs.cards[0].content["confirmed"]=False
    with pytest.raises(TypeError):
        inputs.vector.source_revisions["source:qualification"]=2
    raw=json.loads(inputs.model_dump_json())
    raw["cards"][0]["content"]["tags"].append("mutated")
    assert "mutated" not in inputs.cards[0].content["tags"]
    assert FrozenModelInput.model_validate_json(inputs.model_dump_json())==inputs


def test_original_content_mutation_cannot_change_card():
    original={"tags":["protected"]}
    data=standard_inputs().cards[0].model_dump()
    card=FactCard(**{**data,"content":original,"content_digest":""})
    digest=card.content_digest
    original["tags"].append("changed")
    assert card.content["tags"]==("protected",) and card.content_digest==digest


def test_card_order_and_mapping_order_preserve_input_digest():
    inputs=standard_inputs()
    shuffled=FrozenModelInput.model_validate({**inputs.model_dump(),"cards":tuple(reversed(inputs.cards))})
    assert shuffled==inputs and shuffled.vector.input_digest==inputs.vector.input_digest


def test_changed_observation_is_a_different_input_even_if_streams_are_identical():
    inputs=standard_inputs()
    vector=inputs.vector.model_copy(update={"observed_at":"2026-10-10T04:16:00Z","input_digest":""})
    later=FrozenModelInput.model_validate({**inputs.model_dump(),"vector":vector})
    assert later.vector.input_digest!=inputs.vector.input_digest


def test_content_digest_tampering_and_old_input_digest_are_rejected():
    inputs=standard_inputs()
    original=inputs.cards[0]
    with pytest.raises(ValueError):
        FactCard.model_validate({**original.model_dump(),"content":{"confirmed":False}})
    data=inputs.data.model_copy(update={"confirmed_supply_units":999})
    with pytest.raises(ValueError):
        FrozenModelInput.model_validate({**inputs.model_dump(),"data":data})


def test_missing_historical_content_does_not_fall_back_to_current():
    inputs=standard_inputs()
    with pytest.raises(ValueError):
        FrozenModelInput.model_validate({**inputs.model_dump(),"cards":()})


def test_card_readset_cannot_omit_a_real_source_dependency():
    inputs=standard_inputs()
    original=inputs.cards[0]
    changed=FactCard.model_validate({**original.model_dump(),"source_revision_vector":{
        **dict(original.source_revision_vector),"membership:query":2}})
    with pytest.raises(ValueError,match="source|digest"):
        FrozenModelInput.model_validate({**inputs.model_dump(),"cards":(changed,*inputs.cards[1:])})


@pytest.mark.parametrize("field,value", [("source_revisions",{"source:qualification":True}),
    ("query_pins",{"query:members":""}),("shard_revision","")])
def test_malformed_vectors_are_not_accepted_by_model_copy(field,value):
    inputs=standard_inputs()
    with pytest.raises(ValueError):
        FrozenModelInput.model_validate({**inputs.model_dump(),"vector":inputs.vector.model_copy(update={field:value})})


def test_duplicate_cards_cannot_double_count_a_source():
    inputs=standard_inputs()
    with pytest.raises(ValueError):
        FrozenModelInput.model_validate({**inputs.model_dump(),"cards":(*inputs.cards,inputs.cards[0])})
