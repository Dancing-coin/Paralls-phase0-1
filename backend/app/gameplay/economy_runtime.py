"""Minimal event-sourced account ledger; balances are projections, never inputs."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from types import MappingProxyType
from typing import Mapping, Sequence

from app.gameplay.event_store import GameplayEventStore
from app.gameplay.models import AppendBatchResult, GameplayEvent


class EconomyRuntimeError(ValueError): pass

@dataclass(frozen=True)
class Account:
    account_id: str; owner_ref: str; currency_ref: str; balance: int; source_event_id: str

@dataclass(frozen=True)
class EconomyProjection:
    accounts: Mapping[str, Account]; balances: Mapping[str, int]; source_revision_vector: Mapping[str, int]

class EconomyProjector:
    def rebuild(self, events: Sequence[GameplayEvent]) -> EconomyProjection:
        accounts: dict[str, Account] = {}; revisions: dict[str, int] = {}
        for event in sorted(events, key=lambda item: (item.global_sequence, item.event_id)):
            if event.event_type not in {"gameplay.economy.account_opened", "gameplay.economy.account_debited", "gameplay.economy.account_credited"}: continue
            p = event.payload; account_id = _text(p, "account_id")
            if event.event_type == "gameplay.economy.account_opened":
                if account_id in accounts: raise EconomyRuntimeError("economy_account_duplicate")
                accounts[account_id] = Account(account_id, _text(p,"owner_ref"), _text(p,"currency_ref"), _nonnegative(p,"initial_balance"), event.event_id)
            else:
                prior = accounts.get(account_id)
                if prior is None: raise EconomyRuntimeError("economy_account_missing")
                amount = _positive(p,"amount")
                value = prior.balance - amount if event.event_type.endswith("debited") else prior.balance + amount
                if value < 0: raise EconomyRuntimeError("economy_insufficient_funds")
                accounts[account_id] = Account(prior.account_id, prior.owner_ref, prior.currency_ref, value, event.event_id)
            revisions[event.stream_id] = max(revisions.get(event.stream_id,0), event.stream_revision)
        frozen = MappingProxyType(dict(sorted(accounts.items())))
        return EconomyProjection(frozen, MappingProxyType({key: account.balance for key, account in frozen.items()}), MappingProxyType(dict(sorted(revisions.items()))))

class EconomyAuthorityService:
    _PRINCIPAL="actor_gameplay.economy_domain"
    def __init__(self, *, store: GameplayEventStore): self._store=store; self._projector=EconomyProjector()
    def open_account(self, *, command_id:str, account_id:str, owner_ref:str, currency_ref:str, initial_balance:int, idempotency_key:str, causation_id:str, correlation_id:str)->AppendBatchResult:
        p=self._projector.rebuild(self._store.read_events())
        if account_id in p.accounts or not account_id or not owner_ref or not currency_ref or initial_balance<0: raise EconomyRuntimeError("economy_account_invalid")
        return self._append(command_id,idempotency_key,[self._event(command_id,"gameplay.economy.account_opened",1,{"account_id":account_id,"owner_ref":owner_ref,"currency_ref":currency_ref,"initial_balance":initial_balance},causation_id,correlation_id)],p)
    def transfer(self, *, command_id:str, debit_account_id:str, credit_account_id:str, amount:int, idempotency_key:str, causation_id:str, correlation_id:str)->AppendBatchResult:
        p=self._projector.rebuild(self._store.read_events()); debit=p.accounts.get(debit_account_id); credit=p.accounts.get(credit_account_id)
        if debit is None or credit is None or debit.currency_ref != credit.currency_ref or debit_account_id==credit_account_id or amount<=0: raise EconomyRuntimeError("economy_transfer_invalid")
        if debit.balance<amount: raise EconomyRuntimeError("economy_insufficient_funds")
        return self._append(command_id,idempotency_key,[self._event(command_id,"gameplay.economy.account_debited",1,{"account_id":debit_account_id,"amount":amount},causation_id,correlation_id),self._event(command_id,"gameplay.economy.account_credited",2,{"account_id":credit_account_id,"amount":amount},causation_id,correlation_id)],p)
    def _event(self,command_id:str,event_type:str,index:int,payload:dict[str,object],causation_id:str,correlation_id:str)->dict[str,object]:
        return {"event_id":f"evt:{command_id}:economy:{index}","event_type":event_type,"schema_version":1,"stream_id":"gameplay:economy","stream_revision":0,"global_sequence":0,"transaction_id":f"tx:{command_id}","command_id":command_id,"causation_id":causation_id,"correlation_id":correlation_id,"visibility_policy":"authority_only","payload":payload}
    def _append(self,command_id:str,idempotency_key:str,events:list[dict[str,object]],projection:EconomyProjection)->AppendBatchResult:
        digest=_digest(events); stream="gameplay:economy"
        return self._store.append_batch({"transaction_id":f"tx:{command_id}","command_id":command_id,"expected_stream_revisions":{stream:projection.source_revision_vector.get(stream,0)},"pinned_revisions":{"economy":projection.source_revision_vector.get(stream,0)},"events":events,"idempotency_record":{"principal_ref":self._PRINCIPAL,"idempotency_key":idempotency_key,"payload_digest":digest},"outbox_entries":[],"result_digest":digest,"projection_refresh_hints":[]})

def _text(p:Mapping[str,object],k:str)->str:
    v=p.get(k)
    if not isinstance(v,str) or not v: raise EconomyRuntimeError("economy_event_payload_invalid")
    return v
def _nonnegative(p:Mapping[str,object],k:str)->int:
    v=p.get(k)
    if isinstance(v,bool) or not isinstance(v,int) or v<0: raise EconomyRuntimeError("economy_event_payload_invalid")
    return v
def _positive(p:Mapping[str,object],k:str)->int:
    v=_nonnegative(p,k)
    if not v: raise EconomyRuntimeError("economy_event_payload_invalid")
    return v
def _digest(v:object)->str: return sha256(json.dumps(v,sort_keys=True,separators=(",",":"),default=lambda x:dict(x) if isinstance(x,Mapping) else x.__dict__).encode()).hexdigest()

__all__=["Account","EconomyAuthorityService","EconomyProjection","EconomyProjector","EconomyRuntimeError"]
