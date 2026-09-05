from __future__ import annotations

from app.gameplay.p5.stormnight_action_graph import admit_stormnight_action_graph, stormnight_action_graph, stormnight_action_registry


def test_stormnight_graph_is_admitted_over_registered_primitives() -> None:
    result = admit_stormnight_action_graph()
    assert result.accepted
    assert result.graph_digest and result.graph_digest.startswith("sha256:")
    assert stormnight_action_graph().graph_ref == "graph:stormnight-investigation@1"


def test_stormnight_registry_has_exact_conflict_event_surface() -> None:
    registry = stormnight_action_registry()
    assert registry.require_event("gameplay.conflict.action_window_resolved", 1).stream_grammar_ref == "grammar:stormnight:encounter@1"
