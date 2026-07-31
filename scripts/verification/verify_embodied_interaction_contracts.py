from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.models.embodied_interaction import EmbodiedProjectionPolicy, EmbodiedSettlementWriterSelector
from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = ["backend/tests/test_embodied_interaction_contracts.py"]


def _result(check_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": check_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    pytest_log = log_dir / "embodied-interaction-contracts-pytest.log"
    pytest_result = run_command([python_exe, "-m", "pytest", "-q", *TEST_FILES], project_root, pytest_log)

    selector = EmbodiedSettlementWriterSelector(gameplay_event_batch_writer_available=False)
    kick_selection = selector.select(
        action_semantic="kick",
        effect_scope="single_object_physical",
        requested_writer_kind="esm_compatibility_adapter",
    )
    handoff_selection = selector.select(
        action_semantic="handoff",
        effect_scope="ownership_transfer",
        requested_writer_kind="gameplay_event_batch_writer",
    )
    projection = EmbodiedProjectionPolicy.public_observatory().project(
        {
            "interaction_attempt_id": "attempt:kick-chair:verify",
            "settlement_status": "committed",
            "public_effect_summary": "chair tipped",
            "private_participant_terms": {"char_b": "hidden"},
            "vla_prompt_context": "hidden",
        }
    )
    trace_path = log_dir / "embodied-interaction-contracts-trace.json"
    write_json(
        trace_path,
        {
            "writer_selection": {
                "kick": kick_selection.model_dump(mode="json"),
                "handoff": handoff_selection.model_dump(mode="json"),
            },
            "public_projection": projection,
        },
    )

    results = [
        _result(
            "focused-pytest-pass",
            "Embodied interaction contract pytest suite passes",
            pytest_result.returncode == 0,
            [str(pytest_log)],
        ),
        _result(
            "first-closure-writer-only",
            "kick-chair selects only esm_compatibility_adapter for the first closure",
            kick_selection.accepted
            and kick_selection.writer_kind == "esm_compatibility_adapter"
            and not kick_selection.dual_write,
            [str(trace_path)],
        ),
        _result(
            "cross-domain-fail-closed",
            "cross-domain settlement is blocked until gameplay_event_batch_writer exists",
            not handoff_selection.accepted
            and handoff_selection.error_code == "gameplay_event_batch_writer_unavailable",
            [str(trace_path)],
        ),
        _result(
            "projection-default-deny",
            "public Observatory projection filters private and advisory context fields",
            set(projection) == {"interaction_attempt_id", "settlement_status", "public_effect_summary"},
            [str(trace_path)],
        ),
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_embodied_interaction_contracts_passed": overall,
        "results": results,
        "artifacts": {
            "pytest_log": str(pytest_log),
            "trace": str(trace_path),
        },
    }
    json_path = log_dir / "embodied-interaction-contracts-report.json"
    md_path = log_dir / "embodied-interaction-contracts-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Embodied Interaction Contracts Verification Report", report, "overall_embodied_interaction_contracts_passed")
    print(f"embodied_interaction_contracts_report_json={json_path}")
    print(f"embodied_interaction_contracts_report_md={md_path}")
    print(f"overall_embodied_interaction_contracts_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
