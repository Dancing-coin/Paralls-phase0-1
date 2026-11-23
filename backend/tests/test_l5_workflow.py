from copy import deepcopy
from pathlib import Path
import shutil

import pytest

from app.gameplay.l5_workflow import compile_workflow
from app.gameplay.rule_pack_validator import load_pack


COMMANDS = frozenset({"government.issue_relief_order", "transport.create_shipment"})

DECLARATION = {
    "workflow_id": "siege_supply_relief",
    "steps": [
        {"id": "authorize", "command": "government.issue_relief_order", "on_reject": "abort"},
        {
            "id": "transport", "command": "transport.create_shipment",
            "depends_on": ["authorize"], "on_fail": "record_obligation",
        },
    ],
    "open_obligations": [{"step_id": "transport", "recovery": "reconcile_then_retry"}],
    "timeout_policy": {"default": "record_obligation", "per_step": {"authorize": "abort"}},
}


def test_workflow_preserves_registered_steps_and_obligation_policy():
    declaration = deepcopy(DECLARATION)
    workflow = compile_workflow(declaration, command_types=COMMANDS)
    authorize, transport = workflow.steps

    assert workflow.workflow_id == "siege_supply_relief"
    assert authorize.command == "government.issue_relief_order"
    assert authorize.on_reject == "abort"
    assert authorize.on_timeout == "abort"
    assert transport.depends_on == ("authorize",)
    assert transport.on_fail == "record_obligation"
    assert transport.on_timeout == "record_obligation"
    assert transport.recovery == "reconcile_then_retry"

    declaration["steps"][1]["depends_on"].clear()
    assert transport.depends_on == ("authorize",)


@pytest.mark.parametrize(("field", "value", "code"), [
    ("command", "unknown.command", "pattern_command_unknown"),
    ("depends_on", ["missing"], "workflow_dependency_unknown"),
    ("depends_on", ["transport"], "pattern_workflow_cycle"),
    ("writes", ["fact:transport:*:state"], "pattern_declares_writes"),
])
def test_workflow_rejects_invalid_step_declarations(field, value, code):
    declaration = deepcopy(DECLARATION)
    declaration["steps"][1][field] = value
    with pytest.raises(ValueError, match=code):
        compile_workflow(declaration, command_types=COMMANDS)


def test_workflow_rejects_indirect_cycle():
    declaration = deepcopy(DECLARATION)
    declaration["steps"][0]["depends_on"] = ["transport"]
    with pytest.raises(ValueError, match="pattern_workflow_cycle"):
        compile_workflow(declaration, command_types=COMMANDS)


def test_workflow_requires_recovery_for_each_step_that_can_open_an_obligation():
    declaration = deepcopy(DECLARATION)
    declaration["open_obligations"] = []
    with pytest.raises(ValueError, match="workflow_recovery_required"):
        compile_workflow(declaration, command_types=COMMANDS)


def test_load_pack_resolves_workflow_steps_against_its_command_catalog(tmp_path):
    package = Path(__file__).resolve().parents[2] / "packs" / "credential_reference"
    pack = shutil.copytree(package, tmp_path / "workflow-pack")
    manifest = pack / "pack.yaml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace(
        "contents:\n", 'contents:\n  command_catalog: ["issue"]\n  workflows: ["issuance"]\n',
    ), encoding="utf-8")
    (pack / "command_catalog").mkdir()
    (pack / "command_catalog" / "issue.yaml").write_text(
        'ownership.issue:\n  handled_by: "Ownership"\n  payload_schema: "issue@1"\n'
        '  requires_authority: true\n  idempotency_shape: "command_id"\n  version: 1\n', encoding="utf-8",
    )
    (pack / "workflows").mkdir()
    (pack / "workflows" / "issuance.yaml").write_text(
        'issuance:\n  steps:\n    - id: "issue"\n      command: "ownership.issue"\n', encoding="utf-8",
    )
    loaded = load_pack(
        pack, handlers={"credential_command@1": lambda inputs, params: True},
        owner_domains={"Ownership": "ownership"},
    )
    assert loaded.workflows["issuance"].steps[0].command == "ownership.issue"
