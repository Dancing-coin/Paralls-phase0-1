from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import sqlite3
from copy import deepcopy
from contextlib import contextmanager
from threading import RLock
from uuid import uuid4

from . import ask_storage


class CharacterAgentSessionStore:
    def __init__(
        self,
        storage_root: str | Path | None = None,
        *,
        database_path: str | Path | None = None,
    ) -> None:
        self._lock = RLock()
        self._runtime_id = uuid4().hex
        self._events_by_actor: dict[str, list[dict[str, object]]] = {}
        self._storage_path: Path | None = None
        self._actors_root: Path | None = None
        self._connection: sqlite3.Connection | None = None
        self._closed = False
        self._database_path = str(database_path) if database_path is not None else None
        self._migration_marker: Path | None = None
        self._recovery_enabled = False
        self._recovery: dict[str, dict[str, object]] = {}
        self._receipts: dict[tuple[str, str, str], tuple[dict, str | None]] = {}
        self._candidates: dict[tuple[str, str], dict] = {}
        self._projection_cursors: dict[tuple[str, str], int] = {}
        self._ask_entries: dict[str, dict] = {}
        self._ask_trace: list[dict] = []
        if storage_root is not None:
            root = Path(storage_root)
            root.mkdir(parents=True, exist_ok=True)
            self._storage_path = root / "character_agent_session_store.json"
            self._actors_root = root / "character_agent_session_store" / "actors"
            self._migration_marker = root / 'character_sessions.migrated'
            if database_path is None:
                database_path = root / "character_sessions.sqlite3"
        if database_path is not None:
            self._database_path = str(Path(database_path).resolve()) if str(database_path) != ':memory:' else ':memory:'
            if self._migration_marker is not None and self._migration_marker.exists() and str(database_path) != ':memory:':
                migrated_path = self._migration_marker.read_text(encoding='utf-8')
                if migrated_path == self._database_path and not Path(database_path).exists():
                    raise ValueError('character_session_committed_archive_missing')
            if str(database_path) != ":memory:":
                Path(database_path).parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(str(database_path), check_same_thread=False)
            try:
                self._connection.execute("PRAGMA journal_mode=WAL")
                self._initialize_database()
                marker = self._connection.execute("SELECT value FROM character_session_metadata WHERE key='recovery_version'").fetchone()
                if marker is not None:
                    if marker[0] not in {'1', '2'}:
                        raise ValueError("character_session_recovery_schema_unsupported")
                    required_tables = {
                        'character_session_recovery': {'actor_id','state_json'},
                        'character_session_receipts': {'actor_id','kind','receipt_key','receipt_json','event_id'},
                        'character_session_candidates': {'actor_id','candidate_id','dedup_key','payload_json'},
                        'character_session_projection_cursors': {'actor_id','kind','event_index'},
                        'character_session_ask': {'entry_id','actor_id','entry_key','payload_json'},
                        'character_session_ask_trace': {'sequence','payload_json'},
                    }
                    for name,columns in required_tables.items():
                        if {row[1] for row in self._connection.execute(f'PRAGMA table_info({name})')} != columns:
                            raise ValueError('character_session_recovery_schema_unsupported')
                    if marker[0] == '1':
                        with self.transaction():
                            ask_storage.create_table(self._connection)
                            for (key,) in self._connection.execute('SELECT entry_key FROM character_session_ask ORDER BY rowid').fetchall():
                                payload = self._connection.execute('SELECT payload_json FROM character_session_ask WHERE entry_key=?', (key,)).fetchone()[0]
                                original = json.loads(payload)
                                ask_storage.write(self._connection, key, original)
                                saved = self._connection.execute('SELECT payload_json FROM character_session_ask WHERE entry_key=?', (key,)).fetchone()[0]
                                if ask_storage.read(self._connection, key, saved)[0] != original:
                                    raise ValueError('ask_history_migration_mismatch')
                            self._connection.execute("UPDATE character_session_metadata SET value='2' WHERE key='recovery_version'")
                    if {row[1] for row in self._connection.execute('PRAGMA table_info(character_session_ask_parts)')} != {'entry_key','kind','ordinal','payload_json'}:
                        raise ValueError('character_session_recovery_schema_unsupported')
                    self._recovery_enabled = True
                if self._migration_marker is not None and str(database_path) != ':memory:':
                    temporary = self._migration_marker.with_suffix(f'.{uuid4().hex}.tmp')
                    temporary.write_text(self._database_path, encoding='utf-8')
                    os.replace(temporary,self._migration_marker)
            except BaseException:
                self._connection.close()
                self._connection = None
                raise

    def _initialize_database(self) -> None:
        db = self._connection
        assert db is not None
        db.execute("BEGIN IMMEDIATE")
        try:
            db.execute("CREATE TABLE IF NOT EXISTS character_session_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            version = db.execute("SELECT value FROM character_session_metadata WHERE key='schema_version'").fetchone()
            if version is not None:
                if version[0] not in {"1", "2"}:
                    raise ValueError("character_session_schema_unsupported")
                if version[0] == "1":
                    # 旧 SQL 库原地放宽为 actor 内唯一，事件、head 和版本升级同事务提交。
                    db.execute("ALTER TABLE character_session_events RENAME TO character_session_events_v1")
                    db.execute("DROP INDEX character_session_event_types")
                    self._create_events_table(db)
                    db.execute("INSERT INTO character_session_events SELECT * FROM character_session_events_v1")
                    db.execute("DROP TABLE character_session_events_v1")
                    db.execute("UPDATE character_session_metadata SET value='2' WHERE key='schema_version'")
                db.commit()
                return
            if self._migration_marker is not None and self._migration_marker.exists() and self._migration_marker.read_text(encoding='utf-8') == self._database_path:
                raise ValueError('character_session_committed_archive_missing')
            if self._import_previous_database(db):
                db.commit()
                return
            # 搬迁后的 marker 路径会变，但已切换的事实库缺档仍须拒绝旧 JSON 回退。
            if self._migration_marker is not None and self._migration_marker.exists():
                raise ValueError('character_session_committed_archive_missing')
            self._create_events_table(db)
            db.execute("CREATE TABLE character_session_heads (actor_id TEXT PRIMARY KEY, event_count INTEGER NOT NULL CHECK(event_count>0), event_id TEXT NOT NULL)")
            # 旧 JSON/JSONL 只在切换事务内读取一次；失败时表、head 和版本一起回滚。
            self._load()
            for actor_id, events in self._events_by_actor.items():
                for event in events:
                    self._insert_event(db, event)
                if events:
                    db.execute("INSERT INTO character_session_heads VALUES (?,?,?)", (actor_id, len(events), events[-1]["event_id"]))
            db.execute("INSERT INTO character_session_metadata VALUES ('schema_version','2')")
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            self._events_by_actor.clear()

    def _import_previous_database(self, db: sqlite3.Connection) -> bool:
        if self._storage_path is None:
            return False
        source = self._storage_path.parent / 'character_sessions.sqlite3'
        if str(source.resolve()) == self._database_path or not source.exists():
            return False
        if self._migration_marker is not None and self._migration_marker.exists():
            recorded = Path(self._migration_marker.read_text(encoding='utf-8'))
            if recorded.name != source.name:
                raise ValueError('character_session_committed_archive_missing')
        previous = sqlite3.connect(source.resolve().as_uri()+'?mode=ro',uri=True)
        try:
            version = previous.execute("SELECT value FROM character_session_metadata WHERE key='schema_version'").fetchone()
            if version is None or version[0] not in {'1', '2'}:
                raise ValueError('character_session_schema_unsupported')
            # 迁移所有 session 表，保留非 event 当前态、冷索引与投影 cursor。
            tables = previous.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name LIKE 'character_session_%' ORDER BY name").fetchall()
            for name, ddl in tables:
                if not name.replace('_','').isalnum():
                    raise ValueError('character_session_schema_unsupported')
                if name == 'character_session_events' and version[0] == '1':
                    # 源库保持只读；目的库直接使用 actor 内唯一的现行表结构。
                    self._create_events_table(db)
                    for row in previous.execute(f'SELECT * FROM "{name}"'):
                        event = self._validate_event(json.loads(row[4]))
                        if tuple(event[k] for k in ('actor_id','event_index','event_id','event_type')) != row[:4]:
                            raise ValueError('character_session_event_index_mismatch')
                        self._insert_event(db,event)
                    continue
                if name != 'character_session_metadata':
                    db.execute(ddl)
                for row in previous.execute(f'SELECT * FROM "{name}"'):
                    db.execute(f'INSERT INTO "{name}" VALUES ('+','.join('?' for _ in row)+')',row)
            for name, ddl in previous.execute("SELECT name,sql FROM sqlite_master WHERE type='index' AND tbl_name LIKE 'character_session_%' AND sql IS NOT NULL"):
                if version[0] == '1' and name == 'character_session_event_types':
                    continue
                db.execute(ddl)
            # 旧独立库必须自洽，不能把缺行或不同 actor 的 payload 带入新权威。
            for actor_id,count,event_id in db.execute('SELECT actor_id,event_count,event_id FROM character_session_heads'):
                rows = []
                for indexed in db.execute('SELECT actor_id,event_index,event_id,event_type,payload_json FROM character_session_events WHERE actor_id=? ORDER BY event_index',(actor_id,)):
                    event = self._validate_event(json.loads(indexed[4]))
                    if tuple(event[k] for k in ('actor_id','event_index','event_id','event_type')) != indexed[:4]:
                        raise ValueError('character_session_event_index_mismatch')
                    rows.append(event)
                if len(rows)!=count or any(row['actor_id']!=actor_id or row['event_index']!=i for i,row in enumerate(rows,1)) or rows[-1]['event_id']!=event_id:
                    raise ValueError('character_session_projection_gap')
            if version[0] == '1':
                db.execute("UPDATE character_session_metadata SET value='2' WHERE key='schema_version'")
            return True
        finally:
            previous.close()

    @staticmethod
    def _create_events_table(db: sqlite3.Connection) -> None:
        db.execute("CREATE TABLE character_session_events (actor_id TEXT NOT NULL, event_index INTEGER NOT NULL CHECK(event_index>0), event_id TEXT NOT NULL, event_type TEXT NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY(actor_id,event_index), UNIQUE(actor_id,event_id))")
        db.execute("CREATE INDEX character_session_event_types ON character_session_events(actor_id,event_type,event_index)")

    @staticmethod
    def _insert_event(db: sqlite3.Connection, entry: dict[str, object]) -> None:
        db.execute(
            "INSERT INTO character_session_events VALUES (?,?,?,?,?)",
            (entry["actor_id"], entry["event_index"], entry["event_id"], entry["event_type"],
             json.dumps(entry, ensure_ascii=False, separators=(",", ":"), allow_nan=False)),
        )

    def close(self) -> None:
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None
            self._closed = True

    def _check_open(self) -> None:
        if self._closed:
            raise RuntimeError("character_session_store_closed")

    def append_event(
        self,
        actor_id: str,
        event_type: str,
        producer_ts: int,
        payload: dict[str, object],
        expected_revision: int | None = None,
    ) -> dict[str, object]:
        with self.transaction():
            current = self.event_count(actor_id)
            if expected_revision is not None and expected_revision != current:
                raise ValueError("character_revision_conflict")
            entry = self._make_event(actor_id, event_type, producer_ts, payload, current + 1)
            self._append_entry(entry)
            return entry

    def _append_entry(self, entry: dict) -> None:
        """调用方持有原 session transaction；阶段提交与普通 append 共用事实写入。"""
        actor_id = entry['actor_id']
        if self._connection is not None:
            self._insert_event(self._connection, entry)
            self._connection.execute(
                "INSERT INTO character_session_heads VALUES (?,?,?) ON CONFLICT(actor_id) DO UPDATE SET event_count=excluded.event_count,event_id=excluded.event_id",
                (actor_id, entry['event_index'], entry['event_id']),
            )
        if self._recovery_enabled:
            self._reduce_event(entry)
        if self._connection is None:
            self._events_by_actor.setdefault(actor_id, []).append(entry)

    def commit_cognition_stage(self, *, actor_id: str, key: str, expected_revision: int,
                               events: list[dict], before: dict, after: dict) -> dict:
        """只提交已冻结的 Character 阶段；原事件、恢复态与续接回执同事务落盘。"""
        receipt = self._cognition_stage_receipt(actor_id=actor_id, key=key, expected_revision=expected_revision,
            events=events, before=before, after=after)
        planned = receipt['events']
        with self.transaction():
            if not self._recovery_enabled or self._connection is None or not next((
                    row[2] for row in self._connection.execute('PRAGMA database_list') if row[1] == 'main'), ''):
                raise ValueError('cognition_stage_requires_durable_session')
            previous = self.read_receipt(actor_id, kind='cognition_stage', key=key)
            if previous is not None:
                if previous != receipt:
                    raise ValueError('cognition_stage_conflict')
                if any(self.read_event(actor_id, event_id=event['event_id']) != event for event in planned):
                    raise ValueError('cognition_stage_event_missing_or_conflicting')
                return previous
            if self.event_count(actor_id) != expected_revision:
                raise ValueError('character_revision_conflict')
            for entry in planned:
                self._append_entry(entry)
            self.save_receipt(actor_id, kind='cognition_stage', key=key, receipt=receipt)
            if planned:
                state = self.read_runtime_state(actor_id)
                state['cognition_stage'] = dict(key=key, input_digest=receipt['input_digest'],
                    start=expected_revision, end=expected_revision + len(planned))
                self._write_runtime_state(actor_id, state)
            return receipt

    def _cognition_stage_receipt(self, *, actor_id, key, expected_revision, events, before, after):
        # JSON 往返同时隔离输入，禁止把 generator/callback 塞进续接帧。
        plan = json.loads(self._json(dict(actor_id=actor_id, key=key, expected_revision=expected_revision,
            events=events, before=before, after=after)))
        if (type(actor_id) is not str or not actor_id or type(key) is not str or not key
                or type(expected_revision) is not int or expected_revision < 0
                or not isinstance(before, dict) or not isinstance(after, dict) or not isinstance(events, list)):
            raise ValueError('cognition_stage_invalid')
        planned = []
        for ordinal, value in enumerate(plan['events']):
            if set(value) != {'event_type', 'producer_ts', 'payload'}:
                raise ValueError('cognition_stage_event_invalid')
            entry = self._make_event(actor_id, value['event_type'], value['producer_ts'], value['payload'],
                expected_revision + ordinal + 1)
            entry['event_id'] = 'character-cognition-event:' + hashlib.sha256(
                self._json([actor_id, key, ordinal]).encode()).hexdigest()
            planned.append(entry)
        fingerprint = hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True,
            separators=(',', ':'), allow_nan=False).encode()).hexdigest()
        receipt = dict(schema_version=1, input_digest=fingerprint, plan=plan, events=planned)
        return receipt

    def read_cognition_stage_suffix(self, actor_id: str, *, after_index: int, through_index: int) -> tuple[dict, ...]:
        """只以 current 指向的原阶段回执证明多事件后缀；不扫描历史或放宽未知 gap。"""
        with self._lock:
            state = self.read_runtime_state(actor_id) or {}
            pointer = state.get('cognition_stage') or {}
            if (pointer.get('end') != through_index or type(pointer.get('start')) is not int
                    or not pointer['start'] <= after_index < through_index):
                raise ValueError('character_session_projection_rebuild_required')
            receipt = self._read_cognition_stage_proof(actor_id, pointer, through_index)
            events = tuple(event for event in receipt['events'] if event['event_index'] > after_index)
            if any(self.read_event(actor_id, event_id=event['event_id']) != event for event in events):
                raise ValueError('cognition_stage_event_missing_or_conflicting')
            return events

    def _read_cognition_stage_proof(self, actor_id: str, pointer: dict, through_index: int) -> dict:
        receipt = self.read_receipt(actor_id, kind='cognition_stage', key=pointer.get('key', ''))
        if receipt is None or receipt.get('input_digest') != pointer.get('input_digest'):
            raise ValueError('cognition_stage_projection_proof_invalid')
        expected = self._cognition_stage_receipt(**receipt['plan'])
        if (expected != receipt or receipt['plan']['actor_id'] != actor_id
                or receipt['plan']['key'] != pointer['key']
                or receipt['plan']['expected_revision'] != pointer['start']
                or len(receipt['events']) != through_index - pointer['start']):
            raise ValueError('cognition_stage_projection_proof_invalid')
        return receipt

    def read_current_cognition_stage(self, actor_id: str) -> dict | None:
        """启动时仅点读当前 head 的完整原阶段，不以旧阶段覆盖后续事件。"""
        with self._lock:
            pointer = (self.read_runtime_state(actor_id) or {}).get('cognition_stage')
            head = self.event_count(actor_id)
            if not pointer or pointer.get('end') != head:
                return None
            if type(pointer.get('start')) is not int or not 0 <= pointer['start'] <= head:
                raise ValueError('cognition_stage_projection_proof_invalid')
            receipt = self._read_cognition_stage_proof(actor_id, pointer, head)
            if any(self.read_event(actor_id, event_id=event['event_id']) != event for event in receipt['events']):
                raise ValueError('cognition_stage_event_missing_or_conflicting')
            return receipt

    @contextmanager
    def transaction(self):
        """ASK 投影和 cursor 共用事务；迁移内调用时沿用外层事务。"""
        with self._lock:
            self._check_open()
            db = self._connection
            owner = db is not None and not db.in_transaction
            if owner:
                db.execute("BEGIN IMMEDIATE")
            try:
                yield
                if owner:
                    db.commit()
            except BaseException:
                if owner:
                    db.rollback()
                raise

    def initialize_recovery(self, *, import_legacy=None, project_event=None) -> bool:
        """只在显式 schema 切换时重建；正常 reopen 不读取事件历史。"""
        with self.transaction():
            if self._recovery_enabled:
                if self._connection is None:
                    return False
                return self._connection.execute("SELECT 1 FROM character_session_metadata WHERE key='projection_migration_pending'").fetchone() is not None
            db = self._connection
            if db is not None:
                db.execute("CREATE TABLE character_session_recovery (actor_id TEXT PRIMARY KEY, state_json TEXT NOT NULL)")
                db.execute("CREATE TABLE character_session_receipts (actor_id TEXT NOT NULL, kind TEXT NOT NULL, receipt_key TEXT NOT NULL, receipt_json TEXT NOT NULL, event_id TEXT, PRIMARY KEY(actor_id,kind,receipt_key))")
                db.execute("CREATE TABLE character_session_candidates (actor_id TEXT NOT NULL, candidate_id TEXT NOT NULL, dedup_key TEXT NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY(actor_id,candidate_id))")
                db.execute("CREATE INDEX character_session_candidate_dedup ON character_session_candidates(actor_id,dedup_key)")
                db.execute("CREATE TABLE character_session_projection_cursors (actor_id TEXT NOT NULL, kind TEXT NOT NULL, event_index INTEGER NOT NULL, PRIMARY KEY(actor_id,kind))")
                db.execute("CREATE TABLE character_session_ask (entry_id TEXT NOT NULL, actor_id TEXT NOT NULL, entry_key TEXT PRIMARY KEY, payload_json TEXT NOT NULL)")
                db.execute("CREATE INDEX character_session_ask_actor ON character_session_ask(actor_id)")
                db.execute("CREATE INDEX character_session_ask_entry ON character_session_ask(entry_id)")
                ask_storage.create_table(db)
                db.execute("CREATE TABLE character_session_ask_trace (sequence INTEGER PRIMARY KEY, payload_json TEXT NOT NULL)")
            extras = import_legacy() if import_legacy is not None else {}
            for actor_id in self.actor_ids():
                for event in self.list_events(actor_id):
                    self._reduce_event(event)
                    if project_event is not None:
                        project_event(event)
                self.set_projection_cursor(actor_id, 'ask', self.event_count(actor_id))
                self.set_projection_cursor(actor_id, 'memory', 0)
                if extras and actor_id in extras:
                    state = self.read_runtime_state(actor_id)
                    state.update(extras[actor_id])
                    self._write_runtime_state(actor_id, state)
            if db is not None:
                db.execute("INSERT INTO character_session_metadata VALUES ('recovery_version','2')")
                db.execute("INSERT INTO character_session_metadata VALUES ('projection_migration_pending','1')")
        self._recovery_enabled = True
        return True

    def finish_recovery_migration(self) -> None:
        with self.transaction():
            if self._connection is not None:
                self._connection.execute("DELETE FROM character_session_metadata WHERE key='projection_migration_pending'")

    def import_timeline(self, actor_id: str, events: list[dict]) -> None:
        """仅由持有迁移事务的调用方使用；输入已与 canonical local 合并校验。"""
        normalized = self._normalize_event_sequence(events)
        if any(event['actor_id'] != actor_id for event in normalized):
            raise ValueError('session_event_actor_mismatch')
        if self._connection is None:
            self._events_by_actor[actor_id] = normalized
        else:
            self._connection.execute('DELETE FROM character_session_events WHERE actor_id=?',(actor_id,))
            for event in normalized:
                self._insert_event(self._connection,event)
            if normalized:
                self._connection.execute('INSERT INTO character_session_heads VALUES (?,?,?) ON CONFLICT(actor_id) DO UPDATE SET event_count=excluded.event_count,event_id=excluded.event_id',(actor_id,len(normalized),normalized[-1]['event_id']))

    def merge_legacy_continuity(self, actor_id: str, checkpoint: dict, current: dict) -> tuple[list[dict] | None, dict]:
        """旧 graph/local 只迁移一次，重复 ID 必须同 payload，索引必须连续。"""
        source_field = '_continuity_source_event_ref'
        local = self.list_events(actor_id)
        if current.get('schema_version') == 1 and 'event_index' in current:
            index = current['event_index']
            if type(index) is not int or index < 1:
                raise ValueError('character_session_committed_archive_missing')
            if index <= len(local) and local[index-1]['event_id'] == current.get(source_field):
                return None, {}
            archive = checkpoint.get('session_timeline', [])
            if not isinstance(archive,list) or index > len(archive) or archive[index-1].get('event_id') != current.get(source_field):
                raise ValueError('character_session_committed_archive_missing')
            current = {}
        def validate(events):
            if not isinstance(events,list):
                raise ValueError('character_continuity_timeline_invalid')
            normalized = [self._validate_event(event) for event in events]
            if any(e['actor_id'] != actor_id or e['event_index'] != i for i,e in enumerate(normalized,1)):
                raise ValueError('character_continuity_timeline_invalid')
            if len({e['event_id'] for e in normalized}) != len(normalized):
                raise ValueError('character_continuity_timeline_invalid')
            return normalized
        base = validate(checkpoint.get('session_timeline', []))
        anchors = {e['event_id']:e['event_index'] for e in base}
        anchor = anchors.get(checkpoint.get(source_field))
        checkpoint_cursor = checkpoint.get('checkpoint_event_index', anchor)
        if checkpoint and base and (anchor != len(base) or type(checkpoint_cursor) is not int or checkpoint_cursor != anchor):
            raise ValueError('character_continuity_anchor_invalid')
        if checkpoint and (anchor is None or type(checkpoint_cursor) is not int or checkpoint_cursor != anchor):
            checkpoint,base,anchor = {},[],0
        by_id = {e['event_id']:e for e in base}
        combined = list(base)
        tail = current.get('session_timeline_tail', [])
        if not isinstance(tail,list):
            raise ValueError('character_continuity_timeline_invalid')
        for raw in tail:
            event = self._validate_event(raw)
            prior = by_id.get(event['event_id'])
            if prior is not None:
                if prior != event:
                    raise ValueError('character_continuity_event_conflict')
            else:
                combined.append(event)
                by_id[event['event_id']] = event
        combined = validate(combined)
        current_anchor = next((e['event_index'] for e in combined if e['event_id']==current.get(source_field)), None)
        cursor = current.get('checkpoint_event_index')
        selected = checkpoint
        if current and current_anchor is None:
            raise ValueError('character_continuity_anchor_invalid')
        if current_anchor is not None and current_anchor != len(combined):
            raise ValueError('character_continuity_anchor_invalid')
        if current_anchor is not None:
            if type(cursor) is not int or not (anchor or 0) <= cursor <= current_anchor:
                raise ValueError('character_continuity_anchor_invalid')
            selected = {**checkpoint,**current}
            base = combined
            anchor = current_anchor
        # local 是同一事实流的完整前缀或扩展，不容许通过重编号掩盖分叉。
        for i in range(min(len(base),len(local))):
            if base[i] != local[i]:
                raise ValueError('character_continuity_event_conflict')
        merged = base if len(base)>len(local) else local
        extras = {}
        if selected:
            from app.character_agent.runtime.session_recovery import session_event_facts
            from app.character_agent.models.simulation_seed import CharacterContinuityReceipt, CharacterMemoryCandidate, CharacterMemoryMaterializationReceipt
            expected_receipts, expected_candidates = {}, {}
            for event in merged[:anchor]:
                receipts,candidates = session_event_facts(event)
                expected_receipts.update({(kind,key):value for kind,key,value in receipts})
                expected_candidates.update({value['candidate_id']:value for value in candidates})
            for kind,field,model in (('materialization','materialization_receipts',CharacterMemoryMaterializationReceipt),('continuity','continuity_receipts',CharacterContinuityReceipt)):
                values = selected.get(field,{})
                if not isinstance(values,dict):
                    raise ValueError('character_continuity_receipt_invalid')
                for key,raw in values.items():
                    receipt = model.model_validate(raw).model_dump(mode='json')
                    if receipt['actor_ref'].removeprefix('character:') != actor_id:
                        raise ValueError('character_continuity_commit_actor_mismatch')
                    if receipt['status'] == 'rejected' and (kind,key) not in expected_receipts:
                        self.save_receipt(actor_id,kind=kind,key=key,receipt=receipt)
                    elif expected_receipts.get((kind,key)) != receipt:
                        raise ValueError('character_continuity_receipt_conflict')
            candidates = selected.get('pending_seed_candidates',{})
            if not isinstance(candidates,dict):
                raise ValueError('character_continuity_candidate_invalid')
            for key,raw in candidates.items():
                if expected_candidates.get(key) != CharacterMemoryCandidate.model_validate(raw).model_dump(mode='json'):
                    raise ValueError('character_continuity_candidate_conflict')
        if selected and anchor == len(merged):
            extras = {key:deepcopy(selected[key]) for key in ('continuity_state','supervision_state','dynamic_state') if isinstance(selected.get(key),dict) and selected[key]}
            if any(value.get('actor_id',actor_id) != actor_id for value in extras.values()):
                raise ValueError('character_continuity_commit_actor_mismatch')
            if 'dynamic_state' in extras:
                from app.character_agent.storage.dynamic_state_store import CharacterDynamicStateStore
                normalizer = CharacterDynamicStateStore()
                normalizer.write(actor_id,extras['dynamic_state'])
                extras['dynamic_state'] = normalizer.read_record(actor_id).storage_dump()
            if 'supervision_state' in extras:
                from app.character_agent.models.supervision import CharacterSupervisionState
                extras['supervision_state'] = CharacterSupervisionState.model_validate(extras['supervision_state']).model_dump(mode='json')
            if 'continuity_state' in extras:
                from app.world_runtime.continuity import RuntimeContinuityState
                extras['continuity_state'] = RuntimeContinuityState.model_validate(extras['continuity_state']).model_dump(mode='json')
        return (merged if len(merged)>len(local) else None),extras

    def _reduce_event(self, event: dict[str, object]) -> None:
        from app.character_agent.runtime.session_recovery import reduce_session_event, session_event_facts
        actor_id = str(event['actor_id'])
        if event['event_index'] == 1:
            self.set_projection_cursor(actor_id,'memory',0)
            self.set_projection_cursor(actor_id,'ask',0)
        state = reduce_session_event(self.read_runtime_state(actor_id, validate=False), event)
        receipts, candidates = session_event_facts(event)
        for kind, key, receipt in receipts:
            self.save_receipt(actor_id, kind=kind, key=key, receipt=receipt, event_id=str(event['event_id']))
        for candidate in candidates:
            if self._connection is None:
                self._candidates[(actor_id, candidate['candidate_id'])] = deepcopy(candidate)
            else:
                self._connection.execute("INSERT INTO character_session_candidates VALUES (?,?,?,?) ON CONFLICT(actor_id,candidate_id) DO UPDATE SET dedup_key=excluded.dedup_key,payload_json=excluded.payload_json", (actor_id,candidate['candidate_id'],candidate['dedup_key'],self._json(candidate)))
        self._write_runtime_state(actor_id, state)

    @staticmethod
    def _json(value) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False)

    def _write_runtime_state(self, actor_id: str, state: dict) -> None:
        if self._connection is None:
            self._recovery[actor_id] = deepcopy(state)
        else:
            self._connection.execute("INSERT INTO character_session_recovery VALUES (?,?) ON CONFLICT(actor_id) DO UPDATE SET state_json=excluded.state_json", (actor_id,self._json(state)))

    def read_runtime_state(self, actor_id: str, *, validate: bool = True) -> dict | None:
        with self._lock:
            self._check_open()
            if self._connection is None:
                state = deepcopy(self._recovery.get(actor_id))
            else:
                row = self._connection.execute("SELECT state_json FROM character_session_recovery WHERE actor_id=?", (actor_id,)).fetchone()
                state = json.loads(row[0]) if row else None
            if validate:
                expected_event_id = None
                if self._connection is not None:
                    row = self._connection.execute('SELECT event_count,event_id FROM character_session_heads WHERE actor_id=?',(actor_id,)).fetchone()
                    count = row[0] if row else 0
                    expected_event_id = row[1] if row else None
                else:
                    count = self.event_count(actor_id)
                if state is None and count:
                    raise ValueError('character_session_recovery_missing')
                if state is not None:
                    if state.get('schema_version') != 1 or state.get('actor_id') != actor_id or state.get('event_index') != count:
                        raise ValueError('character_session_recovery_gap')
                    head = self.read_event(actor_id, event_index=count)
                    if head is None or head['actor_id'] != actor_id or head['event_index'] != count or head['event_id'] != state.get('event_id'):
                        raise ValueError('character_session_recovery_anchor_invalid')
                    if expected_event_id is not None and head['event_id'] != expected_event_id:
                        raise ValueError('character_session_recovery_anchor_invalid')
            return state

    def save_runtime_state(self, actor_id: str, *, expected_head: int, snapshot: dict, field_versions: dict | None = None) -> None:
        # 这些字段在原 flush 成功边界保存；绝不覆盖 event reducer 的当前态。
        allowed = {'continuity_state', 'supervision_state', 'dynamic_state'}
        if set(snapshot) - allowed:
            raise ValueError('character_session_runtime_fields_invalid')
        with self.transaction():
            if self.event_count(actor_id) != expected_head:
                raise ValueError('character_revision_conflict')
            state = self.read_runtime_state(actor_id)
            if state is None:
                return
            for field,value in snapshot.items():
                if field == 'continuity_state' or state.get('field_versions',{}).get(field,0) == (field_versions or {}).get(field,0):
                    state[field] = deepcopy(value)
            self._write_runtime_state(actor_id, state)

    def initialize_cognition_admissions(self) -> None:
        """原 receipt 保存入站事实；此表仅为点读与有界待办发现提供指针。"""
        with self.transaction():
            if not self._recovery_enabled:
                raise ValueError('character_session_recovery_required')
            db = self._connection
            if db is None or not next((row[2] for row in db.execute('PRAGMA database_list') if row[1] == 'main'), ''):
                # 空名称的 SQLite 临时库与 :memory: 一样会在关闭后消失，不能依据归一化路径判断。
                raise ValueError('cognition_admission_requires_durable_session')
            version = db.execute("SELECT value FROM character_session_metadata WHERE key='cognition_admission_version'").fetchone()
            base_columns = {'child_key', 'actor_id', 'admitted_at'}
            if version is None:
                db.execute('CREATE TABLE character_session_cognition_heads (child_key TEXT PRIMARY KEY, actor_id TEXT NOT NULL, admitted_at REAL NOT NULL)')
                db.execute("INSERT INTO character_session_metadata VALUES ('cognition_admission_version','1')")
                version = ('1',)
            columns = {row[1] for row in db.execute('PRAGMA table_info(character_session_cognition_heads)')}
            if version[0] == '1' and columns == base_columns:
                db.execute('ALTER TABLE character_session_cognition_heads ADD COLUMN stage_revision INTEGER NOT NULL DEFAULT 0 CHECK(stage_revision>=0)')
                db.execute('ALTER TABLE character_session_cognition_heads ADD COLUMN pending INTEGER NOT NULL DEFAULT 1 CHECK(pending IN (0,1))')
                db.execute('DROP INDEX IF EXISTS character_session_cognition_due')
                db.execute('CREATE INDEX character_session_cognition_due ON character_session_cognition_heads(pending,admitted_at,child_key)')
                db.execute("UPDATE character_session_metadata SET value='2' WHERE key='cognition_admission_version'")
            elif version[0] != '2' or columns != base_columns | {'stage_revision', 'pending'}:
                raise ValueError('character_cognition_schema_unsupported')

    def save_cognition_admission(self, entry: dict) -> None:
        with self.transaction():
            key, actor, admitted = entry['child_key'], entry['actor_id'], entry['admitted_at']
            previous = self.read_cognition_admission(key)
            if previous is not None:
                if previous != entry:
                    raise ValueError('character_session_receipt_conflict')
                return
            self.save_receipt(actor, kind='cognition_admission', key=key, receipt=entry)
            self._connection.execute('INSERT INTO character_session_cognition_heads(child_key,actor_id,admitted_at) VALUES (?,?,?)', (key, actor, admitted))

    def read_cognition_admission(self, key: str) -> dict | None:
        with self._lock:
            self._check_open()
            head = self._connection.execute('SELECT actor_id,admitted_at FROM character_session_cognition_heads WHERE child_key=?', (key,)).fetchone()
            if head is None:
                return None
            receipt = self.read_receipt(head[0], kind='cognition_admission', key=key)
            if receipt is None or (receipt.get('child_key'), receipt.get('actor_id'), receipt.get('admitted_at')) != (key, *head):
                raise ValueError('character_cognition_index_mismatch')
            return receipt

    def list_cognition_admissions(self, *, limit: int, cursor: tuple[float, str] | None = None) -> tuple[dict, ...]:
        if type(limit) is not int or not 1 <= limit <= 32:
            raise ValueError('character_cognition_page_limit')
        with self._lock:
            self._check_open()
            query = 'SELECT child_key FROM character_session_cognition_heads WHERE pending=1'
            params = ()
            if cursor is not None:
                query += ' AND (admitted_at,child_key)>(?,?)'
                params = cursor
            keys = [row[0] for row in self._connection.execute(query + ' ORDER BY admitted_at,child_key LIMIT ?', (*params, limit))]
            return tuple(self.read_cognition_admission(key) for key in keys)

    def read_cognition_progress(self, key: str, *, revision: int | None = None) -> dict | None:
        if revision is not None and (type(revision) is not int or revision < 0):
            raise ValueError('cognition_progress_revision_conflict')
        with self._lock:
            self._check_open()
            head = self._connection.execute('SELECT actor_id,stage_revision,pending FROM character_session_cognition_heads WHERE child_key=?', (key,)).fetchone()
            if head is None:
                return None
            target = head[1] if revision is None else revision
            if target == 0 or target > head[1]:
                return None
            receipt = self.read_receipt(head[0], kind='cognition_progress', key=f'{key}/progress:{target}')
            if (receipt is None or receipt.get('revision') != target or receipt.get('child_key') != key
                    or receipt.get('actor_id') != head[0]
                    or (target == head[1] and bool(head[2]) != (receipt.get('status') not in {'completed', 'stale'}))):
                raise ValueError('cognition_progress_index_mismatch')
            return receipt

    def save_cognition_progress(self, progress: dict, *, expected_revision: int) -> dict:
        with self.transaction():
            key, actor, revision = progress['child_key'], progress['actor_id'], progress['revision']
            previous = self.read_cognition_progress(key, revision=revision)
            if previous is not None:
                if previous != progress:
                    raise ValueError('cognition_progress_conflict')
                return previous
            head = self._connection.execute('SELECT actor_id,stage_revision FROM character_session_cognition_heads WHERE child_key=?', (key,)).fetchone()
            if head != (actor, expected_revision) or revision != expected_revision + 1:
                raise ValueError('cognition_progress_revision_conflict')
            self.save_receipt(actor, kind='cognition_progress', key=f'{key}/progress:{revision}', receipt=progress)
            self._connection.execute('UPDATE character_session_cognition_heads SET stage_revision=?,pending=? WHERE child_key=?',
                (revision, int(progress['status'] not in {'completed', 'stale'}), key))
            return progress

    def save_receipt(self, actor_id: str, *, kind: str, key: str, receipt: dict, event_id: str | None = None) -> None:
        with self.transaction():
            previous = self.read_receipt(actor_id, kind=kind, key=key)
            if previous is not None and previous != receipt:
                raise ValueError('character_session_receipt_conflict')
            if self._connection is None:
                self._receipts[(actor_id,kind,key)] = (deepcopy(receipt),event_id)
            else:
                self._connection.execute("INSERT INTO character_session_receipts VALUES (?,?,?,?,?) ON CONFLICT(actor_id,kind,receipt_key) DO UPDATE SET event_id=COALESCE(excluded.event_id,event_id)", (actor_id,kind,key,self._json(receipt),event_id))

    def read_receipt(self, actor_id: str, *, kind: str, key: str) -> dict | None:
        with self._lock:
            self._check_open()
            if self._connection is None:
                row = self._receipts.get((actor_id,kind,key))
                return deepcopy(row[0]) if row else None
            row = self._connection.execute("SELECT receipt_json FROM character_session_receipts WHERE actor_id=? AND kind=? AND receipt_key=?", (actor_id,kind,key)).fetchone()
            return json.loads(row[0]) if row else None

    def read_committed_event_for_receipt(self, actor_id: str, *, kind: str, key: str) -> dict | None:
        with self._lock:
            self._check_open()
            if self._connection is None:
                row = self._receipts.get((actor_id,kind,key))
                event_id = row[1] if row else None
            else:
                row = self._connection.execute("SELECT event_id FROM character_session_receipts WHERE actor_id=? AND kind=? AND receipt_key=?", (actor_id,kind,key)).fetchone()
                event_id = row[0] if row else None
            return self.read_event(actor_id,event_id=event_id) if event_id else None

    def list_receipts(self, actor_id: str, kind: str) -> dict:
        self._check_open()
        if self._connection is None:
            return {key:deepcopy(value[0]) for (actor,k,key),value in self._receipts.items() if (actor,k)==(actor_id,kind)}
        return {row[0]:json.loads(row[1]) for row in self._connection.execute("SELECT receipt_key,receipt_json FROM character_session_receipts WHERE actor_id=? AND kind=?",(actor_id,kind))}

    def list_candidates(self, actor_id: str) -> list[dict]:
        self._check_open()
        if self._connection is None:
            return [deepcopy(v) for (actor,_),v in self._candidates.items() if actor==actor_id]
        return [json.loads(row[0]) for row in self._connection.execute("SELECT payload_json FROM character_session_candidates WHERE actor_id=? ORDER BY rowid",(actor_id,))]

    def has_other_candidate(self, actor_id: str, candidate_id: str, dedup_key: str) -> bool:
        self._check_open()
        if self._connection is None:
            return any(a==actor_id and k!=candidate_id and v['dedup_key']==dedup_key for (a,k),v in self._candidates.items())
        return self._connection.execute("SELECT 1 FROM character_session_candidates WHERE actor_id=? AND dedup_key=? AND candidate_id<>? LIMIT 1",(actor_id,dedup_key,candidate_id)).fetchone() is not None

    def projection_cursor(self, actor_id: str, kind: str) -> int:
        self._check_open()
        if self._connection is None:
            return self._projection_cursors.get((actor_id,kind),0)
        row = self._connection.execute("SELECT event_index FROM character_session_projection_cursors WHERE actor_id=? AND kind=?",(actor_id,kind)).fetchone()
        if row is None and self._recovery_enabled and self.event_count(actor_id):
            raise ValueError('character_session_projection_missing')
        return row[0] if row else 0

    def set_projection_cursor(self, actor_id: str, kind: str, index: int) -> None:
        with self.transaction():
            if self._connection is None:
                self._projection_cursors[(actor_id,kind)] = index
            else:
                self._connection.execute("INSERT INTO character_session_projection_cursors VALUES (?,?,?) ON CONFLICT(actor_id,kind) DO UPDATE SET event_index=excluded.event_index", (actor_id,kind,index))

    def read_ask(self, *, actor_id=None, entry_id=None, entry_key=None) -> list[dict]:
        self._check_open()
        if self._connection is None:
            return [deepcopy(v) for v in self._ask_entries.values() if (actor_id is None or v['actor_id']==actor_id) and (entry_id is None or v['entry_id']==entry_id) and (entry_key is None or self.ask_key(v)==entry_key)]
        column,value = ('entry_id',entry_id) if entry_id is not None else ('entry_key',entry_key) if entry_key is not None else ('actor_id',actor_id)
        query = 'SELECT entry_key,payload_json FROM character_session_ask'
        return [ask_storage.read(self._connection, row[0], row[1])[0] for row in self._connection.execute(query + (f' WHERE {column}=?' if value is not None else '') + ' ORDER BY rowid', (value,) if value is not None else ())]

    @staticmethod
    def ask_key(entry: dict) -> str:
        return CharacterAgentSessionStore._json([entry[k] for k in ('actor_id','session_id','scene_id','world_anchor_id','knowledge_type')])

    def iter_ask_audit(self, actor_id: str):
        """显式完整审计按序输出规范化记录，不在 ready 或当前状态读取中调用。"""
        self._check_open()
        if self._connection is None:
            raise ValueError('ask_audit_requires_durable_store')
        db = self._connection
        if db.execute("SELECT 1 FROM character_session_ask_parts p LEFT JOIN character_session_ask h ON p.entry_key=h.entry_key WHERE h.entry_key IS NULL LIMIT 1").fetchone():
            raise ValueError('ask_audit_orphan_part')
        for index, (key, payload) in enumerate(db.execute('SELECT entry_key,payload_json FROM character_session_ask WHERE actor_id=? ORDER BY rowid', (actor_id,))):
            head = json.loads(payload)
            yield dict(kind='head', ordinal=index, entry_key=key, value=head)
            if db.execute("SELECT 1 FROM character_session_ask_parts WHERE entry_key=? AND kind NOT IN ('source_refs','source_ref_lineage','conflicts','revisions') LIMIT 1", (key,)).fetchone():
                raise ValueError('ask_audit_unknown_part')
            for kind in (*ask_storage.SOURCES, *ask_storage.HISTORY):
                for ordinal, value in db.execute('SELECT ordinal,payload_json FROM character_session_ask_parts WHERE entry_key=? AND kind=? ORDER BY ordinal', (key, kind)):
                    yield dict(kind=kind, ordinal=ordinal, entry_key=key, value=json.loads(value))
            yield dict(kind='entry_end', ordinal=index, entry_key=key)

    def read_ask_current(self, entry_key: str):
        self._check_open()
        if self._connection is None:
            value = self._ask_entries.get(entry_key)
            if value is None:
                return None
            counts = {name: len(value[name]) for name in (*ask_storage.SOURCES, *ask_storage.HISTORY)}
            counts['unresolved'] = sum(not item['resolved'] for item in value['conflicts'])
            head = deepcopy({name: item for name,item in value.items() if name not in ask_storage.HISTORY})
            head.update(conflicts=[], revisions=[])
            return head, counts
        row = self._connection.execute('SELECT payload_json FROM character_session_ask WHERE entry_key=?', (entry_key,)).fetchone()
        return ask_storage.read(self._connection, entry_key, row[0], history=False) if row else None

    def write_ask(self, entry: dict | ask_storage.AskAppend, trace: dict) -> None:
        with self.transaction():
            append = entry if isinstance(entry, ask_storage.AskAppend) else None
            value = append.entry if append else entry
            key = self.ask_key(value)
            if self._connection is None:
                if append:
                    old = self._ask_entries[key]
                    value = {**value, **{name: [*old[name], *value[name]] for name in ask_storage.HISTORY}}
                self._ask_entries[key] = deepcopy(value)
                self._ask_trace.append(deepcopy(trace))
            else:
                ask_storage.write(self._connection, key, value, previous=append.counts if append else None)
                self._connection.execute("INSERT INTO character_session_ask_trace(payload_json) VALUES (?)",(self._json(trace),))

    def read_ask_trace(self) -> list[dict]:
        self._check_open()
        if self._connection is None:
            return deepcopy(self._ask_trace)
        return [json.loads(row[0]) for row in self._connection.execute('SELECT payload_json FROM character_session_ask_trace ORDER BY sequence')]

    def _make_event(
        self, actor_id: str, event_type: str, producer_ts: int,
        payload: dict[str, object], event_index: int,
    ) -> dict[str, object]:
        return self._validate_event({
            "event_id": f"{actor_id}:{event_type}:{producer_ts}:{self._runtime_id}:{event_index}",
            "event_index": event_index,
            "actor_id": actor_id,
            "event_type": event_type,
            "producer_ts": producer_ts,
            "payload": dict(payload),
        })

    def list_events(self, actor_id: str) -> list[dict[str, object]]:
        with self._lock:
            self._check_open()
            if self._connection is not None:
                return [json.loads(row[0]) for row in self._connection.execute(
                    "SELECT payload_json FROM character_session_events WHERE actor_id=? ORDER BY event_index", (actor_id,))]
            return [dict(event) for event in self._events_by_actor.get(actor_id, [])]

    def event_count(self, actor_id: str) -> int:
        with self._lock:
            self._check_open()
            if self._connection is not None:
                row = self._connection.execute("SELECT event_count FROM character_session_heads WHERE actor_id=?", (actor_id,)).fetchone()
                return row[0] if row is not None else 0
            return len(self._events_by_actor.get(actor_id, []))

    def list_events_after(
        self, actor_id: str, event_count: int
    ) -> list[dict[str, object]]:
        with self._lock:
            self._check_open()
            if self._connection is not None:
                # 保留旧 slice 的负索引语义；有界恢复入口使用 read_events_page。
                if event_count < 0:
                    event_count = max(0, self.event_count(actor_id) + event_count)
                return [json.loads(row[0]) for row in self._connection.execute(
                    "SELECT payload_json FROM character_session_events WHERE actor_id=? AND event_index>? ORDER BY event_index", (actor_id, event_count))]
            return [
                dict(event)
                for event in self._events_by_actor.get(actor_id, [])[event_count:]
            ]

    def last_event(self, actor_id: str, *, event_type: str | None = None) -> dict[str, object] | None:
        with self._lock:
            self._check_open()
            if self._connection is not None:
                if event_type is not None:
                    row = self._connection.execute(
                        "SELECT payload_json FROM character_session_events "
                        "WHERE actor_id=? AND event_type=? ORDER BY event_index DESC LIMIT 1",
                        (actor_id, event_type),
                    ).fetchone()
                    return json.loads(row[0]) if row is not None else None
                count = self.event_count(actor_id)
                return self.read_event(actor_id, event_index=count) if count else None
            events = self._events_by_actor.get(actor_id, [])
            if event_type is None:
                return dict(events[-1]) if events else None
            return next((dict(event) for event in reversed(events) if event["event_type"] == event_type), None)

    def list_all_events(self) -> dict[str, list[dict[str, object]]]:
        with self._lock:
            self._check_open()
            if self._connection is not None:
                return {actor_id: self.list_events(actor_id) for actor_id in self.actor_ids()}
            return {
                actor_id: [dict(event) for event in events]
                for actor_id, events in self._events_by_actor.items()
            }

    def actor_ids(self) -> tuple[str, ...]:
        with self._lock:
            self._check_open()
            if self._connection is not None:
                actors = tuple(row[0] for row in self._connection.execute("SELECT actor_id FROM character_session_heads ORDER BY rowid"))
                if self._recovery_enabled:
                    current_actors = tuple(row[0] for row in self._connection.execute("SELECT actor_id FROM character_session_recovery ORDER BY rowid"))
                    if set(actors) != set(current_actors):
                        raise ValueError('character_session_recovery_gap')
                return actors
            return tuple(self._events_by_actor)

    def read_event(
        self, actor_id: str, *, event_index: int | None = None, event_id: str | None = None,
    ) -> dict[str, object] | None:
        if (event_index is None) == (event_id is None):
            raise ValueError("session_event_selector_invalid")
        if event_index is not None and (type(event_index) is not int or event_index < 1):
            raise ValueError("session_event_index_invalid")
        with self._lock:
            self._check_open()
            if self._connection is not None:
                column, value = ("event_index", event_index) if event_index is not None else ("event_id", event_id)
                row = self._connection.execute(
                    f"SELECT payload_json FROM character_session_events WHERE actor_id=? AND {column}=?", (actor_id, value)
                ).fetchone()
                return json.loads(row[0]) if row is not None else None
            return next((dict(event) for event in self._events_by_actor.get(actor_id, [])
                         if event.get("event_index" if event_index is not None else "event_id") == (event_index if event_index is not None else event_id)), None)

    def read_events_page(
        self, actor_id: str, *, after_index: int = 0, through_index: int | None = None,
        event_types: tuple[str, ...] | None = None, limit: int = 128,
    ) -> list[dict[str, object]]:
        if type(after_index) is not int or after_index < 0 or type(limit) is not int or limit < 1:
            raise ValueError("session_page_bounds_invalid")
        if through_index is not None and (type(through_index) is not int or through_index < 0):
            raise ValueError("session_page_bounds_invalid")
        with self._lock:
            self._check_open()
            if event_types == ():
                return []
            if self._connection is None:
                return [dict(event) for event in self._events_by_actor.get(actor_id, [])
                        if event["event_index"] > after_index
                        and (through_index is None or event["event_index"] <= through_index)
                        and (event_types is None or event["event_type"] in event_types)][:limit]
            clauses = ["actor_id=?", "event_index>?"]
            parameters: list[object] = [actor_id, after_index]
            if through_index is not None:
                clauses.append("event_index<=?")
                parameters.append(through_index)
            if event_types is not None:
                clauses.append("event_type IN (" + ",".join("?" for _ in event_types) + ")")
                parameters.extend(event_types)
            parameters.append(limit)
            # 大 LIMIT 会使 SQLite 为了排序选择扫描全 actor，类型索引避免读取无关历史。
            index = " INDEXED BY character_session_event_types" if event_types is not None else ""
            return [json.loads(row[0]) for row in self._connection.execute(
                "SELECT payload_json FROM character_session_events" + index + " WHERE " + " AND ".join(clauses) + " ORDER BY event_index LIMIT ?", parameters)]

    def _load(self) -> None:
        if self._storage_path is None:
            return
        if self._storage_path.exists():
            raw = self._storage_path.read_text(encoding="utf-8").strip()
            if raw:
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    if self._actors_root is None or not self._actors_root.exists():
                        raise
                else:
                    if isinstance(payload, dict) and payload.get("schema_version") != 2:
                        for actor_id, events in payload.items():
                            if not isinstance(actor_id, str) or not isinstance(events, list):
                                continue
                            loaded_events = self._normalize_event_sequence(events)
                            if any(event["actor_id"] != actor_id for event in loaded_events):
                                raise ValueError("session_event_actor_mismatch")
                            self._events_by_actor[actor_id] = loaded_events
        self._load_actor_files()

    def _load_actor_files(self) -> None:
        if self._actors_root is None or not self._actors_root.exists():
            return
        known_events = {
            actor_id: {str(event["event_id"]): event for event in events}
            for actor_id, events in self._events_by_actor.items()
        }
        for path in sorted(self._actors_root.glob("*.jsonl")):
            data = path.read_bytes()
            lines = data.splitlines(keepends=True)
            valid_size = 0
            truncated = False
            for index, raw_line in enumerate(lines):
                terminated = raw_line.endswith((b"\n", b"\r"))
                content = raw_line.rstrip(b"\r\n")
                try:
                    line = content.decode("utf-8")
                except UnicodeDecodeError:
                    if index == len(lines) - 1 and not terminated:
                        self._truncate_file(path, valid_size)
                        truncated = True
                        break
                    raise
                if not line.strip():
                    valid_size += len(raw_line)
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    if index == len(lines) - 1 and not terminated:
                        self._truncate_file(path, valid_size)
                        truncated = True
                        break
                    raise
                normalized = self._validate_event(event)
                actor_id = str(normalized["actor_id"])
                event_id = str(normalized["event_id"])
                if path != self._actor_storage_path(actor_id):
                    raise ValueError("session_event_actor_path_mismatch")
                actor_events = known_events.setdefault(actor_id, {})
                previous = actor_events.get(event_id)
                if previous is not None:
                    if previous != normalized:
                        raise ValueError("session_event_id_conflict")
                else:
                    if int(normalized["event_index"]) != len(
                        self._events_by_actor.get(actor_id, [])
                    ) + 1:
                        raise ValueError("session_event_index_gap")
                    self._events_by_actor.setdefault(actor_id, []).append(normalized)
                    actor_events[event_id] = normalized
                valid_size += len(raw_line)
            if data and not truncated and not data.endswith((b"\n", b"\r")):
                with path.open("ab") as stream:
                    stream.write(b"\n")
                    stream.flush()
                    os.fsync(stream.fileno())

    def _actor_storage_path(self, actor_id: str) -> Path:
        if self._actors_root is None:
            raise RuntimeError("session_store_not_durable")
        digest = hashlib.sha256(actor_id.encode("utf-8")).hexdigest()
        return self._actors_root / f"{digest}.jsonl"

    @staticmethod
    def _validate_event(event: object) -> dict[str, object]:
        if not isinstance(event, dict):
            raise ValueError("session_event_invalid")
        required = {
            "event_id": str,
            "event_index": int,
            "actor_id": str,
            "event_type": str,
            "producer_ts": int,
            "payload": dict,
        }
        if any(
            key not in event
            or isinstance(event[key], bool)
            or not isinstance(event[key], expected_type)
            for key, expected_type in required.items()
        ):
            raise ValueError("session_event_invalid")
        if (
            not str(event["event_id"])
            or int(event["event_index"]) < 1
            or not str(event["actor_id"])
            or not str(event["event_type"])
        ):
            raise ValueError("session_event_invalid")
        return dict(event)

    @classmethod
    def _normalize_event_sequence(
        cls, events: list[object]
    ) -> list[dict[str, object]]:
        normalized: list[dict[str, object]] = []
        by_id: dict[str, dict[str, object]] = {}
        for raw_event in events:
            event = cls._validate_event(raw_event)
            event_id = str(event["event_id"])
            previous = by_id.get(event_id)
            if previous is not None:
                if previous != event:
                    raise ValueError("session_event_id_conflict")
                continue
            if int(event["event_index"]) != len(normalized) + 1:
                raise ValueError("session_event_index_gap")
            normalized.append(event)
            by_id[event_id] = event
        return normalized

    @staticmethod
    def _truncate_file(path: Path, size: int) -> None:
        with path.open("r+b") as stream:
            stream.truncate(size)
            stream.flush()
            os.fsync(stream.fileno())
