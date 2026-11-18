"""司命环境请求桥接：仅接收 ESM 结算，不自行建立环境真值。"""
from app.models.authority_event import AuthorityEvent
from app.models.environment_request import EnvironmentRequest
from app.models.world_result import ActionResolutionResult, ConstraintStateResult, EnvironmentStateResult


class SimingEnvironmentProtocol:
    def resolve(self, event: AuthorityEvent, *, esm, now_ts: int | None = None):
        payload = event.payload
        target = payload.get('target_environment_id')
        target = target if isinstance(target, str) and target.strip() else None
        request = EnvironmentRequest(
            request_id=event.event_id, candidate_ref=str(payload.get('candidate_ref', '')),
            decision_ref=str(payload.get('decision_ref', '')), room_id=event.room_id,
            scene_id=event.scene_id, zone_id=event.zone_id,
            source={'layer': 'L2', 'system': 'siming', 'event_id': event.event_id},
            target_entity_refs={'environment_ids': [target] if isinstance(target, str) and target else []},
            goal=str(payload.get('goal') or 'environment_change'),
            requested_change_type=str(payload.get('requested_change_type') or 'light_level_drop'),
            requested_strength=str(payload.get('requested_strength') or 'medium'),
            ttl=event.ttl, reason_tag='siming_environment_request', producer_ts=event.producer_ts,
            causation_id=event.causation_id, correlation_id=event.correlation_id,
        )
        reason = None
        if event.event_type != 'siming.environment_request' or event.source.layer != 'L2' or not event.source.system.startswith('siming'):
            reason = 'invalid_environment_source'
        elif not request.target_entity_refs['environment_ids']:
            reason = 'missing_environment_target'
        elif event.ttl is not None and (event.ttl <= 0 or (now_ts is not None and now_ts > event.producer_ts + event.ttl)):
            reason = 'expired_ttl'
        elif event.ttl is not None and now_ts is None:
            # Godot 使用启动后毫秒，不能与 Unix 时钟比较。
            reason = 'ttl_clock_unavailable'
        if reason is None:
            try:
                resolution, state = esm.resolve_environment_request(request)
            except (TimeoutError, RuntimeError, ValueError):
                reason = 'esm_unavailable'
            else:
                if self._valid_results(request, resolution, state):
                    return request, resolution, state
                reason = 'invalid_environment_result'
        # 协议失败只回报约束；不伪造 accepted，不自动升级或重发物理请求。
        return request, ConstraintStateResult(
            request_ref=request.request_id, result_id=f'constraint:{request.request_id}',
            room_id=request.room_id, scene_id=request.scene_id, zone_id=request.zone_id,
            source_type='system', entity_id=target or '', target_environment_id=target or None,
            causation_id=request.causation_id, correlation_id=request.correlation_id,
            producer_ts=request.producer_ts + 1, constraint_type='siming_environment_protocol',
            constraint_code=reason, constraint_summary=reason, blocking_entity_refs=[target] if target else [],
            settlement_status='rejected',
        ), None

    @staticmethod
    def _valid_results(request, resolution, state) -> bool:
        target = request.target_entity_refs['environment_ids'][0]
        def matches(result):
            return (result.request_ref == request.request_id and result.room_id == request.room_id
                and result.scene_id == request.scene_id and result.zone_id == request.zone_id
                and result.causation_id == request.causation_id and result.correlation_id == request.correlation_id
                and result.target_environment_id == target and bool(result.result_id)
                and result.producer_ts >= request.producer_ts)
        if not isinstance(resolution, (ActionResolutionResult, ConstraintStateResult)) or not matches(resolution):
            return False
        if isinstance(resolution, ConstraintStateResult):
            return (resolution.result_type == 'constraint_state_result'
                and state is None and resolution.settlement_status == 'rejected')
        if resolution.result_type != 'action_resolution_result':
            return False
        if resolution.resolution_status != 'accepted':
            return state is None and resolution.resolution_status in {'rejected', 'failed'}
        return (resolution.settlement_status == 'accepted' and target in resolution.resolved_entities
            and isinstance(state, EnvironmentStateResult) and state.result_type == 'environment_state_result'
            and matches(state)
            and state.producer_ts >= resolution.producer_ts and bool(state.current_state))
