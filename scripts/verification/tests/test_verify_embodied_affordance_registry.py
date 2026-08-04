from __future__ import annotations

import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import verify_embodied_affordance_registry as verifier


def test_affordance_registry_verifier_uses_current_physical_door_contract_tests() -> None:
    assert (
        "backend/tests/test_ws_protocol.py::test_websocket_archive_door_open_requires_bound_controller_before_physical_preflight"
        in verifier.TEST_FILES
    )
    assert (
        "backend/tests/test_ws_protocol.py::test_door_close_fails_closed_until_its_physical_path_is_implemented"
        in verifier.TEST_FILES
    )
    assert "backend/tests/test_ws_protocol.py::test_websocket_open_intent_uses_registered_archive_door_authority_policy" not in verifier.TEST_FILES
    assert "backend/tests/test_ws_protocol.py::test_door_close_requires_the_authority_committed_open_state" not in verifier.TEST_FILES
