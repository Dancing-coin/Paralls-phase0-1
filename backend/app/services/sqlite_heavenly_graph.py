import json
import sqlite3
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
    SCHEMA_VERSION = 1

    def __init__(self, database_path: str | Path) -> None:
        self._lock = RLock()
        self._connection = sqlite3.connect(str(database_path), check_same_thread=False)
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._migrate()
        super().__init__()
        self._pending_write_batch: HeavenlyGraphWriteBatch | None = None
        self._load()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def write_batch(self, batch: HeavenlyGraphWriteBatch) -> HeavenlyGraphWriteResult:
        with self._lock:
            snapshot = self._capture_write_batch_state(batch)
            self._pending_write_batch = batch
            try:
                result = super().write_batch(batch)
                if result.applied:
                    self._persist()
                return result
            except Exception:
                self._restore_write_batch_state(snapshot)
                raise
            finally:
                self._pending_write_batch = None

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
        with self._lock:
            snapshot = self._snapshot_mutable_state()
            try:
                result = super().fork_branch(request)
                self._persist()
                return result
            except Exception:
                self._restore_mutable_state(snapshot)
                raise

    def lifecycle_branch(self, request: GraphBranchLifecycleRequest) -> HeavenlyGraphWriteResult:
        with self._lock:
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
        with self._lock:
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
        with self._lock:
            snapshot = self._snapshot_mutable_state()
            try:
                checkpoint = super().create_checkpoint(**kwargs)
                self._persist()
                return checkpoint
            except Exception:
                self._restore_mutable_state(snapshot)
                raise

    def query_nodes(self, query: HeavenlyNodeQuery) -> list[HeavenlyGraphNode]:
        with self._lock:
            return super().query_nodes(query)

    def query_node_history(self, query: HeavenlyNodeQuery) -> list[HeavenlyGraphNode]:
        with self._lock:
            return super().query_node_history(query)

    def query_relations(
        self, query: HeavenlyRelationQuery
    ) -> list[HeavenlyGraphRelation]:
        with self._lock:
            return super().query_relations(query)

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
        with self._lock:
            return super().audit_consistency(scope=scope, reader_context=reader_context)

    def query_subgraph(self, **kwargs: object) -> HeavenlySubgraphResult:
        with self._lock:
            return super().query_subgraph(**kwargs)

    def read_checkpoint(self, checkpoint_ref: str) -> HeavenlyGraphSnapshot:
        with self._lock:
            return super().read_checkpoint(checkpoint_ref)

    def replay_from_checkpoint(
        self,
        checkpoint_ref: str,
        tail_batches: list[HeavenlyGraphWriteBatch],
    ) -> HeavenlyGraphSnapshot:
        with self._lock:
            return super().replay_from_checkpoint(checkpoint_ref, tail_batches)

    def _migrate(self) -> None:
        connection = self._connection
        connection.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)")
        versions = [row[0] for row in connection.execute("SELECT version FROM schema_version")]
        if versions and versions != [self.SCHEMA_VERSION]:
            raise HeavenlyGraphError(f"unsupported Heavenly Graph schema versions: {versions}")
        if not versions:
            connection.execute("INSERT INTO schema_version(version) VALUES (?)", (self.SCHEMA_VERSION,))
        connection.executescript(
            """
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
            """
        )
        connection.commit()

    def _scope_json(self, scope: object) -> str:
        return json.dumps(scope.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

    def _payload_json(self, value: object) -> str:
        return json.dumps(value.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))

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
            connection.execute("BEGIN IMMEDIATE")
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
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    def _scope_json_from_key(self, key: tuple[str, str, str, str | None, str | None, str, str | None]) -> str:
        world_id, session_id, story_branch_id, room_id, scene_id, graph_namespace, owner_actor_id = key
        from app.models.siming_heavenly_graph import HeavenlyGraphScope
        return self._scope_json(HeavenlyGraphScope(world_id=world_id, session_id=session_id, story_branch_id=story_branch_id, room_id=room_id, scene_id=scene_id, graph_namespace=graph_namespace, owner_actor_id=owner_actor_id))

    def _load(self) -> None:
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
        # Databases created before the stream-counter table can still be read;
        # establish a conservative floor before the first new commit.
        for (scope_key, _), versions in self._nodes.items():
            self._scope_stream_revisions.setdefault(
                scope_key,
                (sum(len(items) for (key, _), items in self._nodes.items() if key == scope_key), 0),
            )
        for (scope_key, _), versions in self._relations.items():
            node_revision, relation_revision = self._scope_stream_revisions.get(scope_key, (0, 0))
            self._scope_stream_revisions[scope_key] = (
                node_revision,
                max(relation_revision, sum(len(items) for (key, _), items in self._relations.items() if key == scope_key)),
            )
