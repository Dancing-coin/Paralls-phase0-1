from __future__ import annotations

import pytest

from app.population_continuity.player_preemption import (
    PREEMPTION_REASONS,
    PlayerPreemption,
    PreemptionEpisode,
    WriteBackIntent,
)


def _intent(**updates: object) -> WriteBackIntent:
    values: dict[str, object] = {
        "actor_ref": "character:char_a",
        "player_ref": "player:1",
        "intent_kind": "speak",
        "payload": {"dialogue_text": "hello"},
        "actor_revision_at_start": 5,
    }
    values.update(updates)
    return WriteBackIntent(**values)


def test_declared_preemption_reasons() -> None:
    assert PREEMPTION_REASONS == (
        "player_interaction",
        "player_proximity",
        "critical_plot_beat",
        "debug_inspection",
    )


def test_begin_opens_a_bounded_episode() -> None:
    preemption = PlayerPreemption()
    episode = preemption.begin(
        actor_ref="character:char_a",
        player_ref="player:1",
        reason="player_interaction",
        tick=10,
        actor_revision=5,
    )

    assert episode.is_open
    assert preemption.is_preempted("character:char_a")


def test_overlapping_takeover_is_refused() -> None:
    preemption = PlayerPreemption()
    preemption.begin(
        actor_ref="character:char_a",
        player_ref="player:1",
        reason="player_interaction",
        tick=10,
        actor_revision=5,
    )

    with pytest.raises(ValueError, match="preemption_already_open"):
        preemption.begin(
            actor_ref="character:char_a",
            player_ref="player:2",
            reason="player_proximity",
            tick=11,
            actor_revision=5,
        )


def test_end_closes_the_episode_and_records_the_tick() -> None:
    preemption = PlayerPreemption()
    preemption.begin(
        actor_ref="character:char_a",
        player_ref="player:1",
        reason="player_interaction",
        tick=10,
        actor_revision=5,
    )

    closed = preemption.end(actor_ref="character:char_a", tick=20)

    assert closed.ended_tick == 20
    assert not closed.is_open
    assert not preemption.is_preempted("character:char_a")


def test_end_without_open_episode_is_refused() -> None:
    with pytest.raises(ValueError, match="preemption_not_open"):
        PlayerPreemption().end(actor_ref="character:char_a", tick=20)


def test_end_before_start_is_rejected() -> None:
    with pytest.raises(ValueError, match="preemption_end_before_start"):
        PreemptionEpisode(
            actor_ref="character:char_a",
            player_ref="player:1",
            reason="player_interaction",
            started_tick=20,
            ended_tick=10,
            actor_revision_at_start=5,
        )


def test_write_back_requires_an_open_preemption() -> None:
    # Otherwise a player write becomes a second writer of world facts.
    with pytest.raises(ValueError, match="write_back_without_preemption"):
        PlayerPreemption().write_back(intent=_intent(), current_actor_revision=5)


def test_write_back_from_a_non_holder_is_refused() -> None:
    preemption = PlayerPreemption()
    preemption.begin(
        actor_ref="character:char_a",
        player_ref="player:1",
        reason="player_interaction",
        tick=10,
        actor_revision=5,
    )

    with pytest.raises(ValueError, match="write_back_from_non_holder"):
        preemption.write_back(
            intent=_intent(player_ref="player:2"), current_actor_revision=5
        )


def test_stale_write_back_is_refused() -> None:
    preemption = PlayerPreemption()
    preemption.begin(
        actor_ref="character:char_a",
        player_ref="player:1",
        reason="player_interaction",
        tick=10,
        actor_revision=5,
    )

    with pytest.raises(ValueError, match="write_back_stale_revision"):
        preemption.write_back(intent=_intent(), current_actor_revision=9)


def test_valid_write_back_is_returned_not_settled() -> None:
    preemption = PlayerPreemption()
    preemption.begin(
        actor_ref="character:char_a",
        player_ref="player:1",
        reason="player_interaction",
        tick=10,
        actor_revision=5,
    )

    returned = preemption.write_back(intent=_intent(), current_actor_revision=5)

    # The intent still needs an owner settlement; nothing is committed here.
    assert returned.requires_owner_settlement
    assert returned.payload == {"dialogue_text": "hello"}


def test_write_back_cannot_claim_settlement() -> None:
    with pytest.raises(ValueError, match="write_back_claims_settlement"):
        _intent(payload={"settled": True})


def test_unknown_reason_is_rejected() -> None:
    with pytest.raises(Exception):
        PlayerPreemption().begin(
            actor_ref="character:char_a",
            player_ref="player:1",
            reason="because_i_want_to",
            tick=10,
            actor_revision=5,
        )
