from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import harness
import verify_siming_backend_chain as siming_backend_chain
from registry import load_profile_registry


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_siming_backend_chain_profile_is_registered() -> None:
    registry = load_profile_registry(PROJECT_ROOT)

    assert "siming-backend-chain" in registry.profiles
    profile = registry.profiles["siming-backend-chain"]
    assert profile["script"] == "scripts/verification/verify_siming_backend_chain.py"
    assert profile["requires_godot"] is False
    assert profile["include_in_all"] is False
    assert profile["result_artifact"] == ".harness/verification/siming-backend-chain-report.json"
    assert "siming-backend-chain" not in harness._profiles_for_selection("all", registry)
    assert harness._profiles_for_selection("siming-backend-chain", registry) == ["siming-backend-chain"]


def test_component_only_console_output_is_bilingual_and_writes_report() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verification/verify_siming_backend_chain.py", "--component-only"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0
    assert "司命后端主链证明 / Siming Backend Chain Proof" in result.stdout
    assert "权威事件已接收 / authority event accepted" in result.stdout
    assert "事件生产者已发布 / producer published authority event" in result.stdout
    assert "结果=通过 / result=PASS" in result.stdout
    assert "scenario=app_wiring_live_deepseek_chain" not in result.stdout

    report_path = PROJECT_ROOT / ".harness" / "verification" / "siming-backend-chain-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overall_siming_backend_chain_passed"] is True
    assert any(entry["id"] == "component_fallback_visual_fact_chain" for entry in report["results"])
    assert all(entry["id"] != "app_wiring_live_deepseek_chain" for entry in report["results"])


def test_live_deepseek_without_key_fails_bilingually() -> None:
    env = {
        **os.environ,
        "PYTHONIOENCODING": "utf-8",
        "SIMING_LLM_MODE": "http",
        "SIMING_LLM_PROVIDER_ORDER": "deepseek_chat",
        "SIMING_LLM_API_KEY": "",
        "SIMING_LLM_DEEPSEEK_API_KEY": "",
        "DEEPSEEK_API_KEY": "",
        "SIMING_LLM_ENDPOINT": "https://api.deepseek.com/chat/completions",
        "SIMING_LLM_MODEL": "deepseek-chat",
        "SIMING_LLM_TIMEOUT_SECONDS": "8.0",
        "SIMING_BACKEND_CHAIN_LIVE_PROVIDERS": "deepseek_chat",
    }
    result = subprocess.run(
        [sys.executable, "scripts/verification/verify_siming_backend_chain.py"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )

    assert result.returncode == 1
    assert "scenario=app_wiring_live_deepseek_chain result=FAIL" in result.stdout
    assert "失败阶段 / failed_stage=credential_check" in result.stdout
    assert "实际 / actual=missing API key for deepseek_chat" in result.stdout

    report_path = PROJECT_ROOT / ".harness" / "verification" / "siming-backend-chain-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["overall_siming_backend_chain_passed"] is False
    live_entry = next(entry for entry in report["results"] if entry["id"] == "app_wiring_live_deepseek_chain")
    assert live_entry["status"] == "failed"
    assert "failed_stage=credential_check" in live_entry["notes"]


def test_live_provider_parser_preserves_deepseek_default_and_accepts_matrix() -> None:
    assert siming_backend_chain._parse_live_providers([]) == ["deepseek_chat"]
    assert siming_backend_chain._parse_live_providers(["deepseek_chat,qwen", "seed_doubao"]) == [
        "deepseek_chat",
        "qwen",
        "seed_doubao",
    ]


def test_live_qwen_without_key_is_reported_as_provider_specific_failure() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verification/verify_siming_backend_chain.py", "--component-only", "--live-provider", "qwen"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "SIMING_LLM_QWEN_API_KEY": "", "QWEN_API_KEY": ""},
    )

    assert result.returncode == 1
    assert "scenario=app_wiring_live_qwen_chain result=FAIL" in result.stdout
    assert "实际 / actual=missing API key for qwen" in result.stdout
