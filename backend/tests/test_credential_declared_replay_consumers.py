from pathlib import Path
import re
from shutil import copytree

from app.gameplay.adventure_basic_closure import capture_adventure_basic_closure
from app.gameplay.adventure_basic_reference import AdventureBasicScenario4
from app.gameplay.credential_reference_chain import CredentialReferenceChain, load_credential_pack
from app.gameplay.land_right_runtime import LandRightTransferAuthority, LandRightTransferPolicy
from g3_credential_fixture import PACK, command, setup_reference


def _pack_with_seal(tmp_path: Path):
    directory = tmp_path / "credential-pack"
    copytree(PACK, directory)
    path = directory / "models/credential_command.yaml"
    text = path.read_text(encoding="utf-8")
    pattern = r'(?m)^(\s+credential_kinds: \[[^\r\n]*)(\])$'
    match = re.search(pattern, text)
    assert match is not None
    text = re.sub(pattern, lambda found: f'{found.group(1)}, "seal"]', text, count=1)
    path.write_text(text, encoding="utf-8")
    return load_credential_pack(directory)


def test_land_right_transfer_reads_pack_declared_v2_credential_kind(tmp_path):
    store, registry, chain = setup_reference(pack=_pack_with_seal(tmp_path))
    chain._owner.activate_v2_authority()
    args = command("issue_credential") | {"credential_kind": "seal"}
    assert chain.execute("issue_credential", **args).committed

    authority = LandRightTransferAuthority(
        store=store,
        inventory_registry=registry,
        policies=(LandRightTransferPolicy(
            asset_ref="land:g3",
            credential_presence_container_ids=("container:g3:bag",),
        ),),
    )
    result = authority.transfer(
        command_id="cmd:g3:seal-land-right-transfer",
        asset_ref="land:g3",
        right_id="right:g3",
        from_holder_ref="actor:g3",
        to_holder_ref="actor:g4",
        credential_id=args["credential_id"],
        expected_ownership_revision=store.get_stream_head("gameplay:ownership"),
        idempotency_key="key:g3:seal-land-right-transfer",
        causation_id="cause:g3",
        correlation_id="corr:g3",
    )
    assert result.committed


def test_adventure_basic_closure_hash_rebuilds_pack_declared_v2_kind(tmp_path):
    scenario = AdventureBasicScenario4.create()
    assert scenario.purchase_land().committed
    chain = CredentialReferenceChain(
        store=scenario.store,
        inventory_registry=scenario.inventory_registry,
        pack=_pack_with_seal(tmp_path),
    )
    chain._owner.activate_v2_authority()
    args = command("issue_credential") | {
        "command_id": "cmd:g3:scenario4-seal",
        "idempotency_key": "g3:scenario4-seal",
        "credential_id": scenario.land_deed_credential_id,
        "credential_item_ref": scenario.land_deed_item_id,
        "credential_holder_ref": scenario.player_ref,
        "right_id": scenario.land_right_id,
        "credential_kind": "seal",
        "issuer_ref": "authority:g3",
    }
    assert chain.execute("issue_credential", **args).committed

    evidence = capture_adventure_basic_closure(scenario_id="scenario-4", scenario=scenario)
    assert evidence.online_facade_hash == evidence.full_replay_facade_hash
    assert evidence.online_facade_hash == evidence.checkpoint_tail_facade_hash
