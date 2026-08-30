from app.character_agent.runtime.runtime_loop import CharacterAgentRuntime
from app.gameplay.event_store import GameplayEventStore
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.models import ActivationDecision


def active_dialogue_decision() -> ActivationDecision:
    return ActivationDecision(actor_id="char_a", state="active", reason="player_dialogue", requires_activation_lock=True, load_private_memory=True, policy_revision="policy:activation:v1")


def runtime() -> CharacterAgentRuntime:
    instance = CharacterAgentRuntime()
    instance.set_activation_authority(
        ProfileActivationAuthority(registry=instance._profile_registry, store=GameplayEventStore())
    )
    return instance


def test_activation_preserves_same_character_identity() -> None:
    instance = runtime()
    before = instance.character_identity_digest("char_a")
    receipt = instance.activate_actor("char_a", active_dialogue_decision(), producer_ts=101)
    assert receipt.committed
    assert instance.character_identity_digest("char_a") == before


def test_activation_lock_conflict_requeues_without_duplicate_runtime_state() -> None:
    instance = runtime()
    instance.activate_actor("char_a", active_dialogue_decision(), producer_ts=101)
    second = instance.activate_actor("char_a", active_dialogue_decision(), producer_ts=102)
    assert second.status == "requeued"
    assert second.stop_reason == "activation_lock_conflict"
