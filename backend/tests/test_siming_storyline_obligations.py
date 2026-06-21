from app.models.siming_runtime_state import (
    GroupSimulationBranchSnapshot,
    StateTreeNode,
    StateTreeSnapshot,
    StorylineMarker,
    StorylineStateSnapshot,
)
from app.services.siming_storyline import (
    InMemoryNarrativeObligationLedger,
    InMemoryStorylineState,
)


def make_state_tree() -> StateTreeSnapshot:
    return StateTreeSnapshot(
        snapshot_id="state_tree:room_demo:1",
        schema_version=1,
        producer_system="siming.state_tree",
        room_id="room_demo",
        scene_id="scene_demo",
        zone_id="zone_focus",
        world_ts=300,
        sim_tick_ts=301,
        causation_id="visual_fact:300",
        correlation_id="visual_fact:300",
        environment=StateTreeNode(
            node_id="environment:env_lamp",
            owner_system="L1/ESM",
            authority="mirror",
            status="fresh",
            summary={"established_fact_id": "visual_fact:300:char_c:light_level_drop"},
        ),
        character=StateTreeNode(
            node_id="character:char_b",
            owner_system="character_agent",
            authority="mirror",
            status="fresh",
            summary={"target_actor_id": "char_b"},
        ),
        storyline=StateTreeNode(
            node_id="storyline:room_demo:main",
            owner_system="siming",
            authority="editable",
            status="fresh",
            summary={"active_phase": "rising"},
        ),
        group_simulation=GroupSimulationBranchSnapshot(status="unavailable", summary={}),
    )


def test_storyline_state_builds_runtime_markers_from_state_tree() -> None:
    state_tree = make_state_tree()
    storyline = InMemoryStorylineState().update_from_state_tree(state_tree)

    assert storyline.active_phase == "rising"
    assert storyline.markers[0].marker_type == "information_visibility"
    assert storyline.markers[0].entity_refs == ["environment:env_lamp", "character:char_b"]


def test_obligation_ledger_turns_storyline_markers_into_trackable_debt() -> None:
    state_tree = make_state_tree()
    storyline = InMemoryStorylineState().update_from_state_tree(state_tree)
    ledger = InMemoryNarrativeObligationLedger().update_from_storyline(storyline)

    assert ledger.obligations[0].obligation_type == "unresolved_reveal"
    assert ledger.obligations[0].status == "open"
    assert ledger.obligations[0].source_ref == storyline.markers[0].marker_id


def test_obligation_ledger_ignores_resolved_markers() -> None:
    storyline = StorylineStateSnapshot(
        snapshot_id="storyline:room_demo:2",
        schema_version=1,
        producer_system="siming.storyline",
        room_id="room_demo",
        world_ts=302,
        sim_tick_ts=303,
        causation_id="visual_fact:302",
        correlation_id="visual_fact:302",
        active_phase="rising",
        markers=[
            StorylineMarker(
                marker_id="marker:resolved",
                marker_type="information_visibility",
                status="resolved",
                entity_refs=["environment:env_lamp", "character:char_b"],
                reason="The reveal has already been fulfilled.",
            )
        ],
    )

    ledger = InMemoryNarrativeObligationLedger().update_from_storyline(storyline)

    assert ledger.obligations == []


def test_obligation_ledger_turns_stalled_marker_into_open_obligation() -> None:
    storyline = StorylineStateSnapshot(
        snapshot_id="storyline:room_demo:stalled",
        schema_version=1,
        producer_system="siming.storyline",
        room_id="room_demo",
        world_ts=304,
        sim_tick_ts=305,
        causation_id="visual_fact:304",
        correlation_id="visual_fact:304",
        active_phase="rising",
        markers=[
            StorylineMarker(
                marker_id="marker:stalled",
                marker_type="information_visibility",
                status="stalled",
                entity_refs=["environment:env_lamp", "character:char_b"],
                reason="The reveal surface exists but delivery is not progressing.",
            )
        ],
    )

    ledger = InMemoryNarrativeObligationLedger().update_from_storyline(storyline)

    assert len(ledger.obligations) == 1
    assert ledger.obligations[0].status == "open"
    assert ledger.obligations[0].source_ref == "marker:stalled"


def test_partial_environment_produces_no_markers_or_obligations() -> None:
    state_tree = make_state_tree()
    state_tree.environment.status = "partial"

    storyline = InMemoryStorylineState().update_from_state_tree(state_tree)
    ledger = InMemoryNarrativeObligationLedger().update_from_storyline(storyline)

    assert storyline.active_phase == "rising"
    assert storyline.markers == []
    assert ledger.obligations == []


def test_partial_character_produces_no_markers_or_obligations() -> None:
    state_tree = make_state_tree()
    state_tree.character.status = "partial"

    storyline = InMemoryStorylineState().update_from_state_tree(state_tree)
    ledger = InMemoryNarrativeObligationLedger().update_from_storyline(storyline)

    assert storyline.active_phase == "rising"
    assert storyline.markers == []
    assert ledger.obligations == []


def test_empty_fact_id_produces_no_markers_or_obligations() -> None:
    state_tree = make_state_tree()
    state_tree.environment.summary["established_fact_id"] = ""

    storyline = InMemoryStorylineState().update_from_state_tree(state_tree)
    ledger = InMemoryNarrativeObligationLedger().update_from_storyline(storyline)

    assert storyline.active_phase == "rising"
    assert storyline.markers == []
    assert ledger.obligations == []


def test_none_fact_id_produces_no_markers_or_obligations() -> None:
    state_tree = make_state_tree()
    state_tree.environment.summary["established_fact_id"] = None

    storyline = InMemoryStorylineState().update_from_state_tree(state_tree)
    ledger = InMemoryNarrativeObligationLedger().update_from_storyline(storyline)

    assert storyline.active_phase == "rising"
    assert storyline.markers == []
    assert ledger.obligations == []


def test_missing_fact_id_produces_no_markers_or_obligations() -> None:
    state_tree = make_state_tree()
    del state_tree.environment.summary["established_fact_id"]

    storyline = InMemoryStorylineState().update_from_state_tree(state_tree)
    ledger = InMemoryNarrativeObligationLedger().update_from_storyline(storyline)

    assert storyline.active_phase == "rising"
    assert storyline.markers == []
    assert ledger.obligations == []
