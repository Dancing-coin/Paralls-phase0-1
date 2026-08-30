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


def test_activation_releases_lock_for_same_character_reactivation() -> None:
    instance = runtime()
    first = instance.activate_actor("char_a", active_dialogue_decision(), producer_ts=101)
    second = instance.activate_actor("char_a", active_dialogue_decision(), producer_ts=102)
    assert first.committed and second.committed
    assert second.status == "active"


def test_runtime_does_not_reach_into_authority_private_lock_state() -> None:
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "app" / "character_agent" / "runtime" / "runtime_loop.py"
    assert "authority._locks" not in source.read_text(encoding="utf-8")
