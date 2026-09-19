from __future__ import annotations

import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from check_boundaries import evaluate_boundaries, _scan_siming_llm_side_channels
from common import repo_root


def test_evaluate_boundaries_proves_core_runtime_ownership_rules() -> None:
    report = evaluate_boundaries(repo_root())
    statuses = {entry["id"]: entry["status"] for entry in report["results"]}

    assert statuses["visual_fact_emitter_exists"] == "proved"
    assert statuses["harness_artifacts_are_owned_temporary"] == "proved"
    assert statuses["backend_parses_player_input_models"] == "proved"
    assert statuses["player_input_mapper_emits_structured_intents"] == "proved"
    assert statuses["godot_world_changes_consume_backend_results"] == "proved"
    assert statuses["siming_service_emits_high_level_outputs_only"] == "proved"
    assert statuses["siming_event_bus_port_exists"] == "proved"
    assert statuses["siming_projected_event_reaches_godot_bus"] == "proved"
    assert statuses["runtime_trace_schema_is_enriched"] == "proved"


def test_boundaries_prove_siming_llm_runtime_containment() -> None:
    report = evaluate_boundaries(repo_root())
    statuses = {entry["id"]: entry["status"] for entry in report["results"]}

    assert statuses["siming_llm_stays_inside_runtime"] == "proved"


def test_continuation_adapter_is_allowed_but_unregistered_side_channel_is_not(tmp_path):
    root = tmp_path
    source = Path(__file__).resolve().parents[3] / 'backend' / 'app' / 'services'
    target = root / 'backend' / 'app' / 'services'
    target.mkdir(parents=True)
    shutil.copy2(source / 'siming_continuation.py', target / 'siming_continuation.py')
    assert _scan_siming_llm_side_channels(root) == ''
    (target / 'unregistered_side_channel.py').write_text(
        'from app.services.siming_llm_provider import SimingLlmCandidateProvider\n'
        'def generate():\n    return provider.generate_candidates()\n', encoding='utf-8')
    assert _scan_siming_llm_side_channels(root) == 'backend/app/services/unregistered_side_channel.py:llm-provider-call'
