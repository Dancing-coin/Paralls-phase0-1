"""Read-only development inputs from serial diagnostic archives, never owner proof."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

from app.character_agent.gateway.laya_provider import LayaSystemOneProvider


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


def _record(prepared: dict, call: dict, rows: list[dict], *, provider: LayaSystemOneProvider,
            prepared_line: int, model_line: int) -> dict:
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
    return {
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


def export_runtime_trace(path: Path, *, provider: LayaSystemOneProvider) -> dict:
    """Associate serial archive records; do not contact a model or open a world store.

    The caller supplies the local pinned provider/tokenizer used to rebuild wire
    inputs. Digests prove archive consistency only, never origin authenticity.
    """
    raw = path.read_bytes()
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
                                     prepared_line=prepared_line, model_line=line)
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
