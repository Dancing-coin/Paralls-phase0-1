from dataclasses import dataclass

from app.models.siming_runtime_state import ObservedSimingEvent


@dataclass(frozen=True)
class SimingFactCoreResult:
    accepted: bool
    known_fact_ids: list[str]
    veto_reason: str | None = None


class SimingFactCore:
    def evaluate(self, observed_events: list[ObservedSimingEvent]) -> SimingFactCoreResult:
        known_fact_ids: list[str] = []
        for event in observed_events:
            payload = event.payload
            if payload.get("locked_fact_conflict") is True:
                return SimingFactCoreResult(accepted=False, known_fact_ids=[], veto_reason="locked_fact_conflict")

            established_fact_id = payload.get("established_fact_id")
            if established_fact_id is None:
                continue

            fact_id = str(established_fact_id).strip()
            if fact_id:
                known_fact_ids.append(fact_id)

        return SimingFactCoreResult(accepted=True, known_fact_ids=known_fact_ids)
