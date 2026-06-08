from __future__ import annotations

from typing import Any


ACTOR_LABELS = {
    "char_a": "CharacterA",
    "char_b": "CharacterB",
    "char_c": "CharacterC",
}

OBJECT_LABELS = {
    "obj_letter": "obj_letter",
}

ENVIRONMENT_LABELS = {
    "env_lamp": "env_lamp",
}

ATTENTION_SOURCE_LABELS = {
    "visual_fact": "视觉事实",
    "focus_state": "焦点状态",
    "world_result": "世界结果",
}


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


def label_actor(actor_id: str | None) -> str:
    if not actor_id:
        return "未知角色"
    return ACTOR_LABELS.get(actor_id, actor_id)


def label_object(object_id: str | None) -> str:
    if not object_id:
        return "未知对象"
    return OBJECT_LABELS.get(object_id, object_id)


def label_environment(environment_id: str | None) -> str:
    if not environment_id:
        return "未知环境"
    return ENVIRONMENT_LABELS.get(environment_id, environment_id)


def _pick_target_label(*, actor_id: str | None = None, object_id: str | None = None, environment_id: str | None = None) -> str:
    if actor_id:
        return label_actor(actor_id)
    if object_id:
        return label_object(object_id)
    if environment_id:
        return label_environment(environment_id)
    return "目标"


def summarize_raw_fact_event(event: Any) -> str:
    source_label = label_actor(getattr(event.source, "actor_id", "") or "")
    if event.fact_family == "visual_fact":
        if event.fact_type == "fixed_gaze_on_target":
            if event.targets.actor_id:
                return f"{source_label} 正在看向 {label_actor(event.targets.actor_id)}。"
            if event.targets.object_id:
                return f"{source_label} 正在看向 {label_object(event.targets.object_id)}。"
        if event.fact_type == "spatial_relation" and event.relation_type == "actor_near_object":
            return f"{source_label} 已靠近 {label_object(event.targets.object_id)}，进入可交互观察范围。"
        if event.fact_type == "light_level_drop":
            return f"环境 {label_environment(event.targets.environment_id)} 的光照降低了。"

    if event.fact_family == "spatial_access_fact":
        if event.fact_type == "actor_entered_zone":
            return f"{source_label} 进入了 {event.zone_id}。"
        if event.fact_type == "actor_approached_actor":
            target_label = label_actor(event.targets.actor_id)
            if event.world.distance_m is not None:
                return f"{source_label} 正在接近 {target_label}，当前距离约 {event.world.distance_m:.1f} 米。"
            return f"{source_label} 正在接近 {target_label}。"
        if event.fact_type == "actor_left_actor_range":
            return f"{source_label} 不再接近当前关注的角色了。"
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
    return f"{label_actor(actor_id)} 收到了一个输入：{label}。"


def summarize_character_input_from_fact(event: Any) -> str:
    actor_label = label_actor(getattr(event.source, "actor_id", "") or "")
    if event.fact_family == "visual_fact":
        if event.fact_type == "fixed_gaze_on_target":
            target = _pick_target_label(
                actor_id=event.targets.actor_id,
                object_id=event.targets.object_id,
            )
            return f"{actor_label} 收到了一条视觉事实：当前视线落在 {target}。"
        if event.fact_type == "spatial_relation" and event.relation_type == "actor_near_object":
            return f"{actor_label} 收到了一条视觉事实：自己已靠近 {label_object(event.targets.object_id)}。"
        if event.fact_type == "light_level_drop":
            return f"{actor_label} 收到了一条视觉事实：{label_environment(event.targets.environment_id)} 的光照变暗了。"
    if event.fact_family == "spatial_access_fact":
        if event.fact_type == "actor_entered_zone":
            return f"{actor_label} 收到了一条空间接入事实：自己进入了 {event.zone_id}。"
        if event.fact_type == "actor_approached_actor":
            target = label_actor(event.targets.actor_id)
            if event.world.distance_m is not None:
                return f"{actor_label} 收到了一条空间接入事实：自己正在接近 {target}，距离约 {event.world.distance_m:.1f} 米。"
            return f"{actor_label} 收到了一条空间接入事实：自己正在接近 {target}。"
        if event.fact_type == "actor_left_actor_range":
            return f"{actor_label} 收到了一条空间接入事实：自己已离开当前近距角色范围。"
        if event.fact_type == "privacy_boundary_changed":
            return f"{actor_label} 收到了一条空间接入事实：当前隐私带变成了 {event.world.state_after or 'unknown'}。"
    return f"{actor_label} 收到了一条新事实。"


def summarize_character_input_from_candidate(event: Any) -> str:
    source_label = label_actor(getattr(event, "source_actor_id", "") or "")
    target_label = _pick_target_label(
        actor_id=getattr(event, "target_actor_id", "") or "",
        object_id=getattr(event, "target_object_id", "") or "",
        environment_id=getattr(event, "target_environment_id", "") or "",
    )
    return f"{source_label} 的事实已进入候选感知层，当前候选目标是 {target_label}。"


def summarize_character_input_from_character_perceived(event: Any) -> str:
    actor_label = label_actor(getattr(event, "actor_id", "") or "")
    percept_channel = str(getattr(event, "percept_channel", "") or "unknown")
    return f"{actor_label} 收到了一条角色私有感知，通道是 {percept_channel}。"


def summarize_character_input_from_self_body_perceived(event: Any) -> str:
    actor_label = label_actor(getattr(event, "actor_id", "") or "")
    body_state_class = str(getattr(event, "body_state_class", "") or "unknown")
    return f"{actor_label} 收到了一条自身身体感知，身体状态通道是 {body_state_class}。"


def summarize_character_input_from_world_result(actor_id: str, payload: dict[str, Any]) -> str:
    actor_label = label_actor(actor_id)
    result_type = str(payload.get("result_type", "") or "")
    if result_type == "action_resolution_result":
        return f"{actor_label} 收到了一条世界结果：{label_object(str(payload.get('target_object_id', '') or ''))} 交互结算已确认。"
    if result_type == "body_state_result":
        return f"{actor_label} 收到了一条世界结果：身体状态 {payload.get('body_state_class', 'unknown')} 现在是 {payload.get('current_state', 'unknown')}。"
    if result_type == "constraint_state_result":
        return f"{actor_label} 收到了一条世界结果：交互被拒绝，原因是 {payload.get('constraint_type', '约束不满足')}。"
    if result_type == "environment_state_result":
        return f"{actor_label} 收到了一条世界结果：{label_environment(str(payload.get('target_environment_id', '') or ''))} 变成了 {payload.get('current_state', 'unknown')}。"
    return f"{actor_label} 收到了一条新的世界结果。"


def summarize_character_input_from_siming_output(payload: dict[str, Any]) -> str:
    actor_label = label_actor(str(payload.get("target_actor_id", "") or ""))
    output_type = str(payload.get("output_type", "siming_output"))
    if output_type == "attention_prompt":
        object_id = str(payload.get("target_object_id", "") or "")
        environment_id = str(payload.get("target_environment_id", "") or "")
        actor_id = str(payload.get("target_actor_id", "") or "")
        if object_id:
            target = label_object(object_id)
        elif environment_id:
            target = label_environment(environment_id)
        else:
            target = label_actor(actor_id)
        return f"{actor_label} 收到了一条司命提示：注意 {target}。"
    return f"{actor_label} 收到了一条司命输出：{output_type}。"


def summarize_character_interpretation(actor_id: str, payload: dict[str, Any]) -> str:
    actor_label = label_actor(actor_id)
    focus_target = str(payload.get("current_focus_target", "") or "")
    source = str(payload.get("current_attention_source", "") or "")
    if focus_target != "":
        source_label = ATTENTION_SOURCE_LABELS.get(source, source or "unknown")
        if focus_target in ACTOR_LABELS:
            return f"{actor_label} 当前把 {label_actor(focus_target)} 视为关注焦点，来源是 {source_label}。"
        if focus_target in ENVIRONMENT_LABELS:
            return f"{actor_label} 当前把 {label_environment(focus_target)} 视为关注焦点，来源是 {source_label}。"
        return f"{actor_label} 当前把 {label_object(focus_target)} 视为关注焦点，来源是 {source_label}。"
    privacy_band = payload.get("privacy_band")
    nearby_actor_refs = payload.get("nearby_actor_refs", [])
    current_zone_id = str(payload.get("current_zone_id", "") or "")
    if privacy_band:
        return f"{actor_label} 当前的隐私判断是 {privacy_band}。"
    if nearby_actor_refs:
        return f"{actor_label} 当前最近邻近角色是 {label_actor(str(nearby_actor_refs[0]))}。"
    if current_zone_id != "":
        return f"{actor_label} 当前所在区域是 {current_zone_id}。"
    return f"{actor_label} 的当前理解已更新。"


def summarize_character_candidate(actor_id: str, payload: dict[str, Any]) -> str:
    actor_label = label_actor(actor_id)
    actor_ids = [str(v) for v in payload.get("candidate_actor_ids", [])]
    object_ids = [str(v) for v in payload.get("candidate_object_ids", [])]
    environment_ids = [str(v) for v in payload.get("candidate_environment_ids", [])]
    target = _pick_target_label(
        actor_id=actor_ids[0] if actor_ids else None,
        object_id=object_ids[0] if object_ids else None,
        environment_id=environment_ids[0] if environment_ids else None,
    )
    pressure = str(payload.get("engagement_pressure", "") or "")
    if pressure == "elevated":
        return f"{actor_label} 当前形成了一个新候选：优先注意 {target}。"
    return f"{actor_label} 当前形成了一个新候选：注意 {target}。"


def summarize_character_output(actor_id: str, output_type: str, payload: dict[str, Any]) -> str:
    actor_label = label_actor(actor_id)
    if output_type == "dialogue_response":
        target = label_actor(str(payload.get("target_actor_id", "")))
        content = str(payload.get("content", "") or "")
        tone = str(payload.get("tone", "") or "")
        if content and tone:
            return f"{actor_label} 最终向 {target} 给出了一条{tone}回应：“{content}”"
        if content:
            return f"{actor_label} 最终输出了一条对话回应：“{content}”"
        return f"{actor_label} 最终输出了一条对话回应。"
    return f"{actor_label} 最终输出了 {output_type}。"


def summarize_world_result(payload: dict[str, Any]) -> str:
    result_type = str(payload.get("result_type", "world_result"))
    if result_type == "action_resolution_result":
        return f"系统完成了 {label_object(str(payload.get('target_object_id', '')))} 的动作结算。"
    if result_type == "object_state_result":
        return f"对象状态发生变化：{label_object(str(payload.get('target_object_id', '')))} 现在是 {payload.get('current_state', 'unknown')}。"
    if result_type == "body_state_result":
        return f"身体状态发生变化：{label_actor(str(payload.get('actor_id', '')))} 的 {payload.get('body_state_class', 'unknown')} 现在是 {payload.get('current_state', 'unknown')}。"
    if result_type == "constraint_state_result":
        return f"系统拒绝了这次交互，原因是 {payload.get('constraint_type', '约束不满足')}。"
    if result_type == "environment_state_result":
        return f"环境状态发生变化：{label_environment(str(payload.get('target_environment_id', '')))} 现在是 {payload.get('current_state', 'unknown')}。"
    return f"系统产生了一条 {result_type}。"


def summarize_siming_output(payload: dict[str, Any]) -> str:
    output_type = str(payload.get("output_type", "siming_output"))
    if output_type == "attention_prompt":
        target = _pick_target_label(
            actor_id=str(payload.get("target_actor_id", "") or ""),
            object_id=str(payload.get("target_object_id", "") or ""),
            environment_id=str(payload.get("target_environment_id", "") or ""),
        )
        return f"司命生成了一条 attention prompt，目标是 {target}。"
    return f"司命输出了一条 {output_type}。"
