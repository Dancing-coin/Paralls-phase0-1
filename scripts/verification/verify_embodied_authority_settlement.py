from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.models.embodied_interaction import EmbodiedActionRequest
from app.services.embodied_authority_settlement_service import EmbodiedAuthoritySettlementService
from app.services.embodied_controller_auth_service import EmbodiedControllerAuthService, EmbodiedControllerEnrollment
from common import repo_root, resolve_python_exe, run_command, verification_dir, write_json, write_markdown


TEST_FILES = ["backend/tests/test_embodied_authority_settlement.py"]


def _result(check_id: str, title: str, proved: bool, evidence: list[str], notes: str = "") -> dict[str, object]:
    return {"id": check_id, "title": title, "status": "proved" if proved else "missing", "evidence": evidence if proved else [], "notes": notes}


def _request() -> EmbodiedActionRequest:
    return EmbodiedActionRequest.model_validate(
        {
            "request_id": "embodied_request:kick:verify",
            "interaction_attempt_id": "attempt:kick-chair:verify",
            "actor_id": "char_a",
            "target_ref": "entity:scene_demo:chair_01",
            "action_semantic": "kick",
            "affordance_id": "affordance:chair_01:kick",
            "authority_preflight_ref": "preflight:kick-chair:verify",
            "policy_revision": 2,
            "scene_revision": 5,
            "binding_revision": 7,
            "required_anchor_roles": ["approach_stance", "contact"],
            "execution_profile_ref": "execution_profile:kick:v1",
            "expiration_tick": 2000,
            "causation_id": "cause:kick-chair:verify",
            "correlation_id": "corr:kick-chair:verify",
            "realization_route": "embodied_controller_v1",
            "settlement_writer_kind": "esm_compatibility_adapter",
        }
    )


def _trace(log_dir: Path) -> Path:
    auth = EmbodiedControllerAuthService()
    request = _request()
    credential = auth.create_trusted_local_launch_credential(
        actor_id=request.actor_id,
        controller_instance_id="controller:char_a:verify",
        issued_at=100,
        expires_at=200,
    )
    binding = auth.bind_controller(
        EmbodiedControllerEnrollment(
            credential_kind="trusted_local_launch",
            credential=credential,
            actor_id=request.actor_id,
            controller_instance_id="controller:char_a:verify",
            protocol_version=1,
        ),
        remote_host="127.0.0.1",
        now=110,
    ).binding
    assert binding is not None
    grant = auth.issue_execution_grant(binding=binding, request=request, issued_at=120, ttl=100)
    service = EmbodiedAuthoritySettlementService(auth_service=auth)
    service.register_attempt(request=request, grant=grant)
    payload = {
        "interaction_attempt_id": request.interaction_attempt_id,
        "phase": "terminal",
        "terminal_status": "contact_observed",
        "observed_at": 130,
        "actor_pose_ref": "pose:char_a:bounded",
        "target_binding_ref": "binding:entity:scene_demo:chair_01:7",
        "contact_observation": {
            "contact_ref": "contact:attempt:kick-chair:verify",
            "actor_contact_ref": "collider:char_a:foot_r",
            "target_collider_ref": "collider:chair_01:body",
            "contact_window_ref": "window:kick:verify",
        },
        "object_observation": {
            "object_ref": request.target_ref,
            "previous_state": "upright",
            "observed_state": "tipped",
            "observation_rule_ref": "observation_rule:chair_tipped:v1",
        },
        "trace_refs": ["trace:phase:verify"],
        "causation_id": request.causation_id,
        "correlation_id": request.correlation_id,
        "controller_grant_id": grant.grant_id,
        "connection_epoch": grant.connection_epoch,
        "terminal_sequence": 2,
        "outcome_nonce": grant.one_time_outcome_nonce,
        "payload_digest": "sha256:terminal:verify",
    }
    committed = service.settle_local_outcome(payload, now=130)
    duplicate = service.settle_local_outcome(payload, now=131)
    trace_path = log_dir / "embodied-authority-settlement-trace.json"
    write_json(
        trace_path,
        {
            "committed": committed.model_dump(mode="json"),
            "duplicate": duplicate.model_dump(mode="json"),
            "mutation_count": service.mutation_count,
        },
    )
    return trace_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=None)
    args = parser.parse_args()

    project_root = repo_root()
    log_dir = verification_dir(project_root)
    python_exe = resolve_python_exe(args.python_exe)
    pytest_log = log_dir / "embodied-authority-settlement-pytest.log"
    pytest_result = run_command([python_exe, "-m", "pytest", "-q", *TEST_FILES], project_root, pytest_log)
    trace_path = _trace(log_dir)
    import json

    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    committed = trace["committed"]
    duplicate = trace["duplicate"]
    results = [
        _result("focused-pytest-pass", "Embodied authority settlement focused pytest suite passes", pytest_result.returncode == 0, [str(pytest_log)]),
        _result(
            "esm-compatibility-commit-once",
            "Attested chair contact commits once through esm_compatibility_adapter",
            committed["outcome"] == "committed"
            and committed["settlement_writer_kind"] == "esm_compatibility_adapter"
            and trace["mutation_count"] == 1,
            [str(trace_path)],
        ),
        _result(
            "duplicate-idempotent",
            "Duplicate terminal observation returns original settlement without a second mutation",
            duplicate["idempotent"] is True and trace["mutation_count"] == 1,
            [str(trace_path)],
        ),
    ]
    overall = all(entry["status"] == "proved" for entry in results)
    report = {
        "overall_embodied_authority_settlement_passed": overall,
        "results": results,
        "artifacts": {"pytest_log": str(pytest_log), "trace": str(trace_path)},
    }
    json_path = log_dir / "embodied-authority-settlement-report.json"
    md_path = log_dir / "embodied-authority-settlement-report.md"
    write_json(json_path, report)
    write_markdown(md_path, "Embodied Authority Settlement Verification Report", report, "overall_embodied_authority_settlement_passed")
    print(f"embodied_authority_settlement_report_json={json_path}")
    print(f"embodied_authority_settlement_report_md={md_path}")
    print(f"overall_embodied_authority_settlement_passed={overall}")
    return 0 if overall else 1


if __name__ == "__main__":
    raise SystemExit(main())
