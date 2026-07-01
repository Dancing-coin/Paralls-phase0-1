from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_mainline_unified_runtime as verifier


def test_runtime_verifier_retries_until_report_turns_green(monkeypatch, tmp_path: Path) -> None:
    attempts = {"count": 0}
    report_path = tmp_path / "actor-local-report.json"

    def fake_run_profile(**_kwargs):
        attempts["count"] += 1
        return (1 if attempts["count"] == 1 else 0, str(tmp_path / f"attempt-{attempts['count']}.log"))

    def fake_load_report(_path: Path) -> dict[str, object]:
        if attempts["count"] == 1:
            return {"overall_actor_local_perception_passed": False}
        return {"overall_actor_local_perception_passed": True}

    monkeypatch.setattr(verifier, "_run_profile", fake_run_profile)
    monkeypatch.setattr(verifier, "_load_report", fake_load_report)

    result, artifacts = verifier._run_runtime_verifier_with_retry(
        project_root=tmp_path,
        python_exe="python",
        log_dir=tmp_path,
        result_id="actor_local_perception",
        title="Actor-local perception runtime proof passes",
        script_name="verify_actor_local_perception.py",
        report_path=report_path,
        log_name="actor-local.log",
        godot_exe=Path("godot.exe"),
    )

    assert attempts["count"] == 2
    assert result["status"] == "proved"
    assert artifacts["log"].endswith("attempt-2.log")


def test_mainline_unified_runtime_report_shape(tmp_path: Path) -> None:
    report = {
        "results": [
            {
                "id": "mainline_world_runtime_suite",
                "title": "Canonical world-runtime model, routing, projection, scheduling, and continuity checks pass",
                "status": "proved",
                "evidence": ["world-runtime.log"],
                "notes": "",
            }
        ],
        "overall_mainline_unified_runtime_passed": True,
        "artifacts": {"world_runtime_log": "world-runtime.log"},
    }

    json_path = tmp_path / "mainline-unified-runtime-report.json"
    md_path = tmp_path / "mainline-unified-runtime-report.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    verifier.write_markdown(
        md_path,
        "Mainline Unified Runtime Verification Report",
        report,
        "overall_mainline_unified_runtime_passed",
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = md_path.read_text(encoding="utf-8")

    assert payload["overall_mainline_unified_runtime_passed"] is True
    assert payload["results"][0]["id"] == "mainline_world_runtime_suite"
    assert markdown.startswith("# Mainline Unified Runtime Verification Report")


def test_mainline_unified_runtime_verifier_includes_scheduling_summary_runtime_evidence() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")

    assert (
        "test_runtime_observatory_snapshot_carries_scheduling_summary_for_degraded_population"
        in source
    )


def test_mainline_unified_runtime_verifier_includes_scheduling_state_runtime_evidence() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")

    assert (
        "test_runtime_emits_scheduling_state_event_for_selected_actor_under_population_pressure"
        in source
    )


def test_mainline_unified_runtime_verifier_includes_unified_scheduling_state_runtime_evidence() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")

    assert (
        "test_runtime_exposes_unified_scheduling_state_for_population_tick"
        in source
    )


def test_mainline_unified_runtime_verifier_includes_scheduling_round_runtime_evidence() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")

    assert (
        "test_runtime_scheduling_round_state_advances_round_id_when_new_runtime_tick_arrives"
        in source
    )


def test_mainline_unified_runtime_verifier_includes_scheduling_selection_reason_runtime_evidence() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")

    assert (
        "test_runtime_scheduling_state_exposes_selection_reason_tags_for_active_actor_set"
        in source
    )


def test_mainline_unified_runtime_verifier_includes_scheduling_round_summary_runtime_evidence() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")

    assert (
        "test_runtime_scheduling_state_exposes_round_summary_and_reason_tags_for_active_actor_set"
        in source
    )


def test_mainline_unified_runtime_verifier_includes_scheduling_round_state_runtime_evidence() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")

    assert (
        "test_runtime_emits_single_scheduling_round_state_event_with_unified_summary"
        in source
    )


def test_mainline_unified_runtime_verifier_includes_scheduling_round_debug_stream_evidence() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")

    assert (
        "test_debug_ws_replays_scheduling_round_state_observatory_event"
        in source
    )


def test_mainline_unified_runtime_verifier_includes_scheduling_round_script_beat_debug_stream_evidence() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")

    assert (
        "test_debug_ws_replays_script_beat_event_for_scheduling_round_summary"
        in source
    )


def test_mainline_unified_runtime_verifier_includes_scheduling_round_trace_debug_stream_evidence() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")

    assert (
        "test_debug_ws_replays_scheduling_round_trace_event"
        in source
    )


def test_mainline_unified_runtime_verifier_includes_scheduling_round_trace_runtime_evidence() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")

    assert (
        "test_character_agent_execution_route_emits_scheduling_round_trace"
        in source
    )


def test_mainline_unified_runtime_verifier_includes_websocket_scheduling_round_trace_evidence() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")

    assert (
        "test_websocket_character_agent_execution_emits_scheduling_round_trace"
        in source
    )


def test_mainline_unified_runtime_verifier_includes_interact_websocket_scheduling_round_trace_evidence() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")

    assert (
        "test_websocket_interact_intent_emits_scheduling_round_trace_after_character_agent_execution"
        in source
    )


def test_mainline_unified_runtime_verifier_includes_frontend_scheduling_round_trace_chain_evidence() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")

    assert "backend/tests/test_observatory_message_delivery_static.py" in source
    assert "backend/tests/test_character_director_state_static.py" in source


def test_mainline_unified_runtime_verifier_includes_asset_registry_and_kimodo_contract_evidence() -> None:
    source = Path(verifier.__file__).read_text(encoding="utf-8")

    assert "backend/tests/test_character_asset_registry_static.py" in source
    assert "backend/tests/test_kimodo_adapter_contract.py" in source
