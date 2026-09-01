from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.character_agent.services.character_continuity import CharacterRuntimeContinuityPort
from app.gameplay.event_store import GameplayEventStore
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.activation_policy import ActivationPolicy
from app.population_continuity.models import ActivationDecision
from app.services.siming_population_capability import PopulationSimulationCapability

from test_siming_population_cohort_capability import _Owner, _read_set


class CohortCapabilityFixture:
    def __init__(self) -> None:
        self.character = CharacterAgentRuntime()
        self.character.set_activation_authority(
            ProfileActivationAuthority(
                registry=self.character._profile_registry,
                store=GameplayEventStore(),
            )
        )
        self.owner = _Owner()
        self.continuity = CharacterRuntimeContinuityPort(self.character)
        self.capability = PopulationSimulationCapability(
            owner_executor=self.owner,
            continuity_port=self.continuity,
        )

    @classmethod
    def create(cls) -> "CohortCapabilityFixture":
        return cls()

    def run_window(self, window: str = "W0"):
        cadence, read_set = _read_set(window)
        return self.capability.run_cohort_cycle(cadence, read_set)

    def player_dialogue_char_c(self, *, cognition_callback):
        decision = ActivationPolicy().evaluate(
            actor_id="char_c",
            distance_m=0.0,
            focused=True,
            interaction_type="dialogue",
            pending_seed=False,
            budget=1,
        )
        return self.character.activate_actor(
            "char_c",
            decision,
            producer_ts=2,
            cognition_callback=cognition_callback,
        )


def test_char_b_seed_is_actor_local_and_has_no_pending_memory() -> None:
    fixture = CohortCapabilityFixture.create()
    fixture.run_window("W0")
    assert fixture.character.get_seed_projection("char_b")["presentation_seed"]["behavior_kind"] == "routine_work"
    assert fixture.character.get_pending_seed_candidates("char_b") == []
    assert fixture.character.get_memory_bundle("char_b")["event_memories"] == []


def test_char_c_player_dialogue_activates_same_identity_under_lock() -> None:
    fixture = CohortCapabilityFixture.create()
    fixture.run_window("W0")
    before = fixture.character.character_identity_digest("char_c")
    seen_lock: list[bool] = []
    receipt = fixture.player_dialogue_char_c(
        cognition_callback=lambda: seen_lock.append(
            fixture.character.activation_lock_is_active("char_c")
        )
    )
    assert receipt.status == "active"
    assert seen_lock == [True]
    assert fixture.character.character_identity_digest("char_c") == before


def test_char_c_without_player_input_never_gets_continuity_command() -> None:
    fixture = CohortCapabilityFixture.create()
    result = fixture.run_window("W0")
    assert result.report.activation_candidates == ("projection:char_c:W0",)
    assert fixture.character.get_continuity_revision("char_c") == 0
