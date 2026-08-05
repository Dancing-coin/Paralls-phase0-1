from __future__ import annotations

import json
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verify_siming_heavenly_runtime import (  # noqa: E402
    LiveEvidence,
    evaluate_live_evidence,
    live_preflight,
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def valid_live_evidence(tmp_path: Path) -> LiveEvidence:
    captures = []
    for name in (
        "siming-heavenly-before-destruction.png",
        "siming-heavenly-after-destruction.png",
        "siming-heavenly-char-b-reaction.png",
    ):
        path = tmp_path / name
        path.write_bytes(b"\x89PNG\r\n\x1a\nmeaningful")
        captures.append(path)
    return LiveEvidence(
        result_ids={
            "preflight_live_ready",
            "authority_removed_from_surface",
            "godot_object_disappeared",
            "char_b_observed",
            "char_b_restart_recalled",
            "cross_actor_isolated",
            "summary_free_context_rebuilt",
            "n3_divergence",
            "n4_terminal",
            "n5_unreachable",
            "o2_to_o6",
            "online_private_confrontation",
            "validator_accepted",
            "resource_signature_recorded",
            "single_dispatch",
            "char_b_visible_reaction",
            "outcome_written_back",
        },
        before_capture=captures[0],
        after_capture=captures[1],
        reaction_capture=captures[2],
        provider_audit={
            "provider": "openai_responses",
            "route_id": "primary",
            "model": "gpt-5.4-mini",
            "request_id": "req_live_123",
        },
        graph_payload={
            "node_ids": ["N3", "N4", "N5", "O2", "O6"],
            "char_b": {"Event": True, "Observation": True},
        },
    )


def test_preflight_rejects_disabled_or_fake_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIMING_LLM_MODE", "disabled")
    result = live_preflight(project_root())
    assert result.ok is False
    assert "online_siming_llm_required" in result.reasons


def test_preflight_rejects_route_configuration_without_an_enabled_online_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIMING_LLM_MODE", "http")
    monkeypatch.setenv("SIMING_LLM_ROUTES_JSON", '[{"route_id":"disabled","provider":"disabled","enabled":false}]')

    result = live_preflight(project_root())

    assert result.ok is False
    assert "online_http_route_required" in result.reasons


def test_report_requires_all_three_nonblank_captures(tmp_path: Path) -> None:
    evidence = valid_live_evidence(tmp_path)
    evidence.reaction_capture.unlink()
    assert evaluate_live_evidence(evidence).overall is False
