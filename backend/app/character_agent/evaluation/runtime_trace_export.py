"""Read-only development inputs with optional original owner snapshot association."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from app.character_agent.gateway.laya_provider import LayaSystemOneProvider
from app.gameplay.event_store import GameplayEventStore
from app.models.player_input import InteractIntent
from app.services.esm_service import ESMService


def _digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                     allow_nan=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _unique(rows: list[tuple[int, dict]]) -> list[tuple[int, dict]]:
    seen: set[str] = set()
    result = []
    for line, value in rows:
        digest = _digest(value)
        if digest not in seen:
            result.append((line, value))
            seen.add(digest)
    return result


class _Rejected(ValueError):
    pass


def _owner_association(owner: ESMService, store: GameplayEventStore,
                       contract: dict, boundary: dict) -> dict:
    """Use original recovery/idempotency rules, without executing any command."""
    actions = {"inspect_object": "inspect", "use_object": "use", "finish_use": "finish_use"}
    action = actions.get(contract["semantic_intent_id"])
    if not action or contract["semantic_action_id"] not in {action, "action:" + action}:
        raise _Rejected("owner_request_mismatch")
    try:
        scope = contract["expected_observation"]["execution_scope"]
        actor_id = contract["actor_ref"].removeprefix("character:")
        event = InteractIntent(player_id="character_agent", actor_id=actor_id,
            **scope, producer_ts=contract["producer_ts"], target_object_id=contract["target_ref"],
            interaction_type=action, turn_id=contract["turn_id"],
            execution_contract_ref=contract["idempotency_key"])
        request = owner.build_action_request(event, source_system="character_agent_l4").model_copy(update={
            "request_id": f"{contract['idempotency_key']}:0",
            "source": {"layer": "L4", "system": "character_agent", "actor_id": actor_id},
            **{key: contract[key] for key in ("causation_id", "correlation_id",
                "expected_revision_vector", "expected_memory_revision_vector", "expected_snapshot_revision")},
        })
        original = owner.find_object_settlement(event, action_request=request)
    except (ValueError, TypeError, KeyError) as exc:
        raise _Rejected("owner_request_mismatch") from exc
    if original is None:
        raise _Rejected("owner_receipt_missing")
    result, receipt = original
    saved = result.model_dump(mode="json")
    if any(boundary[key] != saved[key] for key in boundary.keys() & saved.keys()):
        raise _Rejected("owner_boundary_mismatch")
    event = store.get_event(receipt.committed_event_ids[0])
    return {"event_id": event.event_id, "event_digest": _digest(event.model_dump(mode="json")),
            "transaction_id": receipt.transaction_id, "receipt_digest": _digest(receipt.model_dump(mode="json")),
            "global_sequence": event.global_sequence}


def _record(prepared: dict, call: dict, rows: list[dict], *, provider: LayaSystemOneProvider,
            prepared_line: int, model_line: int,
            owner_source: tuple[ESMService, GameplayEventStore, str] | None = None) -> dict:
    context = prepared.get("context", {})
    if (context.get("provider_revision") != provider.PROVIDER_REVISION
            or not context.get("turn_id") or not context.get("actor_id")):
        raise _Rejected("provider_invalid")
    compilation = {name: context.get(field) for name, field in (
        ("universe", "candidate_universe"), ("presented", "frozen_candidates"),
        ("pruned", "candidate_pruned"), ("diagnostics", "candidate_diagnostics"))}
    if (any(not isinstance(value, list) for value in compilation.values())
            or _digest(compilation) != context.get("candidate_digest")):
        raise _Rejected("compilation_digest_mismatch")
    universe = compilation["universe"]
    presented = compilation["presented"]
    if (not presented or any(item not in universe for item in presented)
            or len({item.get("wire_label") for item in universe}) != len(universe)
            or len({item.get("candidate_id") for item in universe}) != len(universe)):
        raise _Rejected("compilation_coverage_invalid")
    try:
        wire = provider.build_wire_request(prepared)
    except (ValueError, TypeError, KeyError) as exc:
        raise _Rejected("provider_invalid") from exc
    observed_wire = call.get("request")
    if (wire != observed_wire or list(wire["questions"]["choice"]["criteria"])
            != list(observed_wire["questions"]["choice"]["criteria"])):
        raise _Rejected("wire_mismatch")
    response = call.get("response") or {}
    answer = (response.get("answers") or {}).get("choice") or {}
    choice = answer.get("choice")
    mapping = context["candidate_mapping"]
    if not isinstance(choice, str) or choice not in mapping:
        raise _Rejected("choice_invalid")
    usage = response.get("usage") or {}
    if (usage.get("truncated") is not False or type(usage.get("state_tokens_dropped")) is not int
            or usage["state_tokens_dropped"] != 0 or usage.get("truncated_questions", []) != []):
        raise _Rejected("usage_invalid")
    selected = mapping[choice]
    executions = _unique([(i, r["contract"]) for i, r in enumerate(rows, 1)
                          if i > model_line and r.get("kind") == "execution_input"
                          and r.get("contract", {}).get("turn_id") == context["turn_id"]])
    if not executions:
        raise _Rejected("execution_missing")
    if len(executions) != 1:
        raise _Rejected("execution_ambiguous")
    execution_line, contract = executions[0]
    expected = contract.get("expected_observation") or {}
    targets = list(selected.get("target_refs", {}).values())
    # This bounded exporter admits owner-bound object actions only. Observation
    # realization may select a local primitive and is a different contract.
    if (selected.get("owner_route") != "esm.interaction" or len(targets) != 1
            or contract.get("actor_ref") != "character:" + context["actor_id"]
            or contract.get("semantic_intent_id") != selected.get("semantic_intent_id")
            or contract.get("semantic_action_id") != selected.get("semantic_action_id")
            or contract.get("target_refs") != targets or contract.get("target_ref") != targets[0]
            or not contract.get("idempotency_key")
            or expected.get("candidate_id") != selected["candidate_id"]
            or expected.get("candidate_digest") != context["candidate_digest"]
            or expected.get("owner_route") != selected["owner_route"]
            or expected.get("target_admission_digest") != selected.get("revision_pins", {}).get("target_admission_digest")):
        raise _Rejected("execution_identity_mismatch")
    boundaries = _unique([(i, r["message"]["payload"]) for i, r in enumerate(rows, 1)
                          if i > execution_line and r.get("kind") == "wire_output"
                          and r.get("message", {}).get("message_type") == "world_result"
                          and r["message"].get("payload", {}).get("turn_id") == context["turn_id"]
                          and r["message"]["payload"].get("settlement_status") == "committed"])
    if not boundaries:
        raise _Rejected("owner_boundary_missing")
    if len(boundaries) != 1:
        raise _Rejected("boundary_ambiguous")
    boundary_line, boundary = boundaries[0]
    scope = expected.get("execution_scope") or {}
    if (not boundary.get("settlement_id") or boundary.get("actor_id") != context["actor_id"]
            or boundary.get("target_object_id") != targets[0]
            or boundary.get("idempotency_key") != contract["idempotency_key"]
            or any(not scope.get(key) or boundary.get(key) != scope[key]
                   for key in ("room_id", "scene_id", "zone_id"))):
        raise _Rejected("boundary_identity_mismatch")
    record = {
        "turn_id": context["turn_id"], "actor_id": context["actor_id"],
        "source_lines": {"prepared": prepared_line, "model": model_line,
                         "execution": execution_line, "boundary": boundary_line},
        "provider_revision": provider.PROVIDER_REVISION, "tokenizer_sha256": provider.tokenizer_sha256,
        "prepared_digest": _digest(prepared), "wire_request": wire,
        "candidate_digest": context["candidate_digest"], "candidate_compilation": compilation,
        "observed_choice": choice, "usage": {key: usage[key] for key in (
            "truncated", "state_tokens_dropped", "input_tokens", "state_tokens", "truncated_questions") if key in usage},
        "execution": {key: contract[key] for key in (
            "turn_id", "actor_ref", "target_refs", "semantic_intent_id", "semantic_action_id", "idempotency_key")},
        "execution_digest": _digest(contract),
        "boundary_result": {key: boundary[key] for key in (
            "settlement_status", "settlement_id", "turn_id", "idempotency_key", "actor_id", "target_object_id")},
        "owner_store_validation": "unverified", "quality": "unscored", "recovery": "unverified",
    }
    if owner_source is not None:
        owner, store, source_digest = owner_source
        record["owner_evidence"] = dict(_owner_association(owner, store, contract, boundary),
                                        source_sha256=source_digest)
        record["owner_store_validation"] = "snapshot_matched"
    return record


def export_runtime_trace(path: Path, *, provider: LayaSystemOneProvider,
                         owner_snapshot: Path | None = None) -> dict:
    """Associate serial records without contacting a model or executing commands.

    The optional Gameplay JSON snapshot is read once and validated through the
    original store and ESM recovery. No writable database is opened. Digests
    prove consistency of supplied artifacts, never independent authenticity.
    """
    raw = path.read_bytes()
    owner_source = None
    if owner_snapshot is not None:
        try:
            owner_raw = owner_snapshot.read_bytes()
            store = GameplayEventStore.from_snapshot(json.loads(owner_raw))
            owner_source = (ESMService(store=store), store,
                            "sha256:" + hashlib.sha256(owner_raw).hexdigest())
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise ValueError("owner_snapshot_invalid") from exc
    rows = [json.loads(line) for line in raw.decode("utf-8-sig").splitlines()]
    records, rejections = [], []
    pending: tuple[int, dict] | None = None
    overlapping = False
    for line, row in enumerate(rows, 1):
        if row.get("kind") == "laya_enter":
            if pending is not None:
                overlapping = True
            pending = (line, row["frozen_request"])
        elif row.get("kind") == "laya_http_result":
            if pending is None or overlapping:
                rejections.append({"line": line, "reason": "overlapping_model_calls" if overlapping else "prepared_missing"})
            else:
                prepared_line, prepared = pending
                try:
                    record = _record(prepared, row["call"], rows, provider=provider,
                                     prepared_line=prepared_line, model_line=line, owner_source=owner_source)
                    record["record_digest"] = _digest(record)
                    records.append(record)
                except _Rejected as exc:
                    rejections.append({"line": line, "reason": str(exc)})
            pending, overlapping = None, False
    if pending is not None:
        rejections.append({"line": pending[0], "reason": "model_result_missing"})
    result = {"schema_version": "runtime_development_source.v1", "status": "development_only",
              "visibility": "developer_private", "formal_eligible": False,
              "source_sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
              "accepted_count": len(records), "records": records, "rejections": rejections}
    result["artifact_digest"] = _digest(result)
    return copy.deepcopy(result)
