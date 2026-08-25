from __future__ import annotations

import json
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_siming_heavenly_runtime as verifier  # noqa: E402

from verify_siming_heavenly_runtime import (  # noqa: E402
    LiveEvidence,
    _collect_result_ids,
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


def test_live_profile_uses_real_rendering_for_meaningful_captures() -> None:
    source = (project_root() / "scripts" / "verification" / "verify_siming_heavenly_runtime.py").read_text(
        encoding="utf-8"
    )

    assert '"--headless"' not in source
    assert '"--render-thread", "safe"' in source
    assert '"--rendering-method", "gl_compatibility"' in source


def test_live_profile_passes_online_character_model_configuration() -> None:
    source = (project_root() / "scripts" / "verification" / "verify_siming_heavenly_runtime.py").read_text(
        encoding="utf-8"
    )

    assert '"CHARACTER_MODEL_PROVIDER_KIND": "deepseek"' in source
    assert '"CHARACTER_MODEL_API_KEY": _env("SIMING_LLM_API_KEY")' in source
    assert '"CHARACTER_MODEL_REQUIRE_ONLINE": "1"' in source
    assert '"CHARACTER_MODEL_ENDPOINT": _env("SIMING_LLM_ENDPOINT")' in source
    assert '"CHARACTER_MODEL_ROUTE_OVERRIDE": "local_only"' in source
    assert '"SIMING_LLM_ADVISORY_DISABLED": "1"' in source
    assert '"SIMING_LLM_ADVISORY_DISABLED": ""' in source
    assert source.index('_ensure_live_backend(root, python_exe, runtime_env)') < source.index(
        '_ensure_live_backend(root, python_exe, online_character_env)'
    )
    assert 'for suffix in ("", "-wal", "-shm", "-journal")' in source


def test_live_verifier_checks_durable_restart_boundary_before_stopping_backend() -> None:
    source = (project_root() / "scripts" / "verification" / "verify_siming_heavenly_runtime.py").read_text(
        encoding="utf-8"
    )

    assert source.index("_wait_for_restart_boundary(db_path)") < source.index(
        "stop_backend(backend_process)"
    )
    assert '"siming_heavenly_restart_ready", 900' in source
    assert '"siming_heavenly_godot_complete", 900' in source


def test_collect_result_ids_derives_phase_seven_proof_from_graph_semantics() -> None:
    correlation_id = "interact:live"

    def artifact(
        node_id: str,
        node_type: str,
        attributes: dict[str, object],
        *,
        owner_actor_id: str | None = None,
    ) -> dict[str, object]:
        return {
            "node_id": node_id,
            "node_type": node_type,
            "attributes": attributes,
            "provenance": {"correlation_id": correlation_id},
            "scope": {
                "graph_namespace": "actor_private" if owner_actor_id else "siming_heavenly",
                "owner_actor_id": owner_actor_id,
            },
        }

    graph_payload = {
        "artifacts": [
            artifact(
                "fact:letter:removed",
                "memory:world_fact",
                {
                    "world_anchor_id": "obj_letter",
                    "state_value": "removed_from_surface",
                    "authority_result_ref": "object_result:obj_letter:10",
                },
            ),
            artifact(
                "actor-memory:event:char_b:1",
                "actor_memory:event",
                {"record": {"actor_id": "char_b", "refs": ["object_result:obj_letter:10"]}},
                owner_actor_id="char_b",
            ),
            artifact(
                "actor-memory:observation:char_b:1",
                "actor_memory:observation",
                {
                    "record": {
                        "actor_id": "char_b",
                        "observed_entity_id": "obj_letter",
                        "refs": ["object_result:obj_letter:10"],
                    },
                },
                owner_actor_id="char_b",
            ),
            artifact(
                "runtime:N3:main",
                "runtime_story_node",
                {"blueprint_id": "N3", "lifecycle": "resolved", "outcome_semantic": "resolved_with_divergence"},
            ),
            artifact(
                "runtime:N4:main",
                "runtime_story_node",
                {"blueprint_id": "N4", "lifecycle": "aborted", "closure_reason": "closed_by_player_choice", "terminal": True},
            ),
            artifact(
                "runtime:N5:main",
                "runtime_story_node",
                {"blueprint_id": "N5", "reachability": "unreachable_by_ledger"},
            ),
            artifact("obligation:O2", "memory:storyline_obligation", {"entry_id": "obligation:O2", "lifecycle": "transformed"}),
            artifact("obligation:O6", "memory:storyline_obligation", {"entry_id": "obligation:O6", "lifecycle": "open"}),
            artifact(
                "adaptive_bridge_audit:private",
                "adaptive_bridge_audit",
                {
                    "proposal": {"pattern": "private_confrontation"},
                    "validation": {"accepted": True},
                },
            ),
            artifact(
                "story_staging:private",
                "memory:intervention_outcome",
                {"stage": "staging", "staging_status": "staged", "realization_signature": "resource-signature"},
            ),
            artifact(
                "heavenly_dispatch:private",
                "memory:intervention_outcome",
                {"stage": "dispatch"},
            ),
            artifact(
                "story_outcome:object_result:obj_letter:10",
                "memory:storyline_obligation",
                {
                    "entry_id": "story_outcome:object_result:obj_letter:10",
                    "record_type": "outcome_port",
                    "supporting_fact_refs": ["object_result:obj_letter:10"],
                },
            ),
        ],
    }

    result_ids = _collect_result_ids(
        "siming_heavenly_restart_ready\nsiming_heavenly_godot_complete",
        graph_payload,
        preflight_ready=True,
    )

    assert result_ids == {
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
    }


def test_restart_boundary_requires_durable_graph_chain_before_backend_stop() -> None:
    correlation_id = "interact:boundary"

    def artifact(
        node_id: str,
        node_type: str,
        attributes: dict[str, object],
        *,
        owner_actor_id: str | None = None,
    ) -> dict[str, object]:
        return {
            "node_id": node_id,
            "node_type": node_type,
            "attributes": attributes,
            "provenance": {"correlation_id": correlation_id},
            "scope": {
                "graph_namespace": "actor_private" if owner_actor_id else "siming_heavenly",
                "owner_actor_id": owner_actor_id,
            },
        }

    payload = {
        "artifacts": [
            artifact(
                "fact:letter:removed",
                "memory:world_fact",
                {
                    "world_anchor_id": "obj_letter",
                    "state_value": "removed_from_surface",
                    "authority_result_ref": "object_result:letter:1",
                },
            ),
            artifact(
                "event:char_b:1",
                "actor_memory:event",
                {"record": {"actor_id": "char_b", "refs": ["object_result:letter:1"]}},
                owner_actor_id="char_b",
            ),
            artifact(
                "observation:char_b:1",
                "actor_memory:observation",
                {
                    "record": {
                        "actor_id": "char_b",
                        "observed_entity_id": "obj_letter",
                        "refs": ["object_result:letter:1"],
                    }
                },
                owner_actor_id="char_b",
            ),
            artifact(
                "adaptive_bridge_audit:private",
                "adaptive_bridge_audit",
                {
                    "proposal": {"pattern": "private_confrontation"},
                    "validation": {"accepted": True},
                },
            ),
            artifact(
                "heavenly_proposal:private",
                "memory:intervention_outcome",
                {
                    "stage": "proposal",
                    "selected_node_ref": "runtime:bridge:private",
                    "staging_request": {"node_id": "runtime:bridge:private"},
                },
            ),
            artifact(
                "heavenly_selection:private",
                "memory:intervention_outcome",
                {"stage": "selection", "selected_node_ref": "runtime:bridge:private"},
            ),
            artifact(
                "heavenly_staging_ack:character",
                "memory:intervention_outcome",
                {
                    "stage": "staging_ack",
                    "staging_ack": {"source": "character", "accepted": True},
                },
            ),
            artifact(
                "heavenly_staging_ack:esm",
                "memory:intervention_outcome",
                {
                    "stage": "staging_ack",
                    "staging_ack": {"source": "esm", "accepted": True},
                },
            ),
        ]
    }
    for item in payload["artifacts"]:
        if item["node_id"] in {"event:char_b:1", "observation:char_b:1"}:
            item["provenance"]["correlation_id"] = "char_b:private:1"

    assert hasattr(verifier, "_restart_boundary_ready")
    if hasattr(verifier, "_restart_boundary_ready"):
        assert verifier._restart_boundary_ready(payload) is True
        payload["artifacts"] = [
            item
            for item in payload["artifacts"]
            if item["node_id"] != "heavenly_staging_ack:esm"
        ]
        assert verifier._restart_boundary_ready(payload) is False
