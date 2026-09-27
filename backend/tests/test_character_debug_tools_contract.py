from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_debug_snapshot_is_immutable_and_deep_copies_inputs() -> None:
    text = read("scripts/debug/CharacterRuntimeDebugSnapshot.gd")
    assert "freeze" in text
    assert "duplicate(true)" in text
    assert "setget" not in text


def test_test_panel_marks_debug_fixture_and_uses_controller_boundary() -> None:
    text = read("scripts/debug/CharacterRuntimeTestPanel.gd")
    assert "debug_fixture" in text
    assert "controller" in text.lower()
    assert "world_truth" not in text
    assert "global_position" not in text


def test_animation_preview_is_presentation_only() -> None:
    text = read("scripts/debug/CharacterAnimationDebugger.gd")
    assert "preview" in text
    assert "ActionAttempt" not in text
    assert "advance_simulation" not in text
    assert "global_position" not in text


def test_performance_monitor_has_bounded_buffer() -> None:
    text = read("scripts/debug/CharacterPerformanceMonitor.gd")
    assert "MAX_SAMPLES" in text
    assert "pop_front" in text
