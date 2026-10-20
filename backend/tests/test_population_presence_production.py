"""Explicit deployment admission through the actual runtime execution ingress."""
import asyncio

import pytest

from app.config import Settings
from app.population_continuity.models import ActivationGrant, ActivationProposal


GRANT = ActivationGrant(profile_ref="character:char_a", world_ref="world:bakery",
    package_revision="package:bakery-authored-agents:v1", policy_revision="policy:population:v1",
    scope_grant=("actor:self",))
PRODUCER = "population:siming"


def proposal(**changes):
    values = dict(proposal_id="activate:production", profile_ref=GRANT.profile_ref,
        world_ref=GRANT.world_ref, package_revision=GRANT.package_revision,
        policy_revision=GRANT.policy_revision, scope_grant=GRANT.scope_grant,
        cadence_class="active", activation_reason="admitted population request",
        source_ref=PRODUCER, expected_revisions={"population:world:bakery": 0},
        idempotency_key="activate:production", correlation_id="correlation:production")
    return ActivationProposal(**(values | changes))


def test_deployment_grants_are_explicit_and_typed():
    assert Settings().population_activation_grants == []
    configured = Settings(population_activation_grants=[GRANT.model_dump()],
        population_activation_producer_ref=PRODUCER)
    assert configured.population_activation_grants == [GRANT]
    with pytest.raises(ValueError):
        Settings(population_activation_producer_ref=" ")


@pytest.mark.asyncio
@pytest.mark.parametrize("admission", ["allowed", "life_response_lost", "no_grant", "wrong_producer", "wrong_package"])
async def test_runtime_ingress_uses_bound_source_and_durable_initial_life(tmp_path, monkeypatch, admission):
    from app import main

    monkeypatch.setattr(main.settings, "heavenly_graph_path", str(tmp_path / "world.sqlite3"))
    monkeypatch.setattr(main.settings, "character_model_provider_kind", "local")
    monkeypatch.setattr(main.settings, "siming_llm_mode", "disabled")
    monkeypatch.setattr(main.settings, "population_activation_grants", [] if admission == "no_grant" else [GRANT])
    monkeypatch.setattr(main.settings, "population_activation_producer_ref", PRODUCER)
    idle = asyncio.Event()

    async def pause(_):
        idle.set()
        await asyncio.Future()

    monkeypatch.setattr(main, "_population_runtime_sleep", pause)
    request = proposal(**({"source_ref": "population:untrusted"} if admission == "wrong_producer" else
                          {"package_revision": "package:other"} if admission == "wrong_package" else {}))
    original_ids = None
    for cycle in range(2 if admission in {"allowed", "life_response_lost"} else 1):
        try:
            idle.clear()
            await main._start_population_runtime_on_startup()
            await asyncio.wait_for(idle.wait(), 5)
            if admission == "life_response_lost" and cycle == 0:
                def lose_response():
                    owner = main.population_activation_presence_service.life_state_authority
                    original = owner.initialize_alive_from_presence
                    def commit_then_lose(**kwargs):
                        assert original(**kwargs).committed
                        raise ValueError("simulated_lost_life_response")
                    owner.initialize_alive_from_presence = commit_then_lose
                await asyncio.wrap_future(main.runtime_execution.submit(lose_response))
            before = await asyncio.wrap_future(main.runtime_execution.submit(lambda: main.gameplay_event_store.read_events()))
            result = await asyncio.wrap_future(main.submit_population_activation_presence(
                proposal=request, presence_idempotency_key="presence:production", presence_expected_revision=0))

            def inspect():
                nonlocal original_ids
                store = main.gameplay_event_store
                if admission not in {"allowed", "life_response_lost"}:
                    assert not result.activation.committed
                    assert store.read_events() == before
                    return
                assert result.activation.committed and result.presence.committed
                if admission == "life_response_lost" and cycle == 0:
                    assert result.recovery_required and not result.life_state.committed
                    lives = store.read_events(event_type="gameplay.character.life_state_changed")
                    assert len(lives) == 1
                    original_ids = (*result.activation.committed_event_ids, *result.presence.committed_event_ids,
                                    lives[0].event_id)
                    return
                assert result.life_state.committed
                ids = (*result.activation.committed_event_ids, *result.presence.committed_event_ids,
                       *result.life_state.committed_event_ids)
                assert len(set(ids)) == 3
                life = store.get_event(ids[-1])
                assert life.schema_version == 2 and life.payload["to_state"] == "alive"
                assert life.payload["source_presence_event_id"] == ids[1]
                assert life.payload["source_activation_event_id"] == ids[0]
                tx = store.get_transaction(life.transaction_id)
                assert tx.idempotency_record.principal_ref == "authority:character:life-state:presence-admission"
                assert tx.read_stream_revisions == {"population:world:bakery": 1, "presence:world:bakery": 1}
                if original_ids is not None:
                    assert ids == original_ids
                    assert store.read_events() == before
                original_ids = ids

            await asyncio.wrap_future(main.runtime_execution.submit(inspect))
        finally:
            await main._stop_population_runtime_on_shutdown()
