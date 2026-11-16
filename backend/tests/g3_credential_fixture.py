"""Deterministic real Owner/store fixture shared by the G3 witnesses."""
from pathlib import Path

from app.gameplay.credential_reference_chain import CredentialReferenceChain, load_credential_pack
from app.gameplay.credential_runtime import CredentialAuthorityService
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.inventory_runtime import ContainerSpec, InventoryAuthorityService, InventoryDefinitionRegistry, ItemDefinition
from app.gameplay.ownership_runtime import OwnershipAuthorityService

PACK = Path(__file__).resolve().parents[2] / "packs" / "credential_reference"


def setup_reference():
    store = GameplayEventStore()
    OwnershipAuthorityService(store=store).grant_initial_title(command_id="cmd:g3:title",
        asset_ref="land:g3", holder_ref="actor:g3", right_id="right:g3",
        idempotency_key="g3:title", causation_id="cause:g3", correlation_id="corr:g3")
    registry = InventoryDefinitionRegistry()
    registry.register_item(ItemDefinition("item:g3:document", "1", 0, 0))
    inventory = InventoryAuthorityService(store=store, registry=registry)
    inventory.create_container(command_id="cmd:g3:bag", actor_ref="actor:g3",
        spec=ContainerSpec("container:g3:bag", 1, 1, 2), idempotency_key="g3:bag",
        causation_id="cause:g3", correlation_id="corr:g3")
    for number in (1, 2):
        inventory.instantiate(command_id=f"cmd:g3:item:{number}", actor_ref="actor:g3",
            item_id=f"item:g3:{number}", definition_id="item:g3:document", quantity=1,
            container_id="container:g3:bag", idempotency_key=f"g3:item:{number}",
            causation_id="cause:g3", correlation_id="corr:g3")
    chain = CredentialReferenceChain(store=store, inventory_registry=registry, pack=load_credential_pack(PACK))
    return store, registry, chain


def command(kind):
    common = dict(command_id=f"cmd:g3:{kind}", idempotency_key=f"g3:{kind}",
        causation_id="cause:g3", correlation_id="corr:g3", issuer_ref="authority:g3")
    if kind == "issue_credential":
        return common | dict(credential_id="credential:g3:1", credential_item_ref="item:g3:1",
            credential_holder_ref="actor:g3", right_id="right:g3", credential_kind="deed", proves="evidence_only")
    if kind == "revoke_credential":
        return common | dict(credential_id="credential:g3:2", reason="replaced")
    return common | dict(prior_credential_id="credential:g3:1", replacement_credential_id="credential:g3:2",
        replacement_item_ref="item:g3:2", replacement_holder_ref="actor:g3")


def lifecycle(chain):
    return [chain.execute(kind, **command(kind)) for kind in (
        "issue_credential", "supersede_credential", "revoke_credential")]
