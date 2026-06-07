from __future__ import annotations

from typing import Any


def build_debug_event(
    *,
    producer_ts: int,
    domain: str,
    stage: str,
    summary: str,
    detail: dict[str, Any],
    actor_id: str | None = None,
) -> dict[str, Any]:
    return {
        "event_type": "debug_trace_event",
        "producer_ts": producer_ts,
        "domain": domain,
        "actor_id": actor_id,
        "stage": stage,
        "summary": summary,
        "detail": detail,
    }


def summarize_raw_fact_event(event: Any) -> str:
    if event.fact_family == "visual_fact":
        if event.fact_type == "fixed_gaze_on_target":
            if event.targets.actor_id:
                return f"{event.source.actor_id} 正在看向 {event.targets.actor_id}。"
            if event.targets.object_id:
                return f"{event.source.actor_id} 正在看向 {event.targets.object_id}。"
        if event.fact_type == "spatial_relation" and event.relation_type == "actor_near_object":
            return f"{event.source.actor_id} 已靠近 {event.targets.object_id}，进入可交互观察范围。"
        if event.fact_type == "light_level_drop":
            return f"环境 {event.targets.environment_id} 的光照降低了。"

    if event.fact_family == "spatial_access_fact":
        if event.fact_type == "actor_entered_zone":
            return f"{event.source.actor_id} 进入了 {event.zone_id}。"
        if event.fact_type == "actor_approached_actor":
            if event.world.distance_m is not None:
                return f"{event.source.actor_id} 正在接近 {event.targets.actor_id}，当前距离约 {event.world.distance_m:.1f} 米。"
            return f"{event.source.actor_id} 正在接近 {event.targets.actor_id}。"
        if event.fact_type == "privacy_boundary_changed":
            return f"当前互动隐私带从 {event.world.state_before or 'unknown'} 变成了 {event.world.state_after or 'unknown'}。"

    return f"收到 {event.fact_family}/{event.fact_type}。"


def summarize_backend_route(event: Any, route: str) -> str:
    if route == "authority_visual_fact":
        return "后端接受了这条视觉事实，并进入视觉事实处理链。"
    if route == "authority_spatial_access_fact":
        return "后端接受了这条空间接入事实，并进入接入证据处理链。"
    return f"后端将该事件路由到 {route}。"


def summarize_character_input(actor_id: str, label: str) -> str:
    return f"{actor_id} 收到了一个输入：{label}。"


def summarize_character_interpretation(actor_id: str, payload: dict[str, Any]) -> str:
    focus_target = str(payload.get("current_focus_target", "") or "")
    source = str(payload.get("current_attention_source", "") or "")
    if focus_target != "":
        return f"{actor_id} 当前将 {focus_target} 视为关注焦点，来源是 {source or 'unknown'}。"
    privacy_band = payload.get("privacy_band")
    nearby_actor_refs = payload.get("nearby_actor_refs", [])
    current_zone_id = str(payload.get("current_zone_id", "") or "")
    if privacy_band:
        return f"{actor_id} 当前的隐私判断是 {privacy_band}。"
    if nearby_actor_refs:
        return f"{actor_id} 当前最近邻近角色是 {nearby_actor_refs[0]}。"
    if current_zone_id != "":
        return f"{actor_id} 当前所在区域是 {current_zone_id}。"
    return f"{actor_id} 的当前理解已更新。"


def summarize_character_candidate(actor_id: str, payload: dict[str, Any]) -> str:
    actor_ids = [str(v) for v in payload.get("candidate_actor_ids", [])]
    object_ids = [str(v) for v in payload.get("candidate_object_ids", [])]
    environment_ids = [str(v) for v in payload.get("candidate_environment_ids", [])]
    target = actor_ids[0] if actor_ids else object_ids[0] if object_ids else environment_ids[0] if environment_ids else actor_id
    return f"{actor_id} 当前形成了一个新候选：注意 {target}。"


def summarize_character_output(actor_id: str, output_type: str, payload: dict[str, Any]) -> str:
    if output_type == "dialogue_response":
        return f"{actor_id} 最终输出了一条对话回应。"
    return f"{actor_id} 最终输出了 {output_type}。"


def summarize_world_result(payload: dict[str, Any]) -> str:
    result_type = str(payload.get("result_type", "world_result"))
    if result_type == "object_interaction_result":
        return f"系统确认 {payload.get('target_object_id', 'object')} 交互成功。"
    if result_type == "constraint_state_result":
        return f"系统拒绝了这次交互，原因是 {payload.get('constraint_type', '约束不满足')}。"
    if result_type == "environment_state_result":
        return f"环境状态发生变化：{payload.get('target_environment_id', 'environment')} 现在是 {payload.get('current_state', 'unknown')}。"
    return f"系统产生了一条 {result_type}。"


def summarize_siming_output(payload: dict[str, Any]) -> str:
    output_type = str(payload.get("output_type", "siming_output"))
    if output_type == "attention_prompt":
        target = payload.get("target_object_id") or payload.get("target_environment_id") or payload.get("target_actor_id") or "目标"
        return f"司命生成了一条 attention prompt，目标是 {target}。"
    return f"司命输出了一条 {output_type}。"
