"""ASK 的有序持久历史；来源引用使用当前序列的冻结前缀与原样后缀。"""
from dataclasses import dataclass
import json


SOURCES = ('source_refs', 'source_ref_lineage')
HISTORY = ('conflicts', 'revisions')


@dataclass(frozen=True)
class AskAppend:
    entry: dict
    counts: dict


def create_table(db):
    db.execute('CREATE TABLE character_session_ask_parts (entry_key TEXT NOT NULL, kind TEXT NOT NULL, ordinal INTEGER NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY(entry_key,kind,ordinal))')


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True)


def pack(value, sources):
    result = dict(value)
    for name in SOURCES:
        if name not in result:
            continue
        refs = result.pop(name)
        base = sources[name]
        prefix = 0
        for left, right in zip(refs, base):
            if left != right:
                break
            prefix += 1
        result[name] = {'prefix': prefix, 'suffix': refs[prefix:]}
    return result


def unpack(value, sources):
    result = dict(value)
    for name in SOURCES:
        if name not in result:
            continue
        reference = result[name]
        prefix = reference['prefix']
        if type(prefix) is not int or not 0 <= prefix <= len(sources[name]):
            raise ValueError('ask_source_prefix_invalid')
        result[name] = [*sources[name][:prefix], *reference['suffix']]
    return result


def parts(db, key, kind, count):
    rows = db.execute('SELECT ordinal,payload_json FROM character_session_ask_parts WHERE entry_key=? AND kind=? ORDER BY ordinal', (key, kind))
    values = []
    for ordinal, payload in rows:
        if ordinal != len(values):
            raise ValueError('ask_history_order_invalid')
        values.append(json.loads(payload))
    if len(values) != count:
        raise ValueError('ask_history_count_invalid')
    return values


def read(db, key, payload, *, history=True):
    head = json.loads(payload)
    counts = head.pop('_counts')
    for name in SOURCES:
        head[name] = parts(db, key, name, counts[name])
    for name in HISTORY:
        head[name] = [unpack(item, head) for item in parts(db, key, name, counts[name])] if history else []
    return head, counts


def write(db, key, value, *, previous=None):
    """全量写重建原顺序；增量写仅追加，前缀身份不随 head 增长变化。"""
    counts = {name: len(value[name]) for name in (*SOURCES, *HISTORY)}
    counts['unresolved'] = sum(not item['resolved'] for item in value['conflicts'])
    if previous is None:
        db.execute('DELETE FROM character_session_ask_parts WHERE entry_key=?', (key,))
    else:
        row = db.execute('SELECT payload_json FROM character_session_ask WHERE entry_key=?', (key,)).fetchone()
        actual = json.loads(row[0])['_counts'] if row else None
        if actual != previous:
            raise ValueError('ask_append_head_changed')
        for name in HISTORY:
            counts[name] += previous[name]
        counts['unresolved'] += previous['unresolved']
    for name in (*SOURCES, *HISTORY):
        start = previous[name] if previous else 0
        items = value[name][start:] if name in SOURCES else value[name]
        if previous and name in SOURCES and len(value[name]) < start:
            raise ValueError('ask_source_prefix_changed')
        db.executemany('INSERT INTO character_session_ask_parts VALUES (?,?,?,?)',
                       ((key, name, start + offset, encode(pack(item, value) if name in HISTORY else item)) for offset, item in enumerate(items)))
    head = {name: item for name, item in value.items() if name not in (*SOURCES, *HISTORY)}
    head['_counts'] = counts
    db.execute('INSERT INTO character_session_ask VALUES (?,?,?,?) ON CONFLICT(entry_key) DO UPDATE SET payload_json=excluded.payload_json',
               (value['entry_id'], value['actor_id'], key, encode(head)))
