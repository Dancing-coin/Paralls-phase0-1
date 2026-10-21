from pathlib import Path

from app.gameplay.event_store import GameplayEventStore, DurableGameplayEventStore
from app.population_continuity.activation import ProfileActivationAuthority
from app.population_continuity.activation_presence import PopulationActivationPresenceService
from app.population_continuity.identity_continuity import PresenceIdentityOwner
from app.population_continuity.models import ActivationGrant, ActivationProposal
from app.population_continuity.presence_runtime import PopulationPresenceAuthority, CharacterDespawnRequest
from app.character_agent.profile.registry import CharacterProfileRegistry

PROFILE_DIR = Path(__file__).resolve().parents[1].parent / "assets" / "characters" / "profiles"


def _proposal(**changes):
    values = dict(
        proposal_id="identity:activation", profile_ref="character:char_a", world_ref="world:identity",
        package_revision="package:v1", policy_revision="policy:v1", activation_reason="test",
        scope_grant=("actor:self",), cadence_class="simulation", expected_revisions={"population:world:identity": 0},
        idempotency_key="activation:identity", correlation_id="corr:identity", source_ref="population:identity",
    )
    values.update(changes)
    return ActivationProposal(**values)


def _service(store):
    activation = ProfileActivationAuthority(
        registry=CharacterProfileRegistry.from_directory(PROFILE_DIR), store=store,
        grants=(ActivationGrant(profile_ref="character:char_a", world_ref="world:identity", package_revision="package:v1", policy_revision="policy:v1", scope_grant=("actor:self",)),),
    )
    return PopulationActivationPresenceService(store=store, activation_authority=activation, presence_authority=PopulationPresenceAuthority(store=store))


def test_identity_owner_reports_presence_despawn_and_new_incarnation():
    store = GameplayEventStore(); service = _service(store)
    first = service.commit_and_spawn(_proposal(), presence_idempotency_key="presence:one", presence_expected_revision=0)
    owner = PresenceIdentityOwner(store=store)
    assert owner.read(world_ref="world:identity", character_ref="character:char_a").status == "present"
    assert service.presence_authority.despawn(CharacterDespawnRequest(world_ref="world:identity", character_ref="character:char_a", incarnation=1, reason="leave", idempotency_key="despawn:one", expected_revision=1)).committed
    assert owner.read(world_ref="world:identity", character_ref="character:char_a").status == "absent"
    second = service.commit_and_spawn(_proposal(proposal_id="identity:activation:2", idempotency_key="activation:identity:2", expected_revisions={"population:world:identity": 1}), presence_idempotency_key="presence:two", presence_expected_revision=2)
    assert second.presence.committed and second.presence.incarnation == 2
    assert owner.read(world_ref="world:identity", character_ref="character:char_a").incarnation == 2


def test_identity_owner_reports_confirmed_case_death_as_dead(tmp_path):
    store = GameplayEventStore()
    service = _service(store)
    service.commit_and_spawn(_proposal(), presence_idempotency_key="presence:death", presence_expected_revision=0)
    stream = "gameplay:character:life:character:char_a"
    from app.gameplay.settlement_plan import build_atomic_event_batch
    death = store.append_batch(build_atomic_event_batch(
        command_id="death", principal_ref="authority:character:life-state",
        stream_id=stream, expected_revision=store.get_stream_head(stream),
        event_specs=[("gameplay.character.life_state_changed", {
            "actor_ref": "character:char_a", "to_state": "dead",
        })], idempotency_key="death", causation_id="death", correlation_id="death"))
    assert death.committed
    result = PresenceIdentityOwner(store=store).read(world_ref="world:identity", character_ref="character:char_a")
    assert result.status == "dead"
