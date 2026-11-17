"""Opt-in reference chain: frozen pure evaluation followed by the real Owner.

The v1 shared stream and unbound visibility role remain known deviations.
Restricted inputs are a data boundary for trusted models, not a Python sandbox.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from app.gameplay.credential_runtime import (
    CredentialAuthorityService, CredentialProjector, CredentialRuntimeError,
)
from app.gameplay.event_store import GameplayEventStore
from app.gameplay.fact_type_registry import freeze
from app.gameplay.inventory_runtime import InventoryDefinitionRegistry, InventoryProjector
from app.gameplay.models import AppendBatchResult
from app.gameplay.ownership_runtime import OwnershipProjector
from app.gameplay.rule_pack_validator import LoadedPack, load_pack

FACT = "fact:credential:*:link"
MODEL = "credential_command@1"


def credential_command_condition(inputs, params):
    """Existing qualification rules expressed over declared projection values."""
    command = inputs["command@1"]
    links = inputs[FACT]
    kind = command["kind"]
    if kind == "issue_credential":
        if (command["credential_id"] in links or not all(command[key] for key in (
                "credential_id", "credential_item_ref", "credential_holder_ref", "right_id", "issuer_ref"))):
            return "credential_invalid"
        if any(link["credential_item_ref"] == command["credential_item_ref"] and link["status"] == "issued" for link in links.values()):
            return "credential_item_already_linked"
        if command["credential_kind"] not in params["credential_kinds"] or command["proves"] not in params["proves"]:
            return "credential_invalid"
        if command["right_id"] not in inputs["ownership.rights@1"]:
            return "ownership_right_missing"
        item = command["credential_item_ref"]
    elif kind == "revoke_credential":
        link = links.get(command["credential_id"])
        if link is None or link["status"] != "issued" or link["issuer_ref"] != command["issuer_ref"] or not command["reason"]:
            return "credential_not_active"
        return None
    elif kind == "supersede_credential":
        prior = links.get(command["prior_credential_id"])
        if (prior is None or prior["status"] != "issued" or prior["issuer_ref"] != command["issuer_ref"]
                or command["replacement_credential_id"] in links or not command["replacement_item_ref"] or not command["replacement_holder_ref"]):
            return "credential_not_active"
        # Deliberately no ownership check: preserve the existing supersede rule.
        item = command["replacement_item_ref"]
    else:
        raise CredentialRuntimeError("credential_command_unknown")
    inventory = inputs["inventory.actor@1"]
    if item not in inventory["items"] or item not in inventory["locations"]:
        return "credential_item_not_present"
    return None


def load_credential_pack(directory: Path) -> LoadedPack:
    return load_pack(directory, handlers={MODEL: credential_command_condition})


@dataclass(frozen=True)
class EvaluationFrame:
    values: Mapping[str, Any]
    source_revision_vector: Mapping[str, int]
    pack_digest: str


class CredentialReferenceChain:
    def __init__(self, *, store: GameplayEventStore, inventory_registry: InventoryDefinitionRegistry, pack: LoadedPack):
        self._store = store
        self._inventory_registry = inventory_registry
        model_params = pack.registry.models[MODEL].params
        self._owner = CredentialAuthorityService(
            store=store,
            inventory_registry=inventory_registry,
            credential_kinds=model_params["credential_kinds"],
            proves=model_params["proves"],
        )
        self.pack = pack

    def freeze_inputs(self, kind: str, command: Mapping[str, Any]) -> EvaluationFrame:
        if kind not in ("issue_credential", "revoke_credential", "supersede_credential"):
            raise CredentialRuntimeError("credential_command_unknown")
        # Every projection and revision comes from this single captured event list.
        events = self._store.read_events()
        heads = {}
        for event in events:
            heads[event.stream_id] = max(heads.get(event.stream_id, 0), event.stream_revision)
        model_params = self.pack.registry.models[MODEL].params
        projection = CredentialProjector(
            credential_kinds=model_params["credential_kinds"], proves=model_params["proves"]
        ).rebuild(events)
        links = {key: asdict(link) | {"status": "issued" if link.status == "active" else link.status}
                 for key, link in projection.links.items()}
        values = {FACT: links, "command@1": dict(command) | {"kind": kind}}
        streams = ["gameplay:credentials"]
        if kind == "issue_credential":
            rights = OwnershipProjector().rebuild(events).rights
            values["ownership.rights@1"] = {key: dict(right_id=right.right_id,
                asset_ref=right.asset_ref, holder_ref=right.holder_ref) for key, right in rights.items()}
            streams.append("gameplay:ownership")
        if kind != "revoke_credential":
            holder = command["credential_holder_ref"] if kind == "issue_credential" else command["replacement_holder_ref"]
            inventory = InventoryProjector(self._inventory_registry).rebuild(holder, events)
            values["inventory.actor@1"] = {"items": sorted(inventory.items), "locations": dict(inventory.locations)}
            streams.append(f"gameplay:inventory:{holder}")
        return EvaluationFrame(freeze(values), freeze({stream: heads.get(stream, 0) for stream in streams}), self.pack.content_hash)

    def evaluate(self, frame: EvaluationFrame) -> str | None:
        if frame.pack_digest != self.pack.content_hash:
            raise CredentialRuntimeError("credential_pack_mismatch")
        return self.pack.registry.evaluate(MODEL, frame.values)

    def execute(self, kind: str, **command: Any) -> AppendBatchResult:
        if kind not in ("issue_credential", "revoke_credential", "supersede_credential"):
            raise CredentialRuntimeError("credential_command_unknown")
        # Retry identity and replay are the Owner's responsibility. Re-evaluating
        # an already committed issue would incorrectly reject its existing ID.
        principals = (self._owner._PRINCIPAL, self._owner._V2_PRINCIPAL) if self._owner._v2_enabled else (self._owner._PRINCIPAL,)
        records = (self._store.get_idempotency_record(principal, command["idempotency_key"]) for principal in principals)
        if not any(record is not None for record in records):
            error = self.evaluate(self.freeze_inputs(kind, command))
            if error is not None:
                raise CredentialRuntimeError(error)
        # The real Owner revalidates and submits with its existing pins/CAS.
        # No result of pure evaluation authorizes a direct append here.
        return getattr(self._owner, kind)(**command)
