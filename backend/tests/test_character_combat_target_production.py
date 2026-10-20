"""Actual startup joins admitted world sources into the private target catalog."""
import asyncio

import pytest
from fastapi.testclient import TestClient

from app.models.character_perceived import CharacterPerceivedEvent
from app.population_continuity.models import ActivationGrant, ActivationProposal
from app.population_continuity.presence_runtime import CharacterDespawnRequest
from test_combat_faction_admin_application import runtime, HEADERS, PATH


@pytest.mark.asyncio
async def test_private_combat_sources_are_current_visible_and_read_only(runtime, monkeypatch):
    main, payload, start = runtime
    world = payload["world_ref"]
    grants = [ActivationGrant(profile_ref="character:" + actor, world_ref=world,
        package_revision="package:bakery-authored-agents:v1", policy_revision="policy:population:v1",
        scope_grant=("actor:self",)) for actor in ("char_a", "char_b")]
    monkeypatch.setattr(main.settings, "population_activation_grants", grants)
    await main._stop_population_runtime_on_shutdown()
    await start()

    async def command(fn):
        return await asyncio.wrap_future(main.runtime_execution.submit(fn))

    for index, grant in enumerate(grants):
        request = ActivationProposal(proposal_id=f"activate:target:{index}",
            **grant.model_dump(), cadence_class="active", activation_reason="explicit test deployment grant",
            source_ref="population:siming", expected_revisions={f"population:{world}": index},
            idempotency_key=f"activate:target:{index}", correlation_id="correlation:targets")
        result = await asyncio.wrap_future(main.submit_population_activation_presence(
            proposal=request, presence_idempotency_key=f"presence:target:{index}",
            presence_expected_revision=index))
        assert result.activation.committed and result.presence.committed and result.life_state.committed

    timeline = await command(lambda: main._population_runtime_driver.clock.timeline.timeline_id)
    client = TestClient(main.component_app, client=("127.0.0.1", 48110))

    def observe(target="char_b", channel="visual"):
        event = CharacterPerceivedEvent(actor_id="char_a", percept_channel=channel,
            producer_ts=200, room_id="room_demo", scene_id="scene_demo", zone_id="zone_focus",
            target_actor_id=target, perceived_summary="an observed actor",
            source_candidate_event_id="perceived:target:200")
        return main.character_agent_runtime._l1.apply_character_perceived_event(event)

    try:
        # An arbitrary requested faction timeline cannot authorize current combat.
        assert client.post(PATH, json=payload, headers=HEADERS).status_code == 200
        assert (await command(observe)).target_catalog == []
        current = dict(payload, timeline_ref=timeline, command_id="faction:current",
                       idempotency_key="faction:current")
        assert client.post(PATH, json=current, headers=HEADERS).status_code == 200
        before = await command(main.gameplay_event_store.read_events)
        snapshot = await command(observe)
        descriptor, = snapshot.target_catalog
        assert descriptor["target_ref"] == "char_b"
        assert descriptor["target_refs"] == {"character": "char_b"}
        assert descriptor["combat_source_context"]["timeline_ref"] == timeline
        assert len(descriptor["combat_source_context"]["source_event_ids"]) == 5
        assert descriptor["target_revision_vector"]
        assert descriptor["target_admission_digest"].startswith("sha256:")
        assert descriptor["target_provenance"] == ["perceived:target:200"]
        # Eligibility is not a capability grant or physics/contact evidence.
        assert descriptor["supported_intents"] == []
        assert descriptor["affordance_result"]["status"] == "unavailable"
        assert (await command(lambda: observe("char_unknown"))).target_catalog == []
        assert (await command(lambda: observe("char_a"))).target_catalog == []
        assert await command(main.gameplay_event_store.read_events) == before
        # Restart recovers canonical sources; resolver reads the new driver/store.
        await main._stop_population_runtime_on_shutdown()
        await start()
        assert (await command(observe)).target_catalog[0]["target_admission_digest"] == descriptor["target_admission_digest"]
        revoke = dict(current, hostile=False, command_id="faction:revoke", idempotency_key="faction:revoke")
        assert client.post(PATH, json=revoke, headers=HEADERS).status_code == 200
        after = await command(main.gameplay_event_store.read_events)
        assert (await command(observe)).target_catalog == []
        assert await command(main.gameplay_event_store.read_events) == after
        restore = dict(current, command_id="faction:restore", idempotency_key="faction:restore")
        assert client.post(PATH, json=restore, headers=HEADERS).status_code == 200
        assert (await command(observe)).target_catalog
        def despawn():
            owner = main.population_presence_authority
            return owner.despawn(CharacterDespawnRequest(world_ref=world,
                character_ref="character:char_b", incarnation=1, reason="admitted departure",
                expected_revision=main.gameplay_event_store.get_stream_head(f"presence:{world}"),
                idempotency_key="presence:target:departure"))
        assert (await command(despawn)).committed
        after = await command(main.gameplay_event_store.read_events)
        assert (await command(observe)).target_catalog == []
        assert await command(main.gameplay_event_store.read_events) == after
    finally:
        client.close()
