from pathlib import Path
import sqlite3

from app.models.siming_event import SimingAuditCorrection, SimingAuditRecord
from app.models.siming_runtime_state import NarrativeReadModel, SimingCheckpoint


class SimingAuditWriter:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._records_by_id: dict[str, SimingAuditRecord] = {}
        self._checkpoints_by_id: dict[str, SimingCheckpoint] = {}
        self._read_models_by_id: dict[str, NarrativeReadModel] = {}
        self.duplicate_count = 0

    def record(self, audit: SimingAuditRecord) -> None:
        if audit.audit_id in self._records_by_id:
            self.duplicate_count += 1
            return
        self._records_by_id[audit.audit_id] = audit.model_copy(deep=True)

    def get_record(self, audit_id: str) -> SimingAuditRecord | None:
        record = self._records_by_id.get(audit_id)
        return record.model_copy(deep=True) if record is not None else None

    def record_checkpoint(self, checkpoint: SimingCheckpoint) -> None:
        self._checkpoints_by_id[checkpoint.checkpoint_id] = checkpoint.model_copy(deep=True)

    def record_read_model(self, read_model: NarrativeReadModel) -> None:
        self._read_models_by_id[read_model.read_model_id] = read_model.model_copy(deep=True)

    def list_checkpoints(self, *, room_id: str) -> list[SimingCheckpoint]:
        return [
            checkpoint.model_copy(deep=True)
            for checkpoint in self._checkpoints_by_id.values()
            if checkpoint.room_id == room_id
        ]

    def list_read_models(self, *, room_id: str) -> list[NarrativeReadModel]:
        return [
            read_model.model_copy(deep=True)
            for read_model in self._read_models_by_id.values()
            if read_model.room_id == room_id
        ]

    def latest_read_model(self, *, room_id: str) -> NarrativeReadModel | None:
        models = self.list_read_models(room_id=room_id)
        if not models:
            return None
        return max(models, key=lambda model: (model.sim_tick_ts, model.world_ts, model.read_model_id))

    def append_correction(self, audit_id: str, correction: SimingAuditCorrection) -> None:
        record = self._records_by_id[audit_id]
        next_record = record.model_copy(deep=True)
        next_record.correction_records.append(correction.model_copy(deep=True))
        self._records_by_id[audit_id] = next_record

    def find_by_correlation(self, *, room_id: str, correlation_id: str) -> list[SimingAuditRecord]:
        return [
            record.model_copy(deep=True)
            for record in self._records_by_id.values()
            if record.room_id == room_id and record.correlation_id == correlation_id
        ]

    def find_by_causation(self, *, room_id: str, causation_id: str) -> list[SimingAuditRecord]:
        return [
            record.model_copy(deep=True)
            for record in self._records_by_id.values()
            if record.room_id == room_id and record.causation_id == causation_id
        ]


class SqliteSimingAuditWriter(SimingAuditWriter):
    """完整审计和读模型保留在磁盘索引中，不随仿真窗口保留内存副本。"""

    _RUNTIME_CACHE_KIB = 256

    def __init__(self, path: str | Path) -> None:
        super().__init__()
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        # 启动和关闭可能由不同的 runtime owner 线程执行，写入仍由 owner 串行调度。
        self._connection = sqlite3.connect(path, check_same_thread=False)
        try:
            with self._connection:
                self._connection.execute("PRAGMA journal_mode=WAL")
                self._connection.execute("PRAGMA synchronous=FULL")
                self._connection.execute(f"PRAGMA cache_size=-{self._RUNTIME_CACHE_KIB}")
                self._connection.execute(
                    "CREATE TABLE IF NOT EXISTS records ("
                    "sequence INTEGER PRIMARY KEY, kind TEXT NOT NULL, id TEXT NOT NULL, "
                    "room_id TEXT NOT NULL, correlation_id TEXT, causation_id TEXT, "
                    "sim_tick_ts INTEGER, world_ts INTEGER, payload TEXT NOT NULL, "
                    "UNIQUE(kind, id))"
                )
                self._connection.execute(
                    "CREATE INDEX IF NOT EXISTS records_correlation "
                    "ON records(kind, room_id, correlation_id, sequence)"
                )
                self._connection.execute(
                    "CREATE INDEX IF NOT EXISTS records_causation "
                    "ON records(kind, room_id, causation_id, sequence)"
                )
                self._connection.execute(
                    "CREATE INDEX IF NOT EXISTS records_latest "
                    "ON records(kind, room_id, sim_tick_ts DESC, world_ts DESC, id DESC)"
                )
        except BaseException:
            self._connection.close()
            raise

    def close(self) -> None:
        self._connection.close()

    def _put(self, kind: str, item, identifier: str) -> None:
        with self._connection:
            self._connection.execute(
                "INSERT INTO records(kind,id,room_id,correlation_id,causation_id,sim_tick_ts,world_ts,payload) "
                "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(kind,id) DO UPDATE SET "
                "room_id=excluded.room_id,correlation_id=excluded.correlation_id,"
                "causation_id=excluded.causation_id,sim_tick_ts=excluded.sim_tick_ts,"
                "world_ts=excluded.world_ts,payload=excluded.payload",
                (kind, identifier, item.room_id, getattr(item, "correlation_id", None),
                 getattr(item, "causation_id", None), getattr(item, "sim_tick_ts", None),
                 getattr(item, "world_ts", None), item.model_dump_json()),
            )

    def _list(self, model, sql: str, parameters: tuple) -> list:
        return [model.model_validate_json(row[0]) for row in self._connection.execute(sql, parameters)]

    def record(self, audit: SimingAuditRecord) -> None:
        with self._connection:
            inserted = self._connection.execute(
                "INSERT OR IGNORE INTO records(kind,id,room_id,correlation_id,causation_id,payload) "
                "VALUES ('audit',?,?,?,?,?)",
                (audit.audit_id, audit.room_id, audit.correlation_id, audit.causation_id,
                 audit.model_dump_json()),
            ).rowcount
        if not inserted:
            self.duplicate_count += 1

    def get_record(self, audit_id: str) -> SimingAuditRecord | None:
        row = self._connection.execute(
            "SELECT payload FROM records WHERE kind='audit' AND id=?", (audit_id,)
        ).fetchone()
        return SimingAuditRecord.model_validate_json(row[0]) if row else None

    def record_checkpoint(self, checkpoint: SimingCheckpoint) -> None:
        self._put("checkpoint", checkpoint, checkpoint.checkpoint_id)

    def record_read_model(self, read_model: NarrativeReadModel) -> None:
        self._put("read_model", read_model, read_model.read_model_id)

    def list_checkpoints(self, *, room_id: str) -> list[SimingCheckpoint]:
        return self._list(SimingCheckpoint,
            "SELECT payload FROM records WHERE kind='checkpoint' AND room_id=? ORDER BY sequence",
            (room_id,))

    def list_read_models(self, *, room_id: str) -> list[NarrativeReadModel]:
        return self._list(NarrativeReadModel,
            "SELECT payload FROM records WHERE kind='read_model' AND room_id=? ORDER BY sequence",
            (room_id,))

    def latest_read_model(self, *, room_id: str) -> NarrativeReadModel | None:
        row = self._connection.execute(
            "SELECT payload FROM records WHERE kind='read_model' AND room_id=? "
            "ORDER BY sim_tick_ts DESC, world_ts DESC, id DESC LIMIT 1", (room_id,)
        ).fetchone()
        return NarrativeReadModel.model_validate_json(row[0]) if row else None

    def append_correction(self, audit_id: str, correction: SimingAuditCorrection) -> None:
        record = self.get_record(audit_id)
        if record is None:
            raise KeyError(audit_id)
        record.correction_records.append(correction.model_copy(deep=True))
        with self._connection:
            self._connection.execute(
                "UPDATE records SET payload=? WHERE kind='audit' AND id=?",
                (record.model_dump_json(), audit_id),
            )

    def find_by_correlation(self, *, room_id: str, correlation_id: str) -> list[SimingAuditRecord]:
        return self._list(SimingAuditRecord,
            "SELECT payload FROM records WHERE kind='audit' AND room_id=? AND correlation_id=? "
            "ORDER BY sequence", (room_id, correlation_id))

    def find_by_causation(self, *, room_id: str, causation_id: str) -> list[SimingAuditRecord]:
        return self._list(SimingAuditRecord,
            "SELECT payload FROM records WHERE kind='audit' AND room_id=? AND causation_id=? "
            "ORDER BY sequence", (room_id, causation_id))
