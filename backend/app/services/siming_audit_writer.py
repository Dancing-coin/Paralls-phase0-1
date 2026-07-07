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
