from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.services.embodied_evidence_ledger import EmbodiedEvidenceLedger
from common import read_text, repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = ["backend/tests/test_embodied_evidence_ledger.py"]


def _result(check_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {"id": check_id, "title": title, "status": "proved" if proved else "missing", "evidence": evidence if proved else [], "notes": notes}


def _build_ledger_trace(log_dir: Path) -> Path:
    ledger = EmbodiedEvidenceLedger()
    attempt_id = "attempt:kick-chair:vertical-slice"
    entries = [
        ("request_authorized", "backend", "backend:authority", 1, 1, "sha256:request", {"interaction_attempt_id": attempt_id, "causation_id": "cause:kick-chair:vertical-slice"}),
        ("registry_binding", "backend", "backend:registry", 1, 2, "sha256:binding", {"binding_revision": 7}),
        ("local_phase", "controller", "controller:char_a", 2, 1, "sha256:phase", {"safe_phase": "execute_contact"}),
        ("terminal_local_observation", "controller", "controller:char_a", 2, 2, "sha256:terminal", {"safe_phase": "terminal", "visible_evidence_refs": ["trace:contact:kick-chair"]}),
        ("settlement", "backend", "backend:settlement", 1, 3, "sha256:settlement", {"settlement_status": "committed", "public_effect_summary": "chair tipped"}),
        ("presentation", "godot_mirror", "godot:mirror", 1, 1, "sha256:presentation", {"presentation_directive": "apply_visible_chair_tip", "visible_evidence_refs": ["screenshot:embodied-kick-chair-vertical-slice"]}),
    ]
    append_results = [
        ledger.append(
            attempt_id=attempt_id,
            event_kind=event_kind,
            emitter_kind=emitter_kind,
            emitter_id=emitter_id,
            emitter_epoch=emitter_epoch,
            source_sequence=source_sequence,
            payload_digest=payload_digest,
            payload=payload,
        )
        for event_kind, emitter_kind, emitter_id, emitter_epoch, source_sequence, payload_digest, payload in entries
    ]
    duplicate = ledger.append(
        attempt_id=attempt_id,
        event_kind="local_phase",
        emitter_kind="controller",
        emitter_id="controller:char_a",
        emitter_epoch=2,
        source_sequence=1,
        payload_digest="sha256:phase",
        payload={"safe_phase": "execute_contact"},
    )
    mismatch = ledger.append(
        attempt_id=attempt_id,
        event_kind="local_phase",
        emitter_kind="controller",
        emitter_id="controller:char_a",
        emitter_epoch=2,
        source_sequence=1,
        payload_digest="sha256:different",
        payload={"safe_phase": "execute_contact"},
    )
    gap = ledger.append(
        attempt_id=attempt_id,
        event_kind="local_phase",
        emitter_kind="controller",
        emitter_id="controller:char_a",
        emitter_epoch=2,
        source_sequence=4,
        payload_digest="sha256:gap",
        payload={"safe_phase": "gap"},
    )
    privacy_projection = ledger.public_projection(
        attempt_id,
        extra_payload={
            "interaction_attempt_id": attempt_id,
            "settlement_status": "committed",
            "public_effect_summary": "chair tipped",
            "private_participant_terms": {"char_b": "hidden"},
            "vla_prompt_context": "hidden",
        },
    )
    replay = ledger.validate_replay(attempt_id)
    trace_path = log_dir / "embodied-interaction-replay-ledger-trace.json"
    write_json(
        trace_path,
        {
            "append_results": [result.model_dump(mode="json") for result in append_results],
            "duplicate": duplicate.model_dump(mode="json"),
            "mismatch": mismatch.model_dump(mode="json"),
            "gap": gap.model_dump(mode="json"),
            "replay": replay.model_dump(mode="json"),
            "public_projection": privacy_projection,
            "events": [event.model_dump(mode="json") for event in ledger.events_for_attempt(attempt_id)],
        },
    )
    return trace_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot-exe", default=None)
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    pytest_log = log_dir / "embodied-interaction-replay-pytest.log"
    pytest_result = run_command([python_exe, "-m", "pytest", "-q", *TEST_FILES], project_root, pytest_log)
    trace_path = _build_ledger_trace(log_dir)
    trace = json.loads(trace_path.read_text(encoding="utf-8"))

    godot_log = log_dir / "embodied-interaction-replay-godot.log"
    godot_artifact = log_dir / "embodied-kick-chair-vertical-slice-godot-runtime.json"
    screenshot = log_dir / "embodied-kick-chair-vertical-slice.png"
    godot_ok = False
    if args.godot_exe:
        godot_result = run_command(
            [
                args.godot_exe,
                "--headless",
                "--path",
                str(project_root),
                "--scene",
                "res://scenes/phase0/EmbodiedKickChairVerticalSliceProbe.tscn",
                "--quit-after",
                "300",
                "--render-thread",
                "safe",
            ],
            project_root,
            godot_log,
        )
        godot_text = read_text(godot_log)
        godot_ok = (
            godot_result.returncode == 0
            and "embodied_kick_chair_probe:verified=true" in godot_text
            and godot_artifact.exists()
            and screenshot.exists()
            and screenshot.stat().st_size > 0
        )
    try:
        runtime_payload = json.loads(godot_artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        runtime_payload = {}
    success = runtime_payload.get("success", {}) if isinstance(runtime_payload, dict) else {}
    failure = runtime_payload.get("failure", {}) if isinstance(runtime_payload, dict) else {}
    replay = trace.get("replay", {})
    projection = trace.get("public_projection", {})
    results = [
        _result("focused-pytest-pass", "Embodied evidence ledger focused pytest suite passes", pytest_result.returncode == 0, [str(pytest_log)]),
        _result(
            "server-ledger-replay-valid",
            "Replay accepts request -> binding -> phase -> terminal observation -> settlement -> presentation in backend server ledger order",
            bool(replay.get("accepted")) and replay.get("server_ledger_sequences") == [1, 2, 3, 4, 5, 6],
            [str(trace_path)],
        ),
        _result(
            "source-sequence-idempotency",
            "Duplicate same digest is idempotent while mismatched duplicate and source gap are rejected",
            trace.get("duplicate", {}).get("idempotent") is True
            and trace.get("mismatch", {}).get("error_code") == "source_sequence_digest_mismatch"
            and trace.get("gap", {}).get("error_code") == "source_sequence_gap",
            [str(trace_path)],
        ),
        _result(
            "public-projection-filters-private-fields",
            "Public Observatory projection filters private participant terms and VLA prompt context",
            projection.get("extra_payload") == {
                "interaction_attempt_id": "attempt:kick-chair:vertical-slice",
                "settlement_status": "committed",
                "public_effect_summary": "chair tipped",
            },
            [str(trace_path)],
        ),
        _result(
            "godot-visible-success-and-failure",
            "Godot runtime probe changes the chair only after settlement and leaves the failed attempt unchanged",
            godot_ok
            and isinstance(success, dict)
            and success.get("changed_only_after_settlement") is True
            and isinstance(failure, dict)
            and failure.get("world_state_unchanged") is True,
            [str(godot_log), str(godot_artifact), str(screenshot)],
        ),
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_embodied_interaction_replay_passed": overall,
        "results": results,
        "artifacts": {
            "pytest_log": str(pytest_log),
            "ledger_trace": str(trace_path),
            "godot_log": str(godot_log),
            "godot_runtime": str(godot_artifact),
            "screenshot": str(screenshot),
        },
    }
    json_path = log_dir / "embodied-interaction-replay-report.json"
    md_path = log_dir / "embodied-interaction-replay-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Embodied Interaction Replay Verification Report", report, "overall_embodied_interaction_replay_passed")
    print(f"embodied_interaction_replay_report_json={json_path}")
    print(f"embodied_interaction_replay_report_md={md_path}")
    print(f"overall_embodied_interaction_replay_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
