"""完整 ASK 审计流：逐项校验原语义，散列每个逻辑字节而非来源指针。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.character_agent.reasoning.actor_scene_knowledge import (
    ActorSceneKnowledgeEntry, ActorSceneKnowledgeConflict, ActorSceneKnowledgeRevision,
)
from app.character_agent.storage.session_store import CharacterAgentSessionStore
from app.character_agent.storage.ask_storage import SOURCES, HISTORY


FORMAT = 'ask-complete-audit-v1'


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def file_hash(path: Path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return 'sha256:' + result.hexdigest()


def write_audit(store, actor_id: str, path: Path):
    with path.open('wb') as stream:
        stream.write(encoded(dict(format=FORMAT, actor_id=actor_id)) + b'\n')
        for record in store.iter_ask_audit(actor_id):
            stream.write(encoded(record) + b'\n')
        stream.write(encoded(dict(kind='end')) + b'\n')
    return verify_audit(path, actor_id)


def verify_audit(path: Path, actor_id: str):
    with path.open('r', encoding='utf-8') as stream:
        def unique_object(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError('ask_audit_duplicate_key')
                value[key] = item
            return value
        def read():
            line = stream.readline()
            if not line:
                raise ValueError('ask_audit_truncated')
            value = json.loads(line, object_pairs_hook=unique_object, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('ask_audit_nonfinite')))
            if not isinstance(value, dict):
                raise ValueError('ask_audit_record_invalid')
            return value
        if read() != dict(format=FORMAT, actor_id=actor_id):
            raise ValueError('ask_audit_identity_invalid')
        logical = hashlib.sha256()
        logical.update(b'[')
        totals = dict(entries=0, source_refs=0, source_ref_lineage=0, conflicts=0, revisions=0)
        keys = set()
        record = read()
        while record != dict(kind='end'):
            index = totals['entries']
            if set(record) != {'kind','ordinal','entry_key','value'} or record['kind'] != 'head' or type(record['ordinal']) is not int or record['ordinal'] != index:
                raise ValueError('ask_audit_head_order_invalid')
            key, head = record['entry_key'], dict(record['value'])
            counts = head.pop('_counts')
            if key in keys or set(counts) != {*SOURCES, *HISTORY, 'unresolved'} or any(type(value) is not int or value < 0 for value in counts.values()):
                raise ValueError('ask_audit_counts_invalid')
            keys.add(key)
            def part(kind, ordinal):
                item = read()
                if set(item) != {'kind','ordinal','entry_key','value'} or item['kind'] != kind or item['entry_key'] != key or type(item['ordinal']) is not int or item['ordinal'] != ordinal:
                    raise ValueError('ask_audit_part_order_invalid')
                return item['value']
            sources = {}
            for kind in SOURCES:
                sources[kind] = [part(kind, ordinal) for ordinal in range(counts[kind])]
                if any(type(value) is not str for value in sources[kind]):
                    raise ValueError('ask_audit_source_invalid')
                totals[kind] += counts[kind]
            source_bytes = {}
            for name, values in sources.items():
                offsets, chunks, size = [0], [], 0
                for ordinal, value in enumerate(values):
                    chunk = (b',' if ordinal else b'') + encoded(value)
                    chunks.append(chunk)
                    size += len(chunk)
                    offsets.append(size)
                source_bytes[name] = (memoryview(b''.join(chunks)), offsets)
            current = {**head, **sources, 'conflicts': [], 'revisions': []}
            validated = ActorSceneKnowledgeEntry.model_validate(current).model_dump(mode='json')
            if validated['actor_id'] != actor_id or CharacterAgentSessionStore.ask_key(validated) != key:
                raise ValueError('ask_audit_head_invalid')
            current = validated
            if index:
                logical.update(b',')
            logical.update(b'{')
            unresolved = 0
            for field_index, name in enumerate(sorted(current)):
                if field_index:
                    logical.update(b',')
                logical.update(encoded(name) + b':')
                if name not in HISTORY:
                    logical.update(encoded(current[name]))
                    continue
                logical.update(b'[')
                model = ActorSceneKnowledgeConflict if name == 'conflicts' else ActorSceneKnowledgeRevision
                for ordinal in range(counts[name]):
                    packed = part(name, ordinal)
                    value = dict(packed)
                    for source_name in SOURCES:
                        if source_name not in packed:
                            continue
                        reference = packed[source_name]
                        if (not isinstance(reference, dict) or set(reference) != {'prefix','suffix'}
                                or type(reference['prefix']) is not int or not 0 <= reference['prefix'] <= len(sources[source_name])
                                or not isinstance(reference['suffix'], list) or any(type(ref) is not str for ref in reference['suffix'])):
                            raise ValueError('ask_audit_prefix_invalid')
                        value[source_name] = reference['suffix']
                    # 前缀元素已逐项验过字符串；此处验证本条全部标量及新增后缀。
                    normalized = model.model_validate(value).model_dump(mode='json')
                    value = normalized
                    if name == 'conflicts':
                        unresolved += not value['resolved']
                    if ordinal:
                        logical.update(b',')
                    logical.update(b'{')
                    for item_index, field in enumerate(sorted(value)):
                        if item_index:
                            logical.update(b',')
                        logical.update(encoded(field) + b':')
                        if field not in SOURCES:
                            logical.update(encoded(value[field]))
                            continue
                        reference = packed.get(field, {'prefix': 0, 'suffix': []})
                        prefix = reference['prefix']
                        base, offsets = source_bytes[field]
                        logical.update(b'[')
                        logical.update(base[:offsets[prefix]])
                        for suffix_index, ref in enumerate(reference['suffix']):
                            if prefix or suffix_index:
                                logical.update(b',')
                            logical.update(encoded(ref))
                        logical.update(b']')
                    logical.update(b'}')
                logical.update(b']')
                totals[name] += counts[name]
            logical.update(b'}')
            end = read()
            if unresolved != counts['unresolved'] or type(end.get('ordinal')) is not int or end != dict(kind='entry_end', ordinal=index, entry_key=key):
                raise ValueError('ask_audit_entry_end_invalid')
            totals['entries'] += 1
            record = read()
        if stream.read():
            raise ValueError('ask_audit_trailing_records')
        logical.update(b']')
    return dict(format=FORMAT, actor_id=actor_id, logical_digest='sha256:' + logical.hexdigest(), **totals)
