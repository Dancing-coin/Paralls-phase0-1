"""Demonstrate the session probe's existence oracle in an isolated component process."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))

from fastapi.testclient import TestClient

import app.main as main


def main_probe() -> None:
    main.reset_runtime_state()
    result = main.embodied_interaction_session_service.propose(
        session_id="session:boundary-existing", semantic_action="handshake",
        initiator_ref="character:siming",
        participant_refs=["character:siming", "character:maya"], target_refs=[],
        authority_preflight_ref="preflight:test", policy_revision=3, scene_revision=11,
        causation_id="cmd:test", correlation_id="corr:test",
    )
    assert result.accepted
    responses = []
    with TestClient(main.component_app).websocket_connect("/ws") as websocket:
        for session_id in ("session:boundary-existing", "session:boundary-new"):
            websocket.send_json({
                "message_type": "embodied_interaction_session_probe",
                "payload": {"session_id": session_id, "initiator_ref": "character:siming",
                            "participant_refs": ["character:siming", "character:maya"]},
            })
            responses.append(websocket.receive_json())
    assert responses[0]["payload"]["error_code"] == "session_exists", responses
    assert responses[1]["payload"]["accepted"] is True, responses
    print("existing:", responses[0])
    print("new:", responses[1])


if __name__ == "__main__":
    main_probe()
