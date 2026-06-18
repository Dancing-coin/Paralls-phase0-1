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
    assert "character_agent_execution_probe:execution_payload_direct=true" in source


def test_phase0_verify_script_reads_character_agent_execution_probe_report() -> None:
    source = (Path(__file__).resolve().parents[1] / "verify_phase0.py").read_text(encoding="utf-8")

    assert "verify_character_agent_execution.py" in source
    assert "character-agent-execution-report.json" in source
    assert "character_agent_execution_consumer" in source
    assert '"PHASE0_DEBUG_LOGGING": "1"' not in source
    assert '"--quit-after"' in source
    assert '"1800"' in source or '"2000"' in source


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
