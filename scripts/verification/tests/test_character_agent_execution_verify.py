from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from common import write_json, write_markdown


def test_character_agent_execution_report_shape(tmp_path: Path) -> None:
    report = {
        "results": [
            {
                "id": "character_agent_execution_contract",
                "title": "Runtime character_agent_execution payload stays on the shared CharacterActor execution contract",
                "status": "proved",
                "evidence": ["character_agent_execution"],
                "notes": "",
            },
            {
                "id": "character_agent_execution_consumer",
                "title": "Shared actor runtime consumes the execution contract",
                "status": "proved",
                "evidence": ["character_agent_execution_applied"],
                "notes": "",
            }
        ],
        "overall_character_agent_execution_passed": True,
    }

    json_path = tmp_path / "character-agent-execution-report.json"
    md_path = tmp_path / "character-agent-execution-report.md"
    write_json(json_path, report)
    write_markdown(
        md_path,
        "Character Agent Execution Verification Report",
        report,
        "overall_character_agent_execution_passed",
    )

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = md_path.read_text(encoding="utf-8")

    assert payload["overall_character_agent_execution_passed"] is True
    assert payload["results"][0]["id"] == "character_agent_execution_contract"
    assert payload["results"][1]["id"] == "character_agent_execution_consumer"
    assert markdown.startswith("# Character Agent Execution Verification Report")


def test_character_agent_execution_verify_script_uses_probe_scene() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "verify_character_agent_execution.py"
    ).read_text(encoding="utf-8")

    assert "res://scenes/phase0/CharacterAgentExecutionProbe.tscn" in source
    assert "character-agent-execution-main.log" in source
    assert "character-agent-execution-focus.log" not in source
    assert '"PHASE0_DEBUG_LOGGING": "1"' in source
    assert '"CHARACTER_MODEL_PROVIDER_KIND": "local"' in source
    assert "character_agent_execution_probe:execution_payload_direct=true" in source
    assert "run_command_until_markers(" in source
    assert "character_agent_execution_probe:consumer_seen=true" in source


def test_character_director_observatory_verify_script_uses_marker_driven_runtime_closeout() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "verify_character_director_observatory.py"
    ).read_text(encoding="utf-8")

    assert "res://scenes/phase0/CharacterDirectorObservatoryProbe.tscn" in source
    assert "run_command_until_markers(" in source
    assert '"CHARACTER_MODEL_PROVIDER_KIND": "local"' in source
    assert '"CHARACTER_MODEL_ROUTE_OVERRIDE": "local_only"' in source
    assert "character_director_observatory_probe:state_payloads_ok=true" in source
    assert "character_director_observatory_probe:panels_populated=true" in source
    assert "character_director_observatory_probe:freeze_roundtrip_ok=true" in source


def test_phase0_verify_script_reads_character_agent_execution_probe_report() -> None:
    source = (Path(__file__).resolve().parents[1] / "verify_phase0.py").read_text(encoding="utf-8")

    assert "verify_character_agent_execution.py" in source
    assert "character-agent-execution-report.json" in source
    assert '"CHARACTER_MODEL_PROVIDER_KIND": "local"' in source
    assert '"character_agent_execution_contract"' in source
    assert "character_agent_execution_consumer" in source
    assert '"PHASE0_DEBUG_LOGGING": "1"' not in source
    assert "SCENE_LOAD_QUIT_AFTER" in source
    assert "MAIN_AUTOTEST_QUIT_AFTER" in source
    assert "FOCUS_AUTOTEST_QUIT_AFTER" in source
    assert '"PHASE0_SCENE_LOAD_ONLY": "1"' in source
    assert "run_command_until_markers(" in source
    assert "phase0_autotest_complete" in source
    assert "phase0_focus_autotest_complete" in source
    assert "verify_character_agent_execution.py" in source
    assert "verify_character_director_observatory.py" in source
    assert "character-agent-execution-from-phase0.log" in source
    assert "character-director-observatory-from-phase0.log" in source


def test_phase0_verify_script_runs_backend_pytest_before_starting_runtime_backend() -> None:
    source = (Path(__file__).resolve().parents[1] / "verify_phase0.py").read_text(encoding="utf-8")

    pytest_index = source.index('pytest_result = run_command([python_exe, "-m", "pytest", "-v"], project_root / "backend", pytest_log)')
    ensure_backend_index = source.index("health, backend_process = ensure_backend(")

    assert pytest_index < ensure_backend_index


def test_phase0_main_demo_ignores_preopen_disconnect_before_first_backend_connected() -> None:
    source = (
        Path(__file__).resolve().parents[2] / "phase0" / "MainDemoController.gd"
    ).read_text(encoding="utf-8")

    disconnect_section = source.split("func _on_backend_disconnected(_code: int = 0) -> void:", 1)[1].split(
        "func _on_backend_ack_received", 1
    )[0]

    assert "backend_connected_once" in source
    assert "if not backend_connected_once and _code == -1:" in disconnect_section
    assert "_request_backend_reconnect()" in disconnect_section.split(
        "if not backend_connected_once and _code == -1:", 1
    )[1].split("return", 1)[0]


def test_phase0_main_demo_supports_fast_scene_load_probe_mode() -> None:
    source = (
        Path(__file__).resolve().parents[2] / "phase0" / "MainDemoController.gd"
    ).read_text(encoding="utf-8")

    assert 'OS.get_environment("PHASE0_SCENE_LOAD_ONLY") == "1"' in source
    assert 'call_deferred("_finish_scene_load_probe")' in source
    assert "func _finish_scene_load_probe() -> void:" in source
    assert 'phase0_scene_load_probe_complete' in source
