from __future__ import annotations

from pathlib import Path

from common import read_text, repo_root, verification_dir, write_json, write_markdown


def _result(result_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {
        "id": result_id,
        "title": title,
        "status": "proved" if proved else "missing",
        "evidence": evidence if proved else [],
        "notes": notes,
    }


def _contains(path: Path, patterns: list[str]) -> bool:
    text = read_text(path)
    return all(pattern in text for pattern in patterns)


def evaluate_backend_contract(project_root: Path) -> dict[str, object]:
    ws_protocol = project_root / "backend" / "app" / "ws_protocol.py"
    player_input = project_root / "backend" / "app" / "models" / "player_input.py"
    ai_output = project_root / "backend" / "app" / "models" / "ai_output.py"
    world_result = project_root / "backend" / "app" / "models" / "world_result.py"
    raw_fact = project_root / "backend" / "app" / "models" / "raw_fact.py"
    visual_fact = project_root / "backend" / "app" / "models" / "visual_fact.py"
    siming_output = project_root / "backend" / "app" / "models" / "siming_output.py"
    runtime_state = project_root / "backend" / "app" / "models" / "runtime_state.py"
    authority_event = project_root / "backend" / "app" / "models" / "authority_event.py"
    ws_tests = project_root / "backend" / "tests" / "test_ws_protocol.py"
    visual_fact_tests = project_root / "backend" / "tests" / "test_visual_fact_pipeline.py"
    authority_event_tests = project_root / "backend" / "tests" / "test_authority_event.py"

    results = [
        _result(
            "backend_protocol_models_exist",
            "Backend protocol model files and explicit websocket envelope exist",
            _contains(ws_protocol, ["class Envelope", "message_type", "payload"])
            and _contains(player_input, ["class DialogueSubmit", "class InteractIntent", "class MoveIntent", "class FocusTargetChange"])
            and _contains(ai_output, ["class DialogueResponse"])
            and _contains(
                world_result,
                [
                    "class ActionResolutionResult",
                    "class ObjectStateResult",
                    "class BodyStateResult",
                    "class EnvironmentStateResult",
                    "class ConstraintStateResult",
                ],
            )
            and _contains(raw_fact, ["class RawFactEvent"])
            and _contains(visual_fact, ["class VisualFactEvent"])
            and _contains(siming_output, ["class AttentionPrompt"])
            and _contains(runtime_state, ["class CharacterRuntimeStateSnapshot", "class CharacterRuntimeStateDelta"]),
            [
                "backend/app/ws_protocol.py",
                "backend/app/models/player_input.py",
                "backend/app/models/ai_output.py",
                "backend/app/models/world_result.py",
                "backend/app/models/raw_fact.py",
                "backend/app/models/visual_fact.py",
                "backend/app/models/siming_output.py",
                "backend/app/models/runtime_state.py",
            ],
        ),
        _result(
            "cross_boundary_models_are_pydantic",
            "Cross-boundary contracts use Pydantic BaseModel types",
            all(
                _contains(path, ["BaseModel"])
                for path in [ws_protocol, player_input, ai_output, world_result, raw_fact, siming_output, runtime_state, authority_event]
            ),
            [
                "backend/app/ws_protocol.py",
                "backend/app/models/player_input.py",
                "backend/app/models/ai_output.py",
                "backend/app/models/world_result.py",
                "backend/app/models/raw_fact.py",
                "backend/app/models/visual_fact.py",
                "backend/app/models/siming_output.py",
                "backend/app/models/runtime_state.py",
                "backend/app/models/authority_event.py",
            ],
        ),
        _result(
            "authority_event_contract_exists",
            "Authority event envelope exists and rejects forbidden public fields",
            _contains(
                authority_event,
                [
                    "class AuthorityEvent",
                    "class AuthorityEventSource",
                    "class AuthorityEventRouting",
                    "world_ts",
                    "sim_tick_ts",
                    "source_actor_id",
                    "target_actor_ids",
                    'Literal["p0", "p1", "p2", "p3"]',
                    'Literal["replayable", "reliable", "realtime"]',
                ],
            )
            and _contains(
                authority_event_tests,
                [
                    "test_authority_event_rejects_domain_time_at_public_envelope_root",
                    "test_authority_event_rejects_legacy_flat_envelope_fields",
                    "test_authority_event_rejects_unknown_priority",
                    "test_authority_event_rejects_unknown_durability",
                ],
            ),
            ["backend/app/models/authority_event.py", "backend/tests/test_authority_event.py"],
        ),
        _result(
            "backend_tests_cover_protocol_contracts",
            "Backend tests cover protocol shapes and websocket boundary behavior",
            _contains(
                ws_tests,
                [
                    "test_player_input_dialogue_submit_shape",
                    "test_websocket_dialogue_submit_emits_ack_and_dialogue_response",
                    "test_websocket_interact_intent_emits_constraint_when_player_is_far",
                ],
            )
            and _contains(
                visual_fact_tests,
                [
                    "test_visual_fact_event_shape",
                    "test_websocket_visual_fact_event_emits_runtime_alignment_messages",
                ],
            ),
            ["backend/tests/test_ws_protocol.py", "backend/tests/test_visual_fact_pipeline.py"],
        ),
    ]
    return {
        "results": results,
        "overall_backend_contract_passed": all(str(entry["status"]) == "proved" for entry in results),
    }


def main() -> int:
    project_root = repo_root()
    report = evaluate_backend_contract(project_root)
    log_dir = verification_dir(project_root)
    json_path = log_dir / "backend-contract-report.json"
    md_path = log_dir / "backend-contract-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Backend Contract Verification Report", report, "overall_backend_contract_passed")

    print(f"backend_contract_report_json={json_path}")
    print(f"backend_contract_report_md={md_path}")
    print(f"overall_backend_contract_passed={report['overall_backend_contract_passed']}")
    for entry in report["results"]:
        print(f"{entry['id']}={entry['status']}")
    return 0 if report["overall_backend_contract_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
