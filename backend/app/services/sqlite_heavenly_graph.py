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
    HeavenlyGraphQueryResult,
    HeavenlyGraphSemanticQuery,
    HeavenlyGraphNode,
    HeavenlyGraphRelation,
    HeavenlyGraphSnapshot,
    HeavenlyGraphWriteBatch,
    HeavenlyGraphWriteResult,
    HeavenlyNodeQuery,
    HeavenlyRelationQuery,
    HeavenlySubgraphResult,
)
from app.services.in_memory_heavenly_graph import InMemoryHeavenlyGraphAdapter
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
        self._load()

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def write_batch(self, batch: HeavenlyGraphWriteBatch) -> HeavenlyGraphWriteResult:
        with self._lock:
            result = super().write_batch(batch)
            if result.applied:
                self._persist()
            return result

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
            checkpoint = super().create_checkpoint(**kwargs)
            self._persist()
            return checkpoint

    def query_nodes(self, query: HeavenlyNodeQuery) -> list[HeavenlyGraphNode]:
        with self._lock:
            return super().query_nodes(query)

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

    def query_subgraph(self, **kwargs: object) -> HeavenlySubgraphResult:
        with self._lock:
            return super().query_subgraph(**kwargs)

    def read_checkpoint(self, checkpoint_ref: str) -> HeavenlyGraphSnapshot:
        with self._lock:
            return super().read_checkpoint(checkpoint_ref)

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
            snapshot = HeavenlyGraphSnapshot.model_validate_json(snapshot_json)
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
