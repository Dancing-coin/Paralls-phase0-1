"""Session 事务内的纯当前态投影；历史和幂等事实由 session 索引保存。"""
from __future__ import annotations

from copy import deepcopy

from app.character_agent.models.background_agenda import CharacterBackgroundAgendaState
from app.character_agent.models.goal_runtime import CharacterGoalStateRecord
from app.character_agent.models.simulation_seed import (
    CharacterContinuityReceipt, CharacterMemoryCandidate, CharacterMemoryMaterializationReceipt,
)
from app.character_agent.models.supervision import CharacterSupervisionConstraints, CharacterSupervisionState
from app.character_agent.storage.dynamic_state_store import CharacterDynamicStateStore
from app.character_agent.storage.goal_state_store import CharacterGoalStateStore
from app.character_agent.storage.need_tension_store import CharacterNeedTensionStore
from app.character_agent.storage.unresolved_tension_store import CharacterUnresolvedTensionStore


def goal_state_from_event(actor_id: str, payload: dict[str, object]) -> CharacterGoalStateRecord:
    """保留旧 timeline 恢复的缺字段/旧字段归一化规则。"""
    strings = {
        key: str(payload.get(key, default) or default)
        for key, default in {
            "primary_goal": "", "long_term_goal": "", "mid_term_strategy": "",
            "immediate_goal": str(payload.get("primary_goal", "") or ""),
            "urgency": "low", "dominant_goal_id": "", "goal_arbitration_summary": "",
            "transition_kind": "initial",
        }.items()
    }
    arrays = {
        key: list(payload[key]) if isinstance(payload.get(key), list) else []
        for key in ("supporting_goals", "blockers", "goal_sources", "preserved_goal_ids",
                    "suppressed_goal_ids", "goal_portfolio", "transition_reason_tags")
    }
    return CharacterGoalStateRecord(actor_id=actor_id, **strings, **arrays)


def reduce_session_event(
    previous: dict[str, object] | None, event: dict[str, object],
) -> dict[str, object]:
    actor_id = str(event["actor_id"])
    if previous and previous.get("actor_id") != actor_id:
        raise ValueError("session_recovery_actor_mismatch")
    if previous and previous.get("schema_version") != 1:
        raise ValueError("session_recovery_schema_unsupported")
    state = deepcopy(previous) if previous else {"schema_version": 1, "actor_id": actor_id, "event_index": 0}
    if type(event["event_index"]) is not int or event["event_index"] != state["event_index"] + 1:
        raise ValueError("session_recovery_gap")
    state.update(event_index=event["event_index"], event_id=event["event_id"])
    payload = event["payload"]
    if not isinstance(payload, dict):
        raise ValueError("session_event_invalid")
    kind = event["event_type"]
    if kind == "goal_state_event":
        store = CharacterGoalStateStore()
        for goal in state.get("goal_history", []):
            store.write(actor_id, goal)
        store.write(actor_id, goal_state_from_event(actor_id, payload))
        state["goal_history"] = store.history(actor_id)
    elif kind == "dynamic_state_event":
        store = CharacterDynamicStateStore()
        store.write(actor_id, payload)
        state["dynamic_state"] = store.read_record(actor_id).storage_dump()
    elif kind == "need_tension_state_event":
        store = CharacterNeedTensionStore()
        store.write(actor_id, payload)
        state["need_tension_state"] = store.read(actor_id)
    elif kind == "character_unresolved_tension_event":
        store = CharacterUnresolvedTensionStore()
        for tension in state.get("unresolved_tensions", []):
            store.upsert(actor_id, tension)
        store.upsert(actor_id, payload)
        state["unresolved_tensions"] = store.recall(actor_id)
    elif kind == "character_supervision_authorization":
        constraints = payload.get("constraints")
        constraints = CharacterSupervisionConstraints(**constraints) if isinstance(constraints, dict) else CharacterSupervisionConstraints()
        state["supervision_state"] = CharacterSupervisionState(
            actor_id=actor_id,
            current_level=str(payload.get("approved_level", "weak") or "weak"),
            source="strategy_authorized" if str(payload.get("approved_by", "strategy_service") or "strategy_service") == "strategy_service" else "gm_override",
            active_constraints=constraints,
            entered_at_ts=int(payload.get("effective_from_ts", 0) or 0),
            expires_at_ts=int(payload.get("expires_at_ts", 0) or 0),
            last_refresh_ts=int(payload.get("producer_ts", 0) or payload.get("effective_from_ts", 0) or 0),
            last_reason_summary=str(payload.get("approval_reason", "") or ""),
        ).model_dump(mode="json")
    elif kind == "character_supervision_cleared":
        state["supervision_state"] = CharacterSupervisionState(**payload).model_dump(mode="json")
    elif kind == "character_background_cognition_event":
        agenda = payload.get("background_agenda_state")
        if isinstance(agenda, dict) and agenda:
            state["background_agenda_state"] = CharacterBackgroundAgendaState(**agenda).model_dump(mode="json")
    elif kind == "character_simulation_seed_event":
        _reduce_seed(state, event)
    versions = state.setdefault('field_versions', {})
    for field in ('dynamic_state', 'supervision_state'):
        if state.get(field) != (previous or {}).get(field) or (field == 'dynamic_state' and kind in {'dynamic_state_event','character_simulation_seed_event'}) or (field == 'supervision_state' and kind in {'character_supervision_authorization','character_supervision_cleared'}):
            versions[field] = event['event_index']
    return state


def _reduce_seed(state: dict[str, object], event: dict[str, object]) -> None:
    actor_id, payload = str(event["actor_id"]), event["payload"]
    commit = payload.get("continuity_commit")
    if not isinstance(commit, dict):
        return
    key = commit.get("idempotency_key")
    if not isinstance(key, str) or not key or not isinstance(commit.get("receipt"), dict):
        raise ValueError("character_continuity_commit_invalid")
    receipt = CharacterContinuityReceipt.model_validate(commit["receipt"])
    if receipt.actor_ref.removeprefix("character:") != actor_id or payload.get("actor_ref") != receipt.actor_ref:
        raise ValueError("character_continuity_commit_actor_mismatch")
    if receipt.character_revision_before != state.get("continuity_revision", 0):
        raise ValueError("character_continuity_projection_gap")
    state["continuity_revision"] = receipt.character_revision_after
    state["seed_event_id"] = event["event_id"]
    modules = payload.get("shared_modules")
    if modules is not None:
        if not isinstance(modules, dict):
            raise ValueError("character_continuity_module_state_invalid")
        state["shared_module_state"] = deepcopy(modules)
    deltas = payload.get("state_deltas", {})
    for field, store, key in (
        ("need_tension_state", CharacterNeedTensionStore(), "need_tension"),
        ("dynamic_state", CharacterDynamicStateStore(), "dynamic_state"),
    ):
        if field in state:
            store.write(actor_id, state[field])
        changed = False
        for delta in (deltas.get(key) if isinstance(deltas, dict) else None, commit.get(key + "_delta")):
            if isinstance(delta, dict) and delta:
                store.merge_delta(actor_id, delta)
                changed = True
        if changed:
            state[field] = store.read_record(actor_id).storage_dump() if field == "dynamic_state" else store.read(actor_id)
    hints = payload.get("activation_hints", ())
    if isinstance(hints, (list, tuple)) and hints:
        state["wake_up"] = {
            "wake_up_requested": True,
            "salience": float(payload.get("activation_salience", 0.0) or 0.0),
            "producer_ts": int(payload.get("to_tick", 0) or 0),
            "activation_hints": [str(item) for item in hints],
        }


def session_event_facts(
    event: dict[str, object],
) -> tuple[list[tuple[str, str, dict[str, object]]], list[dict[str, object]]]:
    """提取与本次提交同事务写入的冷索引，不累计到当前态 JSON。"""
    actor_id, payload = str(event["actor_id"]), event["payload"]
    receipts: list[tuple[str, str, dict[str, object]]] = []
    candidates: list[dict[str, object]] = []
    if event["event_type"] == "character_simulation_seed_event" and isinstance(payload.get("continuity_commit"), dict):
        commit = payload["continuity_commit"]
        key = commit.get("idempotency_key")
        if not isinstance(key, str) or not key:
            raise ValueError("character_continuity_commit_invalid")
        receipt = CharacterContinuityReceipt.model_validate(commit.get("receipt"))
        if receipt.actor_ref.removeprefix("character:") != actor_id:
            raise ValueError("character_continuity_commit_actor_mismatch")
        receipts.append(("continuity", key, receipt.model_dump(mode="json")))
        raw_candidates = commit.get("memory_candidates", [])
        if not isinstance(raw_candidates, list):
            raise ValueError("character_continuity_commit_invalid")
        for raw in raw_candidates:
            candidate = CharacterMemoryCandidate.model_validate(raw)
            if candidate.actor_ref.removeprefix("character:") != actor_id:
                raise ValueError("character_continuity_commit_actor_mismatch")
            candidates.append(candidate.model_dump(mode="json"))
    if isinstance(payload.get("materialization_receipt"), dict):
        receipt = CharacterMemoryMaterializationReceipt.model_validate(payload["materialization_receipt"])
        if receipt.actor_ref.removeprefix("character:") != actor_id:
            raise ValueError("character_materialization_commit_actor_mismatch")
        receipts.append(("materialization", receipt.candidate_id, receipt.model_dump(mode="json")))
    return receipts, candidates
