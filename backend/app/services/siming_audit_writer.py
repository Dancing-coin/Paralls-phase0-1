from app.models.siming_event import SimingAuditCorrection, SimingAuditRecord


class SimingAuditWriter:
    def __init__(self) -> None:
        self._records_by_id: dict[str, SimingAuditRecord] = {}
        self.duplicate_count = 0

    def record(self, audit: SimingAuditRecord) -> None:
        if audit.audit_id in self._records_by_id:
            self.duplicate_count += 1
            return
        self._records_by_id[audit.audit_id] = audit.model_copy(deep=True)

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
