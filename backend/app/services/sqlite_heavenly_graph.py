import json
import sqlite3
from contextlib import contextmanager
from threading import RLock
from pathlib import Path

from app.models.siming_heavenly_graph import (
    GraphBranchDiffQuery,
    GraphBranchDiffResult,
    GraphBranchForkRequest,
    GraphBranchLifecycleMarker,
    GraphBranchLifecycleRequest,
    GraphCorrectionRequest,
    GraphReaderContext,
    GraphRevisionVector,
    HeavenlyGraphQueryResult,
    HeavenlyGraphSemanticQuery,
    HeavenlyGraphNode,
    HeavenlyGraphRelation,
    HeavenlyGraphScope,
    HeavenlyGraphSnapshot,
    HeavenlyGraphWriteBatch,
    HeavenlyGraphWriteResult,
    HeavenlyNodeQuery,
    HeavenlyRelationQuery,
    HeavenlySubgraphResult,
)
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
from app.services.heavenly_graph_consistency import HeavenlyGraphConsistencyReport
from app.services.siming_heavenly_graph_port import HeavenlyGraphError


class SQLiteHeavenlyGraphAdapter(InMemoryHeavenlyGraphAdapter):
    SCHEMA_VERSION = 7
    _WAL_AUTOCHECKPOINT_PAGES = 128
    _CANDIDATE_INDEX_SQL = "CREATE INDEX graph_nodes_candidates ON graph_nodes(scope_json,json_extract(payload_json,'$.node_type'),node_id,revision)"

    def __init__(self, database_path: str | Path) -> None:
        self._lock = RLock()
        self._connection = sqlite3.connect(str(database_path), check_same_thread=False)
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute(f"PRAGMA wal_autocheckpoint={self._WAL_AUTOCHECKPOINT_PAGES}")
        try:
            self._migrate()
            super().__init__()
            self._materialized = False
            self._pending_write_batch: HeavenlyGraphWriteBatch | None = None
            self._load_metadata()
        except BaseException:
            self._connection.close()
            raise

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    @contextmanager
    def historical_read(self):
        with self._lock, self._full_state():
            yield

    @contextmanager
    def _full_state(self):
        # ponytail: 分支编辑、历史快照和完整审计仍为 O(H)，热点查询独立走 SQL。
        if self._materialized:
            yield
            return
        self._materialized = True
        try:
            self._load_full()
            yield
        finally:
            super().__init__()
            self._materialized = False
            self._load_metadata()

    def has_idempotency_key(self, *, scope: HeavenlyGraphScope, idempotency_key: str) -> bool:
        with self._lock:
            if self._materialized:
                return super().has_idempotency_key(scope=scope, idempotency_key=idempotency_key)
            return self._connection.execute(
                "SELECT 1 FROM graph_idempotency WHERE scope_json=? AND idempotency_key=?",
                (self._scope_json(scope), idempotency_key),
            ).fetchone() is not None

    def read_siming_room_head(self, scope):
        from app.models.siming_heavenly_graph import SimingOperationalRoomHead
        with self._lock:
            row = self._connection.execute("SELECT payload_json FROM graph_siming_room_heads WHERE room_scope_json=?",
                (self._scope_json(scope.model_copy(update={"scene_id": None})),)).fetchone()
            return None if row is None else SimingOperationalRoomHead.model_validate_json(row[0])

    def get_node_revision(self, *, scope, node_id, revision):
        with self._lock:
            row = self._connection.execute(
                'SELECT payload_json FROM graph_nodes WHERE scope_json=? AND node_id=? AND revision=?',
                (self._scope_json(scope), node_id, revision)).fetchone()
            return None if row is None else HeavenlyGraphNode.model_validate_json(row[0])

    def get_node(self, *, node_id, scope, valid_at, recorded_at=None):
        with self._lock:
            if self._materialized:
                return super().get_node(node_id=node_id, scope=scope, valid_at=valid_at, recorded_at=recorded_at)
            return self._get_exact_entity(
                scope=scope, entity_id=node_id, valid_at=valid_at, recorded_at=recorded_at, nodes=True)

    def get_relation(self, *, relation_id, scope, valid_at, recorded_at=None):
        with self._lock:
            if self._materialized:
                return super().get_relation(
                    relation_id=relation_id, scope=scope, valid_at=valid_at, recorded_at=recorded_at)
            return self._get_exact_entity(
                scope=scope, entity_id=relation_id, valid_at=valid_at, recorded_at=recorded_at, nodes=False)

    def _get_exact_entity(self, *, scope, entity_id, valid_at, recorded_at, nodes):
        if (not self._branch_available(scope, valid_at=valid_at, recorded_at=recorded_at)
                or self._is_branch_discarded(scope, recorded_at, valid_at)):
            return None
        table, identity, model = (("graph_nodes", "node_id", HeavenlyGraphNode) if nodes
                                  else ("graph_relations", "relation_id", HeavenlyGraphRelation))
        sql = f"""SELECT payload_json FROM {table}
            WHERE scope_json=? AND {identity}=?
            AND json_extract(payload_json,'$.validity.valid_from')<=?
            AND (json_extract(payload_json,'$.validity.valid_to') IS NULL
                 OR json_extract(payload_json,'$.validity.valid_to')>?)"""
        args = [self._scope_json(scope), entity_id, valid_at, valid_at]
        if recorded_at is not None:
            sql += " AND json_extract(payload_json,'$.recorded_at')<=?"
            args.append(recorded_at)
        row = self._connection.execute(
            sql + " ORDER BY json_extract(payload_json,'$.recorded_at') DESC,revision DESC LIMIT 1", args,
        ).fetchone()
        if row is None:
            return None
        entity = model.model_validate_json(row[0])
        if entity.semantic_metadata.derivation_kind in {"retraction", "redaction"}:
            return None
        if nodes and (entity.node_type in {"branch_marker", "siming_admission"}
                or self._is_node_closed(scope, entity_id, valid_at=valid_at, recorded_at=recorded_at)):
            return None
        return entity

    def get_admission_node(self, *, scope, entry_id, revision=None):
        with self._lock:
            sql = "SELECT payload_json FROM graph_nodes WHERE scope_json=? AND node_id=?"
            args = [self._scope_json(scope), entry_id]
            if revision is not None:
                sql += " AND revision=?"
                args.append(revision)
            row = self._connection.execute(sql + " ORDER BY revision DESC LIMIT 1", args).fetchone()
            if row is None:
                return None
            node = HeavenlyGraphNode.model_validate_json(row[0])
            return node if node.node_type == "siming_admission" else None

    def list_pending_admission_nodes(self, *, scope, limit, cursor=None):
        if not 1 <= limit <= 257:
            raise ValueError("siming_admission_page_limit")
        with self._lock:
            sql = """SELECT n.payload_json FROM graph_siming_pending p
                JOIN graph_nodes n ON n.scope_json=p.scope_json AND n.node_id=p.entry_id AND n.revision=p.revision
                WHERE 1=1"""
            args = []
            if scope is not None:
                sql += " AND p.scope_json=?"
                args.append(self._scope_json(scope))
            if cursor is not None:
                if scope is None:
                    sql += " AND (p.scope_json,p.due_at,p.entry_id)>(?,?,?)"
                    args.append(self._scope_json(cursor.scope))
                else:
                    sql += " AND (p.due_at,p.entry_id)>(?,?)"
                args.extend((cursor.due_at, cursor.entry_id))
            sql += " ORDER BY p.scope_json,p.due_at,p.entry_id LIMIT ?"
            args.append(limit)
            return [HeavenlyGraphNode.model_validate_json(row[0]) for row in self._connection.execute(sql, args)]

    def read_siming_room_pending(self, scope):
        with self._lock:
            row = self._connection.execute("""SELECT n.payload_json FROM graph_siming_pending p
                JOIN graph_nodes n ON n.scope_json=p.scope_json AND n.node_id=p.entry_id AND n.revision=p.revision
                WHERE p.room_scope_json=? ORDER BY p.room_sequence,p.entry_id LIMIT 1""",
                (self._scope_json(scope.model_copy(update={"scene_id": None})),)).fetchone()
            return None if row is None else HeavenlyGraphNode.model_validate_json(row[0])

    def _update_admission_index(self, node):
        if node.node_type != "siming_admission":
            return
        from app.models.siming_heavenly_memory import SIMING_ADMISSION_TERMINAL
        scope_json = self._scope_json(node.scope)
        self._connection.execute("DELETE FROM graph_siming_pending WHERE scope_json=? AND entry_id=?", (scope_json, node.node_id))
        if node.attributes["state"] not in SIMING_ADMISSION_TERMINAL:
            self._connection.execute("INSERT INTO graph_siming_pending VALUES (?,?,?,?,?,?,?)",
                (scope_json, node.node_id, node.revision, node.attributes["state"], node.attributes["due_at"],
                 self._scope_json(node.scope.model_copy(update={"scene_id": None})), node.attributes.get("room_sequence", 0)))

    def _rebuild_admission_index(self):
        self._connection.execute("DELETE FROM graph_siming_pending")
        self._connection.execute("""INSERT INTO graph_siming_pending
            SELECT scope_json,node_id,revision,json_extract(payload_json,'$.attributes.state'),
                   json_extract(payload_json,'$.attributes.due_at'), json_set(scope_json,'$.scene_id',NULL),
                   COALESCE(json_extract(payload_json,'$.attributes.room_sequence'),0)
            FROM graph_nodes n WHERE json_extract(payload_json,'$.node_type')='siming_admission'
            AND revision=(SELECT MAX(revision) FROM graph_nodes WHERE scope_json=n.scope_json AND node_id=n.node_id)
            AND json_extract(payload_json,'$.attributes.state') NOT IN ('completed','stale','cancelled','failed')""")

    def rebuild_admission_index(self):
        with self._lock, self._connection:
            self._rebuild_admission_index()

    def _prepare_write(self, batch: HeavenlyGraphWriteBatch) -> None:
        """只安装本批验证所需的前驱和时态端点，提交结束立即释放。"""
        row = self._connection.execute(
            "SELECT payload_hash,result_json FROM graph_idempotency WHERE scope_json=? AND idempotency_key=?",
            (self._scope_json(batch.scope), batch.idempotency_key),
        ).fetchone()
        if row is not None:
            self._idempotency[(self._scope_key(batch.scope), batch.idempotency_key)] = (
                row[0], HeavenlyGraphWriteResult.model_validate_json(row[1]),
            )
            return
        for table, identity, items, model, target in (
            ("graph_nodes", "node_id", batch.nodes, HeavenlyGraphNode, self._nodes),
            ("graph_relations", "relation_id", batch.relations, HeavenlyGraphRelation, self._relations),
        ):
            for item in items:
                key = (self._scope_key(item.scope), getattr(item, identity))
                row = self._connection.execute(
                    f"SELECT payload_json FROM {table} WHERE scope_json=? AND {identity}=? ORDER BY revision DESC LIMIT 1",
                    (self._scope_json(item.scope), key[1]),
                ).fetchone()
                if row is not None:
                    target[key] = [model.model_validate_json(row[0])]
        for relation in batch.relations:
            for scope, node_id in ((relation.source_scope or relation.scope, relation.source_node_id),
                                   (relation.target_scope or relation.scope, relation.target_node_id)):
                row = self._connection.execute(
                    """SELECT payload_json FROM graph_nodes WHERE scope_json=? AND node_id=?
                    AND json_extract(payload_json,'$.recorded_at')<=?
                    AND json_extract(payload_json,'$.validity.valid_from')<=?
                    AND (json_extract(payload_json,'$.validity.valid_to') IS NULL OR json_extract(payload_json,'$.validity.valid_to')>?)
                    ORDER BY json_extract(payload_json,'$.recorded_at') DESC,revision DESC LIMIT 1""",
                    (self._scope_json(scope), node_id, relation.recorded_at, relation.validity.valid_from, relation.validity.valid_from),
                ).fetchone()
                if row is not None:
                    node = HeavenlyGraphNode.model_validate_json(row[0])
                    versions = self._nodes.setdefault((self._scope_key(scope), node_id), [])
                    if all(previous.revision != node.revision for previous in versions):
                        versions.append(node)

    def _query_entities(self, query, *, nodes: bool, history: bool = False):
        if (not self._branch_available(query.scope, valid_at=query.valid_at, recorded_at=query.recorded_at)
                or self._is_branch_discarded(query.scope, query.recorded_at, query.valid_at)):
            return []
        if nodes and not history and query.node_types and query.limit is not None:
            types = list(dict.fromkeys(query.node_types))
            # 仅有限集合使用每类型前K合并；复杂参数沿原IN查询，保留SQLite可用范围。
            parameters = 11 + (2 if query.recorded_at is not None else 0) + len(query.node_ids or [])
            if (len(types) <= self._connection.getlimit(sqlite3.SQLITE_LIMIT_COMPOUND_SELECT)
                    and parameters * len(types) + 1 <= self._connection.getlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER)):
                return self._query_current_typed_nodes(query, types)
        table, identity, model = (("graph_nodes", "node_id", HeavenlyGraphNode) if nodes
                                  else ("graph_relations", "relation_id", HeavenlyGraphRelation))
        where = ["scope_json=?", "json_extract(payload_json,'$.validity.valid_from')<=?",
                 "(json_extract(payload_json,'$.validity.valid_to') IS NULL OR json_extract(payload_json,'$.validity.valid_to')>?)"]
        args = [self._scope_json(query.scope), query.valid_at, query.valid_at]
        if query.recorded_at is not None:
            where.append("json_extract(payload_json,'$.recorded_at')<=?")
            args.append(query.recorded_at)
        ids = query.node_ids if nodes else query.relation_ids
        if ids:
            where.append(f"{identity} IN ({','.join('?' for _ in ids)})")
            args.extend(ids)
        # 先选双时间有效的最后版本，再按类型/端点过滤，避免复活被替代的版本。
        sql = (f"WITH candidates AS (SELECT {identity},revision,payload_json,"
               f"ROW_NUMBER() OVER(PARTITION BY {identity} ORDER BY json_extract(payload_json,'$.recorded_at') DESC,revision DESC) AS rn "
               f"FROM {table} WHERE {' AND '.join(where)}) SELECT payload_json FROM candidates WHERE 1=1")
        if not history:
            # 旧 schema 1 缺省字段与 GraphSemanticMetadata 默认值一致，不能被 SQL NULL 过滤。
            sql += " AND rn=1 AND COALESCE(json_extract(payload_json,'$.semantic_metadata.derivation_kind'),'authority') NOT IN ('retraction','redaction')"
        filters = [("node_type", query.node_types)] if nodes else [
            ("relation_type", query.relation_types), ("source_node_id", query.source_node_ids), ("target_node_id", query.target_node_ids),
        ]
        for field, values in filters:
            if values:
                sql += f" AND json_extract(payload_json,'$.{field}') IN ({','.join('?' for _ in values)})"
                args.extend(values)
        if nodes:
            sql += " AND json_extract(payload_json,'$.node_type') NOT IN ('branch_marker','siming_admission')"
            sql += """ AND node_id NOT IN (
                SELECT json_extract(marker.value,'$.node_id') FROM graph_branch_state,json_each(markers_json) AS marker
                WHERE scope_json=? AND json_extract(marker.value,'$.operation')='close_node'
                AND json_extract(marker.value,'$.valid_at')<=?
                AND (? IS NULL OR json_extract(marker.value,'$.recorded_at')<=?))"""
            args.extend((self._scope_json(query.scope), query.valid_at, query.recorded_at, query.recorded_at))
        sql += f" ORDER BY {identity},revision"
        if query.limit is not None:
            sql += " LIMIT ?"
            args.append(query.limit)
        return [model.model_validate_json(row[0]) for row in self._connection.execute(sql, args)]

    def _query_current_typed_nodes(self, query, types):
        scope = self._scope_json(query.scope)
        selects, args = [], []
        for node_type in types:
            where = ["c.scope_json=?", "json_extract(c.payload_json,'$.node_type')=?",
                     "json_extract(c.payload_json,'$.validity.valid_from')<=?",
                     "(json_extract(c.payload_json,'$.validity.valid_to') IS NULL OR json_extract(c.payload_json,'$.validity.valid_to')>?)"]
            branch_args = [scope, node_type, query.valid_at, query.valid_at]
            if query.recorded_at is not None:
                where.append("json_extract(c.payload_json,'$.recorded_at')<=?")
                branch_args.append(query.recorded_at)
            if query.node_ids:
                where.append(f"c.node_id IN ({','.join('?' for _ in query.node_ids)})")
                branch_args.extend(query.node_ids)
            newer = ["n.scope_json=c.scope_json", "n.node_id=c.node_id",
                     "json_extract(n.payload_json,'$.validity.valid_from')<=?",
                     "(json_extract(n.payload_json,'$.validity.valid_to') IS NULL OR json_extract(n.payload_json,'$.validity.valid_to')>?)"]
            branch_args.extend((query.valid_at, query.valid_at))
            if query.recorded_at is not None:
                newer.append("json_extract(n.payload_json,'$.recorded_at')<=?")
                branch_args.append(query.recorded_at)
            n, c = "json_extract(n.payload_json,'$.recorded_at')", "json_extract(c.payload_json,'$.recorded_at')"
            # 原DESC将NULL放最后；不能用普通tuple比较令NULL版本全部胜出。
            newer.append(f"({n}>{c} OR ({n} IS NOT NULL AND {c} IS NULL) OR ({n} IS {c} AND n.revision>c.revision))")
            where.append(f"NOT EXISTS (SELECT 1 FROM graph_nodes n WHERE {' AND '.join(newer)})")
            where.append("COALESCE(json_extract(c.payload_json,'$.semantic_metadata.derivation_kind'),'authority') NOT IN ('retraction','redaction')")
            where.append("json_extract(c.payload_json,'$.node_type') NOT IN ('branch_marker','siming_admission')")
            where.append("""c.node_id NOT IN (
                SELECT json_extract(marker.value,'$.node_id') FROM graph_branch_state,json_each(markers_json) AS marker
                WHERE scope_json=? AND json_extract(marker.value,'$.operation')='close_node'
                AND json_extract(marker.value,'$.valid_at')<=?
                AND (? IS NULL OR json_extract(marker.value,'$.recorded_at')<=?))""")
            branch_args.extend((scope, query.valid_at, query.recorded_at, query.recorded_at, query.limit))
            selects.append("SELECT * FROM (SELECT c.node_id,c.revision,c.payload_json FROM graph_nodes c INDEXED BY graph_nodes_candidates WHERE "
                           + ' AND '.join(where) + " ORDER BY c.node_id,c.revision LIMIT ?)")
            args.extend(branch_args)
        sql = 'SELECT payload_json FROM (' + ' UNION ALL '.join(selects) + ') ORDER BY node_id,revision LIMIT ?'
        args.append(query.limit)
        return [HeavenlyGraphNode.model_validate_json(row[0]) for row in self._connection.execute(sql, args)]

    def _scope_revision_vector(self, scope: HeavenlyGraphScope, recorded_at: int | None = None,
                               valid_at: int | None = None) -> GraphRevisionVector:
        with self._lock:
            if self._materialized:
                return super()._scope_revision_vector(scope, recorded_at=recorded_at, valid_at=valid_at)
            if valid_at is not None and not self._branch_available(scope, valid_at=valid_at, recorded_at=recorded_at):
                return GraphRevisionVector()
            key = self._scope_key(scope)
            if recorded_at is None:
                summary = self._connection.execute(
                    "SELECT source_revision,policy_revision,branch_revision,max_valid_from FROM graph_revision_summaries WHERE scope_json=?",
                    (self._scope_json(scope),),
                ).fetchone()
                if summary is None:
                    if self._scope_stream_revisions.get(key, (0, 0)) != (0, 0):
                        raise HeavenlyGraphError("graph_revision_summary_missing")
                    summary = (0, 0, 0, 0)
                # 只有无历史 recorded 截点、且 valid 时间覆盖全部版本时才可读汇总。
                if valid_at is None or valid_at >= summary[3]:
                    nodes, relations = self._scope_stream_revisions.get(key, (0, 0))
                    return GraphRevisionVector(node_revision=nodes, relation_revision=relations,
                        source_revision=summary[0], policy_revision=summary[1],
                        branch_revision=max(self._branch_revisions.get(key, 0), summary[2]))
            aggregates = []
            for table in ("graph_nodes", "graph_relations"):
                sql = "SELECT COUNT(*)," + ",".join(
                    f"COALESCE(MAX(json_extract(payload_json,'$.semantic_metadata.source_revision_vector.{field}')),0)"
                    for field in ("source_revision", "policy_revision", "branch_revision")
                ) + f" FROM {table} WHERE scope_json=?"
                args = [self._scope_json(scope)]
                if recorded_at is not None:
                    sql += " AND json_extract(payload_json,'$.recorded_at')<=?"
                    args.append(recorded_at)
                if valid_at is not None:
                    sql += " AND json_extract(payload_json,'$.validity.valid_from')<=?"
                    args.append(valid_at)
                aggregates.append(self._connection.execute(sql, args).fetchone())
            key = self._scope_key(scope)
            node_revision, relation_revision = (self._scope_stream_revisions.get(key, (0, 0)) if recorded_at is None
                                                 else (aggregates[0][0], aggregates[1][0]))
            branch_revision = self._branch_revisions.get(key, 0)
            if recorded_at is not None:
                branch_revision = max((marker.revision_vector.branch_revision for marker in self._branch_markers.get(key, [])
                    if marker.recorded_at <= recorded_at and (valid_at is None or marker.valid_at <= valid_at)), default=0)
            return GraphRevisionVector(node_revision=node_revision, relation_revision=relation_revision,
                source_revision=max(row[1] for row in aggregates), policy_revision=max(row[2] for row in aggregates),
                branch_revision=max(branch_revision, *(row[3] for row in aggregates)))

    def write_batch(self, batch: HeavenlyGraphWriteBatch) -> HeavenlyGraphWriteResult:
        with self._lock:
            snapshot = None
            self._pending_write_batch = batch
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                # 旧 scope 缺汇总必须在接受批次前拒绝，不能用本批 MAX 掩盖历史。
                missing_summary = self._connection.execute("""
                    SELECT 1 FROM graph_stream_revisions AS revisions
                    LEFT JOIN graph_revision_summaries AS summaries USING(scope_json)
                    WHERE revisions.scope_json=?
                    AND (revisions.node_revision!=0 OR revisions.relation_revision!=0)
                    AND summaries.scope_json IS NULL
                """, (self._scope_json(batch.scope),)).fetchone()
                if missing_summary is not None:
                    raise HeavenlyGraphError("graph_revision_summary_missing")
                if not self._materialized:
                    self._prepare_write(batch)
                snapshot = self._capture_write_batch_state(batch)
                result = super().write_batch(batch)
                if result.applied:
                    self._persist()
                else:
                    self._connection.commit()
                return result
            except Exception:
                self._connection.rollback()
                if snapshot is not None:
                    self._restore_write_batch_state(snapshot)
                raise
            finally:
                self._pending_write_batch = None
                if not self._materialized:
                    self._nodes.clear()
                    self._relations.clear()
                    self._idempotency.clear()
                    self._siming_room_heads.clear()

    def _capture_write_batch_state(self, batch: HeavenlyGraphWriteBatch) -> dict[str, object]:
        """Capture only mutable entries that an ordinary batch can touch."""
        node_states: dict[object, tuple[object, int | None]] = {}
        for node in batch.nodes:
            key = (self._scope_key(node.scope), node.node_id)
            if key not in node_states:
                values = self._nodes.get(key)
                node_states[key] = (values, None if values is None else len(values))

        relation_states: dict[object, tuple[object, int | None]] = {}
        for relation in batch.relations:
            key = (self._scope_key(relation.scope), relation.relation_id)
            if key not in relation_states:
                values = self._relations.get(key)
                relation_states[key] = (values, None if values is None else len(values))

        idempotency_key = (self._scope_key(batch.scope), batch.idempotency_key)
        revision_key = self._scope_key(batch.scope)
        return {
            "siming_room_head": (None if batch.siming_room_head is None else
                (self._scope_key(batch.siming_room_head.scope), self._siming_room_heads.get(self._scope_key(batch.siming_room_head.scope)))),
            "nodes": node_states,
            "relations": relation_states,
            "idempotency": (
                idempotency_key,
                self._idempotency.get(idempotency_key),
            ),
            "stream_revision": (
                revision_key,
                self._scope_stream_revisions.get(revision_key),
            ),
        }

    def _restore_write_batch_state(self, snapshot: dict[str, object]) -> None:
        if snapshot["siming_room_head"] is not None:
            key, value = snapshot["siming_room_head"]
            if value is None:
                self._siming_room_heads.pop(key, None)
            else:
                self._siming_room_heads[key] = value
        for key, (values, length) in snapshot["nodes"].items():  # type: ignore[union-attr]
            if values is None:
                self._nodes.pop(key, None)
            else:
                del values[length:]  # type: ignore[index]
                self._nodes[key] = values  # type: ignore[assignment]
        for key, (values, length) in snapshot["relations"].items():  # type: ignore[union-attr]
            if values is None:
                self._relations.pop(key, None)
            else:
                del values[length:]  # type: ignore[index]
                self._relations[key] = values  # type: ignore[assignment]

        idempotency_key, idempotency_value = snapshot["idempotency"]  # type: ignore[misc]
        if idempotency_value is None:
            self._idempotency.pop(idempotency_key, None)
        else:
            self._idempotency[idempotency_key] = idempotency_value

        revision_key, revision_value = snapshot["stream_revision"]  # type: ignore[misc]
        if revision_value is None:
            self._scope_stream_revisions.pop(revision_key, None)
        else:
            self._scope_stream_revisions[revision_key] = revision_value

    def fork_branch(self, request: GraphBranchForkRequest) -> HeavenlyGraphWriteResult:
        with self._lock, self._full_state():
            snapshot = self._snapshot_mutable_state()
            try:
                result = super().fork_branch(request)
                self._persist()
                return result
            except Exception:
                self._restore_mutable_state(snapshot)
                raise

    def lifecycle_branch(self, request: GraphBranchLifecycleRequest) -> HeavenlyGraphWriteResult:
        with self._lock, self._full_state():
            snapshot = self._snapshot_mutable_state()
            try:
                result = super().lifecycle_branch(request)
                self._persist()
                return result
            except Exception:
                self._restore_mutable_state(snapshot)
                raise

    def diff_branches(self, query: GraphBranchDiffQuery) -> GraphBranchDiffResult:
        with self._lock:
            return super().diff_branches(query)

    def correct(self, request: GraphCorrectionRequest) -> HeavenlyGraphWriteResult:
        with self._lock, self._full_state():
            snapshot = self._snapshot_mutable_state()
            try:
                result = super().correct(request)
                if result.applied:
                    self._persist()
                return result
            except Exception:
                self._restore_mutable_state(snapshot)
                raise

    def create_checkpoint(self, **kwargs: object):
        with self._lock, self._full_state():
            snapshot = self._snapshot_mutable_state()
            try:
                checkpoint = super().create_checkpoint(**kwargs)
                self._persist()
                return checkpoint
            except Exception:
                self._restore_mutable_state(snapshot)
                raise

    def scope_current_time_bounds(self, scope: HeavenlyGraphScope) -> tuple[int, int]:
        with self._lock:
            if self._materialized:
                return super().scope_current_time_bounds(scope)
            scope_json = self._scope_json(scope)
            valid = self._connection.execute("""SELECT valid_from FROM graph_current_times INDEXED BY graph_current_times_valid
                WHERE scope_json=? AND entity_kind='node' ORDER BY valid_from DESC LIMIT 1""", (scope_json,)).fetchone()
            recorded = self._connection.execute("""SELECT recorded_at FROM graph_current_times INDEXED BY graph_current_times_recorded
                WHERE scope_json=? ORDER BY length(recorded_at) DESC,recorded_at DESC LIMIT 1""", (scope_json,)).fetchone()
            if ((valid is not None and (type(valid[0]) is not int or not 0 <= valid[0] <= 2**63 - 1))
                    or (recorded is not None and (not recorded[0].isascii() or not recorded[0].isdigit()
                        or str(int(recorded[0])) != recorded[0]))):
                raise HeavenlyGraphError("graph_current_times_invalid")
            return (0 if valid is None else valid[0], 0 if recorded is None else int(recorded[0]))

    def query_nodes(self, query: HeavenlyNodeQuery) -> list[HeavenlyGraphNode]:
        with self._lock:
            return super().query_nodes(query) if self._materialized else self._query_entities(query, nodes=True)

    def query_node_history(self, query: HeavenlyNodeQuery) -> list[HeavenlyGraphNode]:
        with self._lock:
            return super().query_node_history(query) if self._materialized else self._query_entities(query, nodes=True, history=True)

    def query_relations(
        self, query: HeavenlyRelationQuery
    ) -> list[HeavenlyGraphRelation]:
        with self._lock:
            return super().query_relations(query) if self._materialized else self._query_entities(query, nodes=False)

    def query_semantic(
        self, query: HeavenlyGraphSemanticQuery
    ) -> HeavenlyGraphQueryResult:
        """Keep facade reads serialized with SQLite-backed graph mutations."""
        with self._lock:
            return super().query_semantic(query)

    def audit_consistency(
        self,
        *,
        scope: HeavenlyGraphScope,
        reader_context: GraphReaderContext,
    ) -> HeavenlyGraphConsistencyReport:
        """Keep historical audit reads serialized with SQLite mutations."""
        with self._lock, self._full_state():
            return super().audit_consistency(scope=scope, reader_context=reader_context)

    def query_subgraph(self, **kwargs: object) -> HeavenlySubgraphResult:
        with self._lock:
            return super().query_subgraph(**kwargs)

    def read_checkpoint(self, checkpoint_ref: str) -> HeavenlyGraphSnapshot:
        with self._lock, self._full_state():
            return super().read_checkpoint(checkpoint_ref)

    def replay_from_checkpoint(
        self,
        checkpoint_ref: str,
        tail_batches: list[HeavenlyGraphWriteBatch],
    ) -> HeavenlyGraphSnapshot:
        with self._lock, self._full_state():
            return super().replay_from_checkpoint(checkpoint_ref, tail_batches)

    def _migrate(self) -> None:
        connection = self._connection
        connection.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)")
        versions = [row[0] for row in connection.execute("SELECT version FROM schema_version")]
        if versions and versions not in ([1], [2], [3], [4], [5], [6], [self.SCHEMA_VERSION]):
            raise HeavenlyGraphError(f"unsupported Heavenly Graph schema versions: {versions}")
        if versions in ([6], [self.SCHEMA_VERSION]):
            expected = {'graph_current_times', 'graph_current_times_valid', 'graph_current_times_recorded'}
            existing = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE name IN (?,?,?)", tuple(expected))}
            if existing != expected:
                raise HeavenlyGraphError("graph_current_times_missing")
        if versions == [self.SCHEMA_VERSION]:
            row = connection.execute("SELECT sql FROM sqlite_master WHERE name='graph_nodes_candidates' AND type='index'").fetchone()
            if row is None or row[0] != self._CANDIDATE_INDEX_SQL:
                raise HeavenlyGraphError('graph_nodes_candidates_missing')
        if versions == [6]:
            with connection:
                connection.execute('BEGIN IMMEDIATE')
                connection.execute(self._CANDIDATE_INDEX_SQL)
                connection.execute('UPDATE schema_version SET version=?', (self.SCHEMA_VERSION,))
            return
        connection.executescript(
            """
            BEGIN IMMEDIATE;
            CREATE TABLE IF NOT EXISTS graph_current_times (
                scope_json TEXT NOT NULL, entity_kind TEXT NOT NULL, entity_id TEXT NOT NULL,
                valid_from INTEGER NOT NULL, recorded_at TEXT NOT NULL,
                PRIMARY KEY(scope_json,entity_kind,entity_id)
            );
            CREATE INDEX IF NOT EXISTS graph_current_times_valid
                ON graph_current_times(scope_json,entity_kind,valid_from DESC);
            CREATE INDEX IF NOT EXISTS graph_current_times_recorded
                ON graph_current_times(scope_json,length(recorded_at) DESC,recorded_at DESC);
            CREATE TABLE IF NOT EXISTS graph_siming_room_heads (
                room_scope_json TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS graph_siming_pending (
                scope_json TEXT NOT NULL, entry_id TEXT NOT NULL, revision INTEGER NOT NULL,
                state TEXT NOT NULL, due_at REAL NOT NULL, room_scope_json TEXT NOT NULL, room_sequence INTEGER NOT NULL, PRIMARY KEY(scope_json, entry_id)
            );
            CREATE INDEX IF NOT EXISTS graph_siming_pending_order
                ON graph_siming_pending(scope_json, due_at, entry_id);
            CREATE TABLE IF NOT EXISTS graph_nodes (
                scope_json TEXT NOT NULL, node_id TEXT NOT NULL, revision INTEGER NOT NULL,
                payload_json TEXT NOT NULL, PRIMARY KEY(scope_json, node_id, revision)
            );
            CREATE TABLE IF NOT EXISTS graph_relations (
                scope_json TEXT NOT NULL, relation_id TEXT NOT NULL, revision INTEGER NOT NULL,
                payload_json TEXT NOT NULL, PRIMARY KEY(scope_json, relation_id, revision)
            );
            CREATE TABLE IF NOT EXISTS graph_idempotency (
                scope_json TEXT NOT NULL, idempotency_key TEXT NOT NULL,
                payload_hash TEXT NOT NULL, result_json TEXT NOT NULL,
                PRIMARY KEY(scope_json, idempotency_key)
            );
            CREATE TABLE IF NOT EXISTS graph_checkpoints (
                checkpoint_ref TEXT PRIMARY KEY, scope_json TEXT NOT NULL,
                checkpoint_id TEXT NOT NULL, snapshot_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS graph_stream_revisions (
                scope_json TEXT PRIMARY KEY,
                node_revision INTEGER NOT NULL,
                relation_revision INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS graph_branch_state (
                scope_json TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                revision INTEGER NOT NULL,
                markers_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS graph_revision_summaries (
                scope_json TEXT PRIMARY KEY,
                source_revision INTEGER NOT NULL,
                policy_revision INTEGER NOT NULL,
                branch_revision INTEGER NOT NULL,
                max_valid_from INTEGER NOT NULL
            );
            """
        )
        columns = {row[1] for row in connection.execute("PRAGMA table_info(graph_siming_pending)")}
        if "room_scope_json" not in columns:
            connection.execute("ALTER TABLE graph_siming_pending ADD COLUMN room_scope_json TEXT NOT NULL DEFAULT ''")
            connection.execute("ALTER TABLE graph_siming_pending ADD COLUMN room_sequence INTEGER NOT NULL DEFAULT 0")
        connection.execute("CREATE INDEX IF NOT EXISTS graph_siming_pending_room ON graph_siming_pending(room_scope_json,room_sequence,entry_id)")
        if versions != [self.SCHEMA_VERSION]:
            # 旧库缺少 stream counter 的修复只在迁移执行，不能每次启动扫描历史。
            connection.execute("""
                INSERT INTO graph_stream_revisions(scope_json,node_revision,relation_revision)
                SELECT scope_json,SUM(n),SUM(r) FROM (
                    SELECT scope_json,COUNT(*) AS n,0 AS r FROM graph_nodes GROUP BY scope_json
                    UNION ALL
                    SELECT scope_json,0 AS n,COUNT(*) AS r FROM graph_relations GROUP BY scope_json
                ) GROUP BY scope_json
                ON CONFLICT(scope_json) DO UPDATE SET
                    node_revision=MAX(node_revision,excluded.node_revision),
                    relation_revision=MAX(relation_revision,excluded.relation_revision)
            """)
            for table, identity in (("graph_nodes", "node_id"), ("graph_relations", "relation_id")):
                connection.execute(f"CREATE INDEX IF NOT EXISTS {table}_effective ON {table}(scope_json,{identity},json_extract(payload_json,'$.recorded_at') DESC,revision DESC)")
            connection.execute(self._CANDIDATE_INDEX_SQL.replace('CREATE INDEX ', 'CREATE INDEX IF NOT EXISTS ', 1))
            self._rebuild_revision_summaries()
            self._rebuild_admission_index()
            self._rebuild_current_times()
            connection.execute("DELETE FROM schema_version")
            connection.execute("INSERT INTO schema_version(version) VALUES (?)", (self.SCHEMA_VERSION,))
        connection.commit()

    def _insert_current_time(self, entity, kind: str) -> None:
        # recorded_at原合同不限制int64；非负规范十进制按长度/字典序精确排序。
        self._connection.execute("INSERT OR REPLACE INTO graph_current_times VALUES (?,?,?,?,?)",
            (self._scope_json(entity.scope), kind, entity.node_id if kind == 'node' else entity.relation_id,
             entity.validity.valid_from, str(entity.recorded_at)))

    def _update_current_time(self, entity, kind: str) -> None:
        latest = 2**63 - 1
        if not entity.validity.contains(latest):
            return
        # 已通过逐ID的recorded_at非递减/revision连续准入；本批有效新版本必覆盖旧候选。
        scope = entity.scope
        if (entity.semantic_metadata.derivation_kind in {'retraction', 'redaction'}
                or not self._branch_available(scope, valid_at=latest, recorded_at=None)
                or self._is_branch_discarded(scope, valid_at=latest)
                or (kind == 'node' and (entity.node_type in {'branch_marker', 'siming_admission'}
                    or self._is_node_closed(scope, entity.node_id, valid_at=latest)))):
            self._connection.execute("DELETE FROM graph_current_times WHERE scope_json=? AND entity_kind=? AND entity_id=?",
                (self._scope_json(scope), kind, entity.node_id if kind == 'node' else entity.relation_id))
            return
        self._insert_current_time(entity, kind)

    def _rebuild_current_times(self) -> None:
        """仅迁移/显式全量维护调用；与事实及schema版本共用事务。"""
        self._connection.execute("DELETE FROM graph_current_times")
        latest = 2**63 - 1
        for table, identity, kind, model in (
            ('graph_nodes', 'node_id', 'node', HeavenlyGraphNode),
            ('graph_relations', 'relation_id', 'relation', HeavenlyGraphRelation),
        ):
            rows = self._connection.execute(f"""WITH current AS (
                SELECT scope_json,{identity},payload_json,ROW_NUMBER() OVER(
                    PARTITION BY scope_json,{identity} ORDER BY json_extract(payload_json,'$.recorded_at') DESC,revision DESC) AS rn
                FROM {table} WHERE json_extract(payload_json,'$.validity.valid_from')<=?
                AND (json_extract(payload_json,'$.validity.valid_to') IS NULL OR json_extract(payload_json,'$.validity.valid_to')>?))
                SELECT c.payload_json,b.status,b.markers_json FROM current c
                LEFT JOIN graph_branch_state b ON b.scope_json=c.scope_json WHERE rn=1""", (latest, latest))
            for payload, status, encoded_markers in rows:
                entity = model.model_validate_json(payload)
                markers = [GraphBranchLifecycleMarker.model_validate(value) for value in json.loads(encoded_markers or '[]')]
                admitted = [m for m in markers if m.operation == 'admit' and m.target_branch_id == entity.scope.story_branch_id]
                created = admitted or [m for m in markers if m.operation == 'fork']
                if (entity.semantic_metadata.derivation_kind in {'retraction', 'redaction'}
                        or (created and not any(m.valid_at <= latest for m in created))
                        or (status == 'discarded' and any(m.operation == 'discard' and m.valid_at <= latest for m in markers))
                        or (kind == 'node' and (entity.node_type in {'branch_marker', 'siming_admission'}
                            or any(m.operation == 'close_node' and m.node_id == entity.node_id and m.valid_at <= latest for m in markers)))):
                    continue
                self._insert_current_time(entity, kind)

    def _rebuild_revision_summaries(self) -> None:
        """仅迁移或显式全量维护调用；与事实写入共用外层事务。"""
        self._connection.execute("DELETE FROM graph_revision_summaries")
        self._connection.execute("""
            INSERT INTO graph_revision_summaries
            SELECT scope_json,
                COALESCE(MAX(json_extract(payload_json,'$.semantic_metadata.source_revision_vector.source_revision')),0),
                COALESCE(MAX(json_extract(payload_json,'$.semantic_metadata.source_revision_vector.policy_revision')),0),
                COALESCE(MAX(json_extract(payload_json,'$.semantic_metadata.source_revision_vector.branch_revision')),0),
                MAX(json_extract(payload_json,'$.validity.valid_from'))
            FROM (SELECT scope_json,payload_json FROM graph_nodes
                  UNION ALL SELECT scope_json,payload_json FROM graph_relations)
            GROUP BY scope_json
        """)

    def _scope_json(self, scope: object) -> str:
        return json.dumps(scope.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def _payload_json(self, value: object) -> str:
        return value.model_dump_json()

    def _persist(self) -> None:
        if self._pending_write_batch is not None:
            self._persist_write_batch_delta(self._pending_write_batch)
            return
        connection = self._connection
        try:
            connection.execute("BEGIN IMMEDIATE")
            for table in ("graph_nodes", "graph_relations", "graph_idempotency", "graph_checkpoints", "graph_stream_revisions", "graph_branch_state"):
                connection.execute(f"DELETE FROM {table}")
            for (scope_key, node_id), versions in self._nodes.items():
                for node in versions:
                    connection.execute(
                        "INSERT INTO graph_nodes VALUES (?, ?, ?, ?)",
                        (self._scope_json(node.scope), node_id, node.revision, self._payload_json(node)),
                    )
            for (scope_key, relation_id), versions in self._relations.items():
                for relation in versions:
                    connection.execute(
                        "INSERT INTO graph_relations VALUES (?, ?, ?, ?)",
                        (self._scope_json(relation.scope), relation_id, relation.revision, self._payload_json(relation)),
                    )
            for (scope_key, key), (payload_hash, result) in self._idempotency.items():
                scope_json = self._scope_json_from_key(scope_key)
                connection.execute("INSERT INTO graph_idempotency VALUES (?, ?, ?, ?)", (scope_json, key, payload_hash, self._payload_json(result)))
            for checkpoint_ref, checkpoint_key in self._checkpoint_refs.items():
                snapshot = self._checkpoints[checkpoint_key]
                connection.execute(
                    "INSERT INTO graph_checkpoints VALUES (?, ?, ?, ?)",
                    (checkpoint_ref, self._scope_json(snapshot.checkpoint.scope), snapshot.checkpoint.checkpoint_id, self._payload_json(snapshot)),
                )
            for scope_key, (node_revision, relation_revision) in self._scope_stream_revisions.items():
                connection.execute(
                    "INSERT INTO graph_stream_revisions VALUES (?, ?, ?)",
                    (self._scope_json_from_key(scope_key), node_revision, relation_revision),
                )
            for scope_key, status in self._branch_status.items():
                connection.execute(
                    "INSERT INTO graph_branch_state VALUES (?, ?, ?, ?)",
                    (
                        self._scope_json_from_key(scope_key),
                        status,
                        self._branch_revisions.get(scope_key, 0),
                        json.dumps(
                            [marker.model_dump(mode="json") for marker in self._branch_markers.get(scope_key, [])],
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    ),
                )
            self._rebuild_revision_summaries()
            self._rebuild_admission_index()
            self._rebuild_current_times()
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def _persist_write_batch_delta(self, batch: HeavenlyGraphWriteBatch) -> None:
        """Persist append-only graph writes without rewriting historical rows."""
        connection = self._connection
        scope_key = self._scope_key(batch.scope)
        payload_hash, result = self._idempotency[(scope_key, batch.idempotency_key)]
        node_revision, relation_revision = self._scope_stream_revisions.get(
            scope_key, (0, 0)
        )
        try:
            for node in batch.nodes:
                connection.execute(
                    "INSERT INTO graph_nodes VALUES (?, ?, ?, ?)",
                    (
                        self._scope_json(node.scope),
                        node.node_id,
                        node.revision,
                        self._payload_json(node),
                    ),
                )
                self._update_admission_index(node)
                self._update_current_time(node, 'node')
            for relation in batch.relations:
                connection.execute(
                    "INSERT INTO graph_relations VALUES (?, ?, ?, ?)",
                    (
                        self._scope_json(relation.scope),
                        relation.relation_id,
                        relation.revision,
                        self._payload_json(relation),
                    ),
                )
                self._update_current_time(relation, 'relation')
            connection.execute(
                """
                INSERT INTO graph_stream_revisions(scope_json, node_revision, relation_revision)
                VALUES (?, ?, ?)
                ON CONFLICT(scope_json) DO UPDATE SET
                    node_revision = excluded.node_revision,
                    relation_revision = excluded.relation_revision
                """,
                (self._scope_json(batch.scope), node_revision, relation_revision),
            )
            connection.execute(
                "INSERT INTO graph_idempotency VALUES (?, ?, ?, ?)",
                (
                    self._scope_json(batch.scope),
                    batch.idempotency_key,
                    payload_hash,
                    self._payload_json(result),
                ),
            )
            entities = [*batch.nodes, *batch.relations]
            if entities:
                vectors = [entity.semantic_metadata.source_revision_vector for entity in entities]
                connection.execute("""
                    INSERT INTO graph_revision_summaries VALUES (?,?,?,?,?)
                    ON CONFLICT(scope_json) DO UPDATE SET
                        source_revision=MAX(source_revision,excluded.source_revision),
                        policy_revision=MAX(policy_revision,excluded.policy_revision),
                        branch_revision=MAX(branch_revision,excluded.branch_revision),
                        max_valid_from=MAX(max_valid_from,excluded.max_valid_from)
                """, (self._scope_json(batch.scope), max(v.source_revision for v in vectors),
                       max(v.policy_revision for v in vectors), max(v.branch_revision for v in vectors),
                       max(entity.validity.valid_from for entity in entities)))
            if batch.siming_room_head is not None:
                head = batch.siming_room_head
                connection.execute("""INSERT INTO graph_siming_room_heads VALUES (?,?,?)
                    ON CONFLICT(room_scope_json) DO UPDATE SET revision=excluded.revision,payload_json=excluded.payload_json""",
                    (self._scope_json(head.scope), head.revision, head.model_dump_json()))
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def _scope_json_from_key(self, key: tuple[str, str, str, str | None, str | None, str, str | None]) -> str:
        world_id, session_id, story_branch_id, room_id, scene_id, graph_namespace, owner_actor_id = key
        from app.models.siming_heavenly_graph import HeavenlyGraphScope
        return self._scope_json(HeavenlyGraphScope(world_id=world_id, session_id=session_id, story_branch_id=story_branch_id, room_id=room_id, scene_id=scene_id, graph_namespace=graph_namespace, owner_actor_id=owner_actor_id))

    def _load_full(self) -> None:
        for scope_json, node_id, _, payload_json in self._connection.execute("SELECT scope_json, node_id, revision, payload_json FROM graph_nodes ORDER BY revision"):
            node = HeavenlyGraphNode.model_validate_json(payload_json)
            self._nodes.setdefault((self._scope_key(node.scope), node_id), []).append(node)
        for scope_json, relation_id, _, payload_json in self._connection.execute("SELECT scope_json, relation_id, revision, payload_json FROM graph_relations ORDER BY revision"):
            relation = HeavenlyGraphRelation.model_validate_json(payload_json)
            self._relations.setdefault((self._scope_key(relation.scope), relation_id), []).append(relation)
        for scope_json, key, payload_hash, result_json in self._connection.execute("SELECT scope_json, idempotency_key, payload_hash, result_json FROM graph_idempotency"):
            from app.models.siming_heavenly_graph import HeavenlyGraphScope
            scope = HeavenlyGraphScope.model_validate_json(scope_json)
            self._idempotency[(self._scope_key(scope), key)] = (payload_hash, HeavenlyGraphWriteResult.model_validate_json(result_json))
        for checkpoint_ref, _, _, snapshot_json in self._connection.execute("SELECT checkpoint_ref, scope_json, checkpoint_id, snapshot_json FROM graph_checkpoints"):
            payload = json.loads(snapshot_json)
            snapshot = HeavenlyGraphSnapshot.model_validate_json(snapshot_json)
            # Checkpoints written before schema v1's replay frontier fields
            # existed deserialize those fields as empty defaults.  Empty is a
            # valid frontier for a genuinely empty graph, so only the payload
            # shape can distinguish legacy data. Recover the missing portions
            # from the immutable source history loaded above and leave the
            # durable checkpoint row unchanged.
            frontier_update: dict[str, object] = {}
            if "replay_nodes" not in payload or "replay_relations" not in payload:
                history_nodes, history_relations = self._revision_history_at(
                    snapshot.checkpoint.scope,
                    recorded_at=snapshot.checkpoint.recorded_at,
                )
                if "replay_nodes" not in payload:
                    frontier_update["replay_nodes"] = history_nodes
                if "replay_relations" not in payload:
                    frontier_update["replay_relations"] = history_relations
            if frontier_update:
                snapshot = snapshot.model_copy(update=frontier_update, deep=True)
            key = (self._scope_key(snapshot.checkpoint.scope), snapshot.checkpoint.checkpoint_id)
            self._checkpoints[key] = snapshot
            self._checkpoint_refs[checkpoint_ref] = key
        self._load_metadata()

    def _load_metadata(self) -> None:
        for scope_json, node_revision, relation_revision in self._connection.execute(
            "SELECT scope_json, node_revision, relation_revision FROM graph_stream_revisions"
        ):
            from app.models.siming_heavenly_graph import HeavenlyGraphScope
            scope = HeavenlyGraphScope.model_validate_json(scope_json)
            self._scope_stream_revisions[self._scope_key(scope)] = (
                node_revision,
                relation_revision,
            )
        for scope_json, status, revision, markers_json in self._connection.execute(
            "SELECT scope_json, status, revision, markers_json FROM graph_branch_state"
        ):
            from app.models.siming_heavenly_graph import HeavenlyGraphScope
            scope = HeavenlyGraphScope.model_validate_json(scope_json)
            key = self._scope_key(scope)
            self._branch_status[key] = status
            self._branch_revisions[key] = revision
            self._branch_markers[key] = [GraphBranchLifecycleMarker.model_validate(item) for item in json.loads(markers_json)]
