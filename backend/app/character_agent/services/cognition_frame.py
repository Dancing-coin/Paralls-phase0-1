"""认知阶段的三个不可变大字段；引用随原进度提交，正文不在阶段间复制。"""
import hashlib
import json


ORIGINS = {'context': {'l2'}, 'l3_prepared': {'l3', 'suggestion'}, 'suggestion_context': {'suggestion'}}


def receipt_key(ref):
    return f"{ref['child_key']}/frozen:{ref['origin_stage']}:{ref['field']}"


def frame_references(frame, *, actor_id, child_key):
    if not isinstance(frame, dict):
        raise ValueError('cognition_frame_reference_invalid')
    for field, origins in ORIGINS.items():
        name = field + '_ref'
        if name not in frame:
            continue
        ref = frame[name]
        if (field in frame or frame.get('actor_id') != actor_id or frame.get('child_key') != child_key
                or not isinstance(ref, dict)
                or set(ref) != {'actor_id', 'child_key', 'origin_stage', 'field', 'digest'}
                or ref.get('actor_id') != actor_id or ref.get('child_key') != child_key
                or not isinstance(ref.get('origin_stage'), str)
                or ref.get('origin_stage') not in origins or ref.get('field') != field
                or not isinstance(ref.get('digest'), str)):
            raise ValueError('cognition_frame_reference_invalid')
        yield ref


def validate_frame(store, frame, *, actor_id, child_key, checked=None):
    checked = set() if checked is None else checked
    for ref in frame_references(frame, actor_id=actor_id, child_key=child_key):
        key = receipt_key(ref)
        identity = actor_id, key, ref['digest']
        if identity in checked:
            continue
        raw = store.read_receipt_json(actor_id, kind='cognition_frame', key=key)
        if raw is None or hashlib.sha256(raw.encode('utf-8')).hexdigest() != ref['digest']:
            raise ValueError('cognition_frame_payload_missing_or_changed')
        checked.add(identity)


def freeze_fields(store, frame, *, actor_id, child_key, origin_stage, fields):
    # 调用者的 session transaction 同时保存正文和首次引用，失败不能留下孤儿 receipt。
    result = dict(frame, child_key=child_key)
    for field, value in fields.items():
        if field not in ORIGINS or origin_stage not in ORIGINS[field] or frame.get('actor_id') != actor_id:
            raise ValueError('cognition_frame_reference_invalid')
        receipt = json.loads(json.dumps(dict(actor_id=actor_id, child_key=child_key,
            origin_stage=origin_stage, field=field, value=value), ensure_ascii=False, sort_keys=True, allow_nan=False))
        ref = dict(actor_id=actor_id, child_key=child_key, origin_stage=origin_stage, field=field,
            digest=hashlib.sha256(store._json(receipt).encode('utf-8')).hexdigest())
        store.save_receipt(actor_id, kind='cognition_frame', key=receipt_key(ref), receipt=receipt)
        result.pop(field, None)
        result[field + '_ref'] = ref
    return result


def read_field(store, frame, field):
    if field not in ORIGINS:
        raise ValueError('cognition_frame_field_invalid')
    if field + '_ref' not in frame:
        return frame[field]
    ref, = frame_references({key: value for key, value in frame.items()
        if key in {'actor_id', 'child_key', field, field + '_ref'}},
        actor_id=frame['actor_id'], child_key=frame.get('child_key'))
    raw = store.read_receipt_json(frame['actor_id'], kind='cognition_frame', key=receipt_key(ref))
    if raw is None or hashlib.sha256(raw.encode('utf-8')).hexdigest() != ref['digest']:
        raise ValueError('cognition_frame_payload_missing_or_changed')
    receipt = json.loads(raw)
    if any(receipt.get(key) != ref[key] for key in ('actor_id', 'child_key', 'origin_stage', 'field')):
        raise ValueError('cognition_frame_reference_invalid')
    return receipt['value']
