from __future__ import annotations

from scripts.verification.phase1b_contract_fixtures import (
    build_effect_resistance_fixture,
    build_object_ownership_fixture,
)


def test_fixture_builders_are_deterministic_and_pin_revisions() -> None:
    first = build_effect_resistance_fixture()
    second = build_effect_resistance_fixture()
    assert first == second
    assert first.command.pinned_revisions == {"policy": 1, "world": 1}
    assert first.command.payload["stream_ref"] == "stream:p1b:crop"


def test_structurally_different_fixtures_share_contract_and_scope_projection() -> None:
    effect = build_effect_resistance_fixture()
    object_fixture = build_object_ownership_fixture()
    assert effect.command.command_version == object_fixture.command.command_version == 1
    assert effect.command.expected_revisions.keys() != object_fixture.command.expected_revisions.keys()
    assert effect.expected_projection["scope"] == object_fixture.expected_projection["scope"] == "public"
    assert effect.owner_map != object_fixture.owner_map
