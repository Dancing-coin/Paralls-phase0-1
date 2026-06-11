from __future__ import annotations

import sys
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


def _contains_none(path: Path, patterns: list[str]) -> bool:
    text = read_text(path)
    return all(pattern not in text for pattern in patterns)


def _scan_direct_visual_fact_bypass(project_root: Path) -> list[str]:
    suspicious: list[str] = []
    for path in (project_root / "scripts").rglob("*.gd"):
        normalized = str(path.relative_to(project_root)).replace("\\", "/")
        text = read_text(path)
        if "send_envelope(" not in text:
            continue
        if normalized == "scripts/visual/VisualFactEmitter.gd":
            continue
        if '"message_type": "visual_fact_event"' in text:
            suspicious.append(normalized)
    return suspicious


def _scan_retired_state_references(project_root: Path) -> list[str]:
    forbidden_marker = "." + "o" + "mx"
    search_roots = [
        project_root / "AGENTS.md",
        project_root / "PHASE0_README.md",
        project_root / ".gitignore",
        project_root / ".codex",
        project_root / ".github",
        project_root / ".harness",
        project_root / "docs",
        project_root / "openspec",
        project_root / "scripts",
    ]
    references: list[str] = []
    for root in search_roots:
        if not root.exists():
            continue
        paths = [root] if root.is_file() else list(root.rglob("*"))
        for path in paths:
            if not path.is_file():
                continue
            relative_parts = path.relative_to(project_root).parts
            if "__pycache__" in relative_parts:
                continue
            if len(relative_parts) >= 2 and relative_parts[0] == ".harness" and relative_parts[1] == "verification":
                continue
            if path.name == "check_boundaries.py":
                continue
            if path.suffix.lower() not in {".gd", ".md", ".py", ".toml", ".json", ".yaml", ".yml", ".ps1", ""}:
                continue
            if forbidden_marker in read_text(path):
                references.append(str(path.relative_to(project_root)).replace("\\", "/"))
    return references


def evaluate_boundaries(project_root: Path) -> dict[str, object]:
    docs_index = project_root / "docs" / "INDEX.md"
    harness_doc = project_root / "docs" / "harness.md"
    visual_emitter = project_root / "scripts" / "visual" / "VisualFactEmitter.gd"
    raw_fact_emitter = project_root / "scripts" / "l1" / "facts" / "RawFactEmitter.gd"
    fact_envelope_builder = project_root / "scripts" / "l1" / "facts" / "FactEnvelopeBuilder.gd"
    ws_protocol = project_root / "backend" / "app" / "ws_protocol.py"
    backend_main = project_root / "backend" / "app" / "main.py"
    player_intent_mapper = project_root / "scripts" / "player" / "PlayerIntentMapper.gd"
    object_controller = project_root / "scripts" / "object" / "InteractiveObject.gd"
    environment_controller = project_root / "scripts" / "environment" / "EnvironmentStateController.gd"
    backend_bridge = project_root / "scripts" / "autoload" / "BackendBridge.gd"
    siming_service = project_root / "backend" / "app" / "services" / "siming_service.py"
    verify_phase0 = project_root / "scripts" / "verification" / "verify_phase0.py"
    verify_phase1_slice = project_root / "scripts" / "verification" / "verify_phase1_slice.py"
    runtime_trace = project_root / "scripts" / "verification" / "runtime_trace.py"
    common = project_root / "scripts" / "verification" / "common.py"
    authority_bus = project_root / "backend" / "app" / "services" / "authority_event_bus.py"
    siming_pipeline = project_root / "backend" / "app" / "services" / "siming_event_pipeline.py"
    siming_producer = project_root / "backend" / "app" / "services" / "siming_event_producer.py"

    bypasses = _scan_direct_visual_fact_bypass(project_root)
    retired_state_references = _scan_retired_state_references(project_root)
    results = [
        _result(
            "docs_index_exists",
            "Repository docs index exists",
            docs_index.exists(),
            ["docs/INDEX.md"],
        ),
        _result(
            "harness_doc_exists",
            "Harness guide exists",
            harness_doc.exists(),
            ["docs/harness.md"],
        ),
        _result(
            "visual_fact_emitter_exists",
            "Visual facts have an approved emitter path",
            visual_emitter.exists()
            and raw_fact_emitter.exists()
            and fact_envelope_builder.exists()
            and _contains(visual_emitter, ["emit_visual_fact", "emit_raw_fact"])
            and _contains(raw_fact_emitter, ["emit_raw_fact", "send_envelope"])
            and _contains(fact_envelope_builder, ['"message_type": "raw_fact_event"', '"fact_family": fact_family']),
            [
                "scripts/visual/VisualFactEmitter.gd",
                "scripts/l1/facts/RawFactEmitter.gd",
                "scripts/l1/facts/FactEnvelopeBuilder.gd",
            ],
        ),
        _result(
            "direct_visual_fact_send_bypass_absent",
            "No direct visual_fact send bypass outside the emitter remains",
            not bypasses,
            ["scripts/visual/VisualFactEmitter.gd"],
            "\n".join(bypasses),
        ),
        _result(
            "websocket_envelope_model_exists",
            "WebSocket protocol keeps an explicit envelope model",
            _contains(ws_protocol, ["class Envelope", "message_type", "payload"]),
            ["backend/app/ws_protocol.py"],
        ),
        _result(
            "phase0_report_writes_json_and_markdown",
            "Phase 0 verification writes JSON and Markdown reports",
            _contains(verify_phase0, ["phase0-report.json", "phase0-report.md", "write_json", "write_markdown"]),
            ["scripts/verification/verify_phase0.py"],
        ),
        _result(
            "harness_artifacts_are_project_local",
            "Harness artifacts use the project-local .harness directory without retired state references",
            _contains(common, ['".harness"', '"verification"'])
            and not retired_state_references,
            ["scripts/verification/common.py", "AGENTS.md", "PHASE0_README.md"],
            "\n".join(retired_state_references),
        ),
        _result(
            "runtime_trace_artifacts_wired",
            "Runtime verification profiles write structured NDJSON trace artifacts",
            _contains(verify_phase0, ["write_runtime_trace", "phase0-runtime-trace.ndjson"])
            and _contains(verify_phase1_slice, ["write_runtime_trace", "phase1-slice-runtime-trace.ndjson"]),
            ["scripts/verification/verify_phase0.py", "scripts/verification/verify_phase1_slice.py"],
        ),
        _result(
            "backend_parses_player_input_models",
            "Backend parses player_input payloads into explicit Pydantic models at the boundary",
            _contains(
                backend_main,
                [
                    "def _parse_player_input",
                    "return DialogueSubmit(**payload)",
                    "return InteractIntent(**payload)",
                    "return MoveIntent(**payload)",
                    "return FocusTargetChange(**payload)",
                ],
            ),
            ["backend/app/main.py"],
        ),
        _result(
            "player_input_mapper_emits_structured_intents",
            "Godot player input mapper emits structured intent envelopes instead of raw controls",
            _contains(
                player_intent_mapper,
                [
                    '"message_type": "player_input"',
                    '"intent_type": "dialogue_submit"',
                    '"intent_type": "interact_intent"',
                    '"intent_type": "focus_target_change"',
                    '"intent_type": "move_intent"',
                ],
            ),
            ["scripts/player/PlayerIntentMapper.gd"],
        ),
        _result(
            "godot_world_changes_consume_backend_results",
            "Godot object and environment presentation consume backend world_result messages",
            _contains(backend_bridge, ['"world_result"', '"world_result_received"'])
            and _contains(object_controller, ["world_result_received.connect", "_on_world_result_received"])
            and _contains(environment_controller, ["world_result_received.connect", "_on_world_result_received"])
            and _contains_none(object_controller, ["send_envelope("])
            and _contains_none(environment_controller, ["send_envelope("]),
            [
                "scripts/autoload/BackendBridge.gd",
                "scripts/object/InteractiveObject.gd",
                "scripts/environment/EnvironmentStateController.gd",
            ],
        ),
        _result(
            "siming_service_emits_high_level_outputs_only",
            "Siming service emits high-level AttentionPrompt outputs and no low-level motion payloads",
            _contains(siming_service, ["AttentionPrompt", 'output_type="attention_prompt"'])
            and _contains_none(siming_service, ["move_target", "global_position", "velocity", "bone", "animation"]),
            ["backend/app/services/siming_service.py"],
        ),
        _result(
            "siming_event_bus_port_exists",
            "Siming integrates through an authority event bus port and concrete high-level event families",
            _contains(authority_bus, ["class AuthorityEventBusPort", "class InMemoryAuthorityEventBus"])
            and _contains(siming_pipeline, ["class SimingEventPipeline", "handle_event"])
            and _contains(
                siming_producer,
                [
                    "siming.visual_observability_request",
                    "siming.environment_request",
                    "siming.no_action_recorded",
                    "siming.impulse",
                    "siming.opportunity",
                    "siming.fact_reveal",
                ],
            )
            and _contains_none(siming_producer, ['return "siming.dispatch_requested"']),
            [
                "backend/app/services/authority_event_bus.py",
                "backend/app/services/siming_event_pipeline.py",
                "backend/app/services/siming_event_producer.py",
            ],
        ),
        _result(
            "runtime_trace_schema_is_enriched",
            "Runtime trace projects stable message and payload fields for agent consumption",
            _contains(
                runtime_trace,
                [
                    "PROJECTED_PAYLOAD_FIELDS",
                    '"message_type"',
                    '"actor_id"',
                    '"target_object_id"',
                    '"correlation_id"',
                    "_extract_structured_fields",
                ],
            ),
            ["scripts/verification/runtime_trace.py"],
        ),
    ]

    overall = all(str(entry["status"]) == "proved" for entry in results)
    return {
        "results": results,
        "overall_boundaries_passed": overall,
    }


def main() -> int:
    project_root = repo_root()
    report = evaluate_boundaries(project_root)
    log_dir = verification_dir(project_root)
    json_path = log_dir / "boundary-report.json"
    md_path = log_dir / "boundary-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Harness Boundary Verification Report", report, "overall_boundaries_passed")

    print(f"boundary_report_json={json_path}")
    print(f"boundary_report_md={md_path}")
    print(f"overall_boundaries_passed={report['overall_boundaries_passed']}")
    for entry in report["results"]:
        print(f"{entry['id']}={entry['status']}")
    return 0 if report["overall_boundaries_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
