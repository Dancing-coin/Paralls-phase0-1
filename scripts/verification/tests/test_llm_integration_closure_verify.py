from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_llm_integration_closure as closure
from registry import load_profile_registry


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_llm_integration_closure_profile_is_explicit_only() -> None:
    registry = load_profile_registry(PROJECT_ROOT)

    profile = registry.profiles["llm-integration-closure"]
    assert profile["script"] == "scripts/verification/verify_llm_integration_closure.py"
    assert profile["include_in_all"] is False


def test_closure_fails_missing_artifacts(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LLM_CLOSURE_RUN_ID", "fixture-run")
    monkeypatch.setattr(closure, "repo_root", lambda: tmp_path)

    report = closure.build_report()

    assert report["overall_llm_integration_closure_passed"] is False
    assert "missing_artifact:readiness" in report["errors"]


def test_closure_marks_historical_success_artifacts_unverified_when_run_ids_do_not_match(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LLM_CLOSURE_RUN_ID", "fresh-run")
    monkeypatch.setattr(closure, "repo_root", lambda: tmp_path)
    log_dir = tmp_path / ".harness" / "verification"
    log_dir.mkdir(parents=True)
    (log_dir / "model-provider-readiness-report.json").write_text(
        json.dumps(
            {
                "verification_run_id": "historical-run",
                "rows": [
                    {"provider_kind": "character_text", "provider_id": "deepseek", "model_id": "deepseek-chat"},
                    {"provider_kind": "siming_candidate", "provider_id": "deepseek_chat", "model_id": "deepseek-chat"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (log_dir / "character-model-live-report.json").write_text(
        json.dumps(
            {
                "verification_run_id": "historical-run",
                "provider": {"provider_kind": "deepseek", "model": "deepseek-chat"},
                "results": [
                    {"id": "dialogue_live_deepseek", "status": "passed", "transport_attempted": True, "transport_succeeded": True, "fallback_used": False},
                    {"id": "l2_live_deepseek", "status": "passed", "transport_attempted": True, "transport_succeeded": True, "fallback_used": False},
                    {"id": "l3_live_deepseek", "status": "passed", "transport_attempted": True, "transport_succeeded": True, "fallback_used": False},
                ],
            }
        ),
        encoding="utf-8",
    )
    (log_dir / "siming-backend-chain-report.json").write_text(
        json.dumps(
            {
                "verification_run_id": "historical-run",
                "results": [{"id": "app_wiring_live_deepseek_chain", "status": "passed"}],
            }
        ),
        encoding="utf-8",
    )

    report = closure.build_report()

    assert report["overall_llm_integration_closure_passed"] is False
    assert report["claims"] == {
        "character_dialogue_live": "unverified",
        "character_l2_live": "unverified",
        "character_l3_live": "unverified",
        "siming_deepseek_live": "unverified",
    }


def test_closure_passes_with_fresh_live_artifacts(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("LLM_CLOSURE_RUN_ID", "fixture-run")
    monkeypatch.setattr(closure, "repo_root", lambda: tmp_path)
    log_dir = tmp_path / ".harness" / "verification"
    log_dir.mkdir(parents=True)
    (log_dir / "model-provider-readiness-report.json").write_text(
        json.dumps(
            {
                "verification_run_id": "fixture-run",
                "rows": [
                    {"provider_kind": "character_text", "provider_id": "deepseek", "model_id": "deepseek-chat"},
                    {"provider_kind": "siming_candidate", "provider_id": "deepseek_chat", "model_id": "deepseek-chat"},
                ],
            }
        ),
        encoding="utf-8",
    )
    (log_dir / "character-model-live-report.json").write_text(
        json.dumps(
            {
                "verification_run_id": "fixture-run",
                "provider": {"provider_kind": "deepseek", "model": "deepseek-chat"},
                "results": [
                    {"id": "dialogue_live_deepseek", "status": "passed", "transport_attempted": True, "transport_succeeded": True, "fallback_used": False},
                    {"id": "l2_live_deepseek", "status": "passed", "transport_attempted": True, "transport_succeeded": True, "fallback_used": False},
                    {"id": "l3_live_deepseek", "status": "passed", "transport_attempted": True, "transport_succeeded": True, "fallback_used": False},
                ],
            }
        ),
        encoding="utf-8",
    )
    (log_dir / "siming-backend-chain-report.json").write_text(
        json.dumps(
            {
                "verification_run_id": "fixture-run",
                "results": [{"id": "app_wiring_live_deepseek_chain", "status": "passed"}],
            }
        ),
        encoding="utf-8",
    )

    report = closure.build_report()

    assert report["overall_llm_integration_closure_passed"] is True
    assert report["readiness_is_live_proof"] is False
