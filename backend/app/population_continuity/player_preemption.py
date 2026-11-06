"""Player preemption and the write-back contract.

When a player takes over an actor, two things must stay true: the actor's own
continuity is not rewritten by the player, and whatever the player did becomes a
*structured intent* that the domain owner still settles.  Without this, a takeover
becomes a second writer of world facts.

This module models the takeover as an explicit, bounded episode with a recorded
reason and an end, so "the player is currently driving this actor" is a claim that
can expire rather than a hidden flag.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# The control modes the character runtime already distinguishes.  Preemption is
# only meaningful against an agent that could otherwise act.
ControlMode = Literal[
    "agent_full_auto",
    "player_priority_assisted",
    "away_conservative_takeover",
    "scripted_override",
]

PreemptionReason = Literal[
    "player_interaction",
    "player_proximity",
    "critical_plot_beat",
    "debug_inspection",
]

PREEMPTION_REASONS: tuple[str, ...] = (
    "player_interaction",
    "player_proximity",
    "critical_plot_beat",
    "debug_inspection",
)


class PreemptionEpisode(BaseModel):
    """One bounded takeover of an actor by the player."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_ref: str = Field(min_length=1)
    player_ref: str = Field(min_length=1)
    reason: PreemptionReason
    started_tick: int = Field(ge=0)
    # None means still held.  Every episode must be closable; an unbounded takeover
    # would silently disable the actor's own continuity.
    ended_tick: int | None = Field(default=None, ge=0)
    # The actor revision observed at takeover, so write-back can detect that the
    # actor changed underneath the player.
    actor_revision_at_start: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_window(self) -> "PreemptionEpisode":
        if self.ended_tick is not None and self.ended_tick < self.started_tick:
            raise ValueError("preemption_end_before_start")
        return self

    @property
    def is_open(self) -> bool:
        return self.ended_tick is None


class WriteBackIntent(BaseModel):
    """What the player's takeover produces: an intent, never a settled fact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    actor_ref: str = Field(min_length=1)
    player_ref: str = Field(min_length=1)
    intent_kind: str = Field(min_length=1)
    payload: dict[str, object] = Field(default_factory=dict)
    # Carried so the owner can reject a write-back that arrived after the actor
    # moved on; a stale intent must not silently overwrite newer state.
    actor_revision_at_start: int = Field(ge=0)
    # Explicit: a settlement still has to happen elsewhere.
    requires_owner_settlement: bool = True

    @model_validator(mode="after")
    def validate_not_a_fact(self) -> "WriteBackIntent":
        forbidden = {"settled", "committed", "world_effect_applied"}.intersection(
            self.payload
        )
        if forbidden:
            raise ValueError(
                f"write_back_claims_settlement:{','.join(sorted(forbidden))}"
            )
        return self


class PlayerPreemption:
    """Tracks open takeovers and refuses overlapping or stale write-backs."""

    def __init__(self) -> None:
        self._open: dict[str, PreemptionEpisode] = {}

    def begin(
        self,
        *,
        actor_ref: str,
        player_ref: str,
        reason: str,
        tick: int,
        actor_revision: int,
    ) -> PreemptionEpisode:
        if actor_ref in self._open:
            raise ValueError("preemption_already_open")
        episode = PreemptionEpisode(
            actor_ref=actor_ref,
            player_ref=player_ref,
            reason=reason,
            started_tick=tick,
            actor_revision_at_start=actor_revision,
        )
        self._open[actor_ref] = episode
        return episode

    def end(self, *, actor_ref: str, tick: int) -> PreemptionEpisode:
        episode = self._open.pop(actor_ref, None)
        if episode is None:
            raise ValueError("preemption_not_open")
        return episode.model_copy(update={"ended_tick": tick})

    def is_preempted(self, actor_ref: str) -> bool:
        return actor_ref in self._open

    def open_episode(self, actor_ref: str) -> PreemptionEpisode | None:
        return self._open.get(actor_ref)

    def write_back(
        self,
        *,
        intent: WriteBackIntent,
        current_actor_revision: int,
    ) -> WriteBackIntent:
        """Accept a write-back only from the player who currently holds the actor.

        Returns the intent for the owner to settle; it does not settle anything.
        """
        episode = self._open.get(intent.actor_ref)
        if episode is None:
            raise ValueError("write_back_without_preemption")
        if episode.player_ref != intent.player_ref:
            raise ValueError("write_back_from_non_holder")
        if current_actor_revision != intent.actor_revision_at_start:
            raise ValueError("write_back_stale_revision")
        return intent
