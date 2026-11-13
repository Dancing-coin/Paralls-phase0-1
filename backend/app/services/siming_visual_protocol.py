"""视觉输入的纯校验与镜像投影；来源索引随司命状态树提交。"""
from copy import deepcopy

from app.models.authority_event import AuthorityEvent


class SimingVisualFactProtocol:
    PRIMARY_TYPES = {'visual_character_fact', 'visual_object_fact', 'visual_environment_fact', 'visual_spatial_relation_fact'}
    LEGACY_TYPES = {'light_level_drop': 'visual_environment_fact', 'object_state_change': 'visual_object_fact'}
    FORBIDDEN_FIELDS = {'skeleton_transforms', 'face_pose_weights', 'role_belief_truth',
                        'psychology_truth', 'raw_pose', 'bone_transforms', 'au_weights'}

    @classmethod
    def project(cls, event: AuthorityEvent, previous=None) -> dict:
        scope = [event.room_id, event.scene_id, event.zone_id]
        prior = previous.environment.summary if previous is not None else {}
        sources = deepcopy(prior.get('visual_fact_sources', {})) if prior.get('visual_scope') == scope else {}
        if event.event_type != 'visual_fact_event':
            return {'visual_scope': scope, 'visual_fact_sources': sources} if sources else {}
        payload = event.payload
        kind = str(payload.get('fact_type') or '')
        if event.source.layer != 'L1' or cls._contains_raw(payload) or kind.lower().endswith(('sampleframe', 'poseframe')):
            raise ValueError('visual_protocol_rejected:raw_or_non_visual_input')
        visible = payload.get('visible_actor_ids', [])
        if not isinstance(visible, list) or any(not isinstance(actor, str) or not actor for actor in visible):
            raise ValueError('visual_protocol_rejected:invalid_visibility')
        visible = sorted(set(visible))
        observability = payload.get('observability', {})
        if not isinstance(observability, dict):
            raise ValueError('visual_protocol_rejected:invalid_observability')
        if event.ttl is not None and event.ttl <= 0:
            raise ValueError('visual_protocol_rejected:expired_source')
        if observability.get('occluded') is True:
            visible = []
        fact_id = str(payload.get('established_fact_id') or event.event_id)
        if kind == 'visual_evidence_projection':
            source_id = str(payload.get('source_visual_fact_event_id') or '')
            source = sources.get(source_id)
            if (source is None or source['producer_ts'] > event.producer_ts
                    or (source.get('ttl') is not None and event.producer_ts > source['producer_ts'] + source['ttl'])):
                raise ValueError('visual_protocol_rejected:source_missing_or_future')
            for field in ('target_actor_id', 'target_object_id', 'target_environment_id'):
                if payload.get(field) and payload[field] != source.get(field):
                    raise ValueError('visual_protocol_rejected:source_target_mismatch')
            fact_id = source['established_fact_id']
            visible = sorted(set(visible).intersection(source['visible_actor_ids']))
            refs = [source_id]
        else:
            if kind and kind not in cls.PRIMARY_TYPES and kind not in cls.LEGACY_TYPES:
                raise ValueError('visual_protocol_rejected:unsupported_fact_type')
            # 既有 L1 信封允许缺省类型；保留兼容标记，不冒充正式四类。
            category = kind if kind in cls.PRIMARY_TYPES else cls.LEGACY_TYPES.get(kind, 'legacy_visual_fact')
            record = {'category': category, 'producer_ts': event.producer_ts, 'ttl': event.ttl,
                'established_fact_id': fact_id, 'visible_actor_ids': visible,
                **{field: payload.get(field) for field in ('target_actor_id','target_object_id','target_environment_id')}}
            if event.event_id in sources and sources[event.event_id] != record:
                raise ValueError('visual_protocol_rejected:source_identity_conflict')
            sources[event.event_id] = record
            refs = []
        return {'visual_scope': scope, 'visual_fact_sources': sources, 'visible_actor_ids': visible,
                'established_fact_id': fact_id, 'visual_evidence_refs': refs}

    @classmethod
    def _contains_raw(cls, value) -> bool:
        if isinstance(value, dict):
            return bool(cls.FORBIDDEN_FIELDS.intersection(value)) or any(cls._contains_raw(item) for item in value.values())
        return isinstance(value, (list, tuple)) and any(cls._contains_raw(item) for item in value)
